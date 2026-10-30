# -*- coding: utf-8 -*-
"""Alerta de falha do sync: Telegram direto, n8n como reserva."""
import json
import os
import urllib.request


def avisar(texto):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    webhook = os.environ.get("SYNC_ALERTA_WEBHOOK")
    enviado = False
    if token and chat:
        try:
            corpo = json.dumps({"chat_id": chat, "text": texto,
                                "parse_mode": "HTML"}).encode()
            req = urllib.request.Request(
                "https://api.telegram.org/bot%s/sendMessage" % token,
                data=corpo, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=20).read()
            enviado = True
        except Exception as exc:
            print("[--] Telegram falhou: %s" % str(exc)[:120])
    if not enviado and webhook:
        try:
            req = urllib.request.Request(
                webhook, data=json.dumps({"texto": texto}).encode(),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=20).read()
            enviado = True
        except Exception as exc:
            print("[--] webhook falhou: %s" % str(exc)[:120])
    if not enviado:
        print("[--] SEM CANAL DE ALERTA CONFIGURADO. A mensagem seria:")
        print(texto)
    return enviado


def com_copia_temporaria(para, hoje=None):
    """Acrescenta a copia enquanto ela nao venceu.

    O gerente quis acompanhar os primeiros meses e sair da copia depois. Posto
    como data no proprio sistema em vez de lembrete: no dia seguinte ao prazo
    o nome simplesmente para de entrar, sem ninguem precisar lembrar.
    """
    from datetime import datetime, timezone, timedelta
    from rep_campo.infra import email as mod_email
    copia = mod_email.conf("ALERTA_CADASTRO_COPIA")
    ate = mod_email.conf("ALERTA_CADASTRO_COPIA_ATE")
    if not copia or not ate:
        return para
    if hoje is None:
        # -03: o corte e pela data daqui, nao pela de Londres
        hoje = (datetime.now(timezone.utc) - timedelta(hours=3)).date().isoformat()
    if hoje > ate:
        return para
    extras = [e.strip() for e in copia.replace(";", ",").split(",") if e.strip()]
    return para + [e for e in extras if e not in para]


def _registrar(ocorrencia, para, ok, erro):
    """Guarda no banco se o aviso saiu. Falha de e-mail era invisivel: virava
    um print no log da hospedagem, que eu nao alcanco."""
    from datetime import datetime, timezone
    try:
        from rep_campo.infra.db import conectar
        with conectar() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS alertas_log (
                id SERIAL PRIMARY KEY, quando TEXT, ocorrencia TEXT,
                destino TEXT, ok INTEGER, erro TEXT)""")
            con.execute("""INSERT INTO alertas_log
                (quando, ocorrencia, destino, ok, erro) VALUES (%s,%s,%s,%s,%s)""",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 ocorrencia, ", ".join(para or []), 1 if ok else 0,
                 (erro or "")[:400]))
            con.commit()
    except Exception as exc:
        print("[--] nao consegui registrar o alerta: %s" % str(exc)[:120])


def alertar_cadastro(dados):
    """Avisa quem revisa cadastro que entrou uma correcao para fazer no ERP.

    E uma porta injetada no caso de uso (`receber_lote`): a aplicacao monta os
    dados, aqui vira texto e sai. Devolve True/False e NUNCA levanta - o
    registro da visita ja esta gravado quando isto roda, e perder o alerta nao
    pode custar a ficha do representante.
    """
    from rep_campo.infra import email as mod_email
    try:
        if dados.get("sumiu"):
            assunto = "[REP Campo] %s - CLIENTE NAO ESTA MAIS NO ENDERECO - %s" % (
                dados.get("numero") or "nova ocorrencia",
                dados.get("cliente") or "cliente")
        else:
            assunto = "[REP Campo] %s - %s em %s" % (
                dados.get("numero") or "nova ocorrencia",
                dados.get("o_que_mudou") or "cadastro",
                dados.get("cliente") or "cliente")
        linhas = [
            "NAO RESPONDA ESTE E-MAIL - ele sai de uma caixa automatica e a",
            "resposta nao chega em ninguem. Para avisar que ja corrigiu, use o",
            "WhatsApp do representante, logo abaixo.",
            "",
            "-----------------------------------------------------------------",
            "",
            "Correcao de cadastro aberta pelo representante.",
            "",
            "Ocorrencia: %s" % (dados.get("numero") or "-"),
            "Cliente:    %s (cod %s)" % (dados.get("cliente") or "-",
                                         dados.get("cliente_codigo") or "-"),
            "Municipio:  %s" % (dados.get("municipio") or "-"),
            "O que mudou: %s" % (dados.get("o_que_mudou") or "-"),
            "",
            "AVISE ESTA PESSOA QUANDO A CORRECAO ESTIVER FEITA:",
            "  %s" % (dados.get("aberta_por") or "-"),
            "",
            dados.get("descricao") or "",
            "",
            "Fila completa: https://rep-campo.vercel.app/painel (aba Ocorrencias)",
        ]
        if dados.get("cidade_nova"):
            linhas.insert(7, "ATENCAO: mudou de cidade para %s - muda rota e tabela."
                          % dados["cidade_nova"])
        if dados.get("pendente_com_o_rep"):
            linhas.insert(7, "NAO CORRIJA AINDA: o representante foi procurar o "
                             "endereco novo e vai retornar com o desfecho.")
        from rep_campo.dominio import catalogos as C
        login = (dados.get("login") or "").lower()
        responder = C.EMAIL_POR_LOGIN.get(login)
        fone = C.TELEFONE_POR_LOGIN.get(login)
        contato = linhas.index("  %s" % (dados.get("aberta_por") or "-")) + 1
        if fone:
            bonito = "(%s) %s-%s" % (fone[2:4], fone[4:-4], fone[-4:])
            linhas.insert(contato, "  WhatsApp: %s  ->  https://wa.me/%s" % (bonito, fone))
            contato += 1
        if responder:
            linhas.insert(contato, "  E-mail: %s" % responder)
        para = com_copia_temporaria(
            mod_email.destinatarios("ALERTA_CADASTRO_PARA"))
        mod_email.ULTIMO_ERRO = ""
        ok = mod_email.enviar(assunto, "\n".join(linhas), para,
                              responder_para=responder)
        _registrar(dados.get("numero"), para, ok, mod_email.ULTIMO_ERRO)
        return ok
    except Exception as exc:
        print("[--] alerta de cadastro falhou: %s" % str(exc)[:160])
        return False
