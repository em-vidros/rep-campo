# -*- coding: utf-8 -*-
"""
Cria ou atualiza um usuario do REP Campo.
A senha NUNCA fica em texto claro: e pedida no terminal e guardada como hash.

Uso:  python criar_usuario.py <login> "<Nome>" [rep|gestor]
"""
import getpass
import os
import sqlite3
import sys
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get("REP_DB", os.path.join(BASE_DIR, "dados", "rep_campo.db"))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    login = sys.argv[1].strip().lower()
    nome = sys.argv[2].strip()
    papel = (sys.argv[3] if len(sys.argv) > 3 else "rep").strip().lower()
    if papel not in ("rep", "gestor"):
        print("[--] papel deve ser 'rep' ou 'gestor'")
        sys.exit(1)

    senha = os.environ.get("REP_SENHA") or getpass.getpass("Senha para %s: " % login)
    if len(senha) < 8:
        print("[--] senha muito curta (minimo 8 caracteres)")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    # pbkdf2 explicito: o default do Werkzeug 3 e scrypt, que nao existe em
    # builds do Python sem OpenSSL completo (caso do python do macOS).
    senha_hash = generate_password_hash(senha, method="pbkdf2:sha256")

    con.execute("""
        INSERT INTO usuarios (login, nome, senha_hash, papel, base, ativo, criado_em)
        VALUES (?,?,?,?,'ITZ',1,?)
        ON CONFLICT(login) DO UPDATE SET
            nome=excluded.nome, senha_hash=excluded.senha_hash,
            papel=excluded.papel, ativo=1
    """, (login, nome, senha_hash, papel,
          datetime.now(timezone.utc).isoformat(timespec="seconds")))
    con.commit()
    con.close()
    print("[OK] usuario '%s' (%s) pronto." % (login, papel))


if __name__ == "__main__":
    main()
