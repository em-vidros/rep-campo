#!/usr/bin/env python3
"""Liga fichas antigas a viagem pela data, uma vez.

    python scripts/vincular_fichas_viagens.py [--aplicar]

Sem --aplicar so mostra o que faria. O vinculo por data passou a acontecer
sozinho na chegada da ficha; este script existe para o que ja estava gravado.

So toca em ficha com viagem_id NULL: quem ja esta ligada pelo roteiro fica como
esta, porque esse vinculo e mais forte - veio do cliente planejado.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rep_campo.config import carregar_env
from rep_campo.infra.db import conectar

CASAR = """
    SELECT f.uuid, f.cliente_nome, f.municipio, f.usuario_login,
           (f.recebido_em::timestamptz AT TIME ZONE 'America/Sao_Paulo')::date dia,
           v.id vid, v.nome vnome
      FROM fichas f
      JOIN viagens v
        ON (v.criada_por = f.usuario_login OR v.responsavel = f.usuario_login)
       AND v.inicio IS NOT NULL AND v.fim IS NOT NULL
       AND (f.recebido_em::timestamptz AT TIME ZONE 'America/Sao_Paulo')::date
           BETWEEN v.inicio::date AND v.fim::date
     WHERE f.viagem_id IS NULL
     ORDER BY f.recebido_em, v.id DESC
"""


def main():
    aplicar = "--aplicar" in sys.argv
    carregar_env()
    db = conectar()

    # uma ficha pode cair em duas viagens sobrepostas: fica com a mais recente,
    # mesma regra do vinculo automatico
    escolha = {}
    for r in db.execute(CASAR):
        escolha.setdefault(r["uuid"], r)

    if not escolha:
        print("Nenhuma ficha solta dentro de periodo de viagem.")
        return 0

    por_viagem = {}
    for r in escolha.values():
        por_viagem.setdefault((r["vid"], r["vnome"]), []).append(r)

    print("%s %d ficha(s):\n" % ("Ligando" if aplicar else "Ligaria", len(escolha)))
    for (vid, vnome), fichas in sorted(por_viagem.items()):
        print("  viagem %s - %s  (%d ficha(s))" % (vid, vnome, len(fichas)))
        for f in fichas:
            print("     %s  %-32s %s" % (f["dia"], (f["cliente_nome"] or "")[:32],
                                         f["municipio"] or ""))
        print()

    if not aplicar:
        print("Nada foi gravado. Rode de novo com --aplicar para valer.")
        return 0

    for uuid_f, r in escolha.items():
        db.execute("UPDATE fichas SET viagem_id = %s WHERE uuid = %s AND viagem_id IS NULL",
                   (r["vid"], uuid_f))
    db.commit()
    print("[OK] %d ficha(s) ligadas." % len(escolha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
