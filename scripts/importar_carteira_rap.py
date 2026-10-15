# -*- coding: utf-8 -*-
"""
Importa a carteira ATIVA da base Raposa para o app REP Campo.

"Ativo" segue a definicao do painel de gestao de carteiras: vol_12m > 0
(cliente que comprou alguma coisa nos ultimos 12 meses).

Fonte: um JSON com a lista de clientes Raposa, no formato que o painel exporta
  [{"cod": "...", "nome": "...", "cidade": "...", "rota": "...",
    "vendedor": "...", "vol_12m": 0.0, "segmento": "...", "ult": "dd/mm/aaaa"}, ...]

Os municipios que migraram para a base Imperatriz em 01/09/2026 sao EXCLUIDOS:
eles ja estao na carteira do Sipiao e nao podem aparecer duas vezes.

Uso:  python scripts/importar_carteira_rap.py <arquivo.json>            (simulacao)
      python scripts/importar_carteira_rap.py <arquivo.json> --aplicar  (grava)
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg

from rep_campo.config import carregar_env
from rep_campo.dominio.carteira import curva_abc
from rep_campo.dominio.texto import sem_acento

# mesmos municipios do importar_carteira.py: desde 01/09/2026 sao base Imperatriz
JA_SAO_IMPERATRIZ = {
    "santa ines", "ze doca", "bom jardim", "governador newton belo",
    "moncao", "igarape do meio", "pindare mirim", "pio xii",
    "alto alegre do pindare",
}


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v or "").replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(t)
    except ValueError:
        return 0.0


def ler(caminho):
    with open(caminho, encoding="utf-8") as fh:
        dados = json.load(fh)
    linhas = dados if isinstance(dados, list) else dados.get("clientes", [])
    ativos, sem_volume, migrados = [], 0, 0
    for r in linhas:
        cod = str(r.get("cod") or r.get("cli_id") or r.get("ID") or "").strip()
        nome = str(r.get("nome") or r.get("Nome") or "").strip()
        if not cod or not nome:
            continue
        vol = num(r.get("vol_12m") or r.get("Vol 12m (R$)"))
        if vol <= 0:                      # o painel so chama de ativo quem comprou
            sem_volume += 1
            continue
        cidade = str(r.get("cidade") or r.get("Cidade") or "").strip()
        if sem_acento(cidade) in JA_SAO_IMPERATRIZ:
            migrados += 1
            continue
        ativos.append({
            "codigo": "RAP-" + cod,       # prefixo: o id do cliente e por base
            "nome": nome, "cidade": cidade,
            "rota": str(r.get("rota") or r.get("Rota") or "").strip(),
            "tabela": str(r.get("tabela") or r.get("Tabela") or "").strip(),
            "vendedor": str(r.get("vendedor") or r.get("Vendedor") or "").strip(),
            "vol_12m": vol,
            "base": "RAP", "origem": "painel_carteira_ativos",
        })
    return ativos, sem_volume, migrados


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    caminho = sys.argv[1]
    aplicar = "--aplicar" in sys.argv
    if not os.path.exists(caminho):
        print("[--] arquivo nao encontrado: %s" % caminho)
        sys.exit(1)

    ativos, sem_volume, migrados = ler(caminho)
    print("[OK] ativos (vol_12m > 0): %d" % len(ativos))
    print("     fora por nao ter compra em 12m: %d" % sem_volume)
    print("     fora por ja serem base Imperatriz: %d" % migrados)
    if not ativos:
        print("[--] nada a importar")
        sys.exit(1)

    todos = curva_abc(ativos)
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")

    carregar_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[--] DATABASE_URL nao definida. Ponha no .env do projeto.")
        sys.exit(1)

    con = psycopg.connect(url)
    cur = con.cursor()
    cur.execute("SELECT codigo, base FROM clientes")
    existentes = {c: b for c, b in cur.fetchall()}

    # protecao: nunca reescrever um cliente que hoje pertence a outra base
    conflito = [c["codigo"] for c in todos
                if existentes.get(c["codigo"], "RAP") != "RAP"]
    if conflito:
        print("[!!] %d codigos ja existem em outra base e serao PULADOS:" % len(conflito))
        for c in conflito[:10]:
            print("     %s (base %s)" % (c, existentes[c]))
    todos = [c for c in todos if c["codigo"] not in set(conflito)]

    novos = sum(1 for c in todos if c["codigo"] not in existentes)
    print("\n[plano] %d clientes RAP: %d novos, %d atualizados"
          % (len(todos), novos, len(todos) - novos))
    if not aplicar:
        print("\n[simulacao] nada foi gravado. Rode de novo com --aplicar.")
        con.close()
        return

    for c in todos:
        cur.execute("""
            INSERT INTO clientes (codigo, nome, cidade, rota, tabela, vendedor,
                                  vol_12m, curva, base, origem, ativo, atualizado_em)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)
            ON CONFLICT(codigo) DO UPDATE SET
                nome=excluded.nome, cidade=excluded.cidade, rota=excluded.rota,
                tabela=excluded.tabela, vendedor=excluded.vendedor,
                vol_12m=excluded.vol_12m, curva=excluded.curva, base=excluded.base,
                origem=excluded.origem, ativo=1, atualizado_em=excluded.atualizado_em
        """, (c["codigo"], c["nome"], c["cidade"], c["rota"], c["tabela"],
              c["vendedor"], c["vol_12m"], c["curva"], c["base"], c["origem"], agora))
    con.commit()

    cur.execute("SELECT base, COUNT(*) FROM clientes GROUP BY base ORDER BY base")
    print("\n[resultado por base]")
    for base, qtd in cur.fetchall():
        print("  %-5s %5d" % (base, qtd))
    con.close()


if __name__ == "__main__":
    main()
