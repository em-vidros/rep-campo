# -*- coding: utf-8 -*-
"""Fichas: sync offline, leitura e resumo do mês. Borda fina: sem SQL aqui."""
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, session

from rep_campo.aplicacao import fichas as servico
from rep_campo.dominio import catalogos as C
from rep_campo.dominio.texto import inteiro
from rep_campo.infra import db as dbmod
from rep_campo.infra import repositorios as repo
from rep_campo.infra.blob import salvar_foto
from rep_campo.infra.relogio import agora
from rep_campo.web.acesso import eh_gestor, login_obrigatorio

bp = Blueprint("fichas", __name__)


@bp.route("/api/bootstrap")
@login_obrigatorio
def bootstrap():
    db = dbmod.get_db()
    clientes = repo.clientes_bootstrap(db)
    municipios = sorted({c["cidade"] for c in clientes if c["cidade"]} |
                        set(C.MUNICIPIOS_MIGRACAO))
    return jsonify({
        "usuario": {"login": session["login"], "nome": session["nome"],
                    "papel": session["papel"]},
        "clientes": clientes,
        "municipios": municipios,
        "tipos": C.TIPOS,
        "problemas": C.PROBLEMAS_TECNICOS,
        "responsaveis": C.RESPONSAVEIS,
        "cesta_preco": C.CESTA_PRECO,
        "processos_csat": C.PROCESSOS_CSAT,
        "expedicoes": C.EXPEDICOES,
        "tipos_evidencia": C.TIPOS_EVIDENCIA,
        "max_anexos": C.MAX_ANEXOS,
        "etapas_jornada": C.ETAPAS_JORNADA,
        "metrica_por_etapa": C.METRICA_POR_ETAPA,
        "dias_minimos_nps": C.DIAS_MINIMOS_ENTRE_NPS,
        "ultimo_nps": repo.ultimo_nps_por_cliente(db),
        "pergunta_experiencia": C.PERGUNTA_EXPERIENCIA,
        "relato_min": C.RELATO_MIN,
        "gerado_em": agora(),
    })


@bp.route("/api/fichas", methods=["POST"])
@login_obrigatorio
def receber():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("fichas"), list):
        return jsonify({"erro": "payload_invalido"}), 400
    usuario = {"uid": session["uid"], "login": session["login"]}
    aceitas, rejeitadas, ocorrencias = servico.receber_lote(
        dbmod.get_db(), payload["fichas"], usuario,
        salvar_foto=salvar_foto, agora=agora, logger=current_app.logger)
    return jsonify({"aceitas": aceitas, "rejeitadas": rejeitadas,
                    "ocorrencias": ocorrencias, "recebido_em": agora()})


@bp.route("/api/fichas")
@login_obrigatorio
def listar():
    limite = min(inteiro(request.args.get("limite"), 50), 300)
    fichas = repo.listar_fichas(
        dbmod.get_db(), limite,
        usuario_login=None if eh_gestor() else session["login"])
    return jsonify({"fichas": fichas})


@bp.route("/api/resumo")
@login_obrigatorio
def resumo():
    mes = datetime.now(timezone.utc).strftime("%Y-%m")
    r = repo.resumo_mes(
        dbmod.get_db(), mes,
        usuario_login=None if eh_gestor() else session["login"])
    total, validas = r["total"], r["validas"]
    return jsonify({
        "mes": mes, "total": total, "validas": validas,
        "qualidade": round(100.0 * validas / total, 1) if total else 0.0,
        "por_tipo": r["por_tipo"], "por_nivel": r["por_nivel"],
        "municipios": r["municipios"], "clientes": r["clientes"],
    })
