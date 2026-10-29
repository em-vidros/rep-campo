# -*- coding: utf-8 -*-
"""Envio de e-mail. Dois caminhos, escolhidos pelo que estiver configurado.

Por que dois: a Vercel e serverless. Chamada HTTPS para um provedor sempre
passa; SMTP depende do servidor de e-mail aceitar conexao de fora e da porta
nao estar bloqueada. Quem tiver chave de provedor usa ela; quem so tem o
servidor da empresa usa SMTP.

Nada aqui levanta excecao: alerta que falha nao pode derrubar o registro da
visita que o representante fez em campo.
"""
import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage

TEMPO_LIMITE = 8


def destinatarios(variavel):
    """Lista separada por virgula na variavel de ambiente."""
    bruto = os.environ.get(variavel) or ""
    return [e.strip() for e in bruto.replace(";", ",").split(",") if e.strip()]


def _por_resend(assunto, corpo, para, remetente):
    chave = os.environ.get("RESEND_API_KEY")
    if not chave:
        return False
    try:
        dados = json.dumps({"from": remetente, "to": para,
                            "subject": assunto, "text": corpo}).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails", data=dados,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer %s" % chave})
        urllib.request.urlopen(req, timeout=TEMPO_LIMITE).read()
        return True
    except Exception as exc:
        print("[--] Resend falhou: %s" % str(exc)[:160])
        return False


def _por_smtp(assunto, corpo, para, remetente):
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    porta = int(os.environ.get("SMTP_PORT") or 587)
    usuario = os.environ.get("SMTP_USUARIO") or ""
    senha = os.environ.get("SMTP_SENHA") or ""
    try:
        msg = EmailMessage()
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = ", ".join(para)
        msg.set_content(corpo)
        with smtplib.SMTP(host, porta, timeout=TEMPO_LIMITE) as s:
            s.starttls()
            if usuario:
                s.login(usuario, senha)
            s.send_message(msg)
        return True
    except Exception as exc:
        print("[--] SMTP falhou: %s" % str(exc)[:160])
        return False


def enviar(assunto, corpo, para):
    """Devolve True se saiu por algum caminho. Nunca levanta.

    Quando nao sai, o texto vai para o log: o aviso nao pode simplesmente
    sumir so porque o canal nao estava configurado ou falhou.
    """
    remetente = os.environ.get("EMAIL_REMETENTE") or "REP Campo <onboarding@resend.dev>"
    if para and (_por_resend(assunto, corpo, para, remetente)
                 or _por_smtp(assunto, corpo, para, remetente)):
        return True
    motivo = "sem destinatario" if not para else "nenhum canal entregou"
    print("[--] e-mail nao enviado (%s). O aviso seria:" % motivo)
    print("    Para: %s" % (", ".join(para) or "(ninguem)"))
    print("    %s" % assunto)
    print(corpo)
    return False
