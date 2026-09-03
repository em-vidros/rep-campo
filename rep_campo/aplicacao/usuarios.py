# -*- coding: utf-8 -*-
"""Validação de usuários. Devolve (erro, dados) para a borda HTTP decidir o status."""
import re

from rep_campo.dominio import catalogos as C


def sanitizar_login(login):
    return re.sub(r"[^a-z0-9._-]", "", (login or "").strip().lower())[:30]


def validar_criacao(dados):
    login = sanitizar_login(dados.get("login"))
    nome = (dados.get("nome") or "").strip()[:80]
    papel = dados.get("papel") if dados.get("papel") in C.PAPEIS else "rep"
    senha = dados.get("senha") or ""
    if not login or not nome:
        return "login_e_nome_obrigatorios", None
    if len(senha) < C.SENHA_MIN:
        return "senha_curta", None
    return None, {"login": login, "nome": nome, "papel": papel, "senha": senha}
