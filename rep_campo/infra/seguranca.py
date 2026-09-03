# -*- coding: utf-8 -*-
"""Hash de senha e freio de força bruta (contado no banco, não na memória)."""
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from rep_campo.dominio.catalogos import MAX_TENTATIVAS_LOGIN

JANELA_BLOQUEIO = timedelta(minutes=15)


def hash_senha(senha):
    return generate_password_hash(senha, method="pbkdf2:sha256")


def confere_senha(senha_hash, senha):
    return check_password_hash(senha_hash, senha)


def bloqueado(db, origem):
    row = db.execute(
        "SELECT falhas, ultima FROM tentativas_login WHERE origem = %s",
        (origem,)).fetchone()
    if not row:
        return False
    if datetime.now(timezone.utc) - row["ultima"] > JANELA_BLOQUEIO:
        return False
    return row["falhas"] >= MAX_TENTATIVAS_LOGIN


def registrar_falha(db, origem):
    agora = datetime.now(timezone.utc)
    db.execute(
        "INSERT INTO tentativas_login (origem, falhas, ultima) VALUES (%s, 1, %s) "
        "ON CONFLICT (origem) DO UPDATE SET "
        "  falhas = CASE WHEN tentativas_login.ultima < %s THEN 1 "
        "                ELSE tentativas_login.falhas + 1 END, "
        "  ultima = EXCLUDED.ultima",
        (origem, agora, agora - JANELA_BLOQUEIO))
    db.commit()


def limpar_falhas(db, origem):
    db.execute("DELETE FROM tentativas_login WHERE origem = %s", (origem,))
    db.commit()
