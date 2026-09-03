# -*- coding: utf-8 -*-
"""
Importa a carteira da base Itz para o app REP Campo.

Fontes:
  - gestao-carteira/dados/carteira_itz_final.csv          (base Itz atual)
  - gestao-carteira/dados/carteira_rap_final.json         (so os municipios que
    migram para a base Itz em 01/09/2026)

Curva ABC calculada por volume 12m (Pareto: A=80% do faturamento, B=+15%, C=resto).

Uso:  python importar_carteira.py [--sem-migracao]
"""
import csv
import json
import os
import psycopg
import sys
from datetime import datetime, timezone

from rep_campo.config import BASE_DIR, carregar_env
from rep_campo.dominio.carteira import curva_abc
from rep_campo.dominio.texto import num_carteira as num, sem_acento
DADOS_CARTEIRA = os.path.abspath(os.path.join(BASE_DIR, "..", "gestao-carteira", "dados"))
CSV_ITZ = os.path.join(DADOS_CARTEIRA, "carteira_itz_final.csv")
JSON_RAP = os.path.join(DADOS_CARTEIRA, "carteira_rap_final.json")

# municipios que migram da base Rap para a base Itz em 01/09/2026
# Decidido por Ricardo em 27/08 e ampliado em 01/09/2026.
# Alto Alegre do Pindare entrou depois: mesmo eixo geografico, migra junto.
# Os clientes migrados entram SEM ROTA definida - a rota e atribuida aos poucos.
MIGRACAO = {
    "santa ines", "ze doca", "bom jardim", "governador newton belo",
    "moncao", "igarape do meio", "pindare mirim", "pio xii",
    "alto alegre do pindare",
}


def ler_itz():
    saida = []
    with open(CSV_ITZ, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            cod = (r.get("ID") or "").strip()
            nome = (r.get("Nome") or "").strip()
            if not cod or not nome:
                continue
            saida.append({
                "codigo": cod, "nome": nome,
                "cidade": (r.get("Cidade") or "").strip(),
                "rota": (r.get("Rota") or "").strip(),
                "tabela": (r.get("Tabela") or "").strip(),
                "vendedor": (r.get("Vendedor") or "").strip(),
                "vol_12m": num(r.get("Vol 12m (R$)")),
                "base": "ITZ", "origem": "carteira_itz_final.csv",
            })
    return saida


def ler_migracao():
    if not os.path.exists(JSON_RAP):
        print("[--] carteira_rap_final.json nao encontrada - migracao ignorada")
        return []
    with open(JSON_RAP, encoding="utf-8") as fh:
        dados = json.load(fh)
    linhas = dados if isinstance(dados, list) else dados.get("clientes", [])
    saida = []
    for r in linhas:
        cidade = str(r.get("Cidade") or r.get("cidade") or "").strip()
        if sem_acento(cidade) not in MIGRACAO:   # match exato: evita pegar
            continue                              # "Alto Alegre do Pindare"
        cod = str(r.get("cli_id") or r.get("ID") or r.get("id") or "").strip()
        nome = str(r.get("Nome") or r.get("nome") or "").strip()
        if not cod or not nome:
            continue
        saida.append({
            "codigo": "RAP-" + cod,  # prefixo: idPedido/idCliente e por base
            "nome": nome, "cidade": cidade,
            "rota": str(r.get("Rota") or ""), "tabela": str(r.get("Tabela") or ""),
            "vendedor": str(r.get("Vendedor") or ""),
            "vol_12m": num(r.get("Vol 12m (R$)") or r.get("vol_12m")),
            "base": "ITZ", "origem": "migracao_01-09-2026",
        })
    return saida


def main():
    incluir_migracao = "--sem-migracao" not in sys.argv
    itz = ler_itz()
    print("[OK] carteira Itz: %d clientes" % len(itz))
    extra = ler_migracao() if incluir_migracao else []
    if extra:
        print("[OK] municipios da migracao (01/09/2026): %d clientes" % len(extra))

    todos = curva_abc(itz + extra)
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")

    carregar_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[--] DATABASE_URL nao definida. Ponha no .env do projeto.")
        sys.exit(1)

    con = psycopg.connect(url)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM clientes")
    antes = cur.fetchone()[0]
    for c in todos:
        cur.execute("""
            INSERT INTO clientes (codigo, nome, cidade, rota, tabela, vendedor,
                                  vol_12m, curva, base, origem, ativo, atualizado_em)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)
            ON CONFLICT(codigo) DO UPDATE SET
                nome=excluded.nome, cidade=excluded.cidade, rota=excluded.rota,
                tabela=excluded.tabela, vendedor=excluded.vendedor,
                vol_12m=excluded.vol_12m, curva=excluded.curva,
                origem=excluded.origem, atualizado_em=excluded.atualizado_em
        """, (c["codigo"], c["nome"], c["cidade"], c["rota"], c["tabela"],
              c["vendedor"], c["vol_12m"], c["curva"], c["base"], c["origem"], agora))
    con.commit()

    cur.execute("SELECT COALESCE(curva,'sem dado'), COUNT(*), ROUND(SUM(vol_12m)::numeric) "
                "FROM clientes GROUP BY curva ORDER BY curva")
    print("\n[resumo por curva]")
    for curva, qtd, vol in cur.fetchall():
        print("  %-9s %4d clientes  R$ %s" % (curva + ":", qtd,
              format(int(vol or 0), ",d").replace(",", ".")))
    cur.execute("SELECT cidade, COUNT(*) FROM clientes WHERE origem='migracao_01-09-2026' "
                "GROUP BY cidade ORDER BY COUNT(*) DESC")
    mig = cur.fetchall()
    if mig:
        print("\n[clientes que entram na base Itz em 01/09/2026]")
        for cidade, qtd in mig:
            print("  %4d  %s" % (qtd, cidade))
    cur.execute("SELECT COUNT(*) FROM clientes")
    print("\n[OK] total na base: %d (antes: %d)" % (cur.fetchone()[0], antes))
    con.close()


if __name__ == "__main__":
    main()
