# -*- coding: utf-8 -*-
"""Regras da ficha de visita."""
from .catalogos import CANAIS_REMOTOS, RELATO_MIN, RELATO_MIN_TELEFONE


def classificar_evidencia(tem_foto, tem_geo, tem_passo, canal="presencial", relato=""):
    """Evidencia julgada pelo que aquele canal PODE produzir.

    Por telefone ou video o representante nao esta na loja: exigir GPS e foto
    condenaria todo contato remoto a "leve" para sempre, e o indicador de
    qualidade viraria apenas um medidor de presenca fisica. No remoto o que
    prova o trabalho e o relato substancial mais o proximo passo.
    """
    if canal in CANAIS_REMOTOS:
        if len(relato or "") >= RELATO_MIN and tem_passo:
            return "forte"
        if tem_passo:
            return "media"
        return "leve"
    if tem_foto and tem_geo:
        return "forte"
    if tem_geo and tem_passo:
        return "media"
    return "leve"


def canal_valido(valor):
    from .catalogos import CANAIS_VALIDOS, CANAL_PADRAO
    v = (valor or "").strip().lower()
    return v if v in CANAIS_VALIDOS else CANAL_PADRAO


def relato_minimo(canal):
    """Telefone pede menos texto; o resto segue a regra cheia."""
    from .catalogos import RELATO_OBRIGATORIO_MIN
    return RELATO_MIN_TELEFONE if canal == "telefone" else RELATO_OBRIGATORIO_MIN


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
