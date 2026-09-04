# -*- coding: utf-8 -*-
"""Coerções e normalização. Funções puras, sem I/O."""
import re
import unicodedata

RE_UUID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")
RE_NOME_FOTO = re.compile(r"[A-Za-z0-9_\-]+\.(jpg|png)")
RE_NUMERO_OCORRENCIA = re.compile(r"OC-\d{4}-\d{4}")

_EXPANSOES = [
    (r"\bdo ma\b", "do maranhao"), (r"\bdo to\b", "do tocantins"),
    (r"\bdo pa\b", "do para"), (r"\bdo pi\b", "do piaui"),
    (r"\bgov\.?\b", "governador"), (r"\bpres\.?\b", "presidente"),
    (r"\bsto\.?\b", "santo"), (r"\bsta\.?\b", "santa"),
]
_CORRECOES = {"araguaiina": "araguaina"}

# Nomes canônicos: `rotas_oficiais` (gerado) e o resto do código importam
# estes em vez de copiar a tabela. Os `_` acima seguem como alias interno.
EXPANSOES_CIDADE = _EXPANSOES
CORRECOES_CIDADE = _CORRECOES


def norm(txt):
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return t.lower().strip()


def chave_cidade(cidade):
    t = unicodedata.normalize("NFKD", str(cidade or "")).encode("ascii", "ignore").decode()
    t = t.split("/")[0]
    t = re.sub(r"[-_.]+", " ", t).lower()
    t = re.sub(r"\s+", " ", t).strip()
    for padrao, troca in _EXPANSOES:
        t = re.sub(padrao, troca, t)
    t = re.sub(r"\s+", " ", t).strip()
    return _CORRECOES.get(t, t)


def sem_acento(txt):
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode().lower()
    t = t.split("/")[0]
    t = re.sub(r"[-_]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def slug(txt):
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()[:40] or "sem-nome"


def inteiro(valor, padrao):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def num_float(valor):
    try:
        return float(valor) if valor is not None else None
    except (TypeError, ValueError):
        return None


def num_carteira(valor):
    try:
        s = str(valor)
        if isinstance(valor, str) and "," in s:
            return float(s.replace(".", "").replace(",", "."))
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def texto_limitado(ficha, campo, limites):
    v = ficha.get(campo)
    if v is None:
        return None
    return str(v)[:limites.get(campo, 500)]
