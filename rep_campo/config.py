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
        for bruta in fh:
            linha = bruta.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            if linha.startswith("export "):
                linha = linha[7:].lstrip()
            chave, valor = linha.split("=", 1)
            chave = chave.strip()
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
                valor = valor[1:-1]
            if chave:
                os.environ.setdefault(chave, valor)


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
        # 30 dias, e nao 7. A sessao so renova quando o app fala com o servidor, e
        # quem passa uma semana rodando em area sem sinal descobriria a senha
        # vencida no meio da rota, justo onde nao da para entrar de novo.
        "PERMANENT_SESSION_LIFETIME": timedelta(days=30),
    }
