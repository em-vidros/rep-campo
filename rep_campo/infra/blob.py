# -*- coding: utf-8 -*-
"""Fotos na loja privada do Vercel Blob. Leitura sempre via servidor.

Porta `ArmazenamentoFotos`, adapter `VercelBlobFotos`. Antes o cache da base
da URL era um `dict` global mutável (`_base_cache`) — compartilhado entre
threads/requests sem dono. Agora o cache é atributo de instância; o módulo
mantém uma instância padrão só para compatibilidade das funções antigas.
"""
import base64
import os

import requests

from rep_campo.dominio.texto import RE_NOME_FOTO, RE_UUID

BLOB_API = "https://blob.vercel-storage.com"
BLOB_PASTA = "fotos/"
BLOB_VERSAO = "7"

_ASSINATURAS = ((b"\xff\xd8\xff", "jpg"), (b"\x89PNG\r\n\x1a\n", "png"))


def _token():
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN nao definida nas variaveis de ambiente")
    return token


def _cabecalho(extra=None):
    h = {"Authorization": "Bearer " + _token(), "x-api-version": BLOB_VERSAO}
    h.update(extra or {})
    return h


class VercelBlobFotos:
    """Adapter injetável. Uma instância por app, sem estado global."""

    def __init__(self):
        self._base_url: str | None = None

    def gravar(self, nome, binario, tipo):
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
            self._base_url = url[:-len(BLOB_PASTA + nome)]
        return nome

    def endereco(self, nome):
        if self._base_url:
            return self._base_url + BLOB_PASTA + nome
        r = requests.get(BLOB_API + "/", params={"prefix": BLOB_PASTA + nome, "limit": "1"},
                         headers=_cabecalho(), timeout=20)
        if r.status_code != 200:
            return None
        blobs = r.json().get("blobs") or []
        if not blobs:
            return None
        url = blobs[0]["url"]
        self._base_url = url[:-len(BLOB_PASTA + nome)]
        return url

    def ler(self, nome):
        url = self.endereco(nome)
        if not url:
            return None, None
        r = requests.get(url, headers={"Authorization": "Bearer " + _token()}, timeout=25)
        if r.status_code != 200:
            return None, None
        return r.content, r.headers.get("content-type", "application/octet-stream")

    def salvar(self, uuid_ficha, data_url, limite_bytes=1024 * 1024):
        return salvar_foto_puro(uuid_ficha, data_url, self.gravar, limite_bytes)


def salvar_foto_puro(uuid_ficha, data_url, gravar_fn, limite_bytes=1024 * 1024):
    """Núcleo puro da validação: decodifica e valida, I/O só via `gravar_fn`."""
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
    return gravar_fn(nome, binario, "image/jpeg" if ext == "jpg" else "image/png")


_padrao = VercelBlobFotos()


def gravar(nome, binario, tipo):
    return _padrao.gravar(nome, binario, tipo)


def endereco(nome):
    return _padrao.endereco(nome)


def ler(nome):
    return _padrao.ler(nome)


def salvar_foto(uuid_ficha, data_url, limite_bytes=1024 * 1024):
    return _padrao.salvar(uuid_ficha, data_url, limite_bytes)


def nome_foto_valido(nome):
    return bool(RE_NOME_FOTO.fullmatch(nome or ""))
