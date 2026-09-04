# -*- coding: utf-8 -*-
"""Pontuação de quem visitar. Pura: recebe uma linha, devolve peso e motivos."""
from .catalogos import NPS_DETRATOR
from .recados import PESO_MISSAO, motivo_missao


def pontuar_cliente(linha, dias_visita, ciclo):
    peso, motivos = 0, []

    # Recado do gestor vem primeiro e por cima: e pedido explicito de gente, nao
    # inferencia nossa. Se ele mandou passar no cliente, o cliente e o primeiro
    # da lista, doa a heuristica o que doer.
    if linha.get("recados_abertos"):
        peso += PESO_MISSAO
        motivos.append(motivo_missao(linha["recados_abertos"], linha.get("recado_de")))

    dias_sem_comprar = linha.get("dias_sem_comprar")
    vol = linha.get("vol_12m") or 0
    if dias_sem_comprar is not None and dias_sem_comprar > 90:
        peso += 120
        motivos.append("sem comprar há %d dias" % dias_sem_comprar)
    elif dias_sem_comprar is not None and dias_sem_comprar > 30:
        peso += 80
        motivos.append("sem comprar há %d dias" % dias_sem_comprar)
    elif dias_sem_comprar is None and not vol and "dias_sem_comprar" in linha:
        peso += 45
        motivos.append("sem compra nos últimos 12 meses")

    if linha.get("oc_abertas"):
        peso += 100
        motivos.append("%d ocorrência(s) em aberto" % linha["oc_abertas"])

    pior = linha.get("pior_nota")
    if pior is not None and pior <= NPS_DETRATOR:
        peso += 60
        motivos.append("deu nota %d numa pesquisa" % pior)

    if dias_visita is None:
        peso += 50
        motivos.append("nunca recebeu visita")
    elif dias_visita > ciclo:
        peso += 40
        motivos.append("sem visita há %d dias (ciclo %d)" % (dias_visita, ciclo))

    if linha.get("curva") == "A":
        peso += 25
        motivos.append("curva A")
    elif linha.get("curva") == "B":
        peso += 12

    if vol:
        peso += min(vol / 20000.0, 25)

    return peso, motivos
