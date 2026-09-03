# -*- coding: utf-8 -*-
"""Compatibilidade: o app agora mora em rep_campo.create_app().

Mantido porque a Vercel, o teste de fumaça e os scripts importam deste
caminho. Código novo entra em rep_campo/ (dominio -> aplicacao -> infra -> web).
"""
import os

from rep_campo import create_app
from rep_campo.dominio import catalogos as _c
from rep_campo.dominio.cobertura import ciclo_do_municipio  # noqa: F401 (compat)
from rep_campo.dominio.texto import RE_UUID  # noqa: F401 (compat)
from rep_campo.infra.db import agora as _agora  # noqa: F401 (compat)
from rep_campo.infra.db import get_db  # noqa: F401 (compat)

TIPOS = _c.TIPOS
MUNICIPIOS_MIGRACAO = _c.MUNICIPIOS_MIGRACAO
RELATO_MIN = _c.RELATO_MIN
PROBLEMAS_TECNICOS = _c.PROBLEMAS_TECNICOS
RESPONSAVEIS = _c.RESPONSAVEIS
ETAPAS_JORNADA = _c.ETAPAS_JORNADA
METRICA_POR_ETAPA = _c.METRICA_POR_ETAPA
NPS_PROMOTOR, NPS_DETRATOR = _c.NPS_PROMOTOR, _c.NPS_DETRATOR
CSAT_SATISFEITO = _c.CSAT_SATISFEITO
CES_FACIL = _c.CES_FACIL
PERGUNTA_EXPERIENCIA = _c.PERGUNTA_EXPERIENCIA
CESTA_PRECO = _c.CESTA_PRECO
TIPOS_EVIDENCIA = _c.TIPOS_EVIDENCIA
PROCESSOS_CSAT = _c.PROCESSOS_CSAT
EXPEDICOES = _c.EXPEDICOES
ROTAS_FORA_DA_BASE = _c.ROTAS_FORA_DA_BASE
DIAS_MINIMOS_ENTRE_NPS = _c.DIAS_MINIMOS_ENTRE_NPS
CANAIS = _c.CANAIS
SETORES = _c.SETORES
STATUS_OCORRENCIA = _c.STATUS_OCORRENCIA
PAPEIS = _c.PAPEIS
PAPEIS_GESTAO = _c.PAPEIS_GESTAO
LIMITES_TEXTO = _c.LIMITES_TEXTO
MAX_EXTRA_JSON = _c.MAX_EXTRA_JSON
MAX_ANEXOS = _c.MAX_ANEXOS
SENHA_MIN = _c.SENHA_MIN
MAX_TENTATIVAS = _c.MAX_TENTATIVAS_LOGIN
CICLO_IMPERATRIZ = _c.CICLO_IMPERATRIZ
CICLO_MIGRACAO = _c.CICLO_MIGRACAO
CICLO_PARA = _c.CICLO_PARA
CICLO_PADRAO = _c.CICLO_PADRAO

app = create_app()

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8010))
    print("[rep-campo] iniciando em http://127.0.0.1:%d" % porta)
    app.run(host="0.0.0.0", port=porta, debug=False)
