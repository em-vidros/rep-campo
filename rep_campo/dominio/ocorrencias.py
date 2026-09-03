# -*- coding: utf-8 -*-
"""Regras da ocorrência."""
from .catalogos import STATUS_OCORRENCIA
from .texto import RE_NUMERO_OCORRENCIA


def numero_valido(numero):
    return bool(RE_NUMERO_OCORRENCIA.fullmatch(numero or ""))


def status_valido(status):
    return status in STATUS_OCORRENCIA


def numero_formatado(ano, sequencial):
    return "OC-%s-%04d" % (ano, sequencial)
