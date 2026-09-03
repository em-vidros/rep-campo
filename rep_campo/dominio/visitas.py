# -*- coding: utf-8 -*-
"""Regras da ficha de visita."""
from .catalogos import RELATO_MIN


def classificar_evidencia(tem_foto, tem_geo, tem_passo):
    if tem_foto and tem_geo:
        return "forte"
    if tem_geo and tem_passo:
        return "media"
    return "leve"


def validar_nota(valor):
    try:
        nota = int(valor) if valor not in (None, "") else None
    except (TypeError, ValueError):
        return None
    if nota is not None and not 0 <= nota <= 10:
        return None
    return nota


def relato_curto(relato):
    return 1 if len(relato or "") < RELATO_MIN else 0
