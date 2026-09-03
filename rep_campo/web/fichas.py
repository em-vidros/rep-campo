# -*- coding: utf-8 -*-
"""Fichas: sync offline, leitura e resumo do mês."""
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, session

from rep_campo.aplicacao import fichas as servico
from rep_campo.dominio import catalogos as C
from rep_campo.dominio.texto import inteiro
from rep_campo.infra import db as dbmod
from rep_campo.web.acesso import eh_gestor, login_obrigatorio

bp = Blueprint("fichas", __name__)


@bp.route("/api/bootstrap")
@login_obrigatorio
def bootstrap():
    db = dbmod.get_db()
    clientes = [dict(r) for r in db.execute(
        "SELECT codigo, nome, cidade, curva, vol_12m, rota, vendedor "
        "FROM clientes WHERE ativo = 1 ORDER BY nome"
    ).fetchall()]
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
        "ultimo_nps": {r["cliente_codigo"]: r["quando"] for r in db.execute(
            "SELECT cliente_codigo, MAX(recebido_em) quando FROM fichas "
            "WHERE exp_metrica = 'nps' AND cliente_codigo IS NOT NULL "
            "GROUP BY cliente_codigo")},
        "pergunta_experiencia": C.PERGUNTA_EXPERIENCIA,
        "relato_min": C.RELATO_MIN,
        "gerado_em": dbmod.agora(),
    })


@bp.route("/api/fichas", methods=["POST"])
@login_obrigatorio
def receber():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("fichas"), list):
        return jsonify({"erro": "payload_invalido"}), 400
    usuario = {"uid": session["uid"], "login": session["login"]}
    aceitas, rejeitadas, ocorrencias = servico.receber_lote(
        dbmod.get_db(), payload["fichas"], usuario, logger=current_app.logger)
    return jsonify({"aceitas": aceitas, "rejeitadas": rejeitadas,
                    "ocorrencias": ocorrencias, "recebido_em": dbmod.agora()})


@bp.route("/api/fichas")
@login_obrigatorio
def listar():
    limite = min(inteiro(request.args.get("limite"), 50), 300)
    if eh_gestor():
        rows = dbmod.get_db().execute(
            "SELECT * FROM fichas ORDER BY recebido_em DESC LIMIT %s", (limite,)
        ).fetchall()
    else:
        rows = dbmod.get_db().execute(
            "SELECT * FROM fichas WHERE usuario_login = %s "
            "ORDER BY recebido_em DESC LIMIT %s", (session["login"], limite)
        ).fetchall()
    return jsonify({"fichas": [dict(r) for r in rows]})


@bp.route("/api/resumo")
@login_obrigatorio
def resumo():
    db = dbmod.get_db()
    mes = datetime.now(timezone.utc).strftime("%Y-%m")
    where = "WHERE substr(recebido_em,1,7) = %s"
    args = [mes]
    if not eh_gestor():
        where += " AND usuario_login = %s"
        args.append(session["login"])
    total = db.execute("SELECT COUNT(*) c FROM fichas " + where, args).fetchone()["c"]
    por_tipo = {r["tipo"]: r["c"] for r in db.execute(
        "SELECT tipo, COUNT(*) c FROM fichas " + where + " GROUP BY tipo", args)}
    por_nivel = {r["nivel_evidencia"]: r["c"] for r in db.execute(
        "SELECT nivel_evidencia, COUNT(*) c FROM fichas " + where +
        " GROUP BY nivel_evidencia", args)}
    validas = db.execute(
        "SELECT COUNT(*) c FROM fichas " + where + " AND conta_indicador = 1", args
    ).fetchone()["c"]
    municipios = db.execute(
        "SELECT COUNT(DISTINCT municipio) c FROM fichas " + where, args
    ).fetchone()["c"]
    clientes = db.execute(
        "SELECT COUNT(DISTINCT cliente_nome) c FROM fichas " + where, args
    ).fetchone()["c"]
    return jsonify({
        "mes": mes, "total": total, "validas": validas,
        "qualidade": round(100.0 * validas / total, 1) if total else 0.0,
        "por_tipo": por_tipo, "por_nivel": por_nivel,
        "municipios": municipios, "clientes": clientes,
    })
