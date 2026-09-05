# -*- coding: utf-8 -*-
"""Pesquisa de preco do concorrente. Puro: sem banco, sem Flask.

Tudo em R$/m2, inclusive as pecas padrao - so assim box, janela e chapa entram
na mesma comparacao.
"""
from .catalogos import CONCORRENTES

MAX_ITEM = 80
MAX_CONCORRENTE = 60
# acima disso e quase certo erro de digitacao (virgula no lugar errado); abaixo,
# alguem digitou centavos ou um numero solto
PRECO_MIN = 5.0
PRECO_MAX = 5000.0


def normalizar_concorrente(nome, outro=None):
    """Nome da lista fechada, ou o texto livre quando ele escolheu 'Outro'."""
    n = (nome or "").strip()
    if n.lower() == "outro":
        livre = (outro or "").strip()
        return livre[:MAX_CONCORRENTE] or None
    for oficial in CONCORRENTES:
        if oficial.lower() == n.lower():
            return oficial
    return n[:MAX_CONCORRENTE] or None


def preco_valido(valor):
    """Aceita '89,90', '89.90', 'R$ 89,90'. Devolve float ou None."""
    if valor is None:
        return None
    t = str(valor).strip().replace("R$", "").replace(" ", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    if v < PRECO_MIN or v > PRECO_MAX:
        return None
    return round(v, 2)


def linhas_de_preco(extra):
    """Extrai da ficha as linhas que valem virar registro de preco.

    Descarta em silencio o que nao da para comparar: item sem nome, preco fora
    da faixa, concorrente em branco. A ficha continua guardada inteira - aqui so
    se decide o que entra na serie historica.
    """
    concorrente = normalizar_concorrente(
        (extra or {}).get("concorrente"), (extra or {}).get("concorrente_outro"))
    if not concorrente:
        return []
    saida = []
    for linha in (extra or {}).get("itens") or []:
        item = str(linha.get("item") or "").strip()[:MAX_ITEM]
        preco = preco_valido(linha.get("preco"))
        if item and preco is not None:
            saida.append({"concorrente": concorrente, "item": item, "preco": preco})
    return saida


# ------------------------------------------------------------- cobertura

MAX_CIDADES = 200


def cidades_validas(lista):
    """As cidades que aquele preco cobre.

    O mesmo preco quase nunca vale para uma cidade so: o concorrente pratica a
    mesma tabela na rota inteira, ou em parte dela mais alguma cidade de outra
    rota. Por isso a selecao e multipla, e a rota entra so como atalho para
    marcar as cidades dela de uma vez.
    """
    vistas, saida = set(), []
    for c in (lista or [])[:MAX_CIDADES]:
        n = str(c or "").strip()[:120]
        if n and n.lower() not in vistas:
            vistas.add(n.lower())
            saida.append(n)
    return saida


def linhas_digitadas(itens):
    """Mesma limpeza da ficha, para o que vem da tela de atualizacao."""
    saida = []
    for linha in itens or []:
        item = str((linha or {}).get("item") or "").strip()[:MAX_ITEM]
        preco = preco_valido((linha or {}).get("preco"))
        if item and preco is not None:
            saida.append({"item": item, "preco": preco})
    return saida
