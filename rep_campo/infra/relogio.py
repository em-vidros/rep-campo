# -*- coding: utf-8 -*-
"""Relógio canônico. Único dono do "agora" em ISO-8601.

Antes o `agora()` morava em `infra/db.py` — relógio pendurado na conexão.
Quem precisava de tempo importava o banco junto (`aplicacao` importava
`dbmod` só para carimbar data). Agora `db.agora` continua existindo como
alias, mas o dono é este módulo e a aplicação recebe o relógio por injeção.
"""
from datetime import datetime, timezone


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RelogioSistema:
    def agora(self) -> str:
        return agora()
