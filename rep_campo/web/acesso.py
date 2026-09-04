# -*- coding: utf-8 -*-
"""Guards de sessão. Uma regra por guard, sem ramificação espalhada."""
from functools import wraps

from flask import jsonify, redirect, request, session, url_for

from rep_campo.dominio.catalogos import PAPEIS_GESTAO
from rep_campo.infra import db as dbmod
from rep_campo.infra import repositorios as repo


def eh_gestor():
    return session.get("papel") in PAPEIS_GESTAO


def eh_admin():
    return session.get("papel") == "admin"


def sessao_valida():
    """Confere no banco quem o cookie diz que e, a cada pedido.

    O cookie vale 30 dias para o REP nao perder o login no meio da rota. Sem
    esta conferencia, desativar alguem no painel nao tiraria o acesso dele por
    um mes, e trocar o papel so valeria no proximo login.
    """
    if "uid" not in session:
        return False
    row = repo.papel_ativo(dbmod.get_db(), session["uid"])
    if not row or not row["ativo"]:
        session.clear()
        return False
    session["papel"] = row["papel"]
    return True


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
        if not sessao_valida():
            return _sem_acesso()
        return fn(*a, **kw)
    return wrapper


def gestor_obrigatorio(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not sessao_valida():
            return _sem_acesso()
        if not eh_gestor():
            return _sem_permissao()
        return fn(*a, **kw)
    return wrapper


def admin_obrigatorio(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not sessao_valida():
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
