# -*- coding: utf-8 -*-
"""Rotas, sugestão de visitas e planejamento de viagem."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request, session

from rep_campo.aplicacao.viagens import aderencia, dias_desde, pode_acessar
from rep_campo.dominio.cobertura import ciclo_do_municipio, fora_da_base
from rep_campo.dominio.sugestao import pontuar_cliente
from rep_campo.dominio.texto import inteiro
from rep_campo.infra import db as dbmod
from rep_campo.web.acesso import eh_gestor, login_obrigatorio

bp = Blueprint("viagens", __name__)


@bp.route("/viagens")
@login_obrigatorio
def pagina():
    return render_template("viagens.html", nome=session.get("nome"),
                           papel=session.get("papel"))


@bp.route("/api/rotas")
@login_obrigatorio
def rotas():
    db = dbmod.get_db()
    agrupadas, descartados = {}, []
    for r in db.execute("""
        SELECT COALESCE(NULLIF(TRIM(rota),''),'Sem rota') AS rota,
               COALESCE(NULLIF(TRIM(cidade),''),'Sem cidade') AS cidade,
               COUNT(*) n, ROUND(SUM(vol_12m)) vol
          FROM clientes WHERE ativo = 1
         GROUP BY rota, cidade ORDER BY rota, n DESC"""):
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
    return jsonify({"rotas": lista, "total_clientes": sum(x["clientes"] for x in lista),
                    "fora_da_base": descartados,
                    "clientes_fora": sum(x["clientes"] for x in descartados)})


def _filtros_sugestao():
    filtros, args = ["c.ativo = 1"], []
    cidades = [x.strip() for x in (request.args.get("cidades") or "").split("|") if x.strip()]
    municipio = (request.args.get("municipio") or "").strip()
    rota = (request.args.get("rota") or "").strip()
    if cidades:
        filtros.append("COALESCE(NULLIF(TRIM(c.cidade),''),'Sem cidade') = ANY(%s)")
        args.append(cidades)
    elif municipio:
        filtros.append("c.cidade ILIKE %s")
        args.append("%%%s%%" % municipio)
    if rota and not cidades:
        if rota == "Sem rota":
            filtros.append("(c.rota IS NULL OR TRIM(c.rota) = '' OR LOWER(TRIM(c.rota)) = 'sem rota')")
        else:
            filtros.append("TRIM(c.rota) = %s")
            args.append(rota)
    return filtros, args


@bp.route("/api/sugestao")
@login_obrigatorio
def sugestao():
    db = dbmod.get_db()
    limite = min(inteiro(request.args.get("limite"), 40), 200)
    so_parados = request.args.get("parados") == "1"
    filtros, args = _filtros_sugestao()

    rows = db.execute("""
        SELECT c.codigo, c.nome, c.cidade, c.rota, c.curva, c.vol_12m, c.vendedor,
               c.ultima_compra, c.pedidos_12m,
               MAX(f.recebido_em) AS ultima_visita,
               (SELECT COUNT(*) FROM ocorrencias o
                 WHERE o.cliente_codigo = c.codigo AND o.status <> 'resolvida') AS oc_abertas,
               (SELECT MIN(e.nota) FROM experiencia e
                 WHERE e.cliente_codigo = c.codigo) AS pior_nota
          FROM clientes c
          LEFT JOIN fichas f ON f.cliente_codigo = c.codigo
         WHERE __FILTROS__
         GROUP BY c.codigo
    """.replace("__FILTROS__", " AND ".join(filtros)), args).fetchall()

    hoje = datetime.now(timezone.utc)
    saida = []
    for r in rows:
        if fora_da_base(r["rota"]):
            continue
        ciclo = ciclo_do_municipio(r["cidade"])
        dias = dias_desde(r["ultima_visita"], hoje)
        dias_sem_comprar = None
        if r["ultima_compra"]:
            dias_sem_comprar = (hoje.date() - r["ultima_compra"]).days
        peso, motivos = pontuar_cliente({
            "dias_sem_comprar": dias_sem_comprar,
            "vol_12m": r["vol_12m"],
            "oc_abertas": r["oc_abertas"],
            "pior_nota": r["pior_nota"],
            "curva": r["curva"],
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
    return jsonify({"clientes": saida[:limite], "total": len(saida),
                    "municipios": sorted({x["cidade"] for x in saida if x["cidade"]}),
                    "rotas": sorted({x["rota"] for x in saida if x["rota"]})})


@bp.route("/api/viagens", methods=["GET", "POST"])
@login_obrigatorio
def viagens():
    db = dbmod.get_db()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        nome = (d.get("nome") or "").strip()[:120]
        if not nome:
            return jsonify({"erro": "nome_obrigatorio"}), 400
        tipo = d.get("tipo") if d.get("tipo") in ("viagem", "local") else "viagem"
        row = db.execute("""INSERT INTO viagens (nome, inicio, fim, rota,
            observacao, status, criada_por, responsavel, criada_em, tipo)
            VALUES (%s,%s,%s,%s,%s,'planejada',%s,%s,%s,%s) RETURNING id""",
            (nome, (d.get("inicio") or "")[:20] or None,
             (d.get("fim") or "")[:20] or None, (d.get("rota") or "")[:80] or None,
             (d.get("observacao") or "")[:500] or None, session["login"],
             (d.get("responsavel") or session["login"])[:80], dbmod.agora(), tipo)).fetchone()
        db.commit()
        return jsonify({"ok": True, "id": row["id"]})

    if eh_gestor():
        onde, args = "", []
    else:
        onde = "WHERE responsavel = %s OR criada_por = %s"
        args = [session["login"], session["login"]]
    lista = [dict(v) for v in db.execute(f"""
        SELECT v.*, COUNT(vc.id) AS planejados,
               COALESCE(SUM(vc.visitado), 0) AS visitados
          FROM viagens v
          LEFT JOIN viagem_clientes vc ON vc.viagem_id = v.id
          {onde}
         GROUP BY v.id
         ORDER BY COALESCE(v.inicio, v.criada_em) DESC
         LIMIT 60""", args)]
    for d in lista:
        d["aderencia"] = aderencia(d["planejados"], d["visitados"])
    return jsonify({"viagens": lista})


@bp.route("/api/viagens/<int:vid>", methods=["GET", "PATCH", "DELETE"])
@login_obrigatorio
def viagem(vid):
    db = dbmod.get_db()
    v = db.execute("SELECT * FROM viagens WHERE id = %s", (vid,)).fetchone()
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    if not pode_acessar(v, session.get("login"), eh_gestor()):
        return jsonify({"erro": "sem_permissao"}), 403

    if request.method == "DELETE":
        db.execute("DELETE FROM viagem_clientes WHERE viagem_id = %s", (vid,))
        db.execute("DELETE FROM viagens WHERE id = %s", (vid,))
        db.commit()
        return jsonify({"ok": True})

    if request.method == "PATCH":
        d = request.get_json(silent=True) or {}
        if d.get("status") in ("planejada", "em_andamento", "concluida"):
            db.execute("UPDATE viagens SET status = %s WHERE id = %s", (d["status"], vid))
        for campo in ("nome", "inicio", "fim", "rota", "observacao", "responsavel"):
            if campo in d:
                db.execute(f"UPDATE viagens SET {campo} = %s WHERE id = %s",
                           (str(d[campo] or "")[:500] or None, vid))
        db.commit()
        return jsonify({"ok": True})

    clientes = [dict(r) for r in db.execute(
        "SELECT * FROM viagem_clientes WHERE viagem_id = %s ORDER BY visitado, ordem, cliente_nome",
        (vid,))]
    d = dict(v)
    d["clientes"] = clientes
    d["planejados"] = len(clientes)
    d["visitados"] = sum(1 for c in clientes if c["visitado"])
    d["aderencia"] = aderencia(d["planejados"], d["visitados"])
    return jsonify(d)


@bp.route("/api/viagens/<int:vid>/relatorio")
@login_obrigatorio
def relatorio(vid):
    db = dbmod.get_db()
    v = db.execute("SELECT * FROM viagens WHERE id = %s", (vid,)).fetchone()
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    v = dict(v)
    if not pode_acessar(v, session.get("login"), eh_gestor()):
        return jsonify({"erro": "sem_permissao"}), 403

    roteiro = [dict(r) for r in db.execute(
        "SELECT * FROM viagem_clientes WHERE viagem_id = %s ORDER BY visitado, cliente_nome",
        (vid,))]
    fichas = [dict(r) for r in db.execute(
        "SELECT uuid, tipo, cliente_nome, cliente_codigo, municipio, objetivo, relato, "
        "proximo_passo, prox_responsavel, prox_data, encaminhado_para, problema_tipo, "
        "ocorrencia_num, nivel_evidencia, conta_indicador, criado_em_disp, recebido_em "
        "FROM fichas WHERE viagem_id = %s ORDER BY recebido_em", (vid,))]

    uuids = [f["uuid"] for f in fichas]
    respostas, ocorrencias = [], []
    if uuids:
        respostas = [dict(r) for r in db.execute(
            "SELECT cliente_nome, etapa, metrica, nota, comentario, unidade "
            "FROM experiencia WHERE ficha_uuid = ANY(%s) ORDER BY nota", (uuids,))]
        ocorrencias = [dict(r) for r in db.execute(
            "SELECT numero, cliente_nome, tipo, status, responsavel "
            "FROM ocorrencias WHERE ficha_uuid = ANY(%s) ORDER BY numero", (uuids,))]

    por_tipo, municipios = {}, {}
    for f in fichas:
        por_tipo[f["tipo"]] = por_tipo.get(f["tipo"], 0) + 1
        if f["municipio"]:
            municipios[f["municipio"]] = municipios.get(f["municipio"], 0) + 1

    notas = [r["nota"] for r in respostas]
    no_roteiro = {c["cliente_codigo"] for c in roteiro}
    return jsonify({
        "viagem": v,
        "planejados": len(roteiro),
        "visitados": sum(1 for c in roteiro if c["visitado"]),
        "aderencia": (aderencia(len(roteiro), sum(1 for c in roteiro if c["visitado"]))
                      if roteiro else None),
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
    })


@bp.route("/api/visitas-avulsas")
@login_obrigatorio
def visitas_avulsas():
    db = dbmod.get_db()
    mes = request.args.get("mes") or datetime.now(timezone.utc).strftime("%Y-%m")
    filtros = ["viagem_id IS NULL", "substr(recebido_em,1,7) = %s"]
    args = [mes]
    if not eh_gestor():
        filtros.append("usuario_login = %s")
        args.append(session["login"])
    fichas = [dict(r) for r in db.execute(
        "SELECT uuid, tipo, cliente_nome, municipio, proximo_passo, usuario_login, "
        "recebido_em FROM fichas WHERE " + " AND ".join(filtros) +
        " ORDER BY recebido_em DESC LIMIT 300", args)]
    por_municipio = {}
    for f in fichas:
        m = f["municipio"] or "sem município"
        por_municipio[m] = por_municipio.get(m, 0) + 1
    return jsonify({
        "mes": mes, "total": len(fichas),
        "clientes": len({f["cliente_nome"] for f in fichas}),
        "por_municipio": sorted(por_municipio.items(), key=lambda x: -x[1]),
        "fichas": fichas,
    })


@bp.route("/api/viagens/<int:vid>/clientes", methods=["POST"])
@login_obrigatorio
def adicionar_clientes(vid):
    d = request.get_json(silent=True) or {}
    lista = d.get("clientes")
    if not isinstance(lista, list):
        return jsonify({"erro": "lista_invalida"}), 400
    db = dbmod.get_db()
    v = db.execute("SELECT * FROM viagens WHERE id = %s", (vid,)).fetchone()
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    if not pode_acessar(v, session.get("login"), eh_gestor()):
        return jsonify({"erro": "sem_permissao"}), 403

    add = 0
    for i, c in enumerate(lista[:200]):
        cod = str(c.get("codigo") or "")[:40] or None
        nome = str(c.get("nome") or "").strip()[:200]
        if not nome:
            continue
        cur = db.execute("""INSERT INTO viagem_clientes (viagem_id, cliente_codigo,
            cliente_nome, municipio, motivo, ordem) VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (viagem_id, cliente_codigo) WHERE cliente_codigo IS NOT NULL
            DO NOTHING""",
            (vid, cod, nome, str(c.get("cidade") or "")[:120] or None,
             str(c.get("motivo") or "")[:300] or None, i))
        add += cur.rowcount
    db.commit()
    return jsonify({"ok": True, "adicionados": add})


@bp.route("/api/viagens/<int:vid>/clientes/<int:cid>", methods=["DELETE"])
@login_obrigatorio
def remover_cliente(vid, cid):
    db = dbmod.get_db()
    v = db.execute("SELECT * FROM viagens WHERE id = %s", (vid,)).fetchone()
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    if not pode_acessar(v, session.get("login"), eh_gestor()):
        return jsonify({"erro": "sem_permissao"}), 403
    db.execute("DELETE FROM viagem_clientes WHERE id = %s AND viagem_id = %s", (cid, vid))
    db.commit()
    return jsonify({"ok": True})
