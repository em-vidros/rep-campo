# -*- coding: utf-8 -*-
"""Páginas públicas, foto e saúde."""
import os

from flask import Blueprint, Response, current_app, jsonify, render_template, send_from_directory, session

from rep_campo.dominio import catalogos as C
from rep_campo.infra import blob, db as dbmod
from rep_campo.web.acesso import login_obrigatorio

bp = Blueprint("sistema", __name__)


@bp.route("/")
@login_obrigatorio
def index():
    return render_template("index.html", nome=session.get("nome"),
                           papel=session.get("papel"), tipos=C.TIPOS)


@bp.route("/sw.js")
def service_worker():
    resp = send_from_directory(os.path.join(current_app.root_path, "static"), "sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(os.path.join(current_app.root_path, "static"),
                               "manifest.webmanifest")


@bp.route("/foto/<nome>")
@login_obrigatorio
def foto(nome):
    if not blob.nome_foto_valido(nome):
        return "", 404
    binario, tipo = blob.ler(nome)
    if binario is None:
        return "", 404
    return Response(binario, mimetype=tipo,
                    headers={"Cache-Control": "private, max-age=3600"})


@bp.route("/ping")
def ping():
    """Sonda de rede do app. Nao toca no banco: a pergunta e so se ha rede."""
    return jsonify({"ok": True}), 200, {"Cache-Control": "no-store"}


@bp.route("/saude")
def saude():
    try:
        n = dbmod.get_db().execute("SELECT COUNT(*) c FROM clientes").fetchone()["c"]
        return jsonify({"ok": True, "clientes": n, "hora": dbmod.agora()})
    except Exception:
        current_app.logger.exception("saude falhou")
        return jsonify({"ok": False, "erro": "banco_indisponivel"}), 500
