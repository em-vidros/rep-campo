# -*- coding: utf-8 -*-
"""Leitura da pesquisa de preco: o que o painel mostra."""
from rep_campo.dominio import catalogos as C
from rep_campo.dominio import precos as D
from rep_campo.infra.relogio import agora
from rep_campo.infra import repositorios as repo


def matriz(db, rota=None, municipio=None, cliente=None, desde=None):
    """Grade de comparacao: uma linha por item da cesta, uma coluna por
    concorrente. E assim que se decide preco - vendo a linha inteira de uma vez,
    nao filtrando um concorrente por vez.

    A cesta entra completa mesmo sem dado nenhum: a celula vazia diz onde falta
    pesquisar, e isso e informacao tanto quanto o preco.
    """
    linhas = repo.precos_matriz(db, rota or None, municipio or None,
                                cliente or None, desde or None)

    concorrentes, celulas = [], {}
    for r in linhas:
        if r["concorrente"] not in concorrentes:
            concorrentes.append(r["concorrente"])
        celulas[(r["item"], r["concorrente"])] = {
            "preco": float(r["preco"]), "coletado_em": r["coletado_em"],
            "municipio": r["municipio"], "rota": r["rota"],
            "por": r["usuario_login"], "observacao": r.get("observacao"),
        }
    concorrentes.sort(key=lambda x: x.lower())

    # a cesta manda na ordem; item digitado no campo livre entra depois
    da_cesta = [x["item"] for x in C.CESTA_PRECO]
    extras = sorted({r["item"] for r in linhas} - set(da_cesta), key=lambda x: x.lower())

    def bloco(nome_grupo):
        return [{"item": x["item"],
                 "precos": {c: celulas.get((x["item"], c)) for c in concorrentes}}
                for x in C.CESTA_PRECO if x["grupo"] == nome_grupo]

    grupos = []
    for nome in [x["grupo"] for x in C.CESTA_PRECO]:
        if nome not in [g["grupo"] for g in grupos]:
            grupos.append({"grupo": nome, "itens": bloco(nome)})
    if extras:
        grupos.append({"grupo": "Outros itens pesquisados",
                       "itens": [{"item": i,
                                  "precos": {c: celulas.get((i, c)) for c in concorrentes}}
                                 for i in extras]})

    return {
        "concorrentes": concorrentes,
        "grupos": grupos,
        "recortes": repo.precos_recortes(db),
        "unidade": C.UNIDADE_PRECO,
        "coletas": len(linhas),
    }


def painel(db, concorrente=None, item=None, municipio=None, desde=None):
    ultimos = repo.precos_ultimos(db, concorrente or None, item or None,
                                  municipio or None, desde or None)
    for linha in ultimos:
        linha["preco"] = float(linha["preco"])
    opcoes = repo.precos_opcoes(db)
    return {
        "ultimos": ultimos,
        "opcoes": opcoes,
        # a cesta e a lista completa vao junto para o filtro mostrar tambem o
        # que ainda nao foi pesquisado - a lacuna e informacao
        "cesta": [x["item"] for x in C.CESTA_PRECO],
        "concorrentes_catalogo": C.CONCORRENTES,
        "unidade": C.UNIDADE_PRECO,
        "total": len(ultimos),
    }


def onde_atua(db):
    """Area de influencia observada, agrupada por concorrente."""
    saida = {}
    for r in repo.precos_onde_atua(db):
        d = saida.setdefault(r["concorrente"], {"concorrente": r["concorrente"],
                                                "lugares": [], "coletas": 0})
        d["lugares"].append({"municipio": r["municipio"], "rota": r["rota"],
                             "coletas": r["coletas"], "visto_em": r["visto_em"]})
        d["coletas"] += r["coletas"]
    return sorted(saida.values(), key=lambda x: -x["coletas"])


def serie(db, concorrente, item):
    linhas = repo.precos_serie(db, concorrente, item)
    for l in linhas:
        l["media"] = float(l["media"])
    return linhas


# ------------------------------------------------ tela do representante

def formulario(db, concorrente=None, cidades=None):
    """O que a tela de atualizacao precisa: a cesta, as rotas com suas cidades
    para marcar, e - se ja houver pesquisa naquelas cidades - o ultimo preco de
    cada item, para ele so corrigir o que mudou."""
    cidades = D.cidades_validas(cidades)
    conhecidos = repo.precos_das_cidades(db, concorrente, cidades) if concorrente else {}

    itens = []
    for x in C.CESTA_PRECO:
        ant = conhecidos.get(x["item"])
        itens.append({
            "grupo": x["grupo"], "item": x["item"],
            "preco": float(ant["preco"]) if ant else None,
            "coletado_em": ant["coletado_em"] if ant else None,
        })
    extras = [i for i in conhecidos if i not in {x["item"] for x in C.CESTA_PRECO}]
    for i in sorted(extras):
        a = conhecidos[i]
        itens.append({"grupo": "Outros itens", "item": i, "preco": float(a["preco"]),
                      "coletado_em": a["coletado_em"]})

    ultimo = next((c for c in conhecidos.values()), None)
    return {
        "itens": itens,
        "concorrentes": C.CONCORRENTES,
        "rotas": repo.rotas_com_cidades(db),
        "unidade": C.UNIDADE_PRECO,
        "observacao": (ultimo or {}).get("observacao"),
        "prazo_entrega": (ultimo or {}).get("prazo_entrega"),
        "ja_pesquisado": bool(conhecidos),
    }


def registrar(db, usuario_login, dados):
    conc = D.normalizar_concorrente(dados.get("concorrente"),
                                    dados.get("concorrente_outro"))
    if not conc:
        return None, "sem_concorrente"

    cidades = D.cidades_validas(dados.get("cidades"))
    if not cidades:
        return None, "sem_cidades"

    linhas = D.linhas_digitadas(dados.get("itens"))
    if not linhas:
        return None, "sem_precos"

    rotas = repo.rotas_das_cidades(db, cidades)
    n = repo.registrar_precos(
        db, agora(), usuario_login, conc, cidades, rotas, linhas,
        str(dados.get("observacao") or "")[:600] or None,
        str(dados.get("prazo_entrega") or "")[:120] or None)
    db.commit()
    return {"gravados": len(linhas), "cidades": len(cidades), "concorrente": conc}, None
