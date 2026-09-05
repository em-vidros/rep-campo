# -*- coding: utf-8 -*-
"""Leitura da pesquisa de preco: o que o painel mostra."""
from rep_campo.dominio import catalogos as C
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
            "por": r["usuario_login"],
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
