# -*- coding: utf-8 -*-
"""Painel de gestão: borda fina. Regra em `aplicacao/relatorios.py`, SQL em `infra/repositorios.py`."""
from flask import Blueprint, jsonify, render_template, request, session

from rep_campo.aplicacao import ocorrencias as servico_oc
from rep_campo.aplicacao import relatorios
from rep_campo.aplicacao import usuarios as servico_usuarios
from rep_campo.dominio import catalogos as C
from rep_campo.dominio.texto import inteiro
from rep_campo.infra import db as dbmod
from rep_campo.infra import repositorios as repo
from rep_campo.infra import seguranca
from rep_campo.infra.relogio import agora
from rep_campo.web.acesso import admin_obrigatorio, eh_admin, gestor_obrigatorio

bp = Blueprint("gestor", __name__)


@bp.route("/painel")
@gestor_obrigatorio
def painel():
    return render_template("painel.html", nome=session.get("nome"),
                           papel=session.get("papel"), tipos=C.TIPOS)


@bp.route("/api/gestor/fichas")
@gestor_obrigatorio
def fichas():
    limite = min(inteiro(request.args.get("limite"), 200), 500)
    return jsonify(relatorios.montar_fichas_gestor(
        dbmod.get_db(),
        mes=request.args.get("mes"),
        tipo=request.args.get("tipo"),
        municipio=request.args.get("municipio"),
        usuario=request.args.get("usuario"),
        nivel=request.args.get("nivel"),
        busca=request.args.get("busca"),
        limite=limite))


@bp.route("/api/gestor/cobertura")
@gestor_obrigatorio
def cobertura():
    curvas = request.args.get("curvas", "A,B").split(",")
    return jsonify(relatorios.montar_cobertura(dbmod.get_db(), curvas))


@bp.route("/api/gestor/ocorrencias")
@gestor_obrigatorio
def ocorrencias():
    return jsonify(relatorios.montar_ocorrencias(
        dbmod.get_db(),
        situacao=request.args.get("situacao"),
        canal=request.args.get("canal"),
        setor=request.args.get("setor"),
        tipo=request.args.get("tipo")))


@bp.route("/api/gestor/ocorrencia/<numero>", methods=["PATCH"])
@gestor_obrigatorio
def atualizar_ocorrencia(numero):
    dados = request.get_json(silent=True) or {}
    erro, _ = servico_oc.atualizar(dbmod.get_db(), numero, dados, session["login"])
    if erro == "numero_invalido":
        return jsonify({"erro": erro}), 400
    if erro == "nao_encontrada":
        return jsonify({"erro": erro}), 404
    if erro == "status_invalido":
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "numero": numero})


@bp.route("/api/gestor/experiencia")
@gestor_obrigatorio
def experiencia():
    return jsonify(relatorios.montar_experiencia(
        dbmod.get_db(), mes=request.args.get("mes")))


@bp.route("/usuarios")
@admin_obrigatorio
def pagina_usuarios():
    return render_template("usuarios.html", nome=session.get("nome"))


@bp.route("/api/gestor/usuarios")
@admin_obrigatorio
def listar_usuarios():
    db = dbmod.get_db()
    return jsonify({"usuarios": repo.listar_usuarios(db), "eu": session["uid"]})


@bp.route("/api/gestor/usuarios", methods=["POST"])
@admin_obrigatorio
def criar_usuario():
    erro, dados = servico_usuarios.validar_criacao(request.get_json(silent=True) or {})
    if erro:
        return jsonify({"erro": erro}), 400
    db = dbmod.get_db()
    if repo.login_existe(db, dados["login"]):
        return jsonify({"erro": "login_ja_existe"}), 409
    repo.criar_usuario(db, dados["login"], dados["nome"],
                       seguranca.hash_senha(dados["senha"]),
                       dados["papel"], agora())
    return jsonify({"ok": True, "login": dados["login"]})


@bp.route("/api/gestor/usuarios/<int:uid>", methods=["PATCH"])
@admin_obrigatorio
def alterar_usuario(uid):
    d = request.get_json(silent=True) or {}
    db = dbmod.get_db()
    if not repo.obter_usuario(db, uid):
        return jsonify({"erro": "nao_encontrado"}), 404
    if "ativo" in d:
        if uid == session["uid"]:
            return jsonify({"erro": "nao_pode_desativar_a_si_mesmo"}), 400
        repo.atualizar_usuario(db, uid, ativo=bool(d["ativo"]))
    if "papel" in d and d["papel"] in C.PAPEIS:
        if uid == session["uid"] and d["papel"] != "admin":
            return jsonify({"erro": "nao_pode_rebaixar_a_si_mesmo"}), 400
        if d["papel"] == "admin" and not eh_admin():
            return jsonify({"erro": "so_admin_promove_admin"}), 403
        repo.atualizar_usuario(db, uid, papel=d["papel"])
    if "senha" in d:
        if len(d["senha"] or "") < C.SENHA_MIN:
            return jsonify({"erro": "senha_curta"}), 400
        repo.atualizar_usuario(db, uid, senha_hash=seguranca.hash_senha(d["senha"]))
    db.commit()
    return jsonify({"ok": True})
