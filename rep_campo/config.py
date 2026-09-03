# -*- coding: utf-8 -*-
"""Configuração. Única dona do .env, caminhos e segredos."""
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def carregar_env():
    caminho = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(caminho):
        return
    with open(caminho, encoding="utf-8") as fh:
        for linha in fh:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def secret_key():
    chave = os.environ.get("REP_SECRET_KEY")
    if not chave:
        raise RuntimeError("REP_SECRET_KEY nao definida nas variaveis de ambiente")
    return chave


def flask_config():
    return {
        "MAX_CONTENT_LENGTH": 4 * 1024 * 1024,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": os.environ.get("REP_INSECURE_COOKIE") != "1",
        "PERMANENT_SESSION_LIFETIME": timedelta(days=7),
    }
