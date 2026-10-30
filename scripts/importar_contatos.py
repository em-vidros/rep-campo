# -*- coding: utf-8 -*-
"""Traz endereco e telefone do extrato dos ERPs para a tabela de clientes.

Serve para o representante ver na ficha o que esta cadastrado hoje antes de
pedir a correcao - sem isso ele escreve "mudou o endereco" sem saber qual
endereco o sistema tem.

Nao e fonte de verdade: e uma COPIA do que o ERP tinha na data do extrato.
A correcao continua sendo feita no ERP.

Uso:  python scripts/importar_contatos.py            (simulacao)
      python scripts/importar_contatos.py --aplicar
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg

from rep_campo.config import carregar_env

DADOS = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-rbrumcorrea@gmail.com/Meu Drive/RicardoOS"
    "/em-vidros-raposa/gestao-carteira/dados")
FONTES = [("clientes_rap_completo.json", "RAP-"), ("clientes_itz_completo.json", "")]


def limpo(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def telefone_util(v):
    return limpo(v) if len(re.sub(r"\D", "", str(v or ""))) >= 10 else ""


def endereco_util(v):
    """'  - Raposa/MA' e so a cidade: nao ajuda ninguem a achar o cliente."""
    t = limpo(v)
    antes = t.split(" - ")[0].strip()
    return t if len(antes) >= 5 else ""


def ler():
    saida = {}
    for arquivo, prefixo in FONTES:
        caminho = os.path.join(DADOS, arquivo)
        if not os.path.exists(caminho):
            print("[--] nao encontrado, pulando: %s" % arquivo)
            continue
        with open(caminho, encoding="utf-8") as fh:
            linhas = json.load(fh)
        n = 0
        for r in linhas:
            cod = limpo(r.get("webglass_id") or r.get("cli_id") or r.get("ID"))
            if not cod:
                continue
            tel = telefone_util(r.get("telefone")) or telefone_util(r.get("celular"))
            end = endereco_util(r.get("endereco"))
            if not tel and not end:
                continue
            saida[prefixo + cod] = {"endereco": end or None, "telefone": tel or None}
            n += 1
        print("[OK] %-28s %d clientes com endereco ou telefone" % (arquivo, n))
    return saida


def main():
    aplicar = "--aplicar" in sys.argv
    dados = ler()
    if not dados:
        print("[--] nada para importar")
        sys.exit(1)

    carregar_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[--] DATABASE_URL nao definida.")
        sys.exit(1)

    con = psycopg.connect(url)
    cur = con.cursor()
    cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS endereco TEXT")
    cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS telefone TEXT")
    con.commit()

    cur.execute("SELECT codigo FROM clientes")
    na_carteira = {r[0] for r in cur.fetchall()}
    casam = [c for c in dados if c in na_carteira]
    com_end = sum(1 for c in casam if dados[c]["endereco"])
    com_tel = sum(1 for c in casam if dados[c]["telefone"])
    print("\n[plano] %d dos %d clientes da carteira recebem dado"
          % (len(casam), len(na_carteira)))
    print("        %d com endereco, %d com telefone" % (com_end, com_tel))
    print("        %d do extrato nao estao na carteira (ignorados)"
          % (len(dados) - len(casam)))
    if not aplicar:
        print("\n[simulacao] nada gravado. Rode de novo com --aplicar.")
        con.close()
        return

    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # um UPDATE por cliente seriam ~5 mil idas ao banco: lento demais num banco
    # remoto. Uma tabela temporaria resolve em duas.
    cur.execute("CREATE TEMP TABLE _contatos "
                "(codigo TEXT PRIMARY KEY, endereco TEXT, telefone TEXT)")
    with cur.copy("COPY _contatos (codigo, endereco, telefone) FROM STDIN") as cp:
        for cod in casam:
            cp.write_row((cod, dados[cod]["endereco"], dados[cod]["telefone"]))
    cur.execute("""UPDATE clientes c SET endereco = t.endereco,
                          telefone = t.telefone, atualizado_em = %s
                     FROM _contatos t WHERE t.codigo = c.codigo""", (agora,))
    print("[OK] %d linhas atualizadas" % cur.rowcount)
    con.commit()
    cur.execute("SELECT base, COUNT(*) FILTER (WHERE endereco IS NOT NULL), "
                "COUNT(*) FILTER (WHERE telefone IS NOT NULL), COUNT(*) "
                "FROM clientes GROUP BY base ORDER BY base")
    print("\n[resultado]  base   com endereco   com telefone   total")
    for base, e, t, n in cur.fetchall():
        print("             %-5s  %12d   %12d   %5d" % (base, e, t, n))
    con.close()


if __name__ == "__main__":
    main()
