# -*- coding: utf-8 -*-
"""Postgres. Conexão por requisição; o esquema mora em scripts/setup_db.py.

O relógio canônico mora em `infra/relogio.py`. `agora` segue aqui como alias
para não quebrar quem já importa de `db`.
"""
import os

import psycopg
from flask import g
from psycopg.rows import dict_row

from rep_campo.infra.relogio import agora  # noqa: F401 (alias canônico)


def conectar(url=None):
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL nao definida nas variaveis de ambiente")
    return psycopg.connect(url, row_factory=dict_row, prepare_threshold=None,
                            connect_timeout=20)


def get_db():
    if "db" not in g:
        g.db = conectar()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def como_float(valor):
    return float(valor) if valor is not None else None
