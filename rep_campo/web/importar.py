# -*- coding: utf-8 -*-
"""Importação da planilha oficial de rotas pela tela (só admin)."""
from collections import Counter
from io import BytesIO

from flask import Blueprint, jsonify, render_template, request, session

from rep_campo.dominio import catalogos as C
from rep_campo.dominio.texto import chave_cidade
from rep_campo.infra import db as dbmod
from rep_campo.web.acesso import admin_obrigatorio

bp = Blueprint("importar", __name__)


@bp.route("/importar")
@admin_obrigatorio
def pagina():
    return render_template("importar.html", nome=session.get("nome"),
                           papel=session.get("papel"))


@bp.route("/api/importar/rotas", methods=["POST"])
@admin_obrigatorio
def receber_planilha():
    arq = request.files.get("arquivo")
    if not arq or not arq.filename:
        return jsonify({"erro": "arquivo_ausente"}), 400
    dados = arq.read(C.MAX_ARQUIVO_IMPORTACAO + 1)
    if len(dados) > C.MAX_ARQUIVO_IMPORTACAO:
        return jsonify({"erro": "arquivo_grande"}), 413
    try:
        import openpyxl
        wb = openpyxl.load_workbook(BytesIO(dados), data_only=True, read_only=True)
    except Exception as exc:
        return jsonify({"erro": "nao_e_planilha", "detalhe": str(exc)[:160]}), 400

    ws = wb[wb.sheetnames[0]]
    linhas, cabecalho = [], None
    for linha in ws.iter_rows(values_only=True):
        if not linha or not linha[0]:
            continue
        if cabecalho is None:
            cabecalho = [str(c or "").strip().upper() for c in linha]
            if "CIDADE" not in cabecalho:
                return jsonify({"erro": "sem_coluna_cidade",
                                "colunas": cabecalho[:6]}), 400
            continue
        linhas.append([str(c or "").strip() for c in linha[:4]])
    if not linhas:
        return jsonify({"erro": "planilha_vazia"}), 400

    db = dbmod.get_db()
    db.execute("DELETE FROM rotas_cidades")
    for cidade, base, rota, tabela in [(l + ["", "", ""])[:4] for l in linhas]:
        db.execute("""INSERT INTO rotas_cidades (chave, cidade, base, rota, tabela,
                      atualizado_em) VALUES (%s,%s,%s,%s,%s,%s)
                      ON CONFLICT (chave) DO UPDATE SET cidade=excluded.cidade,
                      base=excluded.base, rota=excluded.rota, tabela=excluded.tabela,
                      atualizado_em=excluded.atualizado_em""",
                   (chave_cidade(cidade), cidade, base, rota, tabela, dbmod.agora()))
    db.commit()

    itz = db.execute("SELECT COUNT(*) c FROM rotas_cidades WHERE LOWER(base)='imperatriz'").fetchone()["c"]
    rotas = [r["rota"] for r in db.execute(
        "SELECT DISTINCT rota FROM rotas_cidades WHERE LOWER(base)='imperatriz' "
        "AND rota <> '' AND LOWER(rota) <> 'sem rota' ORDER BY rota")]
    return jsonify({"ok": True, "cidades": len(linhas), "base_itz": itz,
                    "rotas": rotas, "arquivo": arq.filename})


@bp.route("/api/importar/aplicar-rotas", methods=["POST"])
@admin_obrigatorio
def aplicar():
    db = dbmod.get_db()
    mapa = {r["chave"]: r for r in db.execute("SELECT * FROM rotas_cidades")}
    if not mapa:
        return jsonify({"erro": "importe_a_planilha_antes"}), 400

    corrigidos, fora, outra_base = [], [], []
    for c in db.execute("SELECT codigo, cidade, rota FROM clientes WHERE ativo = 1"):
        m = mapa.get(chave_cidade(c["cidade"]))
        if not m:
            fora.append(c["cidade"])
            continue
        if (m["base"] or "").lower() != "imperatriz":
            outra_base.append(c["cidade"])
            continue
        nova = "" if (m["rota"] or "").strip().lower() in ("", "sem rota") else m["rota"].strip()
        atual = (c["rota"] or "").strip()
        if chave_cidade(atual) != chave_cidade(nova):
            db.execute("UPDATE clientes SET rota = %s, tabela = COALESCE(NULLIF(%s,''), tabela) "
                       "WHERE codigo = %s", (nova, m["tabela"], c["codigo"]))
            corrigidos.append({"cidade": c["cidade"], "de": atual or "(sem rota)",
                               "para": nova or "(sem rota)"})
    db.commit()

    resumo = Counter((x["de"], x["para"]) for x in corrigidos)
    return jsonify({
        "ok": True, "corrigidos": len(corrigidos),
        "resumo": [{"de": d, "para": p, "clientes": n}
                   for (d, p), n in resumo.most_common()],
        "fora_da_planilha": sorted(set(fora))[:60],
        "total_fora": len(set(fora)),
        "de_outra_base": sorted(set(outra_base)),
    })
