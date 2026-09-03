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
