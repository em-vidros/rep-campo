# -*- coding: utf-8 -*-
"""Núcleo da sincronização de carteira, sem CLI nem alerta."""
import rotas_oficiais

from rep_campo.dominio.carteira import curva_abc


def corrigir_pela_planilha(clientes):
    corrigidas, sem_mapa, da_raposa = {}, set(), set()
    for c in clientes:
        cidade = c.get("cidade")
        if rotas_oficiais._chave(c.get("rota")) in ("sem rota", ""):
            c["rota"] = ""
        if not rotas_oficiais.e_da_base_itz(cidade):
            if cidade:
                (da_raposa if rotas_oficiais.e_da_raposa(cidade) else sem_mapa).add(cidade)
            continue
        oficial = rotas_oficiais.rota_da_cidade(cidade) or ""
        atual = (c.get("rota") or "").strip()
        if rotas_oficiais._chave(atual) != rotas_oficiais._chave(oficial):
            de = atual or "(sem rota)"
            para = oficial or "(sem rota)"
            corrigidas[(de, para)] = corrigidas.get((de, para), 0) + 1
            c["rota"] = oficial
        c["tabela"] = rotas_oficiais.tabela_da_cidade(cidade) or c.get("tabela")
    return curva_abc(clientes), {"corrigidas": corrigidas, "sem_mapa": sem_mapa,
                                 "da_raposa": da_raposa}


def diff(atuais, clientes):
    novos = alterados = reativados = 0
    for c in clientes:
        a = atuais.get(c["codigo"])
        if a is None:
            novos += 1
            continue
        mudou = (a[1] != c["nome"] or (a[2] or "") != (c["cidade"] or "")
                 or (a[3] or "") != (c["rota"] or "")
                 or (a[4] or "") != (c["vendedor"] or "")
                 or float(a[5] or 0) != float(c["vol_12m"] or 0)
                 or (a[6] or "") != (c["curva"] or ""))
        if mudou:
            alterados += 1
        if not a[7]:
            reativados += 1
    vistos = {c["codigo"] for c in clientes}
    sumiram = [cod for cod, a in atuais.items() if cod not in vistos and a[7]]
    return novos, alterados, reativados, sumiram
