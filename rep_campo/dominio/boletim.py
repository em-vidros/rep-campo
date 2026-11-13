# -*- coding: utf-8 -*-
"""Texto do resumo diario. Puro: recebe numeros, devolve a mensagem.

O resumo existe para tornar a AUSENCIA visivel. Painel so mostra quem
registrou; um dia sem ficha nenhuma nao aparece em lugar nenhum e some. Por
isso o zero vem primeiro e com nome, e nao ha dia sem mensagem.
"""
from .metas import META_DIA_UTIL, situacao

DIAS = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
PAINEL = "https://rep-campo.vercel.app/painel"


def _esc(t):
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _como_chamam(nome, login):
    """O login, nao o primeiro nome: "Tiago Sipiao" e conhecido como Sipiao."""
    if login:
        return login.capitalize()
    partes = (nome or "").strip().split()
    return partes[0] if partes else "?"


def _pct(parte, total):
    return round(100.0 * parte / total) if total else None


def montar(dia, dados):
    """dia = date; dados = saida de repositorios.numeros_do_boletim."""
    reps = dados.get("reps") or []
    fim_de_semana = dia.weekday() >= 5
    linhas = ["<b>REP Campo</b> · %s, %s" % (DIAS[dia.weekday()],
                                             dia.strftime("%d/%m"))]

    linhas.append("")
    linhas.append("<b>HOJE</b>" + ("  (sem meta: fim de semana)" if fim_de_semana else ""))
    total_hoje = 0
    for r in reps:
        nome = _como_chamam(r.get("nome"), r.get("login"))
        hoje = int(r.get("hoje") or 0)
        total_hoje += hoje
        if fim_de_semana:
            linhas.append("%s  %d" % (_esc(nome).ljust(9), hoje))
        else:
            marca = "" if hoje >= META_DIA_UTIL else ("  ⚠️" if hoje == 0 else "")
            linhas.append("%s  %d de %d%s" % (_esc(nome).ljust(9), hoje,
                                              META_DIA_UTIL, marca))
        if hoje == 0 and r.get("ultima_ficha"):
            dias = (dia - r["ultima_ficha"]).days
            if dias >= 1:
                linhas.append("%s  ultima ficha ha %d dia%s"
                              % (" " * 9, dias, "s" if dias > 1 else ""))
        elif hoje == 0 and not r.get("ultima_ficha"):
            linhas.append("%s  nunca registrou uma ficha" % (" " * 9))

    linhas.append("")
    linhas.append("<b>SEMANA</b>")
    soma_sem = soma_cli = soma_gps = soma_passo = 0
    for r in reps:
        nome = _como_chamam(r.get("nome"), r.get("login"))
        sem = int(r.get("semana") or 0)
        s = situacao(int(r.get("hoje") or 0), sem, dia)
        soma_sem += sem
        soma_cli += int(r.get("clientes_semana") or 0)
        soma_gps += int(r.get("com_gps") or 0)
        soma_passo += int(r.get("com_passo") or 0)
        linhas.append("%s  %d de %d  (%d%%)%s"
                      % (_esc(nome).ljust(9), sem, s["meta_semana"],
                         s["pct_semana"] or 0, "" if s["em_dia"] else "  ⚠️"))

    if soma_sem:
        linhas.append("")
        linhas.append("<b>QUALIDADE na semana</b>")
        linhas.append("clientes distintos  %d" % soma_cli)
        linhas.append("com GPS             %d%%" % (_pct(soma_gps, soma_sem) or 0))
        linhas.append("com proximo passo   %d%%" % (_pct(soma_passo, soma_sem) or 0))
        medios = [int(r["relato_medio"]) for r in reps if r.get("relato_medio")]
        if medios:
            linhas.append("relato medio        %d caracteres"
                          % (sum(medios) // len(medios)))

    pend = []
    if dados.get("cadastro_abertas"):
        pend.append("%d correcao de cadastro em aberto" % dados["cadastro_abertas"]
                    if dados["cadastro_abertas"] == 1
                    else "%d correcoes de cadastro em aberto" % dados["cadastro_abertas"])
    if dados.get("buscas_endereco"):
        pend.append("%d busca de endereco com o representante" % dados["buscas_endereco"]
                    if dados["buscas_endereco"] == 1
                    else "%d buscas de endereco com o representante" % dados["buscas_endereco"])
    if pend:
        linhas.append("")
        linhas.append("<b>PENDENCIAS</b>")
        linhas.extend(pend)

    if total_hoje == 0 and not fim_de_semana:
        linhas.append("")
        linhas.append("<i>Nenhuma ficha hoje.</i>")

    linhas.append("")
    linhas.append('<a href="%s">abrir o painel</a>' % PAINEL)
    return "\n".join(linhas)
