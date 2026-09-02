#!/usr/bin/env python3
"""Sincroniza a carteira de clientes com o banco do REP Campo.

Roda uma vez por dia, de madrugada. O REP Campo NAO e dono do cadastro: a
carteira vive no painel de clientes, que puxa do ERP. Aqui e so espelho.

    python3 sincronizar_carteira.py               # sincroniza
    python3 sincronizar_carteira.py --simular     # so mostra o que faria

De onde le, nesta ordem:
  1. CARTEIRA_URL  - endpoint do painel devolvendo JSON (preferido)
  2. arquivos locais em ../gestao-carteira/dados   (fallback de partida)

O que faz, alem de inserir:
  - atualiza quem mudou de nome, cidade, rota ou vendedor
  - recalcula a curva ABC sobre o volume 12m
  - INATIVA quem sumiu da fonte, em vez de deixar a base so crescer
  - nunca apaga: cliente inativado guarda historico de visita e ocorrencia
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

import psycopg

import importar_carteira as base   # reaproveita leitura, curva ABC e municipios

SQL_UPSERT = """
    INSERT INTO clientes (codigo, nome, cidade, rota, tabela, vendedor,
                          vol_12m, curva, base, origem, ativo, atualizado_em)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)
    ON CONFLICT(codigo) DO UPDATE SET
        nome=excluded.nome, cidade=excluded.cidade, rota=excluded.rota,
        tabela=excluded.tabela, vendedor=excluded.vendedor,
        vol_12m=excluded.vol_12m, curva=excluded.curva,
        origem=excluded.origem, ativo=1, atualizado_em=excluded.atualizado_em
"""


def conectar():
    base.carregar_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[--] DATABASE_URL nao definida. Ponha no .env do projeto.")
        sys.exit(1)
    return psycopg.connect(url)


def gravar_cliente(cur, c, agora):
    cur.execute(SQL_UPSERT, (c["codigo"], c["nome"], c["cidade"], c["rota"],
                             c["tabela"], c["vendedor"], c["vol_12m"], c["curva"],
                             c["base"], c["origem"], agora))

CARTEIRA_URL = os.environ.get("CARTEIRA_URL")
CARTEIRA_TOKEN = os.environ.get("CARTEIRA_TOKEN")


def _agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ler_do_painel(url):
    """Le a carteira do painel de clientes. Espera JSON com uma lista."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if CARTEIRA_TOKEN:
        req.add_header("Authorization", "Bearer " + CARTEIRA_TOKEN)
    with urllib.request.urlopen(req, timeout=90) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    linhas = dados if isinstance(dados, list) else dados.get("clientes", [])
    saida = []
    for r in linhas:
        cod = str(r.get("codigo") or r.get("ID") or r.get("cli_id") or "").strip()
        nome = str(r.get("nome") or r.get("Nome") or "").strip()
        if not cod or not nome:
            continue
        saida.append({
            "codigo": cod, "nome": nome,
            "cidade": str(r.get("cidade") or r.get("Cidade") or "").strip(),
            "rota": str(r.get("rota") or r.get("Rota") or "").strip(),
            "tabela": str(r.get("tabela") or r.get("Tabela") or "").strip(),
            "vendedor": str(r.get("vendedor") or r.get("Vendedor") or "").strip(),
            "vol_12m": base.num(r.get("vol_12m") or r.get("Vol 12m (R$)")),
            "base": "ITZ", "origem": "painel_de_clientes",
        })
    return saida


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--simular", action="store_true",
                   help="mostra o que faria, sem escrever no banco")
    args = p.parse_args()

    if CARTEIRA_URL:
        clientes = ler_do_painel(CARTEIRA_URL)
        fonte = "painel de clientes (%s)" % CARTEIRA_URL
    else:
        clientes = base.ler_itz() + base.ler_migracao()
        fonte = "arquivos locais da carteira"

    if not clientes:
        print("[--] a fonte devolveu ZERO cliente. Abortando para nao inativar a base.")
        sys.exit(1)

    clientes = base.curva_abc(clientes)
    print("[fonte] %s" % fonte)
    print("[fonte] %d cliente(s)" % len(clientes))

    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT codigo, nome, cidade, rota, vendedor, vol_12m, curva, ativo "
                "FROM clientes")
    atuais = {r[0]: r for r in cur.fetchall()}

    novos = alterados = reativados = 0
    agora = _agora()
    for c in clientes:
        a = atuais.get(c["codigo"])
        if a is None:
            novos += 1
        else:
            mudou = (a[1] != c["nome"] or (a[2] or "") != (c["cidade"] or "")
                     or (a[3] or "") != (c["rota"] or "")
                     or (a[4] or "") != (c["vendedor"] or "")
                     or float(a[5] or 0) != float(c["vol_12m"] or 0)
                     or (a[6] or "") != (c["curva"] or ""))
            if mudou:
                alterados += 1
            if not a[7]:
                reativados += 1
        if not args.simular:
            gravar_cliente(cur, c, agora)

    vistos = {c["codigo"] for c in clientes}
    sumiram = [cod for cod, a in atuais.items() if cod not in vistos and a[7]]
    if sumiram and not args.simular:
        cur.execute("UPDATE clientes SET ativo = 0, atualizado_em = %s "
                    "WHERE codigo = ANY(%s)", (agora, sumiram))

    print()
    print("  novos ............ %d" % novos)
    print("  atualizados ...... %d" % alterados)
    print("  reativados ....... %d" % reativados)
    print("  inativados ....... %d  (sumiram da fonte; historico preservado)" % len(sumiram))
    if args.simular:
        print()
        print("[simulacao] nada foi gravado.")
        con.rollback()
    else:
        con.commit()
        cur.execute("SELECT COUNT(*) FROM clientes WHERE ativo = 1")
        print()
        print("[OK] %d cliente(s) ativo(s) no banco" % cur.fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()
