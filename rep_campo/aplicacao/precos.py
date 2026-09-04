# -*- coding: utf-8 -*-
"""Leitura da pesquisa de preco: o que o painel mostra."""
from rep_campo.dominio import catalogos as C
from rep_campo.infra import repositorios as repo


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
