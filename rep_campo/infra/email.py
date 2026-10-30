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

# Lido uma vez por instancia. A Vercel recria o processo a cada deploy, entao
# mudar a configuracao no banco vale a partir do proximo deploy ou da proxima
# instancia fria - e aceitavel para algo que muda uma vez por ano.
_DO_BANCO = None


def _config_do_banco():
    """A configuracao de e-mail tambem pode morar no banco.

    A alternativa seria so variavel de ambiente, que exige entrar no painel da
    hospedagem. Como a DATABASE_URL ja esta la, quem le as variaveis ja alcanca
    o banco de qualquer forma - guardar aqui nao abre porta nova.
    """
    global _DO_BANCO
    if _DO_BANCO is not None:
        return _DO_BANCO
    try:
        from rep_campo.infra.db import conectar
        with conectar() as con:
            _DO_BANCO = {r["chave"]: r["valor"] for r in
                         con.execute("SELECT chave, valor FROM config_email")}
    except Exception as exc:
        print("[--] config_email indisponivel: %s" % str(exc)[:120])
        _DO_BANCO = {}
    return _DO_BANCO


def conf(nome):
    """Ambiente primeiro, banco depois. Nunca devolve None."""
    return (os.environ.get(nome) or _config_do_banco().get(nome) or "").strip()


def destinatarios(variavel):
    """Lista separada por virgula, do ambiente ou do banco."""
    bruto = conf(variavel)
    return [e.strip() for e in bruto.replace(";", ",").split(",") if e.strip()]


def _por_resend(assunto, corpo, para, remetente, responder_para=None):
    chave = conf("RESEND_API_KEY")
    if not chave:
        return False
    try:
        corpo_json = {"from": remetente, "to": para,
                      "subject": assunto, "text": corpo}
        if responder_para:
            corpo_json["reply_to"] = responder_para
        dados = json.dumps(corpo_json).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails", data=dados,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer %s" % chave})
        urllib.request.urlopen(req, timeout=TEMPO_LIMITE).read()
        return True
    except Exception as exc:
        print("[--] Resend falhou: %s" % str(exc)[:160])
        return False


def _por_smtp(assunto, corpo, para, remetente, responder_para=None):
    host = conf("SMTP_HOST")
    if not host:
        return False
    porta = int(conf("SMTP_PORT") or 587)
    usuario = conf("SMTP_USUARIO")
    senha = conf("SMTP_SENHA")
    try:
        msg = EmailMessage()
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = ", ".join(para)
        # O Gmail obriga o From a ser a conta autenticada - nao da para mandar
        # "em nome de" outra pessoa. O Reply-To resolve o que interessa: quem
        # recebe aperta Responder e a resposta vai para o representante.
        if responder_para:
            msg["Reply-To"] = responder_para
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


def enviar(assunto, corpo, para, responder_para=None):
    """Devolve True se saiu por algum caminho. Nunca levanta.

    Quando nao sai, o texto vai para o log: o aviso nao pode simplesmente
    sumir so porque o canal nao estava configurado ou falhou.
    """
    remetente = conf("EMAIL_REMETENTE") or "REP Campo <onboarding@resend.dev>"
    if para and (_por_resend(assunto, corpo, para, remetente, responder_para)
                 or _por_smtp(assunto, corpo, para, remetente, responder_para)):
        return True
    motivo = "sem destinatario" if not para else "nenhum canal entregou"
    print("[--] e-mail nao enviado (%s). O aviso seria:" % motivo)
    print("    Para: %s" % (", ".join(para) or "(ninguem)"))
    print("    %s" % assunto)
    print(corpo)
    return False
