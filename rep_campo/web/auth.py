# -*- coding: utf-8 -*-
"""Login, logout e troca de senha."""
from flask import Blueprint, render_template, request, redirect, session, url_for

from rep_campo.dominio import catalogos as C
from rep_campo.infra import db as dbmod
from rep_campo.infra import seguranca
from rep_campo.web.acesso import login_obrigatorio, origem_visitante

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        db = dbmod.get_db()
        origem = origem_visitante()
        if seguranca.bloqueado(db, origem):
            return render_template(
                "login.html",
                erro="Muitas tentativas. Tente de novo em 15 minutos."), 429
        login_txt = (request.form.get("login") or "").strip().lower()
        senha = request.form.get("senha") or ""
        row = db.execute(
            "SELECT * FROM usuarios WHERE login = %s AND ativo = 1", (login_txt,)
        ).fetchone()
        if row and seguranca.confere_senha(row["senha_hash"], senha):
            seguranca.limpar_falhas(db, origem)
            session.clear()
            session.permanent = True
            session["uid"] = row["id"]
            session["login"] = row["login"]
            session["nome"] = row["nome"]
            session["papel"] = row["papel"]
            destino = request.args.get("next") or url_for("sistema.index")
            if not destino.startswith("/"):
                destino = url_for("sistema.index")
            return redirect(destino)
        seguranca.registrar_falha(db, origem)
        erro = "Login ou senha invalidos."
    return render_template("login.html", erro=erro)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/conta", methods=["GET", "POST"])
@login_obrigatorio
def conta():
    aviso = erro = None
    if request.method == "POST":
        atual = request.form.get("atual") or ""
        nova = request.form.get("nova") or ""
        repetir = request.form.get("repetir") or ""
        db = dbmod.get_db()
        row = db.execute("SELECT senha_hash FROM usuarios WHERE id = %s",
                         (session["uid"],)).fetchone()
        if not row or not seguranca.confere_senha(row["senha_hash"], atual):
            erro = "Senha atual incorreta."
        elif len(nova) < C.SENHA_MIN:
            erro = "A senha nova precisa de pelo menos %d caracteres." % C.SENHA_MIN
        elif nova != repetir:
            erro = "A confirmacao nao confere."
        elif nova == atual:
            erro = "A senha nova tem que ser diferente da atual."
        else:
            db.execute("UPDATE usuarios SET senha_hash = %s WHERE id = %s",
                       (seguranca.hash_senha(nova), session["uid"]))
            db.commit()
            aviso = "Senha alterada."
    return render_template("conta.html", aviso=aviso, erro=erro,
                           nome=session.get("nome"), papel=session.get("papel"))
