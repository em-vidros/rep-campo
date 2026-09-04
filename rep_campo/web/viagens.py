# -*- coding: utf-8 -*-
"""Rotas, sugestão de visitas e planejamento de viagem. Borda fina: sem SQL aqui."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request, session

from rep_campo.aplicacao import relatorios
from rep_campo.aplicacao.viagens import aderencia, pode_acessar
from rep_campo.dominio.texto import inteiro
from rep_campo.infra import db as dbmod
from rep_campo.infra import repositorios as repo
from rep_campo.infra.relogio import agora
from rep_campo.web.acesso import eh_gestor, login_obrigatorio

bp = Blueprint("viagens", __name__)

_CAMPOS_EDITAVEIS = ("nome", "inicio", "fim", "rota", "observacao", "responsavel")


@bp.route("/viagens")
@login_obrigatorio
def pagina():
    return render_template("viagens.html", nome=session.get("nome"),
                           papel=session.get("papel"))


@bp.route("/api/rotas")
@login_obrigatorio
def rotas():
    return jsonify(relatorios.montar_rotas(dbmod.get_db()))


@bp.route("/api/sugestao")
@login_obrigatorio
def sugestao():
    limite = min(inteiro(request.args.get("limite"), 40), 200)
    cidades = [x.strip() for x in (request.args.get("cidades") or "").split("|") if x.strip()]
    return jsonify(relatorios.montar_sugestao(
        dbmod.get_db(),
        cidades=cidades,
        municipio=(request.args.get("municipio") or "").strip(),
        rota=(request.args.get("rota") or "").strip(),
        limite=limite,
        so_parados=request.args.get("parados") == "1"))


@bp.route("/api/viagens", methods=["GET", "POST"])
@login_obrigatorio
def viagens():
    db = dbmod.get_db()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        nome = (d.get("nome") or "").strip()[:120]
        if not nome:
            return jsonify({"erro": "nome_obrigatorio"}), 400
        tipo = d.get("tipo") if d.get("tipo") in ("viagem", "local") else "viagem"
        row = repo.criar_viagem(
            db, nome, (d.get("inicio") or "")[:20] or None,
            (d.get("fim") or "")[:20] or None, (d.get("rota") or "")[:80] or None,
            (d.get("observacao") or "")[:500] or None, session["login"],
            (d.get("responsavel") or session["login"])[:80], agora(), tipo)
        db.commit()
        return jsonify({"ok": True, "id": row["id"]})

    lista = repo.listar_viagens(
        db, login=None if eh_gestor() else session["login"])
    for d in lista:
        d["aderencia"] = aderencia(d["planejados"], d["visitados"])
    return jsonify({"viagens": lista})


@bp.route("/api/viagens/<int:vid>", methods=["GET", "PATCH", "DELETE"])
@login_obrigatorio
def viagem(vid):
    db = dbmod.get_db()
    v = repo.obter_viagem(db, vid)
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    if not pode_acessar(v, session.get("login"), eh_gestor()):
        return jsonify({"erro": "sem_permissao"}), 403

    if request.method == "DELETE":
        repo.excluir_viagem(db, vid)
        return jsonify({"ok": True})

    if request.method == "PATCH":
        d = request.get_json(silent=True) or {}
        if d.get("status") in ("planejada", "em_andamento", "concluida"):
            repo.atualizar_viagem_status(db, vid, d["status"])
        for campo in _CAMPOS_EDITAVEIS:
            if campo in d:
                repo.atualizar_viagem_campo(
                    db, vid, campo, str(d[campo] or "")[:500] or None)
        repo.confirmar_viagem(db)
        return jsonify({"ok": True})

    clientes = repo.clientes_da_viagem(db, vid)
    d = dict(v)
    d["clientes"] = clientes
    d["planejados"] = len(clientes)
    d["visitados"] = sum(1 for c in clientes if c["visitado"])
    d["aderencia"] = aderencia(d["planejados"], d["visitados"])
    return jsonify(d)


@bp.route("/api/viagens/<int:vid>/relatorio")
@login_obrigatorio
def relatorio(vid):
    db = dbmod.get_db()
    v = repo.obter_viagem(db, vid)
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    if not pode_acessar(v, session.get("login"), eh_gestor()):
        return jsonify({"erro": "sem_permissao"}), 403
    return jsonify(relatorios.montar_relatorio_viagem(db, v))


@bp.route("/api/visitas-avulsas")
@login_obrigatorio
def visitas_avulsas():
    db = dbmod.get_db()
    mes = request.args.get("mes") or datetime.now(timezone.utc).strftime("%Y-%m")
    fichas = repo.visitas_avulsas(
        db, mes, usuario_login=None if eh_gestor() else session["login"])
    por_municipio = {}
    for f in fichas:
        m = f["municipio"] or "sem município"
        por_municipio[m] = por_municipio.get(m, 0) + 1
    return jsonify({
        "mes": mes, "total": len(fichas),
        "clientes": len({f["cliente_nome"] for f in fichas}),
        "por_municipio": sorted(por_municipio.items(), key=lambda x: -x[1]),
        "fichas": fichas,
    })


@bp.route("/api/viagens/<int:vid>/clientes", methods=["POST"])
@login_obrigatorio
def adicionar_clientes(vid):
    d = request.get_json(silent=True) or {}
    lista = d.get("clientes")
    if not isinstance(lista, list):
        return jsonify({"erro": "lista_invalida"}), 400
    db = dbmod.get_db()
    v = repo.obter_viagem(db, vid)
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    if not pode_acessar(v, session.get("login"), eh_gestor()):
        return jsonify({"erro": "sem_permissao"}), 403
    add = repo.adicionar_clientes(db, vid, lista)
    return jsonify({"ok": True, "adicionados": add})


@bp.route("/api/viagens/<int:vid>/clientes/<int:cid>", methods=["DELETE"])
@login_obrigatorio
def remover_cliente(vid, cid):
    db = dbmod.get_db()
    v = repo.obter_viagem(db, vid)
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    if not pode_acessar(v, session.get("login"), eh_gestor()):
        return jsonify({"erro": "sem_permissao"}), 403
    repo.remover_cliente_viagem(db, vid, cid)
    return jsonify({"ok": True})
