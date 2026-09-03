# -*- coding: utf-8 -*-
"""Curva ABC por Pareto sobre o volume 12m."""


def curva_abc(clientes):
    com_vol = [c for c in clientes if (c.get("vol_12m") or 0) > 0]
    sem_vol = [c for c in clientes if (c.get("vol_12m") or 0) <= 0]
    for c in sem_vol:
        c["curva"] = None
    total = sum(c["vol_12m"] for c in com_vol)
    if not total:
        return com_vol + sem_vol
    acum = 0.0
    for c in sorted(com_vol, key=lambda x: x["vol_12m"], reverse=True):
        acum += c["vol_12m"]
        pct = acum / total
        c["curva"] = "A" if pct <= 0.80 else ("B" if pct <= 0.95 else "C")
    return com_vol + sem_vol
