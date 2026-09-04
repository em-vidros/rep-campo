# -*- coding: utf-8 -*-
"""Entidades do domínio. Dataclasses imutáveis, sem I/O, sem Flask, sem SQL.

Motivo: o código trafegava `dict` + `.get()` em todo lugar
(`sugestao.pontuar_cliente`, `fichas._gravar_ficha`, `viagens.relatorio`).
Dict esconde o contrato — ninguém sabe quais chaves existem nem quais são
obrigatórias. Dataclass congela o contrato e o erro aparece na construção,
não no meio de um SQL.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class UsuarioSessao:
    uid: int
    login: str


@dataclass(frozen=True)
class SinalSugestao:
    dias_sem_comprar: int | None = None
    vol_12m: float = 0.0
    oc_abertas: int = 0
    pior_nota: int | None = None
    curva: str | None = None


@dataclass
class ClienteCobertura:
    codigo: str
    nome: str
    cidade: str | None
    curva: str | None
    vol_12m: float
    vendedor: str | None
    ultima_visita: str | None
    total_visitas: int = 0
    dias: int | None = None
    ciclo: int = 120
    vencido: bool = True


@dataclass(frozen=True)
class RespostaExperiencia:
    etapa: str
    nota: int
    comentario: str | None = None
    unidade: str | None = None


@dataclass(frozen=True)
class NovaViagem:
    nome: str
    inicio: str | None = None
    fim: str | None = None
    rota: str | None = None
    observacao: str | None = None
    tipo: str = "viagem"
    responsavel: str | None = None


@dataclass(frozen=True)
class ClienteRoteiro:
    codigo: str | None
    nome: str
    cidade: str | None = None
    motivo: str | None = None
    ordem: int = 0


@dataclass(frozen=True)
class NovoUsuario:
    login: str
    nome: str
    papel: str
    senha: str = field(repr=False)
