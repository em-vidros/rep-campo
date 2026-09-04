#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unitários puros: sem banco, sem rede, sem Flask. `python3 -m pytest tests/ -q`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_evidencia_forte_media_leve():
    from rep_campo.dominio.visitas import classificar_evidencia
    assert classificar_evidencia(True, True, False) == "forte"
    assert classificar_evidencia(False, True, True) == "media"
    assert classificar_evidencia(True, False, False) == "leve"
    assert classificar_evidencia(False, False, True) == "leve"


def test_validar_nota_limites():
    from rep_campo.dominio.visitas import validar_nota
    assert validar_nota("9") == 9
    assert validar_nota("") is None
    assert validar_nota(None) is None
    assert validar_nota("11") is None
    assert validar_nota("-1") is None
    assert validar_nota("abc") is None


def test_ciclo_por_praca():
    from rep_campo.dominio.cobertura import ciclo_do_municipio
    assert ciclo_do_municipio("Imperatriz/MA") == 90
    assert ciclo_do_municipio("Santa Inês/MA") == 120
    assert ciclo_do_municipio("Belém/PA") == 180
    assert ciclo_do_municipio("Balsas/MA") == 120


def test_chave_cidade_unica_fonte():
    from rep_campo.dominio import rotas_oficiais as r
    from rep_campo.dominio.texto import chave_cidade
    assert r._chave("Santa Inês/MA") == chave_cidade("Santa Inês/MA")
    assert r._chave("Gov. Newton Belo") == chave_cidade("Gov. Newton Belo")
    assert r.rota_da_cidade("Imperatriz") == "Imperatriz"
    assert r.e_da_base_itz("Imperatriz") is True


def test_curva_abc_pareto():
    from rep_campo.dominio.carteira import curva_abc
    clientes = [{"vol_12m": 80.0}, {"vol_12m": 15.0}, {"vol_12m": 5.0}, {"vol_12m": 0.0}]
    out = curva_abc(clientes)
    por_vol = {c["vol_12m"]: c["curva"] for c in out}
    assert por_vol[80.0] == "A"
    assert por_vol[5.0] == "C"
    assert por_vol[0.0] is None


def test_pontuar_prioriza_parado_e_ocorrencia():
    from rep_campo.dominio.sugestao import pontuar_cliente
    peso_alto, mot_alto = pontuar_cliente(
        {"dias_sem_comprar": 120, "vol_12m": 50000, "oc_abertas": 1,
         "pior_nota": 5, "curva": "A"}, None, 120)
    peso_baixo, mot_baixo = pontuar_cliente(
        {"dias_sem_comprar": 5, "vol_12m": 100, "oc_abertas": 0,
         "pior_nota": None, "curva": "C"}, 10, 120)
    assert peso_alto > peso_baixo
    assert any("sem comprar" in m for m in mot_alto)
    assert any("ocorrência" in m for m in mot_alto)


def test_metrica_por_etapa():
    from rep_campo.dominio.experiencia import indice_nps, metrica_para_etapa
    assert metrica_para_etapa("Relacionamento geral") == "nps"
    assert metrica_para_etapa("Preco e condicao") == "csat"
    assert metrica_para_etapa("etapa desconhecida") == "csat"
    assert indice_nps(7, 2, 10) == 50
    assert indice_nps(0, 0, 0) is None


def test_ocorrencia_numero_e_status():
    from rep_campo.dominio.ocorrencias import numero_formatado, numero_valido, status_valido
    assert numero_valido(numero_formatado("2026", 7)) is True
    assert numero_valido("lixo") is False
    assert status_valido("resolvida") is True
    assert status_valido("sumiu") is False


def test_foto_pura_recusa_invalida_sem_io():
    from rep_campo.infra.blob import salvar_foto_puro
    chamadas = []

    def gravar(nome, binario, tipo):
        chamadas.append(nome)
        return nome

    assert salvar_foto_puro("uuid-curto-demais-123", None, gravar) is None
    assert salvar_foto_puro("abcdefgh123", "sem-virgula", gravar) is None
    assert salvar_foto_puro("abcdefgh123", "data:image/png;base64,!!!", gravar) is None
    assert chamadas == []


def test_foto_pura_aceita_png():
    import base64
    from rep_campo.infra.blob import salvar_foto_puro
    png = base64.b64encode(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )).decode()
    gravados = {}

    def gravar(nome, binario, tipo):
        gravados["nome"] = nome
        gravados["tipo"] = tipo
        return nome

    nome = salvar_foto_puro("abcdefgh123", "data:image/png;base64," + png, gravar)
    assert nome == "abcdefgh123.png"
    assert gravados["tipo"] == "image/png"


def test_nome_foto_usa_regex_canonica():
    from rep_campo.dominio.texto import RE_NOME_FOTO
    from rep_campo.infra.blob import nome_foto_valido
    assert nome_foto_valido("abc-123.png") == bool(RE_NOME_FOTO.fullmatch("abc-123.png"))
    assert nome_foto_valido("../x.png") is False
    assert nome_foto_valido("foto.exe") is False


def test_receber_lote_com_fakes():
    from rep_campo.aplicacao import fichas as servico

    class FakeDB:
        def __init__(self):
            self.fichas = set()
            self.commits = 0

        def execute(self, query, params=None):
            q = " ".join(query.split())
            if q.startswith("SELECT 1 FROM fichas"):
                uuid = params[0]
                return _One({"1": 1} if uuid in self.fichas else None)
            if q.startswith("INSERT INTO fichas"):
                self.fichas.add(params[0])
                return _One(None)
            if "UPDATE viagem_clientes" in q:
                return _One(None)
            return _One(None)

        def commit(self):
            self.commits += 1

        def transaction(self):
            return _Tx()

    class _One:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

    class _Tx:
        def __enter__(self):
            return None

        def __exit__(self, *a):
            return False

    db = FakeDB()
    fotos = {}
    aceitas, rejeitadas, _ = servico.receber_lote(
        db, [{"uuid": "abcdefgh123", "tipo": "comercial",
              "cliente_nome": "Cliente X"}],
        {"uid": 1, "login": "rep1"},
        salvar_foto=lambda u, d: fotos.setdefault(u, u + ".png"),
        agora=lambda: "2026-09-04T00:00:00+00:00")
    assert aceitas == ["abcdefgh123"]
    assert rejeitadas == []
    assert db.commits == 1

    aceitas2, _, _ = servico.receber_lote(
        db, [{"uuid": "abcdefgh123", "tipo": "comercial",
              "cliente_nome": "Cliente X"}],
        {"uid": 1, "login": "rep1"},
        salvar_foto=lambda u, d: u + ".png",
        agora=lambda: "2026-09-04T00:00:00+00:00")
    assert aceitas2 == ["abcdefgh123"]


def test_viagens_pode_acessar_e_aderencia():
    from rep_campo.aplicacao.viagens import aderencia, pode_acessar
    assert aderencia(0, 0) is None
    assert aderencia(4, 1) == 25
    assert pode_acessar({"criada_por": "a", "responsavel": "b"}, "a", False) is True
    assert pode_acessar({"criada_por": "a", "responsavel": "b"}, "c", False) is False
    assert pode_acessar({"criada_por": "a", "responsavel": "b"}, "c", True) is True


def test_ordenar_cobertura_nunca_visitado_primeiro():
    from rep_campo.aplicacao.viagens import ordenar_cobertura
    itens = [
        {"dias": 10, "vol_12m": 999999},
        {"dias": None, "vol_12m": 1},
        {"dias": 200, "vol_12m": 5},
    ]
    ordenar_cobertura(itens)
    assert itens[0]["dias"] is None
    assert itens[1]["dias"] == 200
