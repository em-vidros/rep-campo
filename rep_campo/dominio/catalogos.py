# -*- coding: utf-8 -*-
"""Vocabulário do negócio. Só dados, sem I/O nem SQL."""

TIPOS = {
    "comercial": {"label": "Comercial", "foto": "opcional"},
    "cordialidade": {"label": "Cordialidade", "foto": "opcional"},
    "tecnica": {"label": "Tecnica/Reclamacao", "foto": "obrigatoria"},
    "prospeccao": {"label": "Prospeccao", "foto": "obrigatoria"},
    "preco": {"label": "Pesquisa de preco", "foto": "obrigatoria"},
    "voz": {"label": "Voz do cliente", "foto": "opcional"},
    "evento": {"label": "Evento", "foto": "obrigatoria"},
    "cadastro": {"label": "Atualizacao de cadastro", "foto": "opcional"},
}

# O que o representante encontra errado no cadastro do cliente. Lista fechada:
# "mudou o endereco" e "ENDERECO NOVO" seriam dois assuntos diferentes no
# relatorio, e ninguem conseguiria contar quantas correcoes de endereco houve.
MUDANCAS_CADASTRO = [
    "Endereco", "Cidade", "Telefone", "Contato / responsavel",
    "Razao social ou CNPJ", "Ponto de referencia",
    "Cliente nao esta mais neste endereco", "Outro",
]

# O caso que nao e so cadastro errado: o representante foi ate la e o cliente
# nao esta mais. Vira uma busca, com dono e desfecho - nao um dado a corrigir.
MUDANCA_SUMIU = "Cliente nao esta mais neste endereco"

DESFECHOS_SUMIU = [
    "Vou procurar o endereco novo",
    "Encontrei o endereco novo",
    "Nao localizei - mudou de ramo",
    "Nao localizei - empresa fechou",
    "Nao localizei - titular faleceu",
    "Nao localizei - outro motivo",
]

# Enquanto a busca nao termina, a pendencia e do representante.
DESFECHO_PENDENTE = "Vou procurar o endereco novo"

# Campo da ficha por item marcado. A chave e o item da lista acima.
CAMPO_POR_MUDANCA = {
    "Endereco": "endereco_novo",
    "Cidade": "cidade_nova",
    "Telefone": "telefone_novo",
    "Contato / responsavel": "contato_novo",
    "Razao social ou CNPJ": "razao_nova",
    "Ponto de referencia": "referencia_nova",
    "Outro": "outro_novo",
}

# Tipos de ficha que abrem ocorrencia: ganham numero, responsavel, prazo e
# status. Sem isto a informacao fica so no relato e depende de alguem ler.
TIPOS_COM_OCORRENCIA = ("tecnica", "cadastro")

# Para onde a ocorrencia vai. O cadastro nao e problema de producao: quem
# resolve e quem edita o cliente no ERP, nao o Comercial.
SETOR_POR_TIPO = {"tecnica": "Comercial", "cadastro": "Cadastro"}
SETOR_PADRAO = "Comercial"

# Quem recebe a correcao de cadastro quando o representante nao escolhe
# ninguem. Nunca deixar em branco: ocorrencia sem dono nao e cobrada.
RESPONSAVEL_CADASTRO = "Cadastro"

# E-mail de cada login, para o alerta sair com Reply-To de quem abriu. O Gmail
# nao deixa mandar "em nome de" outra conta, entao o From e sempre a conta
# autenticada; o Reply-To e o que faz a recepcao responder direto ao
# representante, em vez de responder para o remetente do sistema.
EMAIL_POR_LOGIN = {
    "ricardo": "ricardo@emvidros.com.br",
    "islanno": "islanno.mesquita@emvidros.com.br",
    "sipiao": "tiago.sipiao@emvidros.com.br",
    "marcia": "marcia.prado@emvidros.com.br",
}

MUNICIPIOS_MIGRACAO = [
    "Santa Ines/MA", "Ze Doca/MA", "Bom Jardim/MA", "Governador Newton Belo/MA",
    "Moncao/MA", "Igarape do Meio/MA", "Pindare-Mirim/MA", "Pio XII/MA",
]

# Recomendado. Abaixo disso a ficha entra marcada como relato curto - nunca e
# recusada: dado de campo se classifica, nao se joga fora.
RELATO_MIN = 200

# Minimo para a ficha existir. Duas fichas chegaram com o relato VAZIO porque a
# tela exigia o proximo passo e nao exigia o relato - o acessorio travava e o
# essencial passava.
RELATO_OBRIGATORIO_MIN = 40

# Por onde a interacao aconteceu. Video chamada e uma versao da visita
# presencial - ve o cliente, ve a loja, conversa de verdade. Telefone e mais
# curto por natureza, e cobrar dele o mesmo preenchimento da visita presencial
# so faria o representante deixar de registrar o contato.
CANAIS_VISITA = [
    {"id": "presencial", "rot": "Presencial", "dica": "estive na loja do cliente"},
    {"id": "video", "rot": "Video chamada", "dica": "conversa por video, com o cliente na tela"},
    {"id": "telefone", "rot": "Telefone / WhatsApp", "dica": "contato rapido, sem ver o cliente"},
]
CANAIS_VALIDOS = tuple(c["id"] for c in CANAIS_VISITA)
CANAIS_REMOTOS = ("telefone", "video")
CANAL_PADRAO = "presencial"

# No telefone o relato e mais curto por natureza: o contato tambem e.
RELATO_MIN_TELEFONE = 20

# Visita de relacionamento nem sempre deixa pendencia. Obrigar um proximo passo
# aqui so produzia texto de fachada ("manter contato") com data do proprio dia.
# Nesses tipos ele escreve o passo real OU declara que nao ficou nada pendente.
# Em cadastro o proximo passo e de outra pessoa (atualizar o ERP) e ja esta
# registrado na ocorrencia - exigir aqui so produziria texto de enfeite.
TIPOS_PASSO_OPCIONAL = ("cordialidade", "cadastro")

PROBLEMAS_TECNICOS = [
    "Arranhao", "Ralado", "Quebra espontanea", "Avaria da peca",
    "Troca de etiqueta", "Mancha", "Erro de fabricacao",
    "Quantidade errada", "Outros",
]

RESPONSAVEIS = {
    "Representante": ["Sipiao"],
    "Gerentes": ["Marcia (Itz)", "Alessandra (Bel)", "Jair (Sti)"],
    "Consultores Itz": ["Ariana", "Ellen", "Nathielly", "Patricia", "Rafaela",
                        "Keliane (aluminio)"],
    "Consultores Bel": ["Clicia", "Jessica"],
    "Consultores Sti": ["Jadson", "Thayna"],
    "Areas": ["Cadastro", "Gerente de Producao", "PCP", "Qualidade",
              "Expedicao", "Financeiro", "Diretoria"],
}

ETAPAS_JORNADA = [
    "Relacionamento geral", "Preco e condicao", "Prazo de producao",
    "Prazo de entrega", "Qualidade da entrega", "Qualidade do produto",
    "Pos-venda e resolucao de problemas", "Atendimento comercial",
    "Atendimento da expedicao",
]

METRICA_POR_ETAPA = {
    "Relacionamento geral": "nps",
    "Pos-venda e resolucao de problemas": "ces",
    "Pos-venda e resolucao de problema": "ces",
    "Preco e condicao": "csat",
    "Prazo de producao": "csat",
    "Prazo de entrega": "csat",
    "Prazo prometido": "csat",
    "Producao e acabamento": "csat",
    "Qualidade da entrega": "csat",
    "Entrega": "csat",
    "Qualidade do produto": "csat",
    "Atendimento comercial": "csat",
    "Atendimento da expedicao": "csat",
    "Cotacao e orcamento": "csat",
}

NPS_PROMOTOR, NPS_DETRATOR = 9, 6
CSAT_SATISFEITO = 8
CES_FACIL = 8

PERGUNTA_EXPERIENCIA = {
    "comercial": ("Atendimento comercial", "Como voce avalia o nosso atendimento comercial?"),
    "cordialidade": ("Relacionamento geral", "De 0 a 10, o quanto recomendaria a EM Vidros?"),
    "tecnica": ("Pos-venda e resolucao de problemas", "De 0 a 10, o quanto foi FACIL resolver esse problema com a gente?"),
    "prospeccao": ("Relacionamento geral", "O que te faria comprar da EM Vidros?"),
    "preco": ("Preco e condicao", "Como avalia nosso preco frente ao prazo e a entrega?"),
    "voz": ("Relacionamento geral", "De 0 a 10, o quanto recomendaria a EM Vidros?"),
    "evento": ("Relacionamento geral", "Como a EM Vidros e vista no mercado hoje?"),
}

# Cesta fixa de comparacao. "Eng" e sob medida personalizada; "pad" e peca
# pronta em medida padrao. TODOS os precos sao em R$/m2 - inclusive os padrao,
# senao box e chapa nao se comparam.
CESTA_PRECO = [
    {"grupo": "Engenharia (sob medida)", "item": "Inc 6 Eng"},
    {"grupo": "Engenharia (sob medida)", "item": "Inc 8 Eng"},
    {"grupo": "Engenharia (sob medida)", "item": "Inc 10 Eng"},
    {"grupo": "Engenharia (sob medida)", "item": "Fume/Verde 8 Eng"},
    {"grupo": "Engenharia (sob medida)", "item": "Fume/Verde 10 Eng"},
    {"grupo": "Padrao (peca pronta)", "item": "Box Inc pad"},
    {"grupo": "Padrao (peca pronta)", "item": "Jan/Porta Inc pad"},
    {"grupo": "Padrao (peca pronta)", "item": "Porta Inc 10 pad"},
    {"grupo": "Padrao (peca pronta)", "item": "Box Fume/Verde pad"},
    {"grupo": "Padrao (peca pronta)", "item": "Jan/Porta Fume/Verde pad"},
]

UNIDADE_PRECO = "R$/m2"

# Lista fechada de proposito: com nome digitado a mao, "Globo", "globo" e
# "Vidros Globo" viram tres concorrentes e nada se compara ao longo do tempo.
# "Outro" abre campo livre para o que ainda nao esta aqui.
CONCORRENTES = [
    "Globo", "Vitral Lux", "Amazon Maraba", "MT", "Di Cristal", "Temper",
    "Vitoria", "Amazon Temper THE", "TPV", "GlassMaxi", "Bandeirantes",
    "Audiolar", "Alupa", "HF", "Quality", "DVN", "NortGlass", "MGG",
    "Marvite", "Perfal", "Outro",
]

TIPOS_EVIDENCIA = [
    "Proposta ou orcamento do concorrente",
    "Conversa do cliente com o concorrente",
    "Material ou produto do concorrente",
    "Tabela de preco",
    "Foto do local ou da peca",
    "Outro",
]

PROCESSOS_CSAT = [
    {"item": "Preco e condicao"},
    {"item": "Prazo de producao"},
    {"item": "Prazo de entrega"},
    {"item": "Qualidade da entrega"},
    {"item": "Qualidade do produto"},
    {"item": "Pos-venda e resolucao de problemas"},
    {"item": "Atendimento comercial"},
    {"item": "Atendimento da expedicao",
     "condicional": "So se o cliente retira na expedicao",
     "unidades": ["Imperatriz", "Santa Ines", "Ananindeua"]},
]

EXPEDICOES = ["Imperatriz", "Santa Ines", "Ananindeua"]

ROTAS_FORA_DA_BASE = {"sao luis", "sao luis/ma", "teresina", "bacabal",
                      "angelim", "guajajaras"}

DIAS_MINIMOS_ENTRE_NPS = 90

CANAIS = ["Visita do representante", "Balcao da loja", "Telefone", "WhatsApp",
          "E-mail", "Entrega", "Outro"]

SETORES = ["Comercial", "Recepcao", "Expedicao", "Producao", "Qualidade",
           "Financeiro", "Assistencia tecnica"]

STATUS_OCORRENCIA = ["aberta", "em_andamento", "resolvida"]

PAPEIS = ("rep", "gestor", "admin")
PAPEIS_GESTAO = ("gestor", "admin")

LIMITES_TEXTO = {
    "cliente_nome": 200, "municipio": 120, "objetivo": 400, "relato": 5000,
    "proximo_passo": 600, "prox_responsavel": 120, "prox_data": 20,
    "encaminhado_para": 120, "criado_em_disp": 40, "app_versao": 20,
    "problema_tipo": 60, "exp_etapa": 60, "exp_comentario": 1200,
}
MAX_EXTRA_JSON = 20000
MAX_ANEXOS = 3
MAX_ARQUIVO_IMPORTACAO = 6 * 1024 * 1024

SENHA_MIN = 8
MAX_TENTATIVAS_LOGIN = 8

CICLO_IMPERATRIZ = 90
CICLO_MIGRACAO = 120
CICLO_PARA = 180
CICLO_PADRAO = 120
