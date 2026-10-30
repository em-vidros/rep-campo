# -*- coding: utf-8 -*-
"""Páginas públicas, foto e saúde. Borda fina: sem SQL aqui."""
import os

from flask import Blueprint, Response, current_app, jsonify, render_template, send_from_directory, session

from rep_campo.dominio import catalogos as C
from rep_campo.infra import blob, db as dbmod
from rep_campo.infra import repositorios as repo
from rep_campo.infra.relogio import agora
from rep_campo.web.acesso import admin_obrigatorio, login_obrigatorio

bp = Blueprint("sistema", __name__)


@bp.route("/")
@login_obrigatorio
def index():
    return render_template("index.html", nome=session.get("nome"),
                           papel=session.get("papel"), tipos=C.TIPOS)


@bp.route("/sw.js")
def service_worker():
    resp = send_from_directory(os.path.join(current_app.root_path, "static"), "sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(os.path.join(current_app.root_path, "static"),
                               "manifest.webmanifest")


@bp.route("/guia")
def guia():
    """Guia do representante. Publico de proposito: o link vai por WhatsApp
    para o celular do representante, antes de ele ter login."""
    return render_template("guia.html")


@bp.route("/foto/<nome>")
@login_obrigatorio
def foto(nome):
    if not blob.nome_foto_valido(nome):
        return "", 404
    binario, tipo = blob.ler(nome)
    if binario is None:
        return "", 404
    return Response(binario, mimetype=tipo,
                    headers={"Cache-Control": "private, max-age=3600"})


@bp.route("/saude/rede")
@admin_obrigatorio
def saude_rede():
    """Da para alcancar o servidor de e-mail daqui?

    Nasceu publica, para diagnosticar o alerta que falhava em silencio sem eu
    ter o painel da hospedagem. Agora e so do admin: ela mostra a configuracao
    (host, usuario, destinatarios) e tenta um login a cada chamada - de porta
    aberta, serviria para alguem mapear isso ou irritar o Google.
    """
    import socket
    from rep_campo.infra import email as mod_email
    host = mod_email.conf("SMTP_HOST") or "smtp.gmail.com"
    saida = {"host": host}
    for porta in (587, 465, 2525):
        try:
            s = socket.create_connection((host, porta), timeout=6)
            s.close()
            saida["porta_%d" % porta] = "abre"
        except Exception as exc:
            saida["porta_%d" % porta] = "%s: %s" % (type(exc).__name__, str(exc)[:80])
    try:
        socket.create_connection(("api.resend.com", 443), timeout=6).close()
        saida["resend_443"] = "abre"
    except Exception as exc:
        saida["resend_443"] = "%s: %s" % (type(exc).__name__, str(exc)[:80])

    # a configuracao chegou ate aqui? (sem mostrar a senha)
    saida["config"] = {k: ("definido (%d car.)" % len(mod_email.conf(k))
                           if k == "SMTP_SENHA" else mod_email.conf(k) or "VAZIO")
                       for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USUARIO",
                                 "SMTP_SENHA", "EMAIL_REMETENTE",
                                 "ALERTA_CADASTRO_PARA")}

    # autentica e desliga, sem mandar mensagem nenhuma
    import smtplib
    try:
        with smtplib.SMTP(host, int(mod_email.conf("SMTP_PORT") or 587),
                          timeout=10) as sm:
            sm.starttls()
            sm.login(mod_email.conf("SMTP_USUARIO"), mod_email.conf("SMTP_SENHA"))
        saida["login_smtp"] = "aceito"
    except Exception as exc:
        saida["login_smtp"] = "%s: %s" % (type(exc).__name__, str(exc)[:200])
    return jsonify(saida), 200, {"Cache-Control": "no-store"}


@bp.route("/ping")
def ping():
    """Sonda de rede do app. Nao toca no banco: a pergunta e so se ha rede."""
    return jsonify({"ok": True}), 200, {"Cache-Control": "no-store"}


@bp.route("/saude")
def saude():
    try:
        n = repo.contar_clientes(dbmod.get_db())
        return jsonify({"ok": True, "clientes": n, "hora": agora()})
    except Exception:
        current_app.logger.exception("saude falhou")
        return jsonify({"ok": False, "erro": "banco_indisponivel"}), 500
