# -*- coding: utf-8 -*-
"""Planejamento de viagem: permissão, aderência e ordenação de cobertura."""
from datetime import datetime


def pode_acessar(viagem, login, papel_gestor):
    return (papel_gestor
            or viagem["criada_por"] == login
            or viagem.get("responsavel") == login)


def aderencia(planejados, visitados):
    if not planejados:
        return None
    return round(100.0 * visitados / planejados)


def dias_desde(quando_iso, hoje=None):
    if not quando_iso:
        return None
    try:
        return ((hoje or datetime.now().astimezone()) - datetime.fromisoformat(quando_iso)).days
    except (TypeError, ValueError):
        return None


def ordenar_cobertura(itens):
    itens.sort(key=lambda x: (x["dias"] is not None, -(x["dias"] or 0), -x["vol_12m"]))
    return itens
