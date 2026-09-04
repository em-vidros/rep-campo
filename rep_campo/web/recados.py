# -*- coding: utf-8 -*-
"""Recados do gestor para quem esta em campo. Borda fina: sem SQL aqui."""
from flask import Blueprint, jsonify, render_template, request, session

from rep_campo.aplicacao import recados as app_recados
from rep_campo.dominio import recados as D
from rep_campo.dominio.texto import inteiro
from rep_campo.infra import db as dbmod
from rep_campo.infra import repositorios as repo
from rep_campo.web.acesso import gestor_obrigatorio, login_obrigatorio

bp = Blueprint("recados", __name__)


@bp.route("/recados")
@gestor_obrigatorio
def pagina():
    return render_template("recados.html", nome=session.get("nome"),
                           papel=session.get("papel"))


@bp.route("/api/recados", methods=["GET"])
@gestor_obrigatorio
def listar():
    db = dbmod.get_db()
    situacao = (request.args.get("situacao") or "").strip()
    status = D.PENDENTES if situacao == "pendentes" else None
    if situacao == "concluidos":
        status = (D.CONCLUIDO,)
    return jsonify({
        "recados": app_recados.listar(db, status=status),
        "reps": [dict(u) for u in repo.listar_usuarios(db)
                 if u["papel"] == "rep" and u["ativo"]],
    })


@bp.route("/api/recados", methods=["POST"])
@gestor_obrigatorio
def criar():
    d = request.get_json(silent=True) or {}
    rid, erro = app_recados.mandar(
        dbmod.get_db(),
        de_login=session["login"], de_nome=session.get("nome") or session["login"],
        para_login=(d.get("para") or "").strip(),
        texto=d.get("texto"),
        cliente_codigo=(d.get("cliente_codigo") or "").strip() or None,
        cliente_nome=(d.get("cliente_nome") or "").strip() or None,
        prazo=(d.get("prazo") or "").strip() or None)
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "id": rid})


@bp.route("/api/recados/<int:rid>/cancelar", methods=["POST"])
@gestor_obrigatorio
def cancelar(rid):
    if not app_recados.cancelar(dbmod.get_db(), rid):
        return jsonify({"erro": "nao_esta_pendente"}), 409
    return jsonify({"ok": True})


# ------------------------------------------------------- lado do representante

@bp.route("/api/meus-recados", methods=["GET"])
@login_obrigatorio
def meus():
    return jsonify(app_recados.para_o_app(dbmod.get_db(), session["login"]))


@bp.route("/api/meus-recados/lidos", methods=["POST"])
@login_obrigatorio
def lidos():
    d = request.get_json(silent=True) or {}
    ids = [inteiro(x, 0) for x in (d.get("ids") or [])]
    n = app_recados.marcar_lidos(dbmod.get_db(), session["login"], [i for i in ids if i])
    return jsonify({"ok": True, "marcados": n})


@bp.route("/api/meus-recados/<int:rid>/concluir", methods=["POST"])
@login_obrigatorio
def concluir(rid):
    d = request.get_json(silent=True) or {}
    n = app_recados.concluir(dbmod.get_db(), session["login"], rid,
                             resposta=d.get("resposta"), ficha_uuid=d.get("ficha_uuid"))
    if not n:
        return jsonify({"erro": "nao_esta_pendente"}), 409
    return jsonify({"ok": True})
