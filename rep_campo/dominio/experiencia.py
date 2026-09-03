# -*- coding: utf-8 -*-
"""NPS, CSAT e CES. Cada etapa tem exatamente uma métrica."""
from .catalogos import CES_FACIL, CSAT_SATISFEITO, METRICA_POR_ETAPA, NPS_DETRATOR, NPS_PROMOTOR


def metrica_para_etapa(etapa, padrao="csat"):
    return METRICA_POR_ETAPA.get(etapa or "", padrao)


def cortes():
    return {
        "nps_promotor": NPS_PROMOTOR,
        "nps_detrator": NPS_DETRATOR,
        "csat_satisfeito": CSAT_SATISFEITO,
        "ces_facil": CES_FACIL,
    }


def indice_nps(bons, ruins, total):
    if not total:
        return None
    return round(100.0 * (bons - ruins) / total)
