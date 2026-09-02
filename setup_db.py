#!/usr/bin/env python3
"""Cria o esquema do REP Campo no Postgres. Roda uma vez, do Mac.

    python3 setup_db.py

Le a DATABASE_URL do ambiente ou do .env ao lado. Pode rodar de novo sem medo:
tudo aqui e IF NOT EXISTS.

Este arquivo e o unico dono do esquema. O app nao cria mais tabela, porque no
Postgres o CREATE toma trava exclusiva e duas instancias frias subindo juntas se
travam uma na outra.
"""
import os
import sys

import psycopg

TABELAS = [
    ("usuarios", """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            login TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            papel TEXT NOT NULL DEFAULT 'rep',
            base TEXT NOT NULL DEFAULT 'ITZ',
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        )"""),
    ("clientes", """
        CREATE TABLE IF NOT EXISTS clientes (
            codigo TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            cidade TEXT,
            rota TEXT,
            tabela TEXT,
            vendedor TEXT,
            vol_12m DOUBLE PRECISION DEFAULT 0,
            curva TEXT,
            base TEXT DEFAULT 'ITZ',
            origem TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            atualizado_em TEXT
        )"""),
    ("viagens", """
        CREATE TABLE IF NOT EXISTS viagens (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            nome TEXT NOT NULL,
            inicio TEXT,
            fim TEXT,
            rota TEXT,
            observacao TEXT,
            status TEXT NOT NULL DEFAULT 'planejada',
            criada_por TEXT NOT NULL,
            responsavel TEXT,
            criada_em TEXT NOT NULL
        )"""),
    ("viagem_clientes", """
        CREATE TABLE IF NOT EXISTS viagem_clientes (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            viagem_id INTEGER NOT NULL
                REFERENCES viagens(id) ON DELETE CASCADE,
            cliente_codigo TEXT,
            cliente_nome TEXT NOT NULL,
            municipio TEXT,
            motivo TEXT,
            ordem INTEGER DEFAULT 0,
            visitado INTEGER NOT NULL DEFAULT 0,
            ficha_uuid TEXT,
            visitado_em TEXT
        )"""),
    ("experiencia", """
        CREATE TABLE IF NOT EXISTS experiencia (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            ficha_uuid TEXT NOT NULL,
            cliente_codigo TEXT,
            cliente_nome TEXT,
            etapa TEXT NOT NULL,
            metrica TEXT NOT NULL,
            nota INTEGER NOT NULL,
            comentario TEXT,
            unidade TEXT,
            registrado_em TEXT NOT NULL,
            usuario_login TEXT
        )"""),
    ("anexos", """
        CREATE TABLE IF NOT EXISTS anexos (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            ficha_uuid TEXT NOT NULL,
            arquivo TEXT NOT NULL,
            tipo TEXT,
            descricao TEXT,
            criado_em TEXT NOT NULL
        )"""),
    ("ocorrencias", """
        CREATE TABLE IF NOT EXISTS ocorrencias (
            numero TEXT PRIMARY KEY,
            aberta_em TEXT NOT NULL,
            aberta_por TEXT NOT NULL,
            setor TEXT NOT NULL DEFAULT 'Comercial',
            canal TEXT NOT NULL DEFAULT 'Visita do representante',
            cliente_codigo TEXT,
            cliente_nome TEXT NOT NULL,
            municipio TEXT,
            tipo TEXT,
            descricao TEXT,
            pedido_nf TEXT,
            status TEXT NOT NULL DEFAULT 'aberta',
            responsavel TEXT,
            prazo TEXT,
            ficha_uuid TEXT,
            foto_arquivo TEXT,
            resolucao TEXT,
            resolvida_em TEXT,
            resolvida_por TEXT
        )"""),
    ("fichas", """
        CREATE TABLE IF NOT EXISTS fichas (
            uuid TEXT PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            usuario_login TEXT NOT NULL,
            tipo TEXT NOT NULL,
            cliente_codigo TEXT,
            cliente_nome TEXT NOT NULL,
            prospect INTEGER NOT NULL DEFAULT 0,
            municipio TEXT,
            objetivo TEXT,
            relato TEXT,
            proximo_passo TEXT,
            prox_responsavel TEXT,
            prox_data TEXT,
            encaminhado_para TEXT,
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION,
            precisao DOUBLE PRECISION,
            criado_em_disp TEXT,
            recebido_em TEXT NOT NULL,
            foto_arquivo TEXT,
            extra_json TEXT,
            nivel_evidencia TEXT,
            conta_indicador INTEGER NOT NULL DEFAULT 0,
            relato_curto INTEGER NOT NULL DEFAULT 0,
            app_versao TEXT,
            problema_tipo TEXT,
            ocorrencia_num TEXT,
            ocorrencia_status TEXT,
            ocorrencia_fechada_em TEXT,
            exp_etapa TEXT,
            exp_nota INTEGER,
            exp_comentario TEXT,
            exp_metrica TEXT
        )"""),
    # O numero da ocorrencia sai daqui, nao de um SELECT MAX seguido de INSERT.
    # Duas instancias da Vercel gerando OC-2026-0007 ao mesmo tempo davam o mesmo
    # numero para clientes diferentes.
    ("contador_ocorrencias", """
        CREATE TABLE IF NOT EXISTS contador_ocorrencias (
            ano TEXT PRIMARY KEY,
            ultimo INTEGER NOT NULL DEFAULT 0
        )"""),
    # O freio de forca bruta vivia num dicionario do processo. Serverless troca de
    # processo entre requisicoes, entao o contador tem que morar no banco.
    ("tentativas_login", """
        CREATE TABLE IF NOT EXISTS tentativas_login (
            origem TEXT PRIMARY KEY,
            falhas INTEGER NOT NULL DEFAULT 0,
            ultima TIMESTAMPTZ NOT NULL
        )"""),
]

INDICES = [
    "CREATE INDEX IF NOT EXISTS ix_vc_viagem ON viagem_clientes(viagem_id)",
    "CREATE INDEX IF NOT EXISTS ix_vc_cliente ON viagem_clientes(cliente_codigo)",
    # sem isto, dois toques no botao de montar roteiro inserem o cliente duas vezes
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_vc_viagem_cliente "
    "ON viagem_clientes(viagem_id, cliente_codigo) WHERE cliente_codigo IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_exp_ficha ON experiencia(ficha_uuid)",
    "CREATE INDEX IF NOT EXISTS ix_exp_metrica ON experiencia(metrica)",
    # a sugestao de visita busca a pior nota por cliente em toda chamada
    "CREATE INDEX IF NOT EXISTS ix_exp_cliente ON experiencia(cliente_codigo)",
    "CREATE INDEX IF NOT EXISTS ix_anexos_ficha ON anexos(ficha_uuid)",
    "CREATE INDEX IF NOT EXISTS ix_oc_status ON ocorrencias(status)",
    "CREATE INDEX IF NOT EXISTS ix_oc_cliente ON ocorrencias(cliente_codigo)",
    "CREATE INDEX IF NOT EXISTS ix_fichas_usuario ON fichas(usuario_login)",
    "CREATE INDEX IF NOT EXISTS ix_fichas_data ON fichas(recebido_em)",
    "CREATE INDEX IF NOT EXISTS ix_fichas_cliente ON fichas(cliente_codigo)",
    "CREATE INDEX IF NOT EXISTS ix_clientes_nome ON clientes(nome)",
]


def carregar_env():
    """Le o .env ao lado deste arquivo, sem depender de pacote extra."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(caminho):
        return
    for linha in open(caminho, encoding="utf-8"):
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def main():
    carregar_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL nao definida. Ponha no .env ou no ambiente.")
        return 1

    with psycopg.connect(url, autocommit=True) as con:
        for nome, ddl in TABELAS:
            con.execute(ddl)
            print("tabela", nome)
        for ddl in INDICES:
            con.execute(ddl)
        print(len(INDICES), "indices")

        faltando = [n for n, _ in TABELAS if not con.execute(
            "SELECT to_regclass(%s) IS NOT NULL", ("public." + n,)).fetchone()[0]]
        assert not faltando, "nao criou: %s" % faltando
        print("pronto:", len(TABELAS), "tabelas no Neon")
    return 0


if __name__ == "__main__":
    sys.exit(main())
