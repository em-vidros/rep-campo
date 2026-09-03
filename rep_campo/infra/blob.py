# -*- coding: utf-8 -*-
"""Fotos na loja privada do Vercel Blob. Leitura sempre via servidor."""
import base64
import os
import re

import requests

from rep_campo.dominio.texto import RE_NOME_FOTO, RE_UUID

BLOB_API = "https://blob.vercel-storage.com"
BLOB_PASTA = "fotos/"
BLOB_VERSAO = "7"

_ASSINATURAS = ((b"\xff\xd8\xff", "jpg"), (b"\x89PNG\r\n\x1a\n", "png"))
_base_cache = {}


def _token():
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN nao definida nas variaveis de ambiente")
    return token


def _cabecalho(extra=None):
    h = {"Authorization": "Bearer " + _token(), "x-api-version": BLOB_VERSAO}
    h.update(extra or {})
    return h


def gravar(nome, binario, tipo):
    r = requests.put(
        BLOB_API + "/" + BLOB_PASTA + nome,
        headers=_cabecalho({"x-content-type": tipo,
                            "x-vercel-blob-access": "private",
                            "x-add-random-suffix": "0",
                            "x-allow-overwrite": "1"}),
        data=binario, timeout=25)
    if r.status_code != 200:
        return None
    url = r.json().get("url") or ""
    if url:
        _base_cache["url"] = url[:-len(BLOB_PASTA + nome)]
    return nome


def endereco(nome):
    base = _base_cache.get("url")
    if base:
        return base + BLOB_PASTA + nome
    r = requests.get(BLOB_API + "/", params={"prefix": BLOB_PASTA + nome, "limit": "1"},
                     headers=_cabecalho(), timeout=20)
    if r.status_code != 200:
        return None
    blobs = r.json().get("blobs") or []
    if not blobs:
        return None
    url = blobs[0]["url"]
    _base_cache["url"] = url[:-len(BLOB_PASTA + nome)]
    return url


def ler(nome):
    url = endereco(nome)
    if not url:
        return None, None
    r = requests.get(url, headers={"Authorization": "Bearer " + _token()}, timeout=25)
    if r.status_code != 200:
        return None, None
    return r.content, r.headers.get("content-type", "application/octet-stream")


def salvar_foto(uuid_ficha, data_url, limite_bytes=1024 * 1024):
    if not data_url or "," not in data_url:
        return None
    if not RE_UUID.match(uuid_ficha or ""):
        return None
    _, b64 = data_url.split(",", 1)
    try:
        binario = base64.b64decode(b64, validate=True)
    except Exception:
        return None
    if len(binario) > limite_bytes:
        return None
    ext = next((e for assinatura, e in _ASSINATURAS if binario.startswith(assinatura)), None)
    if ext is None:
        return None
    nome = "%s.%s" % (uuid_ficha, ext)
    if not RE_NOME_FOTO.fullmatch(nome):
        return None
    return gravar(nome, binario, "image/jpeg" if ext == "jpg" else "image/png")


def nome_foto_valido(nome):
    return bool(re.fullmatch(r"[A-Za-z0-9_\-]+\.(jpg|png)", nome or ""))
