# -*- coding: utf-8 -*-
"""
REP Campo - registro de visitas do representante comercial (base Itz).
Flask + SQLite. PWA offline-first.

Padroes seguidos (EMVIDROS_TECH_PADROES.md):
  - init_db() idempotente com PRAGMA table_info + ALTER TABLE
  - prints em ASCII puro
  - sem senha em texto claro no codigo
"""
import base64
import json
import os
import re
import secrets
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, g, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DADOS_DIR = os.path.join(BASE_DIR, "dados")
FOTOS_DIR = os.path.join(DADOS_DIR, "fotos")
DB_PATH = os.environ.get("REP_DB", os.path.join(DADOS_DIR, "rep_campo.db"))
SECRET_PATH = os.path.join(DADOS_DIR, "secret.key")

os.makedirs(FOTOS_DIR, exist_ok=True)

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
    "Cotacao e orcamento",
    "Preco e condicao",
    "Prazo prometido",
    "Producao e acabamento",
    "Entrega",
    "Qualidade do produto",
    "Pos-venda e resolucao de problema",
    "Relacionamento geral",
]

# Cada etapa da jornada tem a metrica certa. Misturar as tres e chamar tudo
# de NPS produz media com nome errado - e contamina o NPS relacional da
# pesquisa CX formal, que mede outra coisa.
#   NPS  = lealdade a marca ("recomendaria?"), baixa frequencia
#   CSAT = satisfacao com UMA etapa ("como foi essa entrega?")
#   CES  = esforco do cliente ("foi facil resolver?"), melhor em pos-venda
METRICA_POR_ETAPA = {
    "Relacionamento geral": "nps",
    "Pos-venda e resolucao de problema": "ces",
    "Cotacao e orcamento": "csat",
    "Preco e condicao": "csat",
    "Prazo prometido": "csat",
    "Producao e acabamento": "csat",
    "Entrega": "csat",
    "Qualidade do produto": "csat",
}

# Corte de cada metrica na regua unica de 0 a 10 (o REP nao decora escalas).
NPS_PROMOTOR, NPS_DETRATOR = 9, 6
CSAT_SATISFEITO = 8          # top-2-box
CES_FACIL = 8

# A pergunta muda conforme o tipo de visita - pesquisa pertinente a situacao.
PERGUNTA_EXPERIENCIA = {
    "comercial":    ("Cotacao e orcamento", "Como foi a ultima cotacao que fizemos pra voce?"),
    "cordialidade": ("Relacionamento geral", "De 0 a 10, o quanto recomendaria a EM Vidros?"),
    "tecnica":      ("Pos-venda e resolucao de problema", "De 0 a 10, o quanto foi FACIL resolver esse problema com a gente?"),
    "prospeccao":   ("Relacionamento geral", "O que te faria comprar da EM Vidros?"),
    "preco":        ("Preco e condicao", "Como avalia nosso preco frente ao prazo e a entrega?"),
    "voz":          ("Relacionamento geral", "De 0 a 10, o quanto recomendaria a EM Vidros?"),
    "evento":       ("Relacionamento geral", "Como a EM Vidros e vista no mercado hoje?"),
}

# NPS cansa se perguntado toda visita. CSAT e CES podem ser sempre.
DIAS_MINIMOS_ENTRE_NPS = 90


def _secret_key():
    env = os.environ.get("REP_SECRET_KEY")
    if env:
        return env
    if os.path.exists(SECRET_PATH):
        with open(SECRET_PATH, "r") as fh:
            return fh.read().strip()
    key = secrets.token_hex(32)
    with open(SECRET_PATH, "w") as fh:
        fh.write(key)
    os.chmod(SECRET_PATH, 0o600)
    return key


# root_path/instance_path explicitos: sem isso o Flask chama os.getcwd(), que
# falha quando o processo herda um cwd sem permissao de leitura (Google Drive
# no macOS). Deixa o app independente do diretorio de onde foi iniciado.
app = Flask(__name__, root_path=BASE_DIR,
            instance_path=os.path.join(BASE_DIR, "instance"))
app.secret_key = _secret_key()
app.config.update(
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,          # 12 MB por requisicao
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
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = {
    "usuarios": """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            papel TEXT NOT NULL DEFAULT 'rep',
            base TEXT NOT NULL DEFAULT 'ITZ',
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        )""",
    "clientes": """
        CREATE TABLE IF NOT EXISTS clientes (
            codigo TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            cidade TEXT,
            rota TEXT,
            tabela TEXT,
            vendedor TEXT,
            vol_12m REAL DEFAULT 0,
            curva TEXT,
            base TEXT DEFAULT 'ITZ',
            origem TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            atualizado_em TEXT
        )""",
    "fichas": """
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
            lat REAL,
            lon REAL,
            precisao REAL,
            criado_em_disp TEXT,
            recebido_em TEXT NOT NULL,
            foto_arquivo TEXT,
            extra_json TEXT,
            nivel_evidencia TEXT,
            conta_indicador INTEGER NOT NULL DEFAULT 0,
            relato_curto INTEGER NOT NULL DEFAULT 0
        )""",
}

# colunas adicionadas depois da v1 entram aqui (migracao idempotente)
COLUNAS_EXTRA = {
    "fichas": [
        ("app_versao", "TEXT"),
        # v2 (02/09/2026)
        ("problema_tipo", "TEXT"),        # ocorrencia escolhida na lista
        ("ocorrencia_num", "TEXT"),       # numero gerado pelo servidor (so tecnica)
        ("ocorrencia_status", "TEXT"),    # aberta | resolvida
        ("ocorrencia_fechada_em", "TEXT"),
        ("exp_etapa", "TEXT"),            # etapa da jornada avaliada
        ("exp_nota", "INTEGER"),          # 0 a 10
        ("exp_comentario", "TEXT"),       # nas palavras do cliente
        ("exp_metrica", "TEXT"),          # nps | csat | ces - derivada da etapa
    ],
}


def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    for ddl in SCHEMA.values():
        cur.execute(ddl)
    # migracao de colunas novas sem perder dados (padrao EMVIDROS_TECH_PADROES)
    for tabela, colunas in COLUNAS_EXTRA.items():
        cur.execute("PRAGMA table_info(%s)" % tabela)
        existentes = {row[1] for row in cur.fetchall()}
        for nome, tipo in colunas:
            if nome not in existentes:
                cur.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tabela, nome, tipo))
                print("[db] coluna adicionada: %s.%s" % (tabela, nome))
    cur.execute("CREATE INDEX IF NOT EXISTS ix_fichas_usuario ON fichas(usuario_login)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_fichas_data ON fichas(recebido_em)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_clientes_nome ON clientes(nome)")
    con.commit()
    con.close()


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


# Freio de forca bruta no login. Em memoria: o app tem 2-3 usuarios e um so
# processo; nao justifica Redis. Zera quando o servico reinicia.
TENTATIVAS = {}
MAX_TENTATIVAS = 8
JANELA_BLOQUEIO = timedelta(minutes=15)


def _origem():
    return request.remote_addr or "?"


def _bloqueado(chave):
    reg = TENTATIVAS.get(chave)
    if not reg:
        return False
    falhas, ultima = reg
    if datetime.now(timezone.utc) - ultima > JANELA_BLOQUEIO:
        TENTATIVAS.pop(chave, None)
        return False
    return falhas >= MAX_TENTATIVAS


def _registrar_falha(chave):
    falhas, _ = TENTATIVAS.get(chave, (0, None))
    TENTATIVAS[chave] = (falhas + 1, datetime.now(timezone.utc))


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
            "SELECT * FROM usuarios WHERE login = ? AND ativo = 1", (login_txt,)
        ).fetchone()
        if row and check_password_hash(row["senha_hash"], senha):
            TENTATIVAS.pop(_origem(), None)
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


def _slug(txt):
    txt = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", txt).strip("-").lower()[:40] or "sem-nome"


# assinatura dos formatos aceitos - so JPEG e PNG entram no disco
ASSINATURAS = ((b"\xff\xd8\xff", "jpg"), (b"\x89PNG\r\n\x1a\n", "png"))


def _salvar_foto(uuid_ficha, data_url):
    """Grava a foto em disco. Retorna o nome do arquivo, ou None se recusar.

    O nome sai do uuid, que vem do celular - por isso o uuid ja chega validado
    por RE_UUID e o caminho final e conferido contra FOTOS_DIR antes de gravar.
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
    if len(binario) > 6 * 1024 * 1024:
        return None

    # a extensao vem do conteudo, nao do que o cliente declarou no cabecalho
    ext = next((e for assinatura, e in ASSINATURAS if binario.startswith(assinatura)), None)
    if ext is None:
        return None

    nome = "%s.%s" % (uuid_ficha, ext)
    destino = os.path.abspath(os.path.join(FOTOS_DIR, nome))
    if os.path.dirname(destino) != os.path.abspath(FOTOS_DIR):
        return None                      # cinto e suspensorio contra path traversal
    with open(destino, "wb") as fh:
        fh.write(binario)
    return nome


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
    """
    ano = datetime.now(timezone.utc).strftime("%Y")
    prefixo = "OC-%s-" % ano
    ultimo = db.execute(
        "SELECT ocorrencia_num FROM fichas WHERE ocorrencia_num LIKE ? "
        "ORDER BY ocorrencia_num DESC LIMIT 1", (prefixo + "%",)).fetchone()
    seq = 1
    if ultimo and ultimo[0]:
        try:
            seq = int(ultimo[0].rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            seq = 1
    return "%s%04d" % (prefixo, seq)


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
        if db.execute("SELECT 1 FROM fichas WHERE uuid = ?", (uuid_f,)).fetchone():
            aceitas.append(uuid_f)
            continue

        foto_arq = _salvar_foto(uuid_f, ficha.get("foto"))
        nivel, tem_passo = _classificar(ficha, bool(foto_arq))
        relato = (ficha.get("relato") or "").strip()[:LIMITES_TEXTO["relato"]]

        # visita tecnica abre ocorrencia numerada, para ser acompanhada
        ocorrencia = _proxima_ocorrencia(db) if tipo == "tecnica" else None
        status_oc = "aberta" if ocorrencia else None

        etapa = _texto(ficha, "exp_etapa")
        metrica = METRICA_POR_ETAPA.get(etapa or "", "csat") if etapa else None

        nota = ficha.get("exp_nota")
        try:
            nota = int(nota) if nota not in (None, "") else None
            if nota is not None and not (0 <= nota <= 10):
                nota = None
        except (TypeError, ValueError):
            nota = None

        db.execute("""
            INSERT INTO fichas (uuid, usuario_id, usuario_login, tipo, cliente_codigo,
                cliente_nome, prospect, municipio, objetivo, relato, proximo_passo,
                prox_responsavel, prox_data, encaminhado_para, lat, lon, precisao,
                criado_em_disp, recebido_em, foto_arquivo, extra_json,
                nivel_evidencia, conta_indicador, relato_curto, app_versao,
                problema_tipo, ocorrencia_num, ocorrencia_status,
                exp_etapa, exp_nota, exp_comentario, exp_metrica)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
        aceitas.append(uuid_f)
        if ocorrencia:
            ocorrencias.append({"uuid": uuid_f, "numero": ocorrencia})

    db.commit()
    return jsonify({"aceitas": aceitas, "rejeitadas": rejeitadas,
                    "ocorrencias": ocorrencias, "recebido_em": _agora()})


@app.route("/api/fichas")
@login_obrigatorio
def api_listar_fichas():
    limite = min(int(request.args.get("limite", 50)), 300)
    if session.get("papel") == "gestor":
        rows = get_db().execute(
            "SELECT * FROM fichas ORDER BY recebido_em DESC LIMIT ?", (limite,)
        ).fetchall()
    else:
        rows = get_db().execute(
            "SELECT * FROM fichas WHERE usuario_login = ? "
            "ORDER BY recebido_em DESC LIMIT ?", (session["login"], limite)
        ).fetchall()
    return jsonify({"fichas": [dict(r) for r in rows]})


@app.route("/api/resumo")
@login_obrigatorio
def api_resumo():
    """Numeros do mes corrente - base do relatorio semanal/mensal."""
    db = get_db()
    mes = datetime.now(timezone.utc).strftime("%Y-%m")
    where = "WHERE substr(recebido_em,1,7) = ?"
    args = [mes]
    if session.get("papel") != "gestor":
        where += " AND usuario_login = ?"
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
        filtros.append("substr(recebido_em,1,7) = ?")
        args.append(mes)
    for campo, param in (("tipo", "tipo"), ("municipio", "municipio"),
                         ("usuario_login", "usuario"), ("nivel_evidencia", "nivel")):
        v = request.args.get(param)
        if v:
            filtros.append("%s = ?" % campo)
            args.append(v)
    busca = (request.args.get("busca") or "").strip()
    if busca:
        filtros.append("(cliente_nome LIKE ? OR relato LIKE ? OR proximo_passo LIKE ?)")
        args += ["%%%s%%" % busca] * 3

    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    limite = min(int(request.args.get("limite", 200)), 500)
    rows = get_db().execute(
        "SELECT * FROM fichas %s ORDER BY recebido_em DESC LIMIT ?" % onde,
        args + [limite]).fetchall()

    fichas = []
    for r in rows:
        d = dict(r)
        try:
            d["extra"] = json.loads(d.pop("extra_json") or "{}")
        except ValueError:
            d["extra"] = {}
        fichas.append(d)

    db = get_db()
    return jsonify({
        "fichas": fichas,
        "opcoes": {
            "meses": [x[0] for x in db.execute(
                "SELECT DISTINCT substr(recebido_em,1,7) FROM fichas ORDER BY 1 DESC")],
            "municipios": [x[0] for x in db.execute(
                "SELECT DISTINCT municipio FROM fichas WHERE municipio <> '' ORDER BY 1")],
            "usuarios": [x[0] for x in db.execute(
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
    marcadores = ",".join("?" * len(curvas))
    rows = db.execute("""
        SELECT c.codigo, c.nome, c.cidade, c.curva, c.vol_12m, c.vendedor,
               MAX(f.recebido_em) AS ultima_visita,
               COUNT(f.uuid) AS total_visitas
          FROM clientes c
          LEFT JOIN fichas f ON f.cliente_codigo = c.codigo
         WHERE c.ativo = 1 AND c.curva IN (%s)
         GROUP BY c.codigo
    """ % marcadores, curvas).fetchall()

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
    """Ocorrencias tecnicas abertas pela ficha, para acompanhamento."""
    situacao = request.args.get("situacao", "aberta")
    onde = "WHERE ocorrencia_num IS NOT NULL"
    args = []
    if situacao in ("aberta", "resolvida"):
        onde += " AND ocorrencia_status = ?"
        args.append(situacao)
    rows = get_db().execute(
        "SELECT uuid, ocorrencia_num, ocorrencia_status, ocorrencia_fechada_em, "
        "cliente_nome, cliente_codigo, municipio, problema_tipo, relato, "
        "proximo_passo, prox_responsavel, prox_data, encaminhado_para, "
        "recebido_em, criado_em_disp, foto_arquivo, usuario_login "
        "FROM fichas " + onde + " ORDER BY ocorrencia_num DESC LIMIT 300", args
    ).fetchall()

    hoje = datetime.now(timezone.utc)
    saida = []
    for r in rows:
        d = dict(r)
        try:
            d["dias_aberta"] = (hoje - datetime.fromisoformat(r["recebido_em"])).days
        except (TypeError, ValueError):
            d["dias_aberta"] = None
        saida.append(d)

    db = get_db()
    return jsonify({
        "ocorrencias": saida,
        "abertas": db.execute("SELECT COUNT(*) c FROM fichas "
                              "WHERE ocorrencia_status = 'aberta'").fetchone()["c"],
        "resolvidas": db.execute("SELECT COUNT(*) c FROM fichas "
                                 "WHERE ocorrencia_status = 'resolvida'").fetchone()["c"],
    })


@app.route("/api/gestor/ocorrencia/<numero>/resolver", methods=["POST"])
@gestor_obrigatorio
def api_resolver_ocorrencia(numero):
    if not re.fullmatch(r"OC-\d{4}-\d{4}", numero or ""):
        return jsonify({"erro": "numero_invalido"}), 400
    db = get_db()
    cur = db.execute(
        "UPDATE fichas SET ocorrencia_status = 'resolvida', ocorrencia_fechada_em = ? "
        "WHERE ocorrencia_num = ? AND ocorrencia_status = 'aberta'",
        (_agora(), numero))
    db.commit()
    if not cur.rowcount:
        return jsonify({"erro": "nao_encontrada_ou_ja_resolvida"}), 404
    return jsonify({"ok": True, "numero": numero})


@app.route("/api/gestor/experiencia")
@gestor_obrigatorio
def api_gestor_experiencia():
    """Leitura da pesquisa, com cada metrica calculada do seu jeito.

    NPS  -> % promotores menos % detratores (so perguntas de recomendacao)
    CSAT -> % de notas >= 8, por etapa da jornada
    CES  -> % que achou facil (>= 8), no pos-venda
    """
    db = get_db()
    mes = request.args.get("mes")
    base, args = "FROM fichas WHERE exp_nota IS NOT NULL", []
    if mes:
        base += " AND substr(recebido_em,1,7) = ?"
        args.append(mes)

    def bloco(metrica, corte):
        linhas = db.execute(
            "SELECT exp_etapa, COUNT(*) n, ROUND(AVG(exp_nota),1) media, "
            "SUM(CASE WHEN exp_nota >= ? THEN 1 ELSE 0 END) bons, "
            "SUM(CASE WHEN exp_nota <= ? THEN 1 ELSE 0 END) ruins "
            + base + " AND exp_metrica = ? GROUP BY exp_etapa ORDER BY media ASC",
            [corte, NPS_DETRATOR, metrica] + args).fetchall()
        tot = db.execute(
            "SELECT COUNT(*) n, ROUND(AVG(exp_nota),1) media, "
            "SUM(CASE WHEN exp_nota >= ? THEN 1 ELSE 0 END) bons, "
            "SUM(CASE WHEN exp_nota <= ? THEN 1 ELSE 0 END) ruins "
            + base + " AND exp_metrica = ?",
            [corte, NPS_DETRATOR, metrica] + args).fetchone()
        n = tot["n"] or 0
        return {
            "por_etapa": [dict(r) for r in linhas], "n": n, "media": tot["media"],
            "bons": tot["bons"] or 0, "ruins": tot["ruins"] or 0,
            "pct_bons": round(100.0 * (tot["bons"] or 0) / n) if n else None,
        }

    nps = bloco("nps", NPS_PROMOTOR)
    nps["indice"] = (round(100.0 * (nps["bons"] - nps["ruins"]) / nps["n"])
                     if nps["n"] else None)

    comentarios = [dict(r) for r in db.execute(
        "SELECT cliente_nome, exp_etapa, exp_nota, exp_comentario, exp_metrica, recebido_em "
        + base + " AND exp_comentario <> '' ORDER BY exp_nota ASC, recebido_em DESC LIMIT 40",
        args)]

    return jsonify({
        "nps": nps,
        "csat": bloco("csat", CSAT_SATISFEITO),
        "ces": bloco("ces", CES_FACIL),
        "comentarios": comentarios,
        "cortes": {"nps_promotor": NPS_PROMOTOR, "nps_detrator": NPS_DETRATOR,
                   "csat_satisfeito": CSAT_SATISFEITO, "ces_facil": CES_FACIL},
    })


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
        row = db.execute("SELECT senha_hash FROM usuarios WHERE id = ?",
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
            db.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?",
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
    if db.execute("SELECT 1 FROM usuarios WHERE login = ?", (login_txt,)).fetchone():
        return jsonify({"erro": "login_ja_existe"}), 409
    db.execute("INSERT INTO usuarios (login, nome, senha_hash, papel, base, ativo, criado_em)"
               " VALUES (?,?,?,?,'ITZ',1,?)",
               (login_txt, nome, _hash(senha), papel, _agora()))
    db.commit()
    return jsonify({"ok": True, "login": login_txt})


@app.route("/api/gestor/usuarios/<int:uid>", methods=["PATCH"])
@gestor_obrigatorio
def api_alterar_usuario(uid):
    d = request.get_json(silent=True) or {}
    db = get_db()
    alvo = db.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
    if not alvo:
        return jsonify({"erro": "nao_encontrado"}), 404

    if "ativo" in d:
        if uid == session["uid"]:
            return jsonify({"erro": "nao_pode_desativar_a_si_mesmo"}), 400
        db.execute("UPDATE usuarios SET ativo = ? WHERE id = ?",
                   (1 if d["ativo"] else 0, uid))
    if "papel" in d and d["papel"] in ("rep", "gestor"):
        if uid == session["uid"] and d["papel"] != "gestor":
            return jsonify({"erro": "nao_pode_rebaixar_a_si_mesmo"}), 400
        db.execute("UPDATE usuarios SET papel = ? WHERE id = ?", (d["papel"], uid))
    if "senha" in d:
        if len(d["senha"] or "") < SENHA_MIN:
            return jsonify({"erro": "senha_curta"}), 400
        db.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?",
                   (_hash(d["senha"]), uid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/foto/<nome>")
@login_obrigatorio
def foto(nome):
    if not re.fullmatch(r"[A-Za-z0-9_\-]+\.(jpg|png)", nome or ""):
        return "", 404
    return send_from_directory(FOTOS_DIR, nome)


@app.route("/saude")
def saude():
    try:
        n = get_db().execute("SELECT COUNT(*) c FROM clientes").fetchone()["c"]
        return jsonify({"ok": True, "clientes": n, "hora": _agora()})
    except Exception as exc:
        return jsonify({"ok": False, "erro": str(exc)}), 500


init_db()

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8010))
    print("[rep-campo] iniciando em http://127.0.0.1:%d" % porta)
    app.run(host="0.0.0.0", port=porta, debug=False)
