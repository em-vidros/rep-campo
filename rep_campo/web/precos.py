# -*- coding: utf-8 -*-
"""Painel de preco da concorrencia. Borda fina: sem SQL aqui."""
from flask import Blueprint, jsonify, render_template, request, session

from rep_campo.aplicacao import precos as app_precos
from rep_campo.infra import db as dbmod
from rep_campo.web.acesso import gestor_obrigatorio, login_obrigatorio

bp = Blueprint("precos", __name__)


@bp.route("/precos")
@login_obrigatorio
def pagina():
    return render_template("precos.html", nome=session.get("nome"),
                           papel=session.get("papel"))


@bp.route("/api/precos")
@gestor_obrigatorio
def painel():
    return jsonify(app_precos.painel(
        dbmod.get_db(),
        concorrente=(request.args.get("concorrente") or "").strip(),
        item=(request.args.get("item") or "").strip(),
        municipio=(request.args.get("municipio") or "").strip(),
        desde=(request.args.get("desde") or "").strip()))


@bp.route("/api/precos/matriz")
@gestor_obrigatorio
def matriz():
    return jsonify(app_precos.matriz(
        dbmod.get_db(),
        rota=(request.args.get("rota") or "").strip(),
        municipio=(request.args.get("municipio") or "").strip(),
        cliente=(request.args.get("cliente") or "").strip(),
        desde=(request.args.get("desde") or "").strip()))


@bp.route("/api/precos/onde-atua")
@gestor_obrigatorio
def onde_atua():
    return jsonify({"concorrentes": app_precos.onde_atua(dbmod.get_db())})


@bp.route("/api/precos/serie")
@gestor_obrigatorio
def serie():
    c = (request.args.get("concorrente") or "").strip()
    i = (request.args.get("item") or "").strip()
    if not c or not i:
        return jsonify({"erro": "informe_concorrente_e_item"}), 400
    return jsonify({"serie": app_precos.serie(dbmod.get_db(), c, i)})


# ----------------------------------------- atualizacao pelo representante

@bp.route("/api/precos/formulario")
@login_obrigatorio
def formulario():
    cidades = [c for c in (request.args.get("cidades") or "").split("|") if c.strip()]
    return jsonify(app_precos.formulario(
        dbmod.get_db(),
        concorrente=(request.args.get("concorrente") or "").strip(),
        cidades=cidades))


@bp.route("/api/precos/registrar", methods=["POST"])
@login_obrigatorio
def registrar():
    d = request.get_json(silent=True) or {}
    r, erro = app_precos.registrar(dbmod.get_db(), session["login"], d)
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, **r})
