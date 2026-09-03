# -*- coding: utf-8 -*-
"""Transições de status da ocorrência, espelhadas na ficha de origem."""
from rep_campo.dominio.ocorrencias import numero_valido, status_valido
from rep_campo.infra import db as dbmod


def atualizar(db, numero, dados, login):
    if not numero_valido(numero):
        return "numero_invalido", None
    if not db.execute("SELECT 1 FROM ocorrencias WHERE numero = %s", (numero,)).fetchone():
        return "nao_encontrada", None
    if "status" in dados:
        if not status_valido(dados["status"]):
            return "status_invalido", None
        if dados["status"] == "resolvida":
            db.execute("UPDATE ocorrencias SET status = 'resolvida', resolvida_em = %s, "
                       "resolvida_por = %s, resolucao = COALESCE(%s, resolucao) "
                       "WHERE numero = %s",
                       (dbmod.agora(), login,
                        (dados.get("resolucao") or "").strip()[:1000] or None, numero))
            db.execute("UPDATE fichas SET ocorrencia_status = 'resolvida', "
                       "ocorrencia_fechada_em = %s WHERE ocorrencia_num = %s",
                       (dbmod.agora(), numero))
        else:
            db.execute("UPDATE ocorrencias SET status = %s, resolvida_em = NULL, "
                       "resolvida_por = NULL WHERE numero = %s", (dados["status"], numero))
            db.execute("UPDATE fichas SET ocorrencia_status = %s, "
                       "ocorrencia_fechada_em = NULL WHERE ocorrencia_num = %s",
                       (dados["status"], numero))
    if "responsavel" in dados:
        db.execute("UPDATE ocorrencias SET responsavel = %s WHERE numero = %s",
                   ((dados["responsavel"] or "").strip()[:120] or None, numero))
    db.commit()
    return None, numero
