# -*- coding: utf-8 -*-
"""Ciclo de cobertura por praça e pertencimento à base."""
from .catalogos import (
    CICLO_IMPERATRIZ,
    CICLO_MIGRACAO,
    CICLO_PARA,
    CICLO_PADRAO,
    ROTAS_FORA_DA_BASE,
)
from .texto import norm

_MIGRACAO = ("santa ines", "ze doca", "bom jardim", "newton belo",
             "moncao", "igarape do meio", "pindare", "pio xii")


def ciclo_do_municipio(cidade):
    c = norm(cidade)
    if "imperatriz" in c:
        return CICLO_IMPERATRIZ
    if c.endswith("/pa") or "/pa" in c:
        return CICLO_PARA
    if any(m in c for m in _MIGRACAO):
        return CICLO_MIGRACAO
    return CICLO_PADRAO


def fora_da_base(rota):
    return norm(rota) in ROTAS_FORA_DA_BASE
