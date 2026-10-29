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


def alertar_cadastro(dados):
    """Avisa quem revisa cadastro que entrou uma correcao para fazer no ERP.

    E uma porta injetada no caso de uso (`receber_lote`): a aplicacao monta os
    dados, aqui vira texto e sai. Devolve True/False e NUNCA levanta - o
    registro da visita ja esta gravado quando isto roda, e perder o alerta nao
    pode custar a ficha do representante.
    """
    from rep_campo.infra import email as mod_email
    try:
        assunto = "[REP Campo] %s - %s em %s" % (
            dados.get("numero") or "nova ocorrencia",
            dados.get("o_que_mudou") or "cadastro",
            dados.get("cliente") or "cliente")
        linhas = [
            "Correcao de cadastro aberta pelo representante.",
            "",
            "Ocorrencia: %s" % (dados.get("numero") or "-"),
            "Cliente:    %s (cod %s)" % (dados.get("cliente") or "-",
                                         dados.get("cliente_codigo") or "-"),
            "Municipio:  %s" % (dados.get("municipio") or "-"),
            "O que mudou: %s" % (dados.get("o_que_mudou") or "-"),
            "Aberta por: %s" % (dados.get("aberta_por") or "-"),
            "",
            dados.get("descricao") or "",
            "",
            "Fila completa: https://rep-campo.vercel.app/painel (aba Ocorrencias)",
        ]
        if dados.get("cidade_nova"):
            linhas.insert(7, "ATENCAO: mudou de cidade para %s - muda rota e tabela."
                          % dados["cidade_nova"])
        return mod_email.enviar(assunto, "\n".join(linhas),
                                mod_email.destinatarios("ALERTA_CADASTRO_PARA"))
    except Exception as exc:
        print("[--] alerta de cadastro falhou: %s" % str(exc)[:160])
        return False
