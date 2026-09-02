# -*- coding: utf-8 -*-
"""Mapeamento oficial cidade -> rota da base Imperatriz.

Fonte: "CIDADES, ROTAS E TABELAS 30.04.2026.xlsx", validado pelo Ricardo.
O campo `rota` que vem da carteira esta incompleto - Araguaina/TO, por
exemplo, chega como "Sem Rota" quando na verdade e uma das cidades mais
importantes da rota Balsas. Este mapa corrige isso na sincronizacao.

So base Itz. Rotas de outra base sao tratadas em ROTAS_FORA_DA_BASE (app.py).
"""

ROTAS_ITZ = {
    "Imperatriz": ["Davinopolis", "Imperatriz", "Joao Lisboa", "Senador La Roque"],

    "Buriticupu": ["Acailandia", "Bom Jesus das Selvas", "Buriticupu",
                   "Santa Luzia", "Sao Francisco do Brejao"],

    "Pres. Dutra": ["Amarante", "Barra do Corda", "Buritirana", "Colinas",
                    "Dom Pedro", "Grajau", "Presidente Dutra",
                    "Sao Domingos do Maranhao", "Sitio Novo", "Tuntum"],

    "Balsas": ["Araguaina", "Balsas", "Campestre do Maranhao", "Carolina",
               "Estreito", "Formosa da Serra Negra", "Fortaleza dos Nogueiras",
               "Governador Edison Lobao", "Porto Franco", "Riachao",
               "Ribamar Fiquene", "Sao Joao do Paraiso"],

    "Paragominas": ["Cidelandia", "Dom Eliseu", "Itinga do Maranhao",
                    "Paragominas", "Rondon do Para", "Sao Pedro da Agua Branca",
                    "Ulianopolis"],

    "Ananindeua": ["Ananindeua", "Aurora do Para", "Castanhal", "Ipixuna do Para",
                   "Mae do Rio", "Santa Maria do Para", "Sao Miguel do Guama"],

    "Belém": ["Anajas", "Belem", "Benevides", "Breves", "Curralinho", "Marituba",
              "Muana", "Ponta de Pedras", "Santa Barbara do Para",
              "Santa Izabel do Para", "Sao Caetano de Odivelas",
              "Sao Francisco do Para", "Sao Felix do Xingu",
              "Sao Sebastiao da Boa Vista"],

    "Barcarena": ["Abaetetuba", "Acara", "Barcarena", "Concordia do Para",
                  "Igarape-Miri", "Moju"],

    "Salinópolis": ["Braganca", "Capanema", "Capitao Poco", "Nova Timboteua",
                    "Salinopolis", "Santa Luzia do Para", "Tracuateua"],

    "Araguatins": ["Araguatins", "Augustinopolis", "Axixa do Tocantins",
                   "Colinas do Tocantins", "Sao Miguel do Tocantins",
                   "Sao Sebastiao do Tocantins", "Sitio Novo do Tocantins"],

    # Migrou da base Raposa em 01/09/2026, por decisao do Ricardo. Na carteira
    # esses clientes chegam sem rota; aqui ganham a rota que sempre foi deles.
    "Santa Inês": ["Alto Alegre do Pindare", "Bom Jardim", "Governador Newton Belo",
                   "Igarape do Meio", "Moncao", "Pindare-Mirim", "Pio XII",
                   "Santa Ines", "Sao Mateus do Maranhao", "Ze Doca"],
}


def _chave(cidade):
    """Normaliza para comparar: sem acento, sem UF, minusculo."""
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", str(cidade or "")).encode("ascii", "ignore").decode()
    t = t.split("/")[0]                       # "Balsas/MA" -> "Balsas"
    t = re.sub(r"[-_]+", " ", t).lower()
    return re.sub(r"\s+", " ", t).strip()


# cidade normalizada -> rota oficial
CIDADE_ROTA = {}
for _rota, _cidades in ROTAS_ITZ.items():
    for _c in _cidades:
        CIDADE_ROTA[_chave(_c)] = _rota


def rota_da_cidade(cidade):
    """Rota oficial da cidade, ou None se ela nao estiver no mapa."""
    return CIDADE_ROTA.get(_chave(cidade))


TOTAL_CIDADES = len(CIDADE_ROTA)
