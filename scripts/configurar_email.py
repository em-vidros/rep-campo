# -*- coding: utf-8 -*-
"""Grava a configuracao de e-mail na tabela config_email.

Alternativa a variavel de ambiente, para quem nao tem acesso ao painel da
hospedagem. A DATABASE_URL ja mora la, entao isto nao abre porta nova.

Uso:  python scripts/configurar_email.py CHAVE=valor [CHAVE=valor ...]
      python scripts/configurar_email.py --listar     (nao mostra a senha)
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg

from rep_campo.config import carregar_env

SEGREDOS = ("SMTP_SENHA", "RESEND_API_KEY")
ACEITAS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USUARIO", "SMTP_SENHA",
           "EMAIL_REMETENTE", "ALERTA_CADASTRO_PARA", "RESEND_API_KEY",
           "ALERTA_CADASTRO_COPIA", "ALERTA_CADASTRO_COPIA_ATE")


def mascarar(chave, valor):
    return "******** (%d caracteres)" % len(valor) if chave in SEGREDOS else valor


def main():
    carregar_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[--] DATABASE_URL nao definida.")
        sys.exit(1)

    with psycopg.connect(url, autocommit=True) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS config_email (
            chave TEXT PRIMARY KEY, valor TEXT NOT NULL, atualizado_em TEXT)""")

        if "--listar" in sys.argv or len(sys.argv) < 2:
            print("[config_email]")
            for r in con.execute("SELECT chave, valor, atualizado_em "
                                 "FROM config_email ORDER BY chave"):
                print("  %-22s %s" % (r[0], mascarar(r[0], r[1])))
            return

        agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for par in sys.argv[1:]:
            if "=" not in par:
                continue
            chave, valor = par.split("=", 1)
            chave = chave.strip().upper()
            if chave not in ACEITAS:
                print("[--] chave ignorada (nao reconhecida): %s" % chave)
                continue
            con.execute("""INSERT INTO config_email (chave, valor, atualizado_em)
                VALUES (%s,%s,%s) ON CONFLICT (chave) DO UPDATE SET
                valor = excluded.valor, atualizado_em = excluded.atualizado_em""",
                (chave, valor.strip(), agora))
            print("[OK] %-22s %s" % (chave, mascarar(chave, valor.strip())))


if __name__ == "__main__":
    main()
