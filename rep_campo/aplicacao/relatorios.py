# -*- coding: utf-8 -*-
"""Casos de uso de leitura: cobertura, experiência, sugestão, rotas, relatórios.

Antes este código morava nos blueprints (`web/gestor.py`, `web/viagens.py`):
SQL + regra + shaping de JSON misturados na borda HTTP. Agora o web só
extrai parâmetros e chama aqui; SQL mora em `infra/repositorios.py` e regra
pura em `dominio/`. Trocar o transporte (Flask → CLI, job) não mexe em regra.
"""
import json
from datetime import datetime, timezone

from rep_campo.aplicacao.viagens import aderencia, dias_desde, ordenar_cobertura
from rep_campo.dominio import catalogos as C
from rep_campo.dominio.cobertura import ciclo_do_municipio, fora_da_base
from rep_campo.dominio.entidades import SinalSugestao
from rep_campo.dominio.experiencia import cortes, indice_nps
from rep_campo.dominio.sugestao import pontuar_cliente
from rep_campo.infra import repositorios as repo
from rep_campo.infra.db import como_float


def montar_cobertura(db, curvas):
    from datetime import datetime, timezone
    linhas = repo.cobertura_linhas(db, curvas)
    hoje = datetime.now(timezone.utc)
    saida = []
    for r in linhas:
        ciclo = ciclo_do_municipio(r["cidade"])
        dias = dias_desde(r["ultima_visita"], hoje)
        saida.append({
            "codigo": r["codigo"], "nome": r["nome"], "cidade": r["cidade"],
            "curva": r["curva"], "vol_12m": r["vol_12m"], "vendedor": r["vendedor"],
            "ultima_visita": r["ultima_visita"], "total_visitas": r["total_visitas"],
            "dias": dias, "ciclo": ciclo,
            "vencido": (dias is None) or (dias > ciclo),
        })
    ordenar_cobertura(saida)
    vencidos = [x for x in saida if x["vencido"]]
    return {
        "clientes": saida,
        "total": len(saida),
        "vencidos": len(vencidos),
        "nunca_visitados": len([x for x in saida if x["dias"] is None]),
        "cobertura_pct": round(100.0 * (len(saida) - len(vencidos)) / len(saida), 1) if saida else 0.0,
        "risco_reais": round(sum(x["vol_12m"] for x in vencidos), 2),
    }


def montar_experiencia(db, mes=None):
    linhas_nps, tot_nps, base_nps, args_nps = None, None, None, None

    def bloco(metrica, corte_bons, corte_ruins):
        linhas, tot, base, args = repo.experiencia_bloco(
            db, metrica, corte_bons, corte_ruins, mes)
        n = tot["n"] or 0
        return {"por_etapa": [{**dict(r), "media": como_float(r["media"])}
                              for r in linhas], "n": n,
                "media": como_float(tot["media"]), "bons": tot["bons"] or 0,
                "ruins": tot["ruins"] or 0,
                "pct_bons": round(100.0 * (tot["bons"] or 0) / n) if n else None,
                "_base": base, "_args": args}

    # NOTA mantida do original: "ruins" usa o corte de detrator NPS (<=6) para
    # as três métricas. CSAT/ces têm corte de "bons" próprio, mas o de "ruins"
    # segue o mesmo piso. Se um dia CSAT quiser outro piso, trocar aqui num
    # ponto só — antes estava espalhado no blueprint.
    nps = bloco("nps", C.NPS_PROMOTOR, C.NPS_DETRATOR)
    csat = bloco("csat", C.CSAT_SATISFEITO, C.NPS_DETRATOR)
    ces = bloco("ces", C.CES_FACIL, C.NPS_DETRATOR)
    nps["indice"] = indice_nps(nps["bons"], nps["ruins"], nps["n"])

    base, args = nps.pop("_base"), nps.pop("_args")
    csat.pop("_base", None)
    csat.pop("_args", None)
    ces.pop("_base", None)
    ces.pop("_args", None)

    comentarios = repo.experiencia_comentarios(db, base, args)
    expedicao = [{**dict(r), "media": como_float(r["media"])}
                 for r in repo.experiencia_expedicao(db, base, args, C.CSAT_SATISFEITO)]
    return {
        "expedicao": expedicao,
        "nps": nps, "csat": csat, "ces": ces, "comentarios": comentarios,
        "clientes_ouvidos": repo.experiencia_clientes_ouvidos(db, base, args),
        "cortes": cortes(),
    }


def montar_sugestao(db, cidades=None, municipio=None, rota=None,
                    limite=40, so_parados=False):
    from datetime import datetime, timezone
    linhas = repo.sugestao_linhas(db, cidades, municipio, rota)
    hoje = datetime.now(timezone.utc)
    saida = []
    for r in linhas:
        if fora_da_base(r["rota"]):
            continue
        ciclo = ciclo_do_municipio(r["cidade"])
        dias = dias_desde(r["ultima_visita"], hoje)
        dias_sem_comprar = None
        if r["ultima_compra"]:
            dias_sem_comprar = (hoje.date() - r["ultima_compra"]).days
        sinal = SinalSugestao(
            dias_sem_comprar=dias_sem_comprar,
            vol_12m=r["vol_12m"] or 0,
            oc_abertas=r["oc_abertas"] or 0,
            pior_nota=r["pior_nota"],
            curva=r["curva"],
        )
        peso, motivos = pontuar_cliente({
            "dias_sem_comprar": sinal.dias_sem_comprar,
            "vol_12m": sinal.vol_12m,
            "oc_abertas": sinal.oc_abertas,
            "pior_nota": sinal.pior_nota,
            "curva": sinal.curva,
        }, dias, ciclo)
        if not motivos:
            continue
        saida.append({
            "codigo": r["codigo"], "nome": r["nome"], "cidade": r["cidade"],
            "rota": r["rota"], "curva": r["curva"], "vol_12m": r["vol_12m"],
            "vendedor": r["vendedor"], "dias": dias, "ciclo": ciclo,
            "oc_abertas": r["oc_abertas"], "pior_nota": r["pior_nota"],
            "ultima_compra": r["ultima_compra"].isoformat() if r["ultima_compra"] else None,
            "dias_sem_comprar": dias_sem_comprar, "pedidos_12m": r["pedidos_12m"],
            "peso": round(peso), "motivo": " · ".join(motivos),
        })
    if so_parados:
        saida = [x for x in saida
                 if (x["dias_sem_comprar"] or 0) > 30 or not x["vol_12m"]]
    saida.sort(key=lambda x: -x["peso"])
    return {"clientes": saida[:limite], "total": len(saida),
            "municipios": sorted({x["cidade"] for x in saida if x["cidade"]}),
            "rotas": sorted({x["rota"] for x in saida if x["rota"]})}


def montar_rotas(db):
    agrupadas, descartados = {}, []
    for r in repo.rotas_brutas(db):
        nome = r["rota"]
        if nome.lower() in ("sem rota", "sem rota "):
            nome = "Sem rota"
        if fora_da_base(nome):
            descartados.append({"rota": nome, "cidade": r["cidade"], "clientes": r["n"]})
            continue
        d = agrupadas.setdefault(nome, {"rota": nome, "cidades": [], "clientes": 0, "vol_12m": 0})
        d["cidades"].append({"cidade": r["cidade"], "clientes": r["n"],
                             "vol_12m": r["vol"] or 0})
        d["clientes"] += r["n"]
        d["vol_12m"] += r["vol"] or 0
    lista = sorted(agrupadas.values(), key=lambda x: -x["vol_12m"])
    return {"rotas": lista, "total_clientes": sum(x["clientes"] for x in lista),
            "fora_da_base": descartados,
            "clientes_fora": sum(x["clientes"] for x in descartados)}


def montar_relatorio_viagem(db, viagem):
    roteiro = repo.clientes_da_viagem(db, viagem["id"])
    fichas = repo.fichas_da_viagem(db, viagem["id"])
    uuids = [f["uuid"] for f in fichas]
    respostas, ocorrencias = repo.pesquisa_da_viagem(db, uuids)
    por_tipo, municipios = {}, {}
    for f in fichas:
        por_tipo[f["tipo"]] = por_tipo.get(f["tipo"], 0) + 1
        if f["municipio"]:
            municipios[f["municipio"]] = municipios.get(f["municipio"], 0) + 1
    notas = [r["nota"] for r in respostas]
    no_roteiro = {c["cliente_codigo"] for c in roteiro}
    visitados = sum(1 for c in roteiro if c["visitado"])
    return {
        "viagem": viagem,
        "planejados": len(roteiro),
        "visitados": visitados,
        "aderencia": (aderencia(len(roteiro), visitados) if roteiro else None),
        "nao_visitados": [c for c in roteiro if not c["visitado"]],
        "fichas": fichas,
        "fora_do_roteiro": [f for f in fichas if f["cliente_codigo"] not in no_roteiro],
        "por_tipo": por_tipo,
        "municipios": sorted(municipios.items(), key=lambda x: -x[1]),
        "ocorrencias": ocorrencias,
        "encaminhamentos": [f for f in fichas if (f.get("encaminhado_para") or "").strip()],
        "respostas": respostas,
        "media_pesquisa": round(sum(notas) / len(notas), 1) if notas else None,
        "clientes_ouvidos": len({r["cliente_nome"] for r in respostas}),
    }


def montar_fichas_gestor(db, mes=None, tipo=None, municipio=None,
                         usuario=None, nivel=None, busca=None, limite=200):
    import json as _json
    linhas = repo.listar_fichas_gestor(
        db, mes=mes, tipo=tipo, municipio=municipio,
        usuario=usuario, nivel=nivel, busca=busca, limite=limite)
    uuids = [r["uuid"] for r in linhas]
    por_ficha = repo.anexos_por_fichas(db, uuids)
    saida = []
    for r in linhas:
        try:
            r["extra"] = _json.loads(r.pop("extra_json") or "{}")
        except ValueError:
            r["extra"] = {}
        r["anexos"] = por_ficha.get(r["uuid"], [])
        saida.append(r)
    return {"fichas": saida, "opcoes": repo.opcoes_fichas(db)}


def montar_ocorrencias(db, situacao=None, canal=None, setor=None, tipo=None):
    from datetime import datetime, timezone
    linhas = repo.listar_ocorrencias(db, situacao, canal, setor, tipo)
    hoje = datetime.now(timezone.utc)
    saida = []
    for r in linhas:
        r["dias_aberta"] = dias_desde(r["aberta_em"], hoje)
        saida.append(r)
    cont, por_canal = repo.contagem_ocorrencias(db)
    return {
        "ocorrencias": saida,
        "abertas": cont.get("aberta", 0) + cont.get("em_andamento", 0),
        "resolvidas": cont.get("resolvida", 0),
        "por_canal": por_canal,
        "canais": C.CANAIS, "setores": C.SETORES, "status": C.STATUS_OCORRENCIA,
    }
