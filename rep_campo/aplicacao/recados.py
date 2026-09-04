# -*- coding: utf-8 -*-
"""Casos de uso do recado: mandar, ler, concluir, cancelar."""
from rep_campo.dominio import recados as D
from rep_campo.infra import repositorios as repo
from rep_campo.infra.relogio import agora


def mandar(db, de_login, de_nome, para_login, texto, cliente_codigo=None,
           cliente_nome=None, prazo=None):
    limpo = D.texto_valido(texto)
    if not limpo:
        return None, "texto_curto"
    if not (para_login or "").strip():
        return None, "sem_destinatario"
    rid = repo.criar_recado(db, agora(), de_login, de_nome, para_login.strip(),
                            limpo, cliente_codigo, cliente_nome, prazo)
    db.commit()
    return rid, None


def para_o_app(db, login):
    """Bloco que vai no bootstrap: separado em geral e missao por cliente.

    O `por_cliente` chega como dicionario codigo -> lista, para o app achar a
    missao no momento em que o representante escolhe o cliente, sem varrer
    lista nenhuma.
    """
    linhas = repo.recados_pendentes(db, login, D.PENDENTES)
    gerais, por_cliente = [], {}
    for r in linhas:
        if r["cliente_codigo"]:
            por_cliente.setdefault(r["cliente_codigo"], []).append(r)
        else:
            gerais.append(r)
    return {"gerais": gerais, "por_cliente": por_cliente,
            "nao_lidos": sum(1 for r in linhas if r["status"] == D.ABERTO)}


def marcar_lidos(db, login, ids):
    n = repo.marcar_recados_lidos(db, login, [i for i in ids if isinstance(i, int)], agora())
    db.commit()
    return n


def concluir(db, login, rid, resposta=None, ficha_uuid=None):
    resp = (resposta or "").strip()[:D.MAX_RESPOSTA] or None
    n = repo.concluir_recado(db, rid, login, resp, ficha_uuid, agora(), D.PENDENTES)
    db.commit()
    return n


def cancelar(db, rid):
    n = repo.cancelar_recado(db, rid, D.PENDENTES)
    db.commit()
    return n


def listar(db, para_login=None, status=None):
    return repo.listar_recados(db, para_login=para_login, status=status)
