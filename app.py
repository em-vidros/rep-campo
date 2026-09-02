# -*- coding: utf-8 -*-
"""
REP Campo - registro de visitas do representante comercial (base Itz).
Flask + Postgres. PWA offline-first, publicado na Vercel.

O esquema do banco mora no setup_db.py, nao aqui. O app nunca cria tabela, porque
a funcao da Vercel sobe em varios processos ao mesmo tempo e o CREATE do Postgres
toma trava exclusiva.

Padroes seguidos (EMVIDROS_TECH_PADROES.md):
  - prints em ASCII puro
  - sem senha em texto claro no codigo
"""
import base64
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from functools import wraps

import psycopg
import requests
from flask import (Flask, Response, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def carregar_env():
    """Le o .env do projeto no teste local. Na Vercel as variaveis ja vem prontas."""
    caminho = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(caminho):
        return
    for linha in open(caminho, encoding="utf-8"):
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


carregar_env()

TIPOS = {
    "comercial":    {"label": "Comercial",            "foto": "opcional"},
    "cordialidade": {"label": "Cordialidade",         "foto": "opcional"},
    "tecnica":      {"label": "Tecnica/Reclamacao",   "foto": "obrigatoria"},
    "prospeccao":   {"label": "Prospeccao",           "foto": "obrigatoria"},
    "preco":        {"label": "Pesquisa de preco",    "foto": "obrigatoria"},
    "voz":          {"label": "Voz do cliente",       "foto": "opcional"},
    "evento":       {"label": "Evento",               "foto": "obrigatoria"},
}

# Municipios que migram da base Rap para a base Itz em 01/09/2026
MUNICIPIOS_MIGRACAO = [
    "Santa Ines/MA", "Ze Doca/MA", "Bom Jardim/MA", "Governador Newton Belo/MA",
    "Moncao/MA", "Igarape do Meio/MA", "Pindare-Mirim/MA", "Pio XII/MA",
]

RELATO_MIN = 200  # caracteres - regra do manual (§5.1)

# Ocorrencias tecnicas mais comuns (definidas pelo Ricardo em 02/09/2026).
# "etiqueta trocada" e "troca de etiqueta" eram a mesma coisa - unificadas.
PROBLEMAS_TECNICOS = [
    "Arranhao",
    "Ralado",
    "Quebra espontanea",
    "Avaria da peca",
    "Troca de etiqueta",
    "Mancha",
    "Erro de fabricacao",
    "Quantidade errada",
    "Outros",
]

# Quem pode receber um encaminhamento. Fonte: EMVIDROS_COMERCIAL_ESTRUTURA.md
# (recorte da base Itz pos-migracao da Sti em 01/09/2026) + cargos de apoio.
RESPONSAVEIS = {
    "Representante": ["Sipiao"],
    "Gerentes": ["Marcia (Itz)", "Alessandra (Bel)", "Jair (Sti)"],
    "Consultores Itz": ["Ariana", "Ellen", "Nathielly", "Patricia", "Rafaela",
                        "Keliane (aluminio)"],
    "Consultores Bel": ["Clicia", "Jessica"],
    "Consultores Sti": ["Jadson", "Thayna"],
    "Areas": ["Gerente de Producao", "PCP", "Qualidade", "Expedicao",
              "Financeiro", "Diretoria"],
}

# Etapas da jornada de compra - o que a pesquisa de experiencia avalia.
ETAPAS_JORNADA = [
    "Relacionamento geral",
    "Preco e condicao",
    "Prazo de producao",
    "Prazo de entrega",
    "Qualidade da entrega",
    "Qualidade do produto",
    "Pos-venda e resolucao de problemas",
    "Atendimento comercial",
    "Atendimento da expedicao",
]


# Cada etapa da jornada tem a metrica certa. Misturar as tres e chamar tudo
# de NPS produz media com nome errado - e contamina o NPS relacional da
# pesquisa CX formal, que mede outra coisa.
#   NPS  = lealdade a marca ("recomendaria?"), baixa frequencia
#   CSAT = satisfacao com UMA etapa ("como foi essa entrega?")
#   CES  = esforco do cliente ("foi facil resolver?"), melhor em pos-venda
METRICA_POR_ETAPA = {
    "Relacionamento geral": "nps",
    "Pos-venda e resolucao de problemas": "ces",
    "Pos-venda e resolucao de problema": "ces",     # nome antigo, ja gravado
    "Preco e condicao": "csat",
    "Prazo de producao": "csat",
    "Prazo de entrega": "csat",
    "Prazo prometido": "csat",                      # nome antigo
    "Producao e acabamento": "csat",                # nome antigo
    "Qualidade da entrega": "csat",
    "Entrega": "csat",                              # nome antigo, ja gravado
    "Qualidade do produto": "csat",
    "Atendimento comercial": "csat",
    "Atendimento da expedicao": "csat",
    "Cotacao e orcamento": "csat",                  # nome antigo
}


# Corte de cada metrica na regua unica de 0 a 10 (o REP nao decora escalas).
NPS_PROMOTOR, NPS_DETRATOR = 9, 6
CSAT_SATISFEITO = 8          # top-2-box
CES_FACIL = 8

# A pergunta muda conforme o tipo de visita - pesquisa pertinente a situacao.
PERGUNTA_EXPERIENCIA = {
    "comercial":    ("Atendimento comercial", "Como voce avalia o nosso atendimento comercial?"),
    "cordialidade": ("Relacionamento geral", "De 0 a 10, o quanto recomendaria a EM Vidros?"),
    "tecnica":      ("Pos-venda e resolucao de problemas", "De 0 a 10, o quanto foi FACIL resolver esse problema com a gente?"),
    "prospeccao":   ("Relacionamento geral", "O que te faria comprar da EM Vidros?"),
    "preco":        ("Preco e condicao", "Como avalia nosso preco frente ao prazo e a entrega?"),
    "voz":          ("Relacionamento geral", "De 0 a 10, o quanto recomendaria a EM Vidros?"),
    "evento":       ("Relacionamento geral", "Como a EM Vidros e vista no mercado hoje?"),
}

# Cesta fixa do radar de preco (definida pelo Ricardo em 02/09/2026).
# Fixa de proposito: se cada mes vier item diferente, nao da para comparar
# mes a mes - que e justamente o objetivo do radar.
CESTA_PRECO = [
    {"grupo": "Engenharia", "item": "Inc 6 Eng"},
    {"grupo": "Engenharia", "item": "Inc 8 Eng"},
    {"grupo": "Engenharia", "item": "Inc 10 Eng"},
    {"grupo": "Engenharia", "item": "Fume/Verde 8 Eng"},
    {"grupo": "Padrao", "item": "Box Inc 8 pad"},
    {"grupo": "Padrao", "item": "Jan Inc 8 pad"},
    {"grupo": "Padrao", "item": "Porta Inc 8 pad"},
    {"grupo": "Padrao", "item": "Box Fume/Verde 8 pad"},
    {"grupo": "Padrao", "item": "Jan Fume/Verde 8 pad"},
    {"grupo": "Padrao", "item": "Porta Fume/Verde 8 pad"},
]

# Tipos de evidencia que o REP pode anexar (varias por ficha).
TIPOS_EVIDENCIA = [
    "Proposta ou orcamento do concorrente",
    "Conversa do cliente com o concorrente",
    "Material ou produto do concorrente",
    "Tabela de preco",
    "Foto do local ou da peca",
    "Outro",
]

# A visita "Voz do cliente" E a pesquisa - por isso avalia os processos da
# empresa inteiros, e nao so uma etapa como as demais visitas.
PROCESSOS_CSAT = [
    {"item": "Preco e condicao"},
    {"item": "Prazo de producao"},
    {"item": "Prazo de entrega"},
    {"item": "Qualidade da entrega"},
    {"item": "Qualidade do produto"},
    {"item": "Pos-venda e resolucao de problemas"},
    {"item": "Atendimento comercial"},
    # Nem todo cliente retira no balcao - por isso condicional. E as tres
    # expedicoes sao operacoes diferentes, entao a nota guarda qual foi.
    {"item": "Atendimento da expedicao",
     "condicional": "So se o cliente retira na expedicao",
     "unidades": ["Imperatriz", "Santa Ines", "Ananindeua"]},
]

EXPEDICOES = ["Imperatriz", "Santa Ines", "Ananindeua"]

# Rotas que NAO pertencem a base Itz (fonte: reference_rotas_tabelas /
# EMVIDROS_COMERCIAL_ESTRUTURA). Cliente com rota destas na carteira Itz e
# falha de cadastro - o REP da base Itz nao vai visitar. Fica na carteira,
# mas sai do planejamento de viagem. Nada e apagado.
ROTAS_FORA_DA_BASE = {"sao luis", "sao luis/ma", "teresina", "bacabal",
                      "angelim", "guajajaras"}


def _fora_da_base(rota):
    return _norm(rota) in ROTAS_FORA_DA_BASE


# NPS cansa se perguntado toda visita. CSAT e CES podem ser sempre.
DIAS_MINIMOS_ENTRE_NPS = 90

# --------------------------------------------------------------------------
# Ocorrencias: por onde o cliente reclamou e quem registrou.
# Hoje so a visita do REP abre ocorrencia. O modelo ja nasce preparado para
# recepcao, vendedor no balcao, expedicao etc. abrirem tambem - por isso a
# ocorrencia e tabela propria, e nao um campo dentro da ficha de visita.
# --------------------------------------------------------------------------
CANAIS = ["Visita do representante", "Balcao da loja", "Telefone", "WhatsApp",
          "E-mail", "Entrega", "Outro"]

SETORES = ["Comercial", "Recepcao", "Expedicao", "Producao", "Qualidade",
           "Financeiro", "Assistencia tecnica"]

STATUS_OCORRENCIA = ["aberta", "em_andamento", "resolvida"]


def _secret_key():
    # Sem disco e sem chave sorteada na partida: cada instancia da Vercel sortearia
    # uma diferente e o login de uma nao valeria na outra. Faltando a variavel, o
    # app tem que morrer alto, nao inventar chave.
    chave = os.environ.get("REP_SECRET_KEY")
    if not chave:
        raise RuntimeError("REP_SECRET_KEY nao definida nas variaveis de ambiente")
    return chave


# root_path/instance_path explicitos: sem isso o Flask chama os.getcwd(), que
# falha quando o processo herda um cwd sem permissao de leitura (Google Drive
# no macOS). Deixa o app independente do diretorio de onde foi iniciado.
app = Flask(__name__, root_path=BASE_DIR,
            instance_path=os.path.join(BASE_DIR, "instance"))
app.secret_key = _secret_key()
app.config.update(
    # A borda da Vercel recusa acima de 4,5 MB com um 413 que o Flask nem ve.
    # Manter abaixo disso faz o limite ser nosso, com resposta que o app controla.
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,           # 4 MB por requisicao
    SESSION_COOKIE_HTTPONLY=True,                 # JS da pagina nao le o cookie
    SESSION_COOKIE_SAMESITE="Lax",                # corta CSRF entre sites
    # Secure exige HTTPS. Fica desligado so no teste local por HTTP.
    SESSION_COOKIE_SECURE=os.environ.get("REP_INSECURE_COOKIE") != "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

# Limites de tamanho por campo de texto - impede inflar o banco de proposito
LIMITES_TEXTO = {
    "cliente_nome": 200, "municipio": 120, "objetivo": 400, "relato": 5000,
    "proximo_passo": 600, "prox_responsavel": 120, "prox_data": 20,
    "encaminhado_para": 120, "criado_em_disp": 40, "app_versao": 20,
    "problema_tipo": 60, "exp_etapa": 60, "exp_comentario": 1200,
}
MAX_EXTRA_JSON = 20000          # bytes do bloco "extra" ja serializado

# Formato de uuid aceito. O nome do arquivo de foto e derivado dele, entao
# qualquer coisa fora disso viraria escrita de arquivo em caminho arbitrario.
RE_UUID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")


# --------------------------------------------------------------------------
# Banco
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL nao definida nas variaveis de ambiente")
        # prepare_threshold=None porque a URL aponta para o pooler do Neon, que
        # roda em modo transacao e nao guarda prepared statement entre requisicoes.
        g.db = psycopg.connect(url, row_factory=dict_row, prepare_threshold=None)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# O esquema mora no setup_db.py. Aqui ficou so o comentario para quem procurar
# CREATE TABLE neste arquivo e nao achar.



# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def login_obrigatorio(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if "uid" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"erro": "nao_autenticado"}), 401
            return redirect(url_for("login", next=request.path))
        return fn(*a, **kw)
    return wrapper


def gestor_obrigatorio(fn):
    """Rotas de gestao: so papel 'gestor'. REP nunca ve ficha de outro."""
    @wraps(fn)
    def wrapper(*a, **kw):
        if "uid" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"erro": "nao_autenticado"}), 401
            return redirect(url_for("login", next=request.path))
        if session.get("papel") != "gestor":
            if request.path.startswith("/api/"):
                return jsonify({"erro": "sem_permissao"}), 403
            return redirect(url_for("index"))
        return fn(*a, **kw)
    return wrapper


# Freio de forca bruta no login. Mora no banco, nao na memoria: cada requisicao da
# Vercel pode cair num processo diferente, e um contador de processo nunca chega
# ao limite.
MAX_TENTATIVAS = 8
JANELA_BLOQUEIO = timedelta(minutes=15)


def _origem():
    # Atras do proxy da Vercel, remote_addr e sempre o proxy. O IP do visitante
    # vem no X-Forwarded-For, primeiro da lista.
    encaminhado = request.headers.get("X-Forwarded-For", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()[:60]
    return (request.remote_addr or "?")[:60]


def _bloqueado(chave):
    row = get_db().execute(
        "SELECT falhas, ultima FROM tentativas_login WHERE origem = %s",
        (chave,)).fetchone()
    if not row:
        return False
    if datetime.now(timezone.utc) - row["ultima"] > JANELA_BLOQUEIO:
        return False
    return row["falhas"] >= MAX_TENTATIVAS


def _registrar_falha(chave):
    db = get_db()
    db.execute(
        "INSERT INTO tentativas_login (origem, falhas, ultima) VALUES (%s, 1, %s) "
        "ON CONFLICT (origem) DO UPDATE SET "
        "  falhas = CASE WHEN tentativas_login.ultima < %s THEN 1 "
        "                ELSE tentativas_login.falhas + 1 END, "
        "  ultima = EXCLUDED.ultima",
        (chave, datetime.now(timezone.utc),
         datetime.now(timezone.utc) - JANELA_BLOQUEIO))
    db.commit()


def _limpar_falhas(chave):
    db = get_db()
    db.execute("DELETE FROM tentativas_login WHERE origem = %s", (chave,))
    db.commit()


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        if _bloqueado(_origem()):
            return render_template(
                "login.html",
                erro="Muitas tentativas. Tente de novo em 15 minutos."), 429
        login_txt = (request.form.get("login") or "").strip().lower()
        senha = request.form.get("senha") or ""
        row = get_db().execute(
            "SELECT * FROM usuarios WHERE login = %s AND ativo = 1", (login_txt,)
        ).fetchone()
        if row and check_password_hash(row["senha_hash"], senha):
            _limpar_falhas(_origem())
            session.clear()                 # sessao nova a cada login
            session.permanent = True
            session["uid"] = row["id"]
            session["login"] = row["login"]
            session["nome"] = row["nome"]
            session["papel"] = row["papel"]
            destino = request.args.get("next") or url_for("index")
            if not destino.startswith("/"):
                destino = url_for("index")
            return redirect(destino)
        _registrar_falha(_origem())
        erro = "Login ou senha invalidos."
    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
@app.route("/")
@login_obrigatorio
def index():
    return render_template("index.html", nome=session.get("nome"),
                           papel=session.get("papel"), tipos=TIPOS)


@app.route("/sw.js")
def service_worker():
    resp = send_from_directory(os.path.join(BASE_DIR, "static"), "sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "manifest.webmanifest")


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
@app.route("/api/bootstrap")
@login_obrigatorio
def api_bootstrap():
    """Pacote que o app guarda no celular para funcionar offline."""
    db = get_db()
    clientes = [dict(r) for r in db.execute(
        "SELECT codigo, nome, cidade, curva, vol_12m, rota, vendedor "
        "FROM clientes WHERE ativo = 1 ORDER BY nome"
    ).fetchall()]
    municipios = sorted({c["cidade"] for c in clientes if c["cidade"]} |
                        set(MUNICIPIOS_MIGRACAO))
    return jsonify({
        "usuario": {"login": session["login"], "nome": session["nome"],
                    "papel": session["papel"]},
        "clientes": clientes,
        "municipios": municipios,
        "tipos": TIPOS,
        "problemas": PROBLEMAS_TECNICOS,
        "responsaveis": RESPONSAVEIS,
        "cesta_preco": CESTA_PRECO,
        "processos_csat": PROCESSOS_CSAT,
        "expedicoes": EXPEDICOES,
        "tipos_evidencia": TIPOS_EVIDENCIA,
        "max_anexos": MAX_ANEXOS,
        "etapas_jornada": ETAPAS_JORNADA,
        "metrica_por_etapa": METRICA_POR_ETAPA,
        "dias_minimos_nps": DIAS_MINIMOS_ENTRE_NPS,
        "ultimo_nps": {r["cliente_codigo"]: r["quando"] for r in db.execute(
            "SELECT cliente_codigo, MAX(recebido_em) quando FROM fichas "
            "WHERE exp_metrica = 'nps' AND cliente_codigo IS NOT NULL "
            "GROUP BY cliente_codigo")},
        "pergunta_experiencia": PERGUNTA_EXPERIENCIA,
        "relato_min": RELATO_MIN,
        "gerado_em": _agora(),
    })


def _agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _float(valor):
    """AVG e ROUND devolvem Decimal no psycopg, e o Flask serializa Decimal como
    texto. A tela receberia "8.5" no lugar de 8.5 e a primeira conta viraria
    concatenacao."""
    return float(valor) if valor is not None else None


def _media_float(d):
    if "media" in d:
        d["media"] = _float(d["media"])
    return d


def _inteiro(valor, padrao):
    """int() de parametro de URL sem derrubar a rota. %slimite=abc dava 500."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def _slug(txt):
    txt = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", txt).strip("-").lower()[:40] or "sem-nome"


# assinatura dos formatos aceitos - so JPEG e PNG sobem para o Blob
ASSINATURAS = ((b"\xff\xd8\xff", "jpg"), (b"\x89PNG\r\n\x1a\n", "png"))


# --------------------------------------------------------------------------
# Fotos no Vercel Blob
# --------------------------------------------------------------------------
# A loja esta configurada como privada: quem pedir a URL sem o token recebe 403.
# Isso importa porque a foto vem com a coordenada de GPS do cliente na mesma
# ficha. O app le a foto pelo servidor e devolve para quem esta logado.
BLOB_API = "https://blob.vercel-storage.com"
BLOB_PASTA = "fotos/"
BLOB_VERSAO = "7"          # a 11 e a 12 recusam a loja privada com "Invalid pathname"
_BLOB_BASE = {}            # host da loja, aprendido na primeira chamada


def _blob_token():
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN nao definida nas variaveis de ambiente")
    return token


def _blob_cabecalho(extra=None):
    h = {"Authorization": "Bearer " + _blob_token(), "x-api-version": BLOB_VERSAO}
    h.update(extra or {})
    return h


def _blob_gravar(nome, binario, tipo):
    r = requests.put(
        BLOB_API + "/" + BLOB_PASTA + nome,
        headers=_blob_cabecalho({"x-content-type": tipo,
                                 "x-vercel-blob-access": "private",
                                 "x-add-random-suffix": "0",
                                 "x-allow-overwrite": "1"}),
        data=binario, timeout=25)
    if r.status_code != 200:
        return None
    url = r.json().get("url") or ""
    if url:
        _BLOB_BASE["url"] = url[:-len(BLOB_PASTA + nome)]
    return nome


def _blob_endereco(nome):
    """URL de leitura da foto. Pergunta ao Blob uma vez por processo e guarda o host."""
    base = _BLOB_BASE.get("url")
    if base:
        return base + BLOB_PASTA + nome
    r = requests.get(BLOB_API + "/", params={"prefix": BLOB_PASTA + nome, "limit": "1"},
                     headers=_blob_cabecalho(), timeout=20)
    if r.status_code != 200:
        return None
    blobs = r.json().get("blobs") or []
    if not blobs:
        return None
    url = blobs[0]["url"]
    _BLOB_BASE["url"] = url[:-len(BLOB_PASTA + nome)]
    return url


def _blob_ler(nome):
    url = _blob_endereco(nome)
    if not url:
        return None, None
    r = requests.get(url, headers={"Authorization": "Bearer " + _blob_token()}, timeout=25)
    if r.status_code != 200:
        return None, None
    return r.content, r.headers.get("content-type", "application/octet-stream")


def _salvar_foto(uuid_ficha, data_url):
    """Sobe a foto para o Blob. Retorna o nome do arquivo, ou None se recusar.

    O nome sai do uuid, que vem do celular, por isso o uuid ja chega validado por
    RE_UUID. Sem barra no nome: a rota /foto so aceita nome sem caminho.
    """
    if not data_url or "," not in data_url:
        return None
    if not RE_UUID.match(uuid_ficha or ""):
        return None
    _, b64 = data_url.split(",", 1)
    try:
        binario = base64.b64decode(b64, validate=True)
    except Exception:
        return None
    # 6 MB numa foto so nao cabe: o limite de corpo da requisicao inteira e 4 MB.
    if len(binario) > 1024 * 1024:
        return None

    # a extensao vem do conteudo, nao do que o cliente declarou no cabecalho
    ext = next((e for assinatura, e in ASSINATURAS if binario.startswith(assinatura)), None)
    if ext is None:
        return None

    nome = "%s.%s" % (uuid_ficha, ext)
    if not re.fullmatch(r"[A-Za-z0-9_\-]+\.(jpg|png)", nome):
        return None                      # cinto e suspensorio: nome sem barra
    return _blob_gravar(nome, binario, "image/jpeg" if ext == "jpg" else "image/png")


# 8 evidencias mais a foto principal davam 3 MB numa ficha so, acima do que a
# Vercel aceita por requisicao.
MAX_ANEXOS = 3


def _salvar_anexos(uuid_ficha, lista, db):
    """Grava as evidencias extras da ficha. Mesma validacao da foto principal:
    nome derivado do uuid ja validado, tipo conferido pela assinatura."""
    if not isinstance(lista, list):
        return 0
    gravados = 0
    for i, a in enumerate(lista[:MAX_ANEXOS]):
        if not isinstance(a, dict):
            continue
        nome = _salvar_foto("%s-anexo%d" % (uuid_ficha, i), a.get("foto"))
        if not nome:
            continue
        db.execute("INSERT INTO anexos (ficha_uuid, arquivo, tipo, descricao, criado_em)"
                   " VALUES (%s,%s,%s,%s,%s)",
                   (uuid_ficha, nome, str(a.get("tipo") or "")[:80] or None,
                    str(a.get("descricao") or "")[:300] or None, _agora()))
        gravados += 1
    return gravados


def _texto(ficha, campo):
    """Le um campo de texto da ficha ja cortado no limite."""
    v = ficha.get(campo)
    if v is None:
        return None
    return str(v)[:LIMITES_TEXTO.get(campo, 500)]


def _num(v):
    """Coordenadas so entram como numero - texto vira None."""
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _proxima_ocorrencia(db):
    """Numero sequencial por ano: OC-2026-0001.

    Gerado no SERVIDOR, nao no celular: o aparelho pode estar offline e dois
    aparelhos gerariam o mesmo numero. O app mostra o numero depois do sync.

    O numero sai de uma linha por ano na tabela contador_ocorrencias, incrementada
    dentro do proprio INSERT. Ler o maior numero e somar 1 dava o mesmo numero para
    duas instancias da Vercel atendendo dois representantes no mesmo segundo.
    """
    ano = datetime.now(timezone.utc).strftime("%Y")
    row = db.execute(
        "INSERT INTO contador_ocorrencias (ano, ultimo) VALUES (%s, 1) "
        "ON CONFLICT (ano) DO UPDATE SET ultimo = contador_ocorrencias.ultimo + 1 "
        "RETURNING ultimo", (ano,)).fetchone()
    return "OC-%s-%04d" % (ano, row["ultimo"])


def _classificar(ficha, tem_foto):
    """Nivel de evidencia conforme o manual §4. Nunca rejeita - classifica."""
    tem_geo = ficha.get("lat") is not None and ficha.get("lon") is not None
    tem_passo = bool((ficha.get("proximo_passo") or "").strip())
    if tem_foto and tem_geo:
        nivel = "forte"
    elif tem_geo and tem_passo:
        nivel = "media"
    else:
        nivel = "leve"
    return nivel, tem_passo


@app.route("/api/fichas", methods=["POST"])
@login_obrigatorio
def api_receber_fichas():
    """Recebe um lote de fichas da fila offline. Idempotente por uuid."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("fichas"), list):
        return jsonify({"erro": "payload_invalido"}), 400

    db = get_db()
    aceitas, rejeitadas, ocorrencias = [], [], []

    for ficha in payload["fichas"][:50]:
        uuid_f = (ficha.get("uuid") or "").strip()
        tipo = (ficha.get("tipo") or "").strip()
        cliente_nome = (ficha.get("cliente_nome") or "").strip()[:200]

        if not uuid_f or tipo not in TIPOS or not cliente_nome:
            rejeitadas.append({"uuid": uuid_f[:64], "motivo": "campos_obrigatorios"})
            continue
        if not RE_UUID.match(uuid_f):
            rejeitadas.append({"uuid": uuid_f[:64], "motivo": "uuid_invalido"})
            continue

        # idempotencia: ja recebida em sync anterior -> confirma sem duplicar
        if db.execute("SELECT 1 FROM fichas WHERE uuid = %s", (uuid_f,)).fetchone():
            aceitas.append(uuid_f)
            continue

        foto_arq = _salvar_foto(uuid_f, ficha.get("foto"))
        nivel, tem_passo = _classificar(ficha, bool(foto_arq))
        relato = (ficha.get("relato") or "").strip()[:LIMITES_TEXTO["relato"]]

        etapa = _texto(ficha, "exp_etapa")
        metrica = METRICA_POR_ETAPA.get(etapa or "", "csat") if etapa else None

        nota = ficha.get("exp_nota")
        try:
            nota = int(nota) if nota not in (None, "") else None
            if nota is not None and not (0 <= nota <= 10):
                nota = None
        except (TypeError, ValueError):
            nota = None

        # Uma ficha por transacao. No Postgres o primeiro erro aborta a transacao
        # inteira, e sem isto uma nota fora de faixa na setima ficha jogaria fora
        # as seis que ja tinham entrado.
        try:
            with db.transaction():
                # visita tecnica abre ocorrencia numerada, para ser acompanhada
                ocorrencia = _proxima_ocorrencia(db) if tipo == "tecnica" else None
                status_oc = "aberta" if ocorrencia else None
                db.execute("""
                    INSERT INTO fichas (uuid, usuario_id, usuario_login, tipo, cliente_codigo,
                        cliente_nome, prospect, municipio, objetivo, relato, proximo_passo,
                        prox_responsavel, prox_data, encaminhado_para, lat, lon, precisao,
                        criado_em_disp, recebido_em, foto_arquivo, extra_json,
                        nivel_evidencia, conta_indicador, relato_curto, app_versao,
                        problema_tipo, ocorrencia_num, ocorrencia_status,
                        exp_etapa, exp_nota, exp_comentario, exp_metrica)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    uuid_f, session["uid"], session["login"], tipo,
                    str(ficha.get("cliente_codigo") or "")[:40] or None, cliente_nome,
                    1 if ficha.get("prospect") else 0,
                    _texto(ficha, "municipio"), _texto(ficha, "objetivo"), relato,
                    _texto(ficha, "proximo_passo"), _texto(ficha, "prox_responsavel"),
                    _texto(ficha, "prox_data"), _texto(ficha, "encaminhado_para"),
                    _num(ficha.get("lat")), _num(ficha.get("lon")), _num(ficha.get("precisao")),
                    _texto(ficha, "criado_em_disp"), _agora(), foto_arq,
                    json.dumps(ficha.get("extra") or {}, ensure_ascii=False)[:MAX_EXTRA_JSON],
                    nivel, 1 if tem_passo else 0,
                    1 if len(relato) < RELATO_MIN else 0,
                    _texto(ficha, "app_versao"),
                    _texto(ficha, "problema_tipo"), ocorrencia, status_oc,
                    etapa, nota, _texto(ficha, "exp_comentario"), metrica,
                ))
                if ocorrencia:
                    extra = ficha.get("extra") or {}
                    db.execute("""
                        INSERT INTO ocorrencias
                            (numero, aberta_em, aberta_por, setor, canal, cliente_codigo,
                             cliente_nome, municipio, tipo, descricao, pedido_nf, status,
                             responsavel, prazo, ficha_uuid, foto_arquivo)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'aberta',%s,%s,%s,%s)
                        ON CONFLICT (numero) DO NOTHING
                    """, (ocorrencia, _agora(), session["login"], "Comercial",
                          "Visita do representante",
                          str(ficha.get("cliente_codigo") or "")[:40] or None, cliente_nome,
                          _texto(ficha, "municipio"), _texto(ficha, "problema_tipo"),
                          relato, str(extra.get("pedido_nf") or "")[:60] or None,
                          _texto(ficha, "prox_responsavel"), _texto(ficha, "prox_data"),
                          uuid_f, foto_arq))

                # respostas de experiencia: 1 nas visitas comuns, varias na Voz do Cliente
                respostas = ficha.get("experiencia")
                if not isinstance(respostas, list):
                    respostas = ([{"etapa": etapa, "nota": nota,
                                   "comentario": ficha.get("exp_comentario")}]
                                 if etapa and nota is not None else [])
                for resp in respostas[:12]:
                    et = str(resp.get("etapa") or "")[:60]
                    try:
                        nt = int(resp.get("nota"))
                    except (TypeError, ValueError):
                        continue
                    if not et or not (0 <= nt <= 10):
                        continue
                    uni = str(resp.get("unidade") or "")[:40] or None
                    db.execute("""INSERT INTO experiencia (ficha_uuid, cliente_codigo,
                        cliente_nome, etapa, metrica, nota, comentario, unidade,
                        registrado_em, usuario_login) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (uuid_f, str(ficha.get("cliente_codigo") or "")[:40] or None,
                         cliente_nome, et, METRICA_POR_ETAPA.get(et, "csat"), nt,
                         str(resp.get("comentario") or "")[:1200] or None, uni,
                         _agora(), session["login"]))

                # se o cliente estava no roteiro de uma viagem aberta, marca visitado.
                # E o que alimenta a aderencia ao roteiro sem digitacao extra.
                cod = str(ficha.get("cliente_codigo") or "")[:40]
                if cod:
                    # so no roteiro de quem registrou a visita. Sem o filtro por
                    # dono, a visita de um marcava o cliente como visitado na
                    # viagem aberta de todos os outros representantes.
                    db.execute("""
                        UPDATE viagem_clientes SET visitado = 1, ficha_uuid = %s, visitado_em = %s
                         WHERE visitado = 0 AND cliente_codigo = %s AND viagem_id IN (
                               SELECT id FROM viagens
                                WHERE status IN ('planejada','em_andamento')
                                  AND (criada_por = %s OR responsavel = %s))
                    """, (uuid_f, _agora(), cod, session["login"], session["login"]))

                _salvar_anexos(uuid_f, ficha.get("anexos"), db)
        except Exception:
            app.logger.exception("ficha %s recusada", uuid_f)
            rejeitadas.append({"uuid": uuid_f[:64], "motivo": "erro_ao_gravar"})
            continue
        if ocorrencia:
            ocorrencias.append({"uuid": uuid_f, "numero": ocorrencia})
        aceitas.append(uuid_f)

    db.commit()
    return jsonify({"aceitas": aceitas, "rejeitadas": rejeitadas,
                    "ocorrencias": ocorrencias, "recebido_em": _agora()})


@app.route("/api/fichas")
@login_obrigatorio
def api_listar_fichas():
    limite = min(_inteiro(request.args.get("limite"), 50), 300)
    if session.get("papel") == "gestor":
        rows = get_db().execute(
            "SELECT * FROM fichas ORDER BY recebido_em DESC LIMIT %s", (limite,)
        ).fetchall()
    else:
        rows = get_db().execute(
            "SELECT * FROM fichas WHERE usuario_login = %s "
            "ORDER BY recebido_em DESC LIMIT %s", (session["login"], limite)
        ).fetchall()
    return jsonify({"fichas": [dict(r) for r in rows]})


@app.route("/api/resumo")
@login_obrigatorio
def api_resumo():
    """Numeros do mes corrente - base do relatorio semanal/mensal."""
    db = get_db()
    mes = datetime.now(timezone.utc).strftime("%Y-%m")
    where = "WHERE substr(recebido_em,1,7) = %s"
    args = [mes]
    if session.get("papel") != "gestor":
        where += " AND usuario_login = %s"
        args.append(session["login"])
    total = db.execute("SELECT COUNT(*) c FROM fichas " + where, args).fetchone()["c"]
    por_tipo = {r["tipo"]: r["c"] for r in db.execute(
        "SELECT tipo, COUNT(*) c FROM fichas " + where + " GROUP BY tipo", args)}
    por_nivel = {r["nivel_evidencia"]: r["c"] for r in db.execute(
        "SELECT nivel_evidencia, COUNT(*) c FROM fichas " + where +
        " GROUP BY nivel_evidencia", args)}
    validas = db.execute(
        "SELECT COUNT(*) c FROM fichas " + where + " AND conta_indicador = 1", args
    ).fetchone()["c"]
    municipios = db.execute(
        "SELECT COUNT(DISTINCT municipio) c FROM fichas " + where, args
    ).fetchone()["c"]
    clientes = db.execute(
        "SELECT COUNT(DISTINCT cliente_nome) c FROM fichas " + where, args
    ).fetchone()["c"]
    return jsonify({
        "mes": mes, "total": total, "validas": validas,
        "qualidade": round(100.0 * validas / total, 1) if total else 0.0,
        "por_tipo": por_tipo, "por_nivel": por_nivel,
        "municipios": municipios, "clientes": clientes,
    })


# --------------------------------------------------------------------------
# Painel do gestor
# --------------------------------------------------------------------------

# Ciclo de cobertura por praca (manual §6). Dias ate a proxima visita esperada.
CICLO_IMPERATRIZ = 90       # praca principal
CICLO_MIGRACAO = 120        # Sti + eixo Pindare (entra em 01/09/2026)
CICLO_PARA = 180            # Bel/Ananindeua e demais pracas do PA
CICLO_PADRAO = 120


def ciclo_do_municipio(cidade):
    c = _norm(cidade)
    if "imperatriz" in c:
        return CICLO_IMPERATRIZ
    if c.endswith("/pa") or "/pa" in c:
        return CICLO_PARA
    if any(m in c for m in ("santa ines", "ze doca", "bom jardim", "newton belo",
                            "moncao", "igarape do meio", "pindare", "pio xii")):
        return CICLO_MIGRACAO
    return CICLO_PADRAO


def _norm(txt):
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return t.lower().strip()


@app.route("/painel")
@gestor_obrigatorio
def painel():
    return render_template("painel.html", nome=session.get("nome"), tipos=TIPOS)


@app.route("/api/gestor/fichas")
@gestor_obrigatorio
def api_gestor_fichas():
    """Fichas de todos, com filtros. Retorna tudo que a tela precisa mostrar."""
    filtros, args = [], []
    mes = request.args.get("mes")
    if mes:
        filtros.append("substr(recebido_em,1,7) = %s")
        args.append(mes)
    for campo, param in (("tipo", "tipo"), ("municipio", "municipio"),
                         ("usuario_login", "usuario"), ("nivel_evidencia", "nivel")):
        v = request.args.get(param)
        if v:
            filtros.append(f"{campo} = %s")
            args.append(v)
    busca = (request.args.get("busca") or "").strip()
    if busca:
        # ILIKE porque o texto vem digitado. O LIKE do Postgres, ao contrario do
        # SQLite, diferencia maiuscula de minuscula, e a busca voltaria vazia.
        filtros.append("(cliente_nome ILIKE %s OR relato ILIKE %s OR proximo_passo ILIKE %s)")
        args += ["%%%s%%" % busca] * 3

    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    limite = min(_inteiro(request.args.get("limite"), 200), 500)
    rows = get_db().execute(
        f"SELECT * FROM fichas {onde} ORDER BY recebido_em DESC LIMIT %s",
        args + [limite]).fetchall()

    # Uma consulta para os anexos das ate 500 fichas, nao uma por ficha. Cada ida
    # ao Neon passa pelo pooler e pela rede; 500 delas estouram o tempo da funcao.
    db = get_db()
    uuids = [r["uuid"] for r in rows]
    por_ficha = {}
    if uuids:
        for a in db.execute(
                "SELECT ficha_uuid, arquivo, tipo, descricao FROM anexos "
                "WHERE ficha_uuid = ANY(%s) ORDER BY id", (uuids,)):
            por_ficha.setdefault(a["ficha_uuid"], []).append(
                {"arquivo": a["arquivo"], "tipo": a["tipo"], "descricao": a["descricao"]})

    fichas = []
    for r in rows:
        d = dict(r)
        try:
            d["extra"] = json.loads(d.pop("extra_json") or "{}")
        except ValueError:
            d["extra"] = {}
        d["anexos"] = por_ficha.get(d["uuid"], [])
        fichas.append(d)

    return jsonify({
        "fichas": fichas,
        "opcoes": {
            "meses": [x["mes"] for x in db.execute(
                "SELECT DISTINCT substr(recebido_em,1,7) AS mes FROM fichas "
                "ORDER BY 1 DESC")],
            "municipios": [x["municipio"] for x in db.execute(
                "SELECT DISTINCT municipio FROM fichas WHERE municipio <> '' ORDER BY 1")],
            "usuarios": [x["usuario_login"] for x in db.execute(
                "SELECT DISTINCT usuario_login FROM fichas ORDER BY 1")],
        },
    })


@app.route("/api/gestor/cobertura")
@gestor_obrigatorio
def api_gestor_cobertura():
    """Clientes A/B e ha quanto tempo nao recebem visita.

    E a lista NOMINAL do manual §7: '78% de cobertura' nao gera acao;
    'estes 14 clientes A estao sem visita ha 5 meses' gera.
    """
    db = get_db()
    curvas = request.args.get("curvas", "A,B").split(",")
    rows = db.execute("""
        SELECT c.codigo, c.nome, c.cidade, c.curva, c.vol_12m, c.vendedor,
               MAX(f.recebido_em) AS ultima_visita,
               COUNT(f.uuid) AS total_visitas
          FROM clientes c
          LEFT JOIN fichas f ON f.cliente_codigo = c.codigo
         WHERE c.ativo = 1 AND c.curva = ANY(%s)
         GROUP BY c.codigo
    """, (curvas,)).fetchall()

    hoje = datetime.now(timezone.utc)
    saida = []
    for r in rows:
        ciclo = ciclo_do_municipio(r["cidade"])
        ultima = r["ultima_visita"]
        if ultima:
            try:
                dias = (hoje - datetime.fromisoformat(ultima)).days
            except ValueError:
                dias = None
        else:
            dias = None
        saida.append({
            "codigo": r["codigo"], "nome": r["nome"], "cidade": r["cidade"],
            "curva": r["curva"], "vol_12m": r["vol_12m"], "vendedor": r["vendedor"],
            "ultima_visita": ultima, "total_visitas": r["total_visitas"],
            "dias": dias, "ciclo": ciclo,
            "vencido": (dias is None) or (dias > ciclo),
        })

    # nunca visitados primeiro, depois os mais atrasados; desempate por volume
    saida.sort(key=lambda x: (x["dias"] is not None, -(x["dias"] or 0), -x["vol_12m"]))
    vencidos = [x for x in saida if x["vencido"]]
    return jsonify({
        "clientes": saida,
        "total": len(saida),
        "vencidos": len(vencidos),
        "nunca_visitados": len([x for x in saida if x["dias"] is None]),
        "cobertura_pct": round(100.0 * (len(saida) - len(vencidos)) / len(saida), 1) if saida else 0.0,
        "risco_reais": round(sum(x["vol_12m"] for x in vencidos), 2),
    })


@app.route("/api/gestor/ocorrencias")
@gestor_obrigatorio
def api_gestor_ocorrencias():
    """Ocorrencias de qualquer canal. Hoje so a visita abre; o modelo ja
    aceita balcao, telefone, entrega e outros setores."""
    filtros, args = [], []
    for campo, param in (("status", "situacao"), ("canal", "canal"),
                         ("setor", "setor"), ("tipo", "tipo")):
        v = request.args.get(param)
        if v:
            filtros.append(f"{campo} = %s")
            args.append(v)
    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    rows = get_db().execute(
        "SELECT * FROM ocorrencias " + onde + " ORDER BY numero DESC LIMIT 300", args
    ).fetchall()

    hoje = datetime.now(timezone.utc)
    saida = []
    for r in rows:
        d = dict(r)
        try:
            d["dias_aberta"] = (hoje - datetime.fromisoformat(r["aberta_em"])).days
        except (TypeError, ValueError):
            d["dias_aberta"] = None
        saida.append(d)

    db = get_db()
    cont = {x["status"]: x["n"] for x in db.execute(
        "SELECT status, COUNT(*) AS n FROM ocorrencias GROUP BY status")}
    return jsonify({
        "ocorrencias": saida,
        "abertas": cont.get("aberta", 0) + cont.get("em_andamento", 0),
        "resolvidas": cont.get("resolvida", 0),
        "por_canal": {x["canal"]: x["n"] for x in db.execute(
            "SELECT canal, COUNT(*) AS n FROM ocorrencias GROUP BY canal")},
        "canais": CANAIS, "setores": SETORES, "status": STATUS_OCORRENCIA,
    })


@app.route("/api/gestor/ocorrencia/<numero>", methods=["PATCH"])
@gestor_obrigatorio
def api_atualizar_ocorrencia(numero):
    if not re.fullmatch(r"OC-\d{4}-\d{4}", numero or ""):
        return jsonify({"erro": "numero_invalido"}), 400
    d = request.get_json(silent=True) or {}
    db = get_db()
    if not db.execute("SELECT 1 FROM ocorrencias WHERE numero = %s", (numero,)).fetchone():
        return jsonify({"erro": "nao_encontrada"}), 404

    if "status" in d:
        if d["status"] not in STATUS_OCORRENCIA:
            return jsonify({"erro": "status_invalido"}), 400
        if d["status"] == "resolvida":
            db.execute("UPDATE ocorrencias SET status = 'resolvida', resolvida_em = %s, "
                       "resolvida_por = %s, resolucao = COALESCE(%s, resolucao) "
                       "WHERE numero = %s",
                       (_agora(), session["login"],
                        (d.get("resolucao") or "").strip()[:1000] or None, numero))
            # mantem a ficha de origem coerente
            db.execute("UPDATE fichas SET ocorrencia_status = 'resolvida', "
                       "ocorrencia_fechada_em = %s WHERE ocorrencia_num = %s",
                       (_agora(), numero))
        else:
            db.execute("UPDATE ocorrencias SET status = %s, resolvida_em = NULL, "
                       "resolvida_por = NULL WHERE numero = %s", (d["status"], numero))
            db.execute("UPDATE fichas SET ocorrencia_status = %s, "
                       "ocorrencia_fechada_em = NULL WHERE ocorrencia_num = %s",
                       (d["status"], numero))
    if "responsavel" in d:
        db.execute("UPDATE ocorrencias SET responsavel = %s WHERE numero = %s",
                   ((d["responsavel"] or "").strip()[:120] or None, numero))
    db.commit()
    return jsonify({"ok": True, "numero": numero})


@app.route("/api/gestor/experiencia")
@gestor_obrigatorio
def api_gestor_experiencia():
    """Le da tabela de respostas - uma visita pode ter varias.

    NPS  -> % promotores menos % detratores (so perguntas de recomendacao)
    CSAT -> % de notas >= 8, por processo da empresa
    CES  -> % que achou facil (>= 8), no pos-venda
    """
    db = get_db()
    mes = request.args.get("mes")
    base, args = "FROM experiencia WHERE 1=1", []
    if mes:
        base += " AND substr(registrado_em,1,7) = %s"
        args.append(mes)

    def bloco(metrica, corte):
        linhas = db.execute(
            "SELECT etapa, COUNT(*) n, ROUND(AVG(nota),1) media, "
            "SUM(CASE WHEN nota >= %s THEN 1 ELSE 0 END) bons, "
            "SUM(CASE WHEN nota <= %s THEN 1 ELSE 0 END) ruins "
            + base + " AND metrica = %s GROUP BY etapa ORDER BY media ASC",
            [corte, NPS_DETRATOR] + args + [metrica]).fetchall()
        tot = db.execute(
            "SELECT COUNT(*) n, ROUND(AVG(nota),1) media, "
            "SUM(CASE WHEN nota >= %s THEN 1 ELSE 0 END) bons, "
            "SUM(CASE WHEN nota <= %s THEN 1 ELSE 0 END) ruins "
            + base + " AND metrica = %s",
            [corte, NPS_DETRATOR] + args + [metrica]).fetchone()
        n = tot["n"] or 0
        return {"por_etapa": [_media_float(dict(r)) for r in linhas], "n": n,
                "media": _float(tot["media"]), "bons": tot["bons"] or 0,
                "ruins": tot["ruins"] or 0,
                "pct_bons": round(100.0 * (tot["bons"] or 0) / n) if n else None}

    nps = bloco("nps", NPS_PROMOTOR)
    nps["indice"] = (round(100.0 * (nps["bons"] - nps["ruins"]) / nps["n"])
                     if nps["n"] else None)

    comentarios = [dict(r) for r in db.execute(
        "SELECT cliente_nome, etapa AS exp_etapa, nota AS exp_nota, "
        "comentario AS exp_comentario, metrica AS exp_metrica, "
        "registrado_em AS recebido_em " + base +
        " AND comentario IS NOT NULL AND comentario <> '' "
        "ORDER BY nota ASC, registrado_em DESC LIMIT 40", args)]

    expedicao = [_media_float(dict(r)) for r in db.execute(
        "SELECT unidade, COUNT(*) n, ROUND(AVG(nota),1) media, "
        "SUM(CASE WHEN nota >= %s THEN 1 ELSE 0 END) bons " + base +
        " AND etapa = 'Atendimento da expedicao' AND unidade IS NOT NULL "
        "GROUP BY unidade ORDER BY media ASC", [CSAT_SATISFEITO] + args)]

    return jsonify({
        "expedicao": expedicao,
        "nps": nps, "csat": bloco("csat", CSAT_SATISFEITO),
        "ces": bloco("ces", CES_FACIL), "comentarios": comentarios,
        "clientes_ouvidos": db.execute(
            "SELECT COUNT(DISTINCT COALESCE(cliente_codigo, cliente_nome)) c "
            + base, args).fetchone()["c"],
        "cortes": {"nps_promotor": NPS_PROMOTOR, "nps_detrator": NPS_DETRATOR,
                   "csat_satisfeito": CSAT_SATISFEITO, "ces_facil": CES_FACIL},
    })


# --------------------------------------------------------------------------
# Conta e usuarios
# --------------------------------------------------------------------------
SENHA_MIN = 8


def _hash(senha):
    # pbkdf2 explicito: o default do Werkzeug 3 e scrypt, ausente em builds
    # do Python sem OpenSSL completo (caso do python do macOS).
    return generate_password_hash(senha, method="pbkdf2:sha256")


@app.route("/conta", methods=["GET", "POST"])
@login_obrigatorio
def conta():
    """Cada um troca a propria senha. Exige a senha atual."""
    aviso = erro = None
    if request.method == "POST":
        atual = request.form.get("atual") or ""
        nova = request.form.get("nova") or ""
        repetir = request.form.get("repetir") or ""
        db = get_db()
        row = db.execute("SELECT senha_hash FROM usuarios WHERE id = %s",
                         (session["uid"],)).fetchone()
        if not row or not check_password_hash(row["senha_hash"], atual):
            erro = "Senha atual incorreta."
        elif len(nova) < SENHA_MIN:
            erro = "A senha nova precisa de pelo menos %d caracteres." % SENHA_MIN
        elif nova != repetir:
            erro = "A confirmacao nao confere."
        elif nova == atual:
            erro = "A senha nova tem que ser diferente da atual."
        else:
            db.execute("UPDATE usuarios SET senha_hash = %s WHERE id = %s",
                       (_hash(nova), session["uid"]))
            db.commit()
            aviso = "Senha alterada."
    return render_template("conta.html", aviso=aviso, erro=erro,
                           nome=session.get("nome"), papel=session.get("papel"))


@app.route("/usuarios")
@gestor_obrigatorio
def usuarios():
    return render_template("usuarios.html", nome=session.get("nome"))


@app.route("/api/gestor/usuarios")
@gestor_obrigatorio
def api_usuarios():
    rows = get_db().execute(
        "SELECT id, login, nome, papel, ativo, criado_em FROM usuarios ORDER BY ativo DESC, nome"
    ).fetchall()
    return jsonify({"usuarios": [dict(r) for r in rows], "eu": session["uid"]})


@app.route("/api/gestor/usuarios", methods=["POST"])
@gestor_obrigatorio
def api_criar_usuario():
    d = request.get_json(silent=True) or {}
    login_txt = re.sub(r"[^a-z0-9._-]", "", (d.get("login") or "").strip().lower())[:30]
    nome = (d.get("nome") or "").strip()[:80]
    papel = d.get("papel") if d.get("papel") in ("rep", "gestor") else "rep"
    senha = d.get("senha") or ""
    if not login_txt or not nome:
        return jsonify({"erro": "login_e_nome_obrigatorios"}), 400
    if len(senha) < SENHA_MIN:
        return jsonify({"erro": "senha_curta"}), 400
    db = get_db()
    if db.execute("SELECT 1 FROM usuarios WHERE login = %s", (login_txt,)).fetchone():
        return jsonify({"erro": "login_ja_existe"}), 409
    db.execute("INSERT INTO usuarios (login, nome, senha_hash, papel, base, ativo, criado_em)"
               " VALUES (%s,%s,%s,%s,'ITZ',1,%s)",
               (login_txt, nome, _hash(senha), papel, _agora()))
    db.commit()
    return jsonify({"ok": True, "login": login_txt})


@app.route("/api/gestor/usuarios/<int:uid>", methods=["PATCH"])
@gestor_obrigatorio
def api_alterar_usuario(uid):
    d = request.get_json(silent=True) or {}
    db = get_db()
    alvo = db.execute("SELECT * FROM usuarios WHERE id = %s", (uid,)).fetchone()
    if not alvo:
        return jsonify({"erro": "nao_encontrado"}), 404

    if "ativo" in d:
        if uid == session["uid"]:
            return jsonify({"erro": "nao_pode_desativar_a_si_mesmo"}), 400
        db.execute("UPDATE usuarios SET ativo = %s WHERE id = %s",
                   (1 if d["ativo"] else 0, uid))
    if "papel" in d and d["papel"] in ("rep", "gestor"):
        if uid == session["uid"] and d["papel"] != "gestor":
            return jsonify({"erro": "nao_pode_rebaixar_a_si_mesmo"}), 400
        db.execute("UPDATE usuarios SET papel = %s WHERE id = %s", (d["papel"], uid))
    if "senha" in d:
        if len(d["senha"] or "") < SENHA_MIN:
            return jsonify({"erro": "senha_curta"}), 400
        db.execute("UPDATE usuarios SET senha_hash = %s WHERE id = %s",
                   (_hash(d["senha"]), uid))
    db.commit()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Planejamento de viagem e sugestao de visitas
# --------------------------------------------------------------------------

@app.route("/api/rotas")
@login_obrigatorio
def api_rotas():
    """Rotas reais da carteira, com as cidades de cada uma.

    A rota pode ser dividida: o representante escolhe quais cidades entram
    nesta viagem, porque nem toda rota se faz de uma vez.
    """
    db = get_db()
    rotas, descartados = {}, []
    for r in db.execute("""
        SELECT COALESCE(NULLIF(TRIM(rota),''),'Sem rota') AS rota,
               COALESCE(NULLIF(TRIM(cidade),''),'Sem cidade') AS cidade,
               COUNT(*) n, ROUND(SUM(vol_12m)) vol
          FROM clientes WHERE ativo = 1
         GROUP BY rota, cidade ORDER BY rota, n DESC"""):
        nome = r["rota"]
        # "Sem Rota" e "sem Rota" sao a mesma coisa na carteira
        if nome.lower() in ("sem rota", "sem rota "):
            nome = "Sem rota"
        if _fora_da_base(nome):
            descartados.append({"rota": nome, "cidade": r["cidade"], "clientes": r["n"]})
            continue
        d = rotas.setdefault(nome, {"rota": nome, "cidades": [], "clientes": 0, "vol_12m": 0})
        d["cidades"].append({"cidade": r["cidade"], "clientes": r["n"],
                             "vol_12m": r["vol"] or 0})
        d["clientes"] += r["n"]
        d["vol_12m"] += r["vol"] or 0

    lista = sorted(rotas.values(), key=lambda x: -x["vol_12m"])
    return jsonify({"rotas": lista, "total_clientes": sum(x["clientes"] for x in lista),
                    "fora_da_base": descartados,
                    "clientes_fora": sum(x["clientes"] for x in descartados)})


@app.route("/api/sugestao")
@login_obrigatorio
def api_sugestao():
    """Quem visitar, e por que.

    Cruza o que o sistema ja sabe: cobertura vencida, ocorrencia aberta,
    nota baixa e volume. Cada cliente vem com o motivo em texto - sugestao
    sem o porque nao ajuda ninguem a montar rota.
    """
    db = get_db()
    municipio = (request.args.get("municipio") or "").strip()
    rota = (request.args.get("rota") or "").strip()
    limite = min(_inteiro(request.args.get("limite"), 40), 200)

    cidades = [x.strip() for x in (request.args.get("cidades") or "").split("|") if x.strip()]

    filtros, args = ["c.ativo = 1"], []
    if cidades:
        filtros.append("COALESCE(NULLIF(TRIM(c.cidade),''),'Sem cidade') = ANY(%s)")
        args.append(cidades)
    elif municipio:
        filtros.append("c.cidade ILIKE %s")
        args.append("%%%s%%" % municipio)
    # cidades escolhidas mandam no escopo - podem ser de outra rota (passagem)
    if rota and not cidades:
        if rota == "Sem rota":
            filtros.append("(c.rota IS NULL OR TRIM(c.rota) = '' OR LOWER(TRIM(c.rota)) = 'sem rota')")
        else:
            filtros.append("TRIM(c.rota) = %s")
            args.append(rota)

    rows = db.execute("""
        SELECT c.codigo, c.nome, c.cidade, c.rota, c.curva, c.vol_12m, c.vendedor,
               MAX(f.recebido_em) AS ultima_visita,
               (SELECT COUNT(*) FROM ocorrencias o
                 WHERE o.cliente_codigo = c.codigo AND o.status <> 'resolvida') AS oc_abertas,
               (SELECT MIN(e.nota) FROM experiencia e
                 WHERE e.cliente_codigo = c.codigo) AS pior_nota
          FROM clientes c
          LEFT JOIN fichas f ON f.cliente_codigo = c.codigo
         WHERE __FILTROS__
         GROUP BY c.codigo
    """.replace("__FILTROS__", " AND ".join(filtros)), args).fetchall()

    hoje = datetime.now(timezone.utc)
    saida = []
    for r in rows:
        # rota de outra base na carteira Itz e falha de cadastro: nao sugere.
        # Filtrado aqui, e nao no SQL, porque o LOWER do SQLite nao tira acento
        # ("Sao Luis" e "Sao Luis" com acento nao batem).
        if _fora_da_base(r["rota"]):
            continue
        ciclo = ciclo_do_municipio(r["cidade"])
        dias = None
        if r["ultima_visita"]:
            try:
                dias = (hoje - datetime.fromisoformat(r["ultima_visita"])).days
            except ValueError:
                dias = None

        peso, motivos = 0, []
        if r["oc_abertas"]:
            peso += 100
            motivos.append("%d ocorrência(s) em aberto" % r["oc_abertas"])
        if r["pior_nota"] is not None and r["pior_nota"] <= NPS_DETRATOR:
            peso += 60
            motivos.append("deu nota %d numa pesquisa" % r["pior_nota"])
        if dias is None:
            peso += 50
            motivos.append("nunca recebeu visita")
        elif dias > ciclo:
            peso += 40
            motivos.append("sem visita há %d dias (ciclo %d)" % (dias, ciclo))
        if r["curva"] == "A":
            peso += 25
            motivos.append("curva A")
        elif r["curva"] == "B":
            peso += 12
        if r["vol_12m"]:
            peso += min(r["vol_12m"] / 20000.0, 25)   # volume pesa, mas nao domina

        if not motivos:
            continue                                   # sem motivo, nao sugere
        saida.append({
            "codigo": r["codigo"], "nome": r["nome"], "cidade": r["cidade"],
            "rota": r["rota"], "curva": r["curva"], "vol_12m": r["vol_12m"],
            "vendedor": r["vendedor"], "dias": dias, "ciclo": ciclo,
            "oc_abertas": r["oc_abertas"], "pior_nota": r["pior_nota"],
            "peso": round(peso), "motivo": " · ".join(motivos),
        })

    saida.sort(key=lambda x: -x["peso"])
    municipios = sorted({x["cidade"] for x in saida if x["cidade"]})
    rotas = sorted({x["rota"] for x in saida if x["rota"]})
    return jsonify({"clientes": saida[:limite], "total": len(saida),
                    "municipios": municipios, "rotas": rotas})


@app.route("/api/viagens", methods=["GET", "POST"])
@login_obrigatorio
def api_viagens():
    db = get_db()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        nome = (d.get("nome") or "").strip()[:120]
        if not nome:
            return jsonify({"erro": "nome_obrigatorio"}), 400
        # RETURNING id porque o psycopg nao tem lastrowid
        row = db.execute("""INSERT INTO viagens (nome, inicio, fim, rota,
            observacao, status, criada_por, responsavel, criada_em)
            VALUES (%s,%s,%s,%s,%s,'planejada',%s,%s,%s) RETURNING id""",
            (nome, (d.get("inicio") or "")[:20] or None,
             (d.get("fim") or "")[:20] or None, (d.get("rota") or "")[:80] or None,
             (d.get("observacao") or "")[:500] or None, session["login"],
             (d.get("responsavel") or session["login"])[:80], _agora())).fetchone()
        db.commit()
        return jsonify({"ok": True, "id": row["id"]})

    # O login ia direto para dentro do texto do SQL, entre aspas. Agora e parametro.
    if session.get("papel") == "gestor":
        onde, args = "", []
    else:
        onde = "WHERE responsavel = %s OR criada_por = %s"
        args = [session["login"], session["login"]]
    # uma consulta so: 1 + 60 idas ao banco por abertura de tela nao paga a viagem
    viagens = [dict(v) for v in db.execute(f"""
        SELECT v.*, COUNT(vc.id) AS planejados,
               COALESCE(SUM(vc.visitado), 0) AS visitados
          FROM viagens v
          LEFT JOIN viagem_clientes vc ON vc.viagem_id = v.id
          {onde}
         GROUP BY v.id
         ORDER BY COALESCE(v.inicio, v.criada_em) DESC
         LIMIT 60""", args)]
    for d in viagens:
        d["aderencia"] = (round(100.0 * d["visitados"] / d["planejados"])
                          if d["planejados"] else None)
    return jsonify({"viagens": viagens})


def _pode_na_viagem(v):
    """Gestor ve tudo. Representante so mexe na viagem que criou ou conduz.

    Sem isto, trocar o numero na URL dava acesso ao roteiro de qualquer outro.
    """
    return (session.get("papel") == "gestor"
            or v["criada_por"] == session.get("login")
            or v["responsavel"] == session.get("login"))


@app.route("/api/viagens/<int:vid>", methods=["GET", "PATCH", "DELETE"])
@login_obrigatorio
def api_viagem(vid):
    db = get_db()
    v = db.execute("SELECT * FROM viagens WHERE id = %s", (vid,)).fetchone()
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404

    if not _pode_na_viagem(v):
        return jsonify({"erro": "sem_permissao"}), 403

    if request.method == "DELETE":
        db.execute("DELETE FROM viagem_clientes WHERE viagem_id = %s", (vid,))
        db.execute("DELETE FROM viagens WHERE id = %s", (vid,))
        db.commit()
        return jsonify({"ok": True})

    if request.method == "PATCH":
        d = request.get_json(silent=True) or {}
        if d.get("status") in ("planejada", "em_andamento", "concluida"):
            db.execute("UPDATE viagens SET status = %s WHERE id = %s", (d["status"], vid))
        for campo in ("nome", "inicio", "fim", "rota", "observacao", "responsavel"):
            if campo in d:
                # f-string, nao %: com o placeholder %s do psycopg o operador %
                # do Python tentaria preencher o proprio placeholder. O campo vem
                # da tupla escrita acima, entao nao ha porta para injecao.
                db.execute(f"UPDATE viagens SET {campo} = %s WHERE id = %s",
                           (str(d[campo] or "")[:500] or None, vid))
        db.commit()
        return jsonify({"ok": True})

    clientes = [dict(r) for r in db.execute(
        "SELECT * FROM viagem_clientes WHERE viagem_id = %s ORDER BY visitado, ordem, cliente_nome",
        (vid,))]
    d = dict(v)
    d["clientes"] = clientes
    d["planejados"] = len(clientes)
    d["visitados"] = sum(1 for c in clientes if c["visitado"])
    d["aderencia"] = round(100.0 * d["visitados"] / d["planejados"]) if clientes else None
    return jsonify(d)


@app.route("/api/viagens/<int:vid>/clientes", methods=["POST"])
@login_obrigatorio
def api_viagem_add(vid):
    d = request.get_json(silent=True) or {}
    lista = d.get("clientes")
    if not isinstance(lista, list):
        return jsonify({"erro": "lista_invalida"}), 400
    db = get_db()
    v = db.execute("SELECT * FROM viagens WHERE id = %s", (vid,)).fetchone()
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    if not _pode_na_viagem(v):
        return jsonify({"erro": "sem_permissao"}), 403

    # ON CONFLICT no lugar de ler antes e inserir depois: dois toques no botao
    # chegam em processos diferentes na Vercel, os dois leem o roteiro vazio e os
    # dois inserem. O indice unico ux_vc_viagem_cliente e quem segura.
    add = 0
    for i, c in enumerate(lista[:200]):
        cod = str(c.get("codigo") or "")[:40] or None
        nome = str(c.get("nome") or "").strip()[:200]
        if not nome:
            continue
        cur = db.execute("""INSERT INTO viagem_clientes (viagem_id, cliente_codigo,
            cliente_nome, municipio, motivo, ordem) VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (viagem_id, cliente_codigo) WHERE cliente_codigo IS NOT NULL
            DO NOTHING""",
            (vid, cod, nome, str(c.get("cidade") or "")[:120] or None,
             str(c.get("motivo") or "")[:300] or None, i))
        add += cur.rowcount
    db.commit()
    return jsonify({"ok": True, "adicionados": add})


@app.route("/api/viagens/<int:vid>/clientes/<int:cid>", methods=["DELETE"])
@login_obrigatorio
def api_viagem_remove(vid, cid):
    db = get_db()
    v = db.execute("SELECT * FROM viagens WHERE id = %s", (vid,)).fetchone()
    if not v:
        return jsonify({"erro": "nao_encontrada"}), 404
    if not _pode_na_viagem(v):
        return jsonify({"erro": "sem_permissao"}), 403
    db.execute("DELETE FROM viagem_clientes WHERE id = %s AND viagem_id = %s", (cid, vid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/viagens")
@login_obrigatorio
def viagens():
    return render_template("viagens.html", nome=session.get("nome"),
                           papel=session.get("papel"))


@app.route("/foto/<nome>")
@login_obrigatorio
def foto(nome):
    if not re.fullmatch(r"[A-Za-z0-9_\-]+\.(jpg|png)", nome or ""):
        return "", 404
    binario, tipo = _blob_ler(nome)
    if binario is None:
        return "", 404
    # private, porque a foto sai daqui so para quem esta logado e o cache do
    # navegador nao pode servir ela para o proximo usuario do mesmo aparelho.
    return Response(binario, mimetype=tipo,
                    headers={"Cache-Control": "private, max-age=3600"})


@app.route("/saude")
def saude():
    try:
        n = get_db().execute("SELECT COUNT(*) c FROM clientes").fetchone()["c"]
        return jsonify({"ok": True, "clientes": n, "hora": _agora()})
    except Exception:
        # sem str(exc): a rota e publica e a excecao do psycopg carrega host,
        # porta e nome do banco.
        app.logger.exception("saude falhou")
        return jsonify({"ok": False, "erro": "banco_indisponivel"}), 500


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8010))
    print("[rep-campo] iniciando em http://127.0.0.1:%d" % porta)
    app.run(host="0.0.0.0", port=porta, debug=False)
