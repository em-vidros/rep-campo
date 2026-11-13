# -*- coding: utf-8 -*-
"""Resumo diario do campo. Monta, manda uma vez por dia e registra."""
from datetime import date, datetime, timedelta, timezone

from rep_campo.dominio import boletim as dom
from rep_campo.infra import repositorios as repo


def hoje_sp():
    """A data de Sao Paulo (-03). O servidor pensa em UTC; o campo, nao."""
    return (datetime.now(timezone.utc) - timedelta(hours=3)).date()


def montar(db, dia=None):
    dia = dia or hoje_sp()
    segunda = dia - timedelta(days=dia.weekday())
    dados = repo.numeros_do_boletim(db, dia.isoformat(), segunda.isoformat())
    dados["fichas_do_dia"] = repo.fichas_do_dia(db, dia.isoformat())
    dados["total_do_dia"] = repo.contar_fichas_do_dia(db, dia.isoformat())
    return dia, dom.montar(dia, dados)


def ja_foi_hoje(db, dia):
    db.execute("""CREATE TABLE IF NOT EXISTS boletim_log (
        dia TEXT PRIMARY KEY, enviado_em TEXT, ok INTEGER, erro TEXT)""")
    r = db.execute("SELECT ok FROM boletim_log WHERE dia = %s",
                   (dia.isoformat(),)).fetchone()
    return bool(r and r["ok"])


def _registrar(db, dia, ok, erro):
    db.execute("""INSERT INTO boletim_log (dia, enviado_em, ok, erro)
        VALUES (%s,%s,%s,%s) ON CONFLICT (dia) DO UPDATE SET
        enviado_em = excluded.enviado_em, ok = excluded.ok, erro = excluded.erro""",
        (dia.isoformat(), datetime.now(timezone.utc).isoformat(timespec="seconds"),
         1 if ok else 0, (erro or "")[:400]))
    db.commit()


def enviar(db, dia=None, forcar=False, mandar=None):
    """Uma vez por dia. `forcar` reenvia; `mandar` e injetavel para teste.

    A trava por dia existe porque a rota e publica: sem ela, qualquer um que
    descobrisse o endereco encheria o Telegram do Ricardo.
    """
    if mandar is None:
        from rep_campo.infra.alertas import avisar as mandar
    dia, texto = montar(db, dia)
    if not forcar and ja_foi_hoje(db, dia):
        return {"enviado": False, "motivo": "ja_enviado_hoje",
                "dia": dia.isoformat()}
    ok = bool(mandar(texto))
    erro = ""
    if not ok:
        from rep_campo.infra import alertas
        erro = getattr(alertas, "ULTIMO_ERRO_TG", "") or "sem canal configurado"
    _registrar(db, dia, ok, erro)
    return {"enviado": ok, "dia": dia.isoformat(), "erro": erro,
            "caracteres": len(texto)}
