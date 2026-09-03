# -*- coding: utf-8 -*-
"""Painel de gestão: fichas, cobertura, ocorrências, experiência e usuários."""
import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request, session

from rep_campo.aplicacao import ocorrencias as servico_oc
from rep_campo.aplicacao import usuarios as servico_usuarios
from rep_campo.aplicacao.viagens import dias_desde, ordenar_cobertura
from rep_campo.dominio import catalogos as C
from rep_campo.dominio.cobertura import ciclo_do_municipio
from rep_campo.dominio.experiencia import cortes, indice_nps
from rep_campo.dominio.texto import inteiro
from rep_campo.infra import db as dbmod
from rep_campo.infra import seguranca
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
    filtros, args = [], []
    mes = request.args.get("mes")
    if mes:
        filtros.append("substr(recebido_em,1,7) = %s")
        args.append(mes)
    for campo, param in (("tipo", "tipo"), ("municipio", "municipio"),
                         ("usuario_login", "usuario"), ("nivel_evidencia", "nivel")):
        v = request.args.get(param)
        if v:
            filtros.append(f"{campo} = %s")
            args.append(v)
    busca = (request.args.get("busca") or "").strip()
    if busca:
        filtros.append("(cliente_nome ILIKE %s OR relato ILIKE %s OR proximo_passo ILIKE %s)")
        args += ["%%%s%%" % busca] * 3

    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    limite = min(inteiro(request.args.get("limite"), 200), 500)
    db = dbmod.get_db()
    rows = db.execute(
        f"SELECT * FROM fichas {onde} ORDER BY recebido_em DESC LIMIT %s",
        args + [limite]).fetchall()

    uuids = [r["uuid"] for r in rows]
    por_ficha = {}
    if uuids:
        for a in db.execute(
                "SELECT ficha_uuid, arquivo, tipo, descricao FROM anexos "
                "WHERE ficha_uuid = ANY(%s) ORDER BY id", (uuids,)):
            por_ficha.setdefault(a["ficha_uuid"], []).append(
                {"arquivo": a["arquivo"], "tipo": a["tipo"], "descricao": a["descricao"]})

    saida = []
    for r in rows:
        d = dict(r)
        try:
            d["extra"] = json.loads(d.pop("extra_json") or "{}")
        except ValueError:
            d["extra"] = {}
        d["anexos"] = por_ficha.get(d["uuid"], [])
        saida.append(d)

    return jsonify({
        "fichas": saida,
        "opcoes": {
            "meses": [x["mes"] for x in db.execute(
                "SELECT DISTINCT substr(recebido_em,1,7) AS mes FROM fichas "
                "ORDER BY 1 DESC")],
            "municipios": [x["municipio"] for x in db.execute(
                "SELECT DISTINCT municipio FROM fichas WHERE municipio <> '' ORDER BY 1")],
            "usuarios": [x["usuario_login"] for x in db.execute(
                "SELECT DISTINCT usuario_login FROM fichas ORDER BY 1")],
        },
    })


@bp.route("/api/gestor/cobertura")
@gestor_obrigatorio
def cobertura():
    db = dbmod.get_db()
    curvas = request.args.get("curvas", "A,B").split(",")
    rows = db.execute("""
        SELECT c.codigo, c.nome, c.cidade, c.curva, c.vol_12m, c.vendedor,
               MAX(f.recebido_em) AS ultima_visita,
               COUNT(f.uuid) AS total_visitas
          FROM clientes c
          LEFT JOIN fichas f ON f.cliente_codigo = c.codigo
         WHERE c.ativo = 1 AND c.curva = ANY(%s)
         GROUP BY c.codigo
    """, (curvas,)).fetchall()

    hoje = datetime.now(timezone.utc)
    saida = []
    for r in rows:
        ciclo = ciclo_do_municipio(r["cidade"])
        dias = dias_desde(r["ultima_visita"], hoje)
        saida.append({
            "codigo": r["codigo"], "nome": r["nome"], "cidade": r["cidade"],
            "curva": r["curva"], "vol_12m": r["vol_12m"], "vendedor": r["vendedor"],
            "ultima_visita": r["ultima_visita"], "total_visitas": r["total_visitas"],
            "dias": dias, "ciclo": ciclo,
            "vencido": (dias is None) or (dias > ciclo),
        })

    ordenar_cobertura(saida)
    vencidos = [x for x in saida if x["vencido"]]
    return jsonify({
        "clientes": saida,
        "total": len(saida),
        "vencidos": len(vencidos),
        "nunca_visitados": len([x for x in saida if x["dias"] is None]),
        "cobertura_pct": round(100.0 * (len(saida) - len(vencidos)) / len(saida), 1) if saida else 0.0,
        "risco_reais": round(sum(x["vol_12m"] for x in vencidos), 2),
    })


@bp.route("/api/gestor/ocorrencias")
@gestor_obrigatorio
def ocorrencias():
    filtros, args = [], []
    for campo, param in (("status", "situacao"), ("canal", "canal"),
                         ("setor", "setor"), ("tipo", "tipo")):
        v = request.args.get(param)
        if v:
            filtros.append(f"{campo} = %s")
            args.append(v)
    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    db = dbmod.get_db()
    rows = db.execute(
        "SELECT * FROM ocorrencias " + onde + " ORDER BY numero DESC LIMIT 300", args
    ).fetchall()

    hoje = datetime.now(timezone.utc)
    saida = []
    for r in rows:
        d = dict(r)
        d["dias_aberta"] = dias_desde(r["aberta_em"], hoje)
        saida.append(d)

    cont = {x["status"]: x["n"] for x in db.execute(
        "SELECT status, COUNT(*) AS n FROM ocorrencias GROUP BY status")}
    return jsonify({
        "ocorrencias": saida,
        "abertas": cont.get("aberta", 0) + cont.get("em_andamento", 0),
        "resolvidas": cont.get("resolvida", 0),
        "por_canal": {x["canal"]: x["n"] for x in db.execute(
            "SELECT canal, COUNT(*) AS n FROM ocorrencias GROUP BY canal")},
        "canais": C.CANAIS, "setores": C.SETORES, "status": C.STATUS_OCORRENCIA,
    })


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
    db = dbmod.get_db()
    mes = request.args.get("mes")
    base, args = "FROM experiencia WHERE 1=1", []
    if mes:
        base += " AND substr(registrado_em,1,7) = %s"
        args.append(mes)

    def bloco(metrica, corte):
        linhas = db.execute(
            "SELECT etapa, COUNT(*) n, ROUND(AVG(nota),1) media, "
            "SUM(CASE WHEN nota >= %s THEN 1 ELSE 0 END) bons, "
            "SUM(CASE WHEN nota <= %s THEN 1 ELSE 0 END) ruins "
            + base + " AND metrica = %s GROUP BY etapa ORDER BY media ASC",
            [corte, C.NPS_DETRATOR] + args + [metrica]).fetchall()
        tot = db.execute(
            "SELECT COUNT(*) n, ROUND(AVG(nota),1) media, "
            "SUM(CASE WHEN nota >= %s THEN 1 ELSE 0 END) bons, "
            "SUM(CASE WHEN nota <= %s THEN 1 ELSE 0 END) ruins "
            + base + " AND metrica = %s",
            [corte, C.NPS_DETRATOR] + args + [metrica]).fetchone()
        n = tot["n"] or 0
        return {"por_etapa": [{**dict(r), "media": dbmod.como_float(r["media"])}
                              for r in linhas], "n": n,
                "media": dbmod.como_float(tot["media"]), "bons": tot["bons"] or 0,
                "ruins": tot["ruins"] or 0,
                "pct_bons": round(100.0 * (tot["bons"] or 0) / n) if n else None}

    nps = bloco("nps", C.NPS_PROMOTOR)
    nps["indice"] = indice_nps(nps["bons"], nps["ruins"], nps["n"])

    comentarios = [dict(r) for r in db.execute(
        "SELECT cliente_nome, etapa AS exp_etapa, nota AS exp_nota, "
        "comentario AS exp_comentario, metrica AS exp_metrica, "
        "registrado_em AS recebido_em " + base +
        " AND comentario IS NOT NULL AND comentario <> '' "
        "ORDER BY nota ASC, registrado_em DESC LIMIT 40", args)]

    expedicao = [{**dict(r), "media": dbmod.como_float(r["media"])} for r in db.execute(
        "SELECT unidade, COUNT(*) n, ROUND(AVG(nota),1) media, "
        "SUM(CASE WHEN nota >= %s THEN 1 ELSE 0 END) bons " + base +
        " AND etapa = 'Atendimento da expedicao' AND unidade IS NOT NULL "
        "GROUP BY unidade ORDER BY media ASC", [C.CSAT_SATISFEITO] + args)]

    return jsonify({
        "expedicao": expedicao,
        "nps": nps, "csat": bloco("csat", C.CSAT_SATISFEITO),
        "ces": bloco("ces", C.CES_FACIL), "comentarios": comentarios,
        "clientes_ouvidos": db.execute(
            "SELECT COUNT(DISTINCT COALESCE(cliente_codigo, cliente_nome)) c "
            + base, args).fetchone()["c"],
        "cortes": cortes(),
    })


@bp.route("/usuarios")
@admin_obrigatorio
def pagina_usuarios():
    return render_template("usuarios.html", nome=session.get("nome"))


@bp.route("/api/gestor/usuarios")
@admin_obrigatorio
def listar_usuarios():
    rows = dbmod.get_db().execute(
        "SELECT id, login, nome, papel, ativo, criado_em FROM usuarios ORDER BY ativo DESC, nome"
    ).fetchall()
    return jsonify({"usuarios": [dict(r) for r in rows], "eu": session["uid"]})


@bp.route("/api/gestor/usuarios", methods=["POST"])
@admin_obrigatorio
def criar_usuario():
    erro, dados = servico_usuarios.validar_criacao(request.get_json(silent=True) or {})
    if erro:
        return jsonify({"erro": erro}), 400
    db = dbmod.get_db()
    if db.execute("SELECT 1 FROM usuarios WHERE login = %s", (dados["login"],)).fetchone():
        return jsonify({"erro": "login_ja_existe"}), 409
    db.execute("INSERT INTO usuarios (login, nome, senha_hash, papel, base, ativo, criado_em)"
               " VALUES (%s,%s,%s,%s,'ITZ',1,%s)",
               (dados["login"], dados["nome"], seguranca.hash_senha(dados["senha"]),
                dados["papel"], dbmod.agora()))
    db.commit()
    return jsonify({"ok": True, "login": dados["login"]})


@bp.route("/api/gestor/usuarios/<int:uid>", methods=["PATCH"])
@admin_obrigatorio
def alterar_usuario(uid):
    d = request.get_json(silent=True) or {}
    db = dbmod.get_db()
    if not db.execute("SELECT * FROM usuarios WHERE id = %s", (uid,)).fetchone():
        return jsonify({"erro": "nao_encontrado"}), 404
    if "ativo" in d:
        if uid == session["uid"]:
            return jsonify({"erro": "nao_pode_desativar_a_si_mesmo"}), 400
        db.execute("UPDATE usuarios SET ativo = %s WHERE id = %s",
                   (1 if d["ativo"] else 0, uid))
    if "papel" in d and d["papel"] in C.PAPEIS:
        if uid == session["uid"] and d["papel"] != "admin":
            return jsonify({"erro": "nao_pode_rebaixar_a_si_mesmo"}), 400
        if d["papel"] == "admin" and not eh_admin():
            return jsonify({"erro": "so_admin_promove_admin"}), 403
        db.execute("UPDATE usuarios SET papel = %s WHERE id = %s", (d["papel"], uid))
    if "senha" in d:
        if len(d["senha"] or "") < C.SENHA_MIN:
            return jsonify({"erro": "senha_curta"}), 400
        db.execute("UPDATE usuarios SET senha_hash = %s WHERE id = %s",
                   (seguranca.hash_senha(d["senha"]), uid))
    db.commit()
    return jsonify({"ok": True})
