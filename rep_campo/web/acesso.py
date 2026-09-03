# -*- coding: utf-8 -*-
"""Guards de sessão. Uma regra por guard, sem ramificação espalhada."""
from functools import wraps

from flask import jsonify, redirect, request, session, url_for

from rep_campo.dominio.catalogos import PAPEIS_GESTAO


def eh_gestor():
    return session.get("papel") in PAPEIS_GESTAO


def eh_admin():
    return session.get("papel") == "admin"


def _sem_acesso():
    if request.path.startswith("/api/"):
        return jsonify({"erro": "nao_autenticado"}), 401
    return redirect(url_for("auth.login", next=request.path))


def _sem_permissao():
    if request.path.startswith("/api/"):
        return jsonify({"erro": "sem_permissao"}), 403
    return redirect(url_for("sistema.index"))


def login_obrigatorio(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if "uid" not in session:
            return _sem_acesso()
        return fn(*a, **kw)
    return wrapper


def gestor_obrigatorio(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if "uid" not in session:
            return _sem_acesso()
        if not eh_gestor():
            return _sem_permissao()
        return fn(*a, **kw)
    return wrapper


def admin_obrigatorio(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if "uid" not in session:
            return _sem_acesso()
        if not eh_admin():
            return _sem_permissao()
        return fn(*a, **kw)
    return wrapper


def origem_visitante():
    encaminhado = request.headers.get("X-Forwarded-For", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()[:60]
    return (request.remote_addr or "?")[:60]
