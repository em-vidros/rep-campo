# -*- coding: utf-8 -*-
"""Recebimento do lote offline. Uma ficha por transação, idempotente por uuid."""
import json
from datetime import datetime, timezone

from rep_campo.dominio import catalogos as C
from rep_campo.dominio.experiencia import metrica_para_etapa
from rep_campo.dominio.ocorrencias import numero_formatado
from rep_campo.dominio.texto import RE_UUID, num_float, texto_limitado
from rep_campo.dominio.visitas import classificar_evidencia, relato_curto, validar_nota
from rep_campo.infra import blob, db as dbmod


def proxima_ocorrencia(db):
    ano = datetime.now(timezone.utc).strftime("%Y")
    row = db.execute(
        "INSERT INTO contador_ocorrencias (ano, ultimo) VALUES (%s, 1) "
        "ON CONFLICT (ano) DO UPDATE SET ultimo = contador_ocorrencias.ultimo + 1 "
        "RETURNING ultimo", (ano,)).fetchone()
    return numero_formatado(ano, row["ultimo"])


def salvar_anexos(db, uuid_ficha, lista):
    if not isinstance(lista, list):
        return 0
    gravados = 0
    for i, anexo in enumerate(lista[:C.MAX_ANEXOS]):
        if not isinstance(anexo, dict):
            continue
        nome = blob.salvar_foto("%s-anexo%d" % (uuid_ficha, i), anexo.get("foto"))
        if not nome:
            continue
        db.execute("INSERT INTO anexos (ficha_uuid, arquivo, tipo, descricao, criado_em)"
                   " VALUES (%s,%s,%s,%s,%s)",
                   (uuid_ficha, nome, str(anexo.get("tipo") or "")[:80] or None,
                    str(anexo.get("descricao") or "")[:300] or None, dbmod.agora()))
        gravados += 1
    return gravados


def _respostas(ficha, etapa, nota):
    respostas = ficha.get("experiencia")
    if not isinstance(respostas, list):
        respostas = ([{"etapa": etapa, "nota": nota,
                       "comentario": ficha.get("exp_comentario")}]
                     if etapa and nota is not None else [])
    saida = []
    for resp in respostas[:12]:
        etapa_r = str(resp.get("etapa") or "")[:60]
        try:
            nota_r = int(resp.get("nota"))
        except (TypeError, ValueError):
            continue
        if not etapa_r or not 0 <= nota_r <= 10:
            continue
        saida.append({
            "etapa": etapa_r, "nota": nota_r,
            "comentario": str(resp.get("comentario") or "")[:1200] or None,
            "unidade": str(resp.get("unidade") or "")[:40] or None,
        })
    return saida


def _gravar_ficha(db, ficha, uuid_f, tipo, cliente_nome, usuario, foto_arq):
    nivel = classificar_evidencia(
        bool(foto_arq),
        ficha.get("lat") is not None and ficha.get("lon") is not None,
        bool((ficha.get("proximo_passo") or "").strip()))
    relato = (ficha.get("relato") or "").strip()[:C.LIMITES_TEXTO["relato"]]
    etapa = texto_limitado(ficha, "exp_etapa", C.LIMITES_TEXTO)
    metrica = metrica_para_etapa(etapa) if etapa else None
    nota = validar_nota(ficha.get("exp_nota"))

    with db.transaction():
        ocorrencia = proxima_ocorrencia(db) if tipo == "tecnica" else None
        db.execute("""
            INSERT INTO fichas (uuid, usuario_id, usuario_login, tipo, cliente_codigo,
                cliente_nome, prospect, municipio, objetivo, relato, proximo_passo,
                prox_responsavel, prox_data, encaminhado_para, lat, lon, precisao,
                criado_em_disp, recebido_em, foto_arquivo, extra_json,
                nivel_evidencia, conta_indicador, relato_curto, app_versao,
                problema_tipo, ocorrencia_num, ocorrencia_status,
                exp_etapa, exp_nota, exp_comentario, exp_metrica)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            uuid_f, usuario["uid"], usuario["login"], tipo,
            str(ficha.get("cliente_codigo") or "")[:40] or None, cliente_nome,
            1 if ficha.get("prospect") else 0,
            texto_limitado(ficha, "municipio", C.LIMITES_TEXTO),
            texto_limitado(ficha, "objetivo", C.LIMITES_TEXTO), relato,
            texto_limitado(ficha, "proximo_passo", C.LIMITES_TEXTO),
            texto_limitado(ficha, "prox_responsavel", C.LIMITES_TEXTO),
            texto_limitado(ficha, "prox_data", C.LIMITES_TEXTO),
            texto_limitado(ficha, "encaminhado_para", C.LIMITES_TEXTO),
            num_float(ficha.get("lat")), num_float(ficha.get("lon")),
            num_float(ficha.get("precisao")),
            texto_limitado(ficha, "criado_em_disp", C.LIMITES_TEXTO),
            dbmod.agora(), foto_arq,
            json.dumps(ficha.get("extra") or {}, ensure_ascii=False)[:C.MAX_EXTRA_JSON],
            nivel, 1 if (ficha.get("proximo_passo") or "").strip() else 0,
            relato_curto(relato),
            texto_limitado(ficha, "app_versao", C.LIMITES_TEXTO),
            texto_limitado(ficha, "problema_tipo", C.LIMITES_TEXTO),
            ocorrencia, "aberta" if ocorrencia else None,
            etapa, nota, texto_limitado(ficha, "exp_comentario", C.LIMITES_TEXTO), metrica,
        ))
        if ocorrencia:
            extra = ficha.get("extra") or {}
            db.execute("""
                INSERT INTO ocorrencias
                    (numero, aberta_em, aberta_por, setor, canal, cliente_codigo,
                     cliente_nome, municipio, tipo, descricao, pedido_nf, status,
                     responsavel, prazo, ficha_uuid, foto_arquivo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'aberta',%s,%s,%s,%s)
                ON CONFLICT (numero) DO NOTHING
            """, (ocorrencia, dbmod.agora(), usuario["login"], "Comercial",
                  "Visita do representante",
                  str(ficha.get("cliente_codigo") or "")[:40] or None, cliente_nome,
                  texto_limitado(ficha, "municipio", C.LIMITES_TEXTO),
                  texto_limitado(ficha, "problema_tipo", C.LIMITES_TEXTO),
                  relato, str(extra.get("pedido_nf") or "")[:60] or None,
                  texto_limitado(ficha, "prox_responsavel", C.LIMITES_TEXTO),
                  texto_limitado(ficha, "prox_data", C.LIMITES_TEXTO),
                  uuid_f, foto_arq))
        for resp in _respostas(ficha, etapa, nota):
            db.execute("""INSERT INTO experiencia (ficha_uuid, cliente_codigo,
                cliente_nome, etapa, metrica, nota, comentario, unidade,
                registrado_em, usuario_login) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uuid_f, str(ficha.get("cliente_codigo") or "")[:40] or None,
                 cliente_nome, resp["etapa"], metrica_para_etapa(resp["etapa"]),
                 resp["nota"], resp["comentario"], resp["unidade"],
                 dbmod.agora(), usuario["login"]))
        cod = str(ficha.get("cliente_codigo") or "")[:40]
        if cod:
            achou = db.execute("""
                UPDATE viagem_clientes SET visitado = 1, ficha_uuid = %s, visitado_em = %s
                 WHERE visitado = 0 AND cliente_codigo = %s AND viagem_id IN (
                       SELECT id FROM viagens
                        WHERE status IN ('planejada','em_andamento')
                          AND (criada_por = %s OR responsavel = %s))
             RETURNING viagem_id
            """, (uuid_f, dbmod.agora(), cod, usuario["login"], usuario["login"])).fetchone()
            if achou:
                db.execute("UPDATE fichas SET viagem_id = %s WHERE uuid = %s",
                           (achou["viagem_id"], uuid_f))
        salvar_anexos(db, uuid_f, ficha.get("anexos"))
    return ocorrencia


def receber_lote(db, fichas, usuario, logger=None):
    aceitas, rejeitadas, ocorrencias = [], [], []
    for ficha in (fichas or [])[:50]:
        uuid_f = (ficha.get("uuid") or "").strip()
        tipo = (ficha.get("tipo") or "").strip()
        cliente_nome = (ficha.get("cliente_nome") or "").strip()[:200]
        if not uuid_f or tipo not in C.TIPOS or not cliente_nome:
            rejeitadas.append({"uuid": uuid_f[:64], "motivo": "campos_obrigatorios"})
            continue
        if not RE_UUID.match(uuid_f):
            rejeitadas.append({"uuid": uuid_f[:64], "motivo": "uuid_invalido"})
            continue
        if db.execute("SELECT 1 FROM fichas WHERE uuid = %s", (uuid_f,)).fetchone():
            aceitas.append(uuid_f)
            continue
        try:
            foto_arq = blob.salvar_foto(uuid_f, ficha.get("foto"))
            ocorrencia = _gravar_ficha(db, ficha, uuid_f, tipo, cliente_nome, usuario, foto_arq)
        except Exception:
            if logger is not None:
                logger.exception("ficha %s recusada", uuid_f)
            rejeitadas.append({"uuid": uuid_f[:64], "motivo": "erro_ao_gravar"})
            continue
        if ocorrencia:
            ocorrencias.append({"uuid": uuid_f, "numero": ocorrencia})
        aceitas.append(uuid_f)
    db.commit()
    return aceitas, rejeitadas, ocorrencias
