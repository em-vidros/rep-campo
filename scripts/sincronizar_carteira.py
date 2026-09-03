#!/usr/bin/env python3
"""Sincroniza a carteira de clientes com o banco do REP Campo.

Roda uma vez por dia, de madrugada. O REP Campo NAO e dono do cadastro: a
carteira vive no painel de clientes, que puxa do ERP. Aqui e so espelho.

    python3 scripts/sincronizar_carteira.py               # sincroniza
    python3 scripts/sincronizar_carteira.py --simular     # so mostra o que faria

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
import time
import urllib.request
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

import psycopg

import importar_carteira as base   # reaproveita leitura de CSV/JSON legada
from rep_campo.aplicacao.carteira import corrigir_pela_planilha, diff
from rep_campo.infra.alertas import avisar
from rep_campo.infra.db import agora as _agora

SQL_UPSERT = """
    INSERT INTO clientes (codigo, nome, cidade, rota, tabela, vendedor,
                          vol_12m, curva, base, origem, ativo, atualizado_em,
                          ultima_compra, pedidos_12m)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s)
    ON CONFLICT(codigo) DO UPDATE SET
        nome=excluded.nome, cidade=excluded.cidade, rota=excluded.rota,
        tabela=excluded.tabela, vendedor=excluded.vendedor,
        vol_12m=excluded.vol_12m, curva=excluded.curva,
        origem=excluded.origem, ativo=1, atualizado_em=excluded.atualizado_em,
        ultima_compra=COALESCE(excluded.ultima_compra, clientes.ultima_compra),
        pedidos_12m=COALESCE(excluded.pedidos_12m, clientes.pedidos_12m)
"""


def conectar():
    base.carregar_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[--] DATABASE_URL nao definida. Ponha no .env do projeto.")
        sys.exit(1)
    return psycopg.connect(url)


def gravar_cliente(cur, c, agora):
    def inteiro(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    cur.execute(SQL_UPSERT, (c["codigo"], c["nome"], c["cidade"], c["rota"],
                             c["tabela"], c["vendedor"], c["vol_12m"], c["curva"],
                             c["base"], c["origem"], agora,
                             c.get("ultima_compra") or None,
                             inteiro(c.get("pedidos_12m"))))

CARTEIRA_URL = os.environ.get("CARTEIRA_URL")
CARTEIRA_TOKEN = os.environ.get("CARTEIRA_TOKEN")

# Falha de rede e banco costuma passar sozinha. So avisa quem tem que agir
# se nao passar - alerta que toca todo dia vira ruido e para de ser lido.
TENTATIVAS = 4
ESPERA = [30, 120, 300]          # segundos entre uma tentativa e a seguinte


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
            # o que diz se o cliente parou de comprar - o sinal mais forte
            # para priorizar visita. Aceita os nomes mais provaveis da fonte.
            "ultima_compra": (r.get("ultima_compra") or r.get("Ultima Compra")
                              or r.get("ultima_venda") or r.get("dt_ultima_compra") or None),
            "pedidos_12m": r.get("pedidos_12m") or r.get("Pedidos ERP") or None,
            "base": "ITZ", "origem": "painel_de_clientes",
        })
    return saida


def sincronizar(args):
    """Uma tentativa. Levanta excecao se algo der errado - quem chama repete."""

    if CARTEIRA_URL:
        clientes = ler_do_painel(CARTEIRA_URL)
        fonte = "painel de clientes (%s)" % CARTEIRA_URL
    else:
        clientes = base.ler_itz() + base.ler_migracao()
        fonte = "arquivos locais da carteira"

    if not clientes:
        print("[--] a fonte devolveu ZERO cliente. Abortando para nao inativar a base.")
        sys.exit(1)

    clientes, mapa_info = corrigir_pela_planilha(clientes)
    corrigidas, sem_mapa, da_raposa = (mapa_info["corrigidas"], mapa_info["sem_mapa"],
                                       mapa_info["da_raposa"])
    print("[fonte] %s" % fonte)
    print("[fonte] %d cliente(s)" % len(clientes))
    if corrigidas:
        print()
        print("[rota] corrigidas pela planilha oficial de 28/08/2026:")
        for (de, para), n in sorted(corrigidas.items(), key=lambda x: -x[1]):
            print("   %4d cliente(s)  %-18s -> %s" % (n, de[:18], para))
    if da_raposa:
        print()
        print("[rota] %d cidade(s) que a planilha atribui a base RAPOSA:" % len(da_raposa))
        for c in sorted(da_raposa)[:8]:
            print("   %s" % c)
        if len(da_raposa) > 8:
            print("   ... e mais %d" % (len(da_raposa) - 8))
    if sem_mapa:
        print()
        print("[rota] %d cidade(s) que nao estao na planilha (rota da carteira mantida):"
              % len(sem_mapa))
        for c in sorted(sem_mapa)[:12]:
            print("   %s" % c)
        if len(sem_mapa) > 12:
            print("   ... e mais %d" % (len(sem_mapa) - 12))

    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT codigo, nome, cidade, rota, vendedor, vol_12m, curva, ativo "
                "FROM clientes")
    atuais = {r[0]: r for r in cur.fetchall()}

    novos, alterados, reativados, sumiram = diff(atuais, clientes)
    agora = _agora()
    if not args.simular:
        for c in clientes:
            gravar_cliente(cur, c, agora)
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--simular", action="store_true",
                   help="mostra o que faria, sem escrever no banco")
    p.add_argument("--sem-retry", action="store_true",
                   help="falha na primeira, sem repetir (para teste)")
    args = p.parse_args()

    tentativas = 1 if (args.simular or args.sem_retry) else TENTATIVAS
    erros = []
    for n in range(1, tentativas + 1):
        try:
            sincronizar(args)
            if n > 1:
                print()
                print("[OK] deu certo na tentativa %d de %d." % (n, tentativas))
            return 0
        except SystemExit:
            raise
        except Exception as exc:
            erros.append("tentativa %d: %s" % (n, exc))
            print("[--] tentativa %d de %d falhou: %s" % (n, tentativas, str(exc)[:160]))
            if n < tentativas:
                espera = ESPERA[min(n - 1, len(ESPERA) - 1)]
                print("     esperando %ds antes de tentar de novo..." % espera)
                time.sleep(espera)

    # so chega aqui depois de esgotar as tentativas
    texto = ("<b>REP Campo — sincronização da carteira falhou</b>\n"
             "%s\n\n%d tentativas, todas sem sucesso:\n%s\n\n"
             "A base de clientes está congelada até isso ser resolvido — o "
             "representante continua vendo a carteira da última sincronização."
             % (datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M"),
                tentativas, "\n".join("• " + e[:180] for e in erros)))
    avisar(texto)
    return 1


if __name__ == "__main__":
    sys.exit(main())
