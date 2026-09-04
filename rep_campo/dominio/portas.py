# -*- coding: utf-8 -*-
"""Portas hexagonais: o que a aplicação precisa, sem dizer como é feito.

`dominio` e `aplicacao` só enxergam estes Protocols. `infra` implementa.
`web` injeta a implementação via `create_app()` ou via argumento.

Antes: `aplicacao/fichas.py` importava `infra.blob` e `infra.db` direto, e
`web/gestor.py` abria SQL no meio do blueprint. A dependência apontava para
dentro do concreto — trocar Neon por outro banco ou Blob por disco exigia
mexer em regra de negócio. Agora a seta inverte: o concreto depende da porta.
"""
from typing import Any, Protocol


class Relogio(Protocol):
    def agora(self) -> str:
        """Instante atual em ISO-8601 com timezone, ex. `db.agora()`."""
        ...


class ArmazenamentoFotos(Protocol):
    def salvar(self, uuid_ficha: str, data_url: str | None) -> str | None:
        """Grava a foto e devolve o nome do arquivo, ou None se ausente/inválida."""
        ...


class Conexao(Protocol):
    """Superfície mínima que os repositórios usam. `psycopg` atende sem adapter."""

    def execute(self, query: str, params: Any = None) -> Any:
        ...

    def commit(self) -> None:
        ...


class ContadorOcorrencias(Protocol):
    def proxima(self, db: Conexao) -> str:
        ...
