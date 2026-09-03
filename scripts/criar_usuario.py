# -*- coding: utf-8 -*-
"""
Cria ou atualiza um usuario do REP Campo.
A senha NUNCA fica em texto claro: e pedida no terminal e guardada como hash.

Uso:  python scripts/criar_usuario.py <login> "<Nome>" [rep|gestor]
"""
import getpass
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg
from werkzeug.security import generate_password_hash

from rep_campo.config import carregar_env


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

    carregar_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[--] DATABASE_URL nao definida. Ponha no .env do projeto.")
        sys.exit(1)

    # pbkdf2 explicito: o default do Werkzeug 3 e scrypt, que nao existe em
    # builds do Python sem OpenSSL completo (caso do python do macOS).
    senha_hash = generate_password_hash(senha, method="pbkdf2:sha256")

    with psycopg.connect(url, autocommit=True) as con:
        con.execute("""
            INSERT INTO usuarios (login, nome, senha_hash, papel, base, ativo, criado_em)
            VALUES (%s,%s,%s,%s,'ITZ',1,%s)
            ON CONFLICT(login) DO UPDATE SET
                nome=excluded.nome, senha_hash=excluded.senha_hash,
                papel=excluded.papel, ativo=1
        """, (login, nome, senha_hash, papel,
              datetime.now(timezone.utc).isoformat(timespec="seconds")))
    print("[OK] usuario '%s' (%s) pronto." % (login, papel))


if __name__ == "__main__":
    main()
