# -*- coding: utf-8 -*-
"""Repositórios Postgres. Único lugar com SQL fora de `scripts/setup_db.py`.

Antes cada blueprint montava seu próprio `SELECT` (`web/gestor.py`,
`web/viagens.py`, `web/fichas.py`, `web/importar.py`). A mesma tabela era
lida de 3 jeitos diferentes e mudar uma coluna exigia caçar SQL espalhado.
Agora o web chama estas funções e a aplicação orquestra — SQL mora aqui só.
"""
from collections import Counter


# --- acesso / auth ---

def papel_ativo(db, uid):
    return db.execute(
        "SELECT papel, ativo FROM usuarios WHERE id = %s", (uid,)
    ).fetchone()


def usuario_ativo_por_login(db, login):
    return db.execute(
        "SELECT * FROM usuarios WHERE login = %s AND ativo = 1", (login,)
    ).fetchone()


def senha_hash_por_uid(db, uid):
    return db.execute(
        "SELECT senha_hash FROM usuarios WHERE id = %s", (uid,)
    ).fetchone()


# --- fichas / bootstrap / resumo ---

def clientes_bootstrap(db):
    return [dict(r) for r in db.execute(
        "SELECT codigo, nome, cidade, curva, vol_12m, rota, vendedor "
        "FROM clientes WHERE ativo = 1 ORDER BY nome"
    ).fetchall()]


def ultimo_nps_por_cliente(db):
    return {r["cliente_codigo"]: r["quando"] for r in db.execute(
        "SELECT cliente_codigo, MAX(recebido_em) quando FROM fichas "
        "WHERE exp_metrica = 'nps' AND cliente_codigo IS NOT NULL "
        "GROUP BY cliente_codigo")}


def ficha_existe(db, uuid_f):
    return bool(db.execute(
        "SELECT 1 FROM fichas WHERE uuid = %s", (uuid_f,)).fetchone())


def listar_fichas(db, limite, usuario_login=None):
    if usuario_login is None:
        rows = db.execute(
            "SELECT * FROM fichas ORDER BY recebido_em DESC LIMIT %s", (limite,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM fichas WHERE usuario_login = %s "
            "ORDER BY recebido_em DESC LIMIT %s", (usuario_login, limite)
        ).fetchall()
    return [dict(r) for r in rows]


def resumo_mes(db, mes, usuario_login=None):
    where = "WHERE substr(recebido_em,1,7) = %s"
    args = [mes]
    if usuario_login is not None:
        where += " AND usuario_login = %s"
        args.append(usuario_login)
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
    return {"total": total, "por_tipo": por_tipo, "por_nivel": por_nivel,
            "validas": validas, "municipios": municipios, "clientes": clientes}


# --- painel gestor: fichas ---

def listar_fichas_gestor(db, mes=None, tipo=None, municipio=None,
                         usuario=None, nivel=None, busca=None, limite=200):
    filtros, args = [], []
    if mes:
        filtros.append("substr(recebido_em,1,7) = %s")
        args.append(mes)
    for campo, valor in (("tipo", tipo), ("municipio", municipio),
                         ("usuario_login", usuario), ("nivel_evidencia", nivel)):
        if valor:
            filtros.append(f"{campo} = %s")
            args.append(valor)
    busca = (busca or "").strip()
    if busca:
        filtros.append("(cliente_nome ILIKE %s OR relato ILIKE %s OR proximo_passo ILIKE %s)")
        args += ["%%%s%%" % busca] * 3
    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    rows = db.execute(
        f"SELECT * FROM fichas {onde} ORDER BY recebido_em DESC LIMIT %s",
        args + [limite]).fetchall()
    return [dict(r) for r in rows]


def anexos_por_fichas(db, uuids):
    por_ficha: dict = {}
    if not uuids:
        return por_ficha
    for a in db.execute(
            "SELECT ficha_uuid, arquivo, tipo, descricao FROM anexos "
            "WHERE ficha_uuid = ANY(%s) ORDER BY id", (uuids,)):
        por_ficha.setdefault(a["ficha_uuid"], []).append(
            {"arquivo": a["arquivo"], "tipo": a["tipo"], "descricao": a["descricao"]})
    return por_ficha


def opcoes_fichas(db):
    return {
        "meses": [x["mes"] for x in db.execute(
            "SELECT DISTINCT substr(recebido_em,1,7) AS mes FROM fichas "
            "ORDER BY 1 DESC")],
        "municipios": [x["municipio"] for x in db.execute(
            "SELECT DISTINCT municipio FROM fichas WHERE municipio <> '' ORDER BY 1")],
        "usuarios": [x["usuario_login"] for x in db.execute(
            "SELECT DISTINCT usuario_login FROM fichas ORDER BY 1")],
    }


# --- cobertura / ocorrências / experiência ---

def cobertura_linhas(db, curvas):
    return [dict(r) for r in db.execute("""
        SELECT c.codigo, c.nome, c.cidade, c.curva, c.vol_12m, c.vendedor,
               MAX(f.recebido_em) AS ultima_visita,
               COUNT(f.uuid) AS total_visitas
          FROM clientes c
          LEFT JOIN fichas f ON f.cliente_codigo = c.codigo
         WHERE c.ativo = 1 AND c.curva = ANY(%s)
         GROUP BY c.codigo
    """, (curvas,)).fetchall()]


def listar_ocorrencias(db, situacao=None, canal=None, setor=None, tipo=None):
    filtros, args = [], []
    for campo, valor in (("status", situacao), ("canal", canal),
                         ("setor", setor), ("tipo", tipo)):
        if valor:
            filtros.append(f"{campo} = %s")
            args.append(valor)
    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    return [dict(r) for r in db.execute(
        "SELECT * FROM ocorrencias " + onde + " ORDER BY numero DESC LIMIT 300", args
    ).fetchall()]


def contagem_ocorrencias(db):
    cont = {x["status"]: x["n"] for x in db.execute(
        "SELECT status, COUNT(*) AS n FROM ocorrencias GROUP BY status")}
    por_canal = {x["canal"]: x["n"] for x in db.execute(
        "SELECT canal, COUNT(*) AS n FROM ocorrencias GROUP BY canal")}
    return cont, por_canal


def ocorrencia_existe(db, numero):
    return bool(db.execute(
        "SELECT 1 FROM ocorrencias WHERE numero = %s", (numero,)).fetchone())


def experiencia_bloco(db, metrica, corte_bons, corte_ruins, mes=None):
    base, args = "FROM experiencia WHERE 1=1", []
    if mes:
        base += " AND substr(registrado_em,1,7) = %s"
        args.append(mes)
    linhas = db.execute(
        "SELECT etapa, COUNT(*) n, ROUND(AVG(nota),1) media, "
        "SUM(CASE WHEN nota >= %s THEN 1 ELSE 0 END) bons, "
        "SUM(CASE WHEN nota <= %s THEN 1 ELSE 0 END) ruins "
        + base + " AND metrica = %s GROUP BY etapa ORDER BY media ASC",
        [corte_bons, corte_ruins] + args + [metrica]).fetchall()
    tot = db.execute(
        "SELECT COUNT(*) n, ROUND(AVG(nota),1) media, "
        "SUM(CASE WHEN nota >= %s THEN 1 ELSE 0 END) bons, "
        "SUM(CASE WHEN nota <= %s THEN 1 ELSE 0 END) ruins "
        + base + " AND metrica = %s",
        [corte_bons, corte_ruins] + args + [metrica]).fetchone()
    return linhas, tot, base, args


def experiencia_comentarios(db, base, args):
    return [dict(r) for r in db.execute(
        "SELECT cliente_nome, etapa AS exp_etapa, nota AS exp_nota, "
        "comentario AS exp_comentario, metrica AS exp_metrica, "
        "registrado_em AS recebido_em " + base +
        " AND comentario IS NOT NULL AND comentario <> '' "
        "ORDER BY nota ASC, registrado_em DESC LIMIT 40", args)]


def experiencia_expedicao(db, base, args, corte):
    return [dict(r) for r in db.execute(
        "SELECT unidade, COUNT(*) n, ROUND(AVG(nota),1) media, "
        "SUM(CASE WHEN nota >= %s THEN 1 ELSE 0 END) bons " + base +
        " AND etapa = 'Atendimento da expedicao' AND unidade IS NOT NULL "
        "GROUP BY unidade ORDER BY media ASC", [corte] + args)]


def experiencia_clientes_ouvidos(db, base, args):
    return db.execute(
        "SELECT COUNT(DISTINCT COALESCE(cliente_codigo, cliente_nome)) c "
        + base, args).fetchone()["c"]


# --- usuários ---

def listar_usuarios(db):
    return [dict(r) for r in db.execute(
        "SELECT id, login, nome, papel, ativo, criado_em FROM usuarios ORDER BY ativo DESC, nome"
    ).fetchall()]


def login_existe(db, login):
    return bool(db.execute(
        "SELECT 1 FROM usuarios WHERE login = %s", (login,)).fetchone())


def obter_usuario(db, uid):
    return db.execute("SELECT * FROM usuarios WHERE id = %s", (uid,)).fetchone()


def criar_usuario(db, login, nome, senha_hash, papel, agora):
    db.execute("INSERT INTO usuarios (login, nome, senha_hash, papel, base, ativo, criado_em)"
               " VALUES (%s,%s,%s,%s,'ITZ',1,%s)",
               (login, nome, senha_hash, papel, agora))
    db.commit()


def atualizar_usuario(db, uid, ativo=None, papel=None, senha_hash=None):
    if ativo is not None:
        db.execute("UPDATE usuarios SET ativo = %s WHERE id = %s",
                   (1 if ativo else 0, uid))
    if papel is not None:
        db.execute("UPDATE usuarios SET papel = %s WHERE id = %s", (papel, uid))
    if senha_hash is not None:
        db.execute("UPDATE usuarios SET senha_hash = %s WHERE id = %s",
                   (senha_hash, uid))


def atualizar_senha(db, uid, senha_hash):
    db.execute("UPDATE usuarios SET senha_hash = %s WHERE id = %s",
               (senha_hash, uid))
    db.commit()


# --- viagens / rotas / sugestão ---

def rotas_brutas(db):
    return list(db.execute("""
        SELECT COALESCE(NULLIF(TRIM(rota),''),'Sem rota') AS rota,
               COALESCE(NULLIF(TRIM(cidade),''),'Sem cidade') AS cidade,
               COUNT(*) n, ROUND(SUM(vol_12m)) vol
          FROM clientes WHERE ativo = 1
         GROUP BY rota, cidade ORDER BY rota, n DESC"""))


def sugestao_linhas(db, cidades=None, municipio=None, rota=None):
    filtros, args = ["c.ativo = 1"], []
    cidades = cidades or []
    if cidades:
        filtros.append("COALESCE(NULLIF(TRIM(c.cidade),''),'Sem cidade') = ANY(%s)")
        args.append(cidades)
    elif municipio:
        filtros.append("c.cidade ILIKE %s")
        args.append("%%%s%%" % municipio)
    if rota and not cidades:
        if rota == "Sem rota":
            filtros.append("(c.rota IS NULL OR TRIM(c.rota) = '' OR LOWER(TRIM(c.rota)) = 'sem rota')")
        else:
            filtros.append("TRIM(c.rota) = %s")
            args.append(rota)
    return [dict(r) for r in db.execute("""
        SELECT c.codigo, c.nome, c.cidade, c.rota, c.curva, c.vol_12m, c.vendedor,
               c.ultima_compra, c.pedidos_12m,
               MAX(f.recebido_em) AS ultima_visita,
               (SELECT COUNT(*) FROM ocorrencias o
                 WHERE o.cliente_codigo = c.codigo AND o.status <> 'resolvida') AS oc_abertas,
               (SELECT MIN(e.nota) FROM experiencia e
                 WHERE e.cliente_codigo = c.codigo) AS pior_nota,
               (SELECT COUNT(*) FROM recados rc
                 WHERE rc.cliente_codigo = c.codigo
                   AND rc.status IN ('aberto','lido')) AS recados_abertos,
               (SELECT rc.criado_por_nome FROM recados rc
                 WHERE rc.cliente_codigo = c.codigo
                   AND rc.status IN ('aberto','lido')
                 ORDER BY rc.id DESC LIMIT 1) AS recado_de
          FROM clientes c
          LEFT JOIN fichas f ON f.cliente_codigo = c.codigo
         WHERE __FILTROS__
         GROUP BY c.codigo
    """.replace("__FILTROS__", " AND ".join(filtros)), args)]


def criar_viagem(db, nome, inicio, fim, rota, observacao, criada_por,
                 responsavel, criada_em, tipo):
    return db.execute("""INSERT INTO viagens (nome, inicio, fim, rota,
        observacao, status, criada_por, responsavel, criada_em, tipo)
        VALUES (%s,%s,%s,%s,%s,'planejada',%s,%s,%s,%s) RETURNING id""",
        (nome, inicio, fim, rota, observacao, criada_por,
         responsavel, criada_em, tipo)).fetchone()


def listar_viagens(db, login=None):
    if login is None:
        onde, args = "", []
    else:
        onde = "WHERE responsavel = %s OR criada_por = %s"
        args = [login, login]
    return [dict(v) for v in db.execute(f"""
        SELECT v.*, COUNT(vc.id) AS planejados,
               COALESCE(SUM(vc.visitado), 0) AS visitados
          FROM viagens v
          LEFT JOIN viagem_clientes vc ON vc.viagem_id = v.id
          {onde}
         GROUP BY v.id
         ORDER BY COALESCE(v.inicio, v.criada_em) DESC
         LIMIT 60""", args)]


def obter_viagem(db, vid):
    row = db.execute("SELECT * FROM viagens WHERE id = %s", (vid,)).fetchone()
    return dict(row) if row else None


def atualizar_viagem_status(db, vid, status):
    db.execute("UPDATE viagens SET status = %s WHERE id = %s", (status, vid))
    db.commit()


def atualizar_viagem_campo(db, vid, campo, valor):
    db.execute(f"UPDATE viagens SET {campo} = %s WHERE id = %s", (valor, vid))


def confirmar_viagem(db):
    db.commit()


def excluir_viagem(db, vid):
    db.execute("DELETE FROM viagem_clientes WHERE viagem_id = %s", (vid,))
    db.execute("DELETE FROM viagens WHERE id = %s", (vid,))
    db.commit()


def adicionar_clientes(db, vid, lista):
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
    return add


def remover_cliente_viagem(db, vid, cid):
    db.execute("DELETE FROM viagem_clientes WHERE id = %s AND viagem_id = %s", (cid, vid))
    db.commit()


def clientes_da_viagem(db, vid):
    return [dict(r) for r in db.execute(
        "SELECT * FROM viagem_clientes WHERE viagem_id = %s ORDER BY visitado, ordem, cliente_nome",
        (vid,))]


def fichas_da_viagem(db, vid):
    return [dict(r) for r in db.execute(
        "SELECT uuid, tipo, cliente_nome, cliente_codigo, municipio, objetivo, relato, "
        "proximo_passo, prox_responsavel, prox_data, encaminhado_para, problema_tipo, "
        "ocorrencia_num, nivel_evidencia, conta_indicador, criado_em_disp, recebido_em "
        "FROM fichas WHERE viagem_id = %s ORDER BY recebido_em", (vid,))]


def pesquisa_da_viagem(db, uuids):
    if not uuids:
        return [], []
    respostas = [dict(r) for r in db.execute(
        "SELECT cliente_nome, etapa, metrica, nota, comentario, unidade "
        "FROM experiencia WHERE ficha_uuid = ANY(%s) ORDER BY nota", (uuids,))]
    ocorrencias = [dict(r) for r in db.execute(
        "SELECT numero, cliente_nome, tipo, status, responsavel "
        "FROM ocorrencias WHERE ficha_uuid = ANY(%s) ORDER BY numero", (uuids,))]
    return respostas, ocorrencias


def visitas_avulsas(db, mes, usuario_login=None):
    filtros = ["viagem_id IS NULL", "substr(recebido_em,1,7) = %s"]
    args = [mes]
    if usuario_login is not None:
        filtros.append("usuario_login = %s")
        args.append(usuario_login)
    return [dict(r) for r in db.execute(
        "SELECT uuid, tipo, cliente_nome, municipio, proximo_passo, usuario_login, "
        "recebido_em FROM fichas WHERE " + " AND ".join(filtros) +
        " ORDER BY recebido_em DESC LIMIT 300", args)]


# --- importar rotas ---

def substituir_rotas(db, linhas, agora):
    from rep_campo.dominio.texto import chave_cidade
    db.execute("DELETE FROM rotas_cidades")
    for cidade, base, rota, tabela in [(l + ["", "", ""])[:4] for l in linhas]:
        db.execute("""INSERT INTO rotas_cidades (chave, cidade, base, rota, tabela,
                      atualizado_em) VALUES (%s,%s,%s,%s,%s,%s)
                      ON CONFLICT (chave) DO UPDATE SET cidade=excluded.cidade,
                      base=excluded.base, rota=excluded.rota, tabela=excluded.tabela,
                      atualizado_em=excluded.atualizado_em""",
                   (chave_cidade(cidade), cidade, base, rota, tabela, agora))
    db.commit()
    itz = db.execute("SELECT COUNT(*) c FROM rotas_cidades WHERE LOWER(base)='imperatriz'").fetchone()["c"]
    rotas = [r["rota"] for r in db.execute(
        "SELECT DISTINCT rota FROM rotas_cidades WHERE LOWER(base)='imperatriz' "
        "AND rota <> '' AND LOWER(rota) <> 'sem rota' ORDER BY rota")]
    return itz, rotas


def mapa_rotas(db):
    return {r["chave"]: dict(r) for r in db.execute("SELECT * FROM rotas_cidades")}


def aplicar_mapa_rotas(db, mapa):
    from rep_campo.dominio.texto import chave_cidade
    corrigidos, fora, outra_base = [], [], []
    for c in db.execute("SELECT codigo, cidade, rota FROM clientes WHERE ativo = 1"):
        m = mapa.get(chave_cidade(c["cidade"]))
        if not m:
            fora.append(c["cidade"])
            continue
        if (m["base"] or "").lower() != "imperatriz":
            outra_base.append(c["cidade"])
            continue
        nova = "" if (m["rota"] or "").strip().lower() in ("", "sem rota") else m["rota"].strip()
        atual = (c["rota"] or "").strip()
        if chave_cidade(atual) != chave_cidade(nova):
            db.execute("UPDATE clientes SET rota = %s, tabela = COALESCE(NULLIF(%s,''), tabela) "
                       "WHERE codigo = %s", (nova, m["tabela"], c["codigo"]))
            corrigidos.append({"cidade": c["cidade"], "de": atual or "(sem rota)",
                               "para": nova or "(sem rota)"})
    db.commit()
    resumo = Counter((x["de"], x["para"]) for x in corrigidos)
    return corrigidos, resumo, fora, outra_base


# --- sistema ---

def contar_clientes(db):
    return db.execute("SELECT COUNT(*) c FROM clientes").fetchone()["c"]


# ------------------------------------------------------------------ recados

def criar_recado(db, criado_em, criado_por, criado_por_nome, para_login, texto,
                 cliente_codigo, cliente_nome, prazo):
    return db.execute("""
        INSERT INTO recados (criado_em, criado_por, criado_por_nome, para_login,
                             texto, cliente_codigo, cliente_nome, prazo)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (criado_em, criado_por, criado_por_nome, para_login, texto,
         cliente_codigo or None, cliente_nome or None, prazo or None)).fetchone()["id"]


def obter_recado(db, rid):
    return db.execute("SELECT * FROM recados WHERE id = %s", (rid,)).fetchone()


def listar_recados(db, para_login=None, status=None, limite=200):
    filtros, args = [], []
    if para_login:
        filtros.append("para_login = %s")
        args.append(para_login)
    if status:
        filtros.append("status = ANY(%s)")
        args.append(list(status))
    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    args.append(limite)
    return [dict(r) for r in db.execute(
        "SELECT * FROM recados %s ORDER BY id DESC LIMIT %%s" % onde, args)]


def recados_pendentes(db, para_login, pendentes):
    """O que o app do representante carrega. Vai no bootstrap, entao fica
    guardado no aparelho e ele le mesmo sem sinal."""
    return [dict(r) for r in db.execute("""
        SELECT id, texto, cliente_codigo, cliente_nome, prazo, status,
               criado_em, criado_por_nome
          FROM recados
         WHERE para_login = %s AND status = ANY(%s)
         ORDER BY (cliente_codigo IS NULL) DESC, id DESC""",
        (para_login, list(pendentes)))]


def marcar_recados_lidos(db, para_login, ids, quando):
    if not ids:
        return 0
    cur = db.execute("""
        UPDATE recados SET status = 'lido', lido_em = %s
         WHERE para_login = %s AND id = ANY(%s) AND status = 'aberto'""",
        (quando, para_login, list(ids)))
    return cur.rowcount


def concluir_recado(db, rid, para_login, resposta, ficha_uuid, quando, pendentes):
    cur = db.execute("""
        UPDATE recados SET status = 'concluido', concluido_em = %s,
               resposta = %s, ficha_uuid = COALESCE(%s, ficha_uuid)
         WHERE id = %s AND para_login = %s AND status = ANY(%s)""",
        (quando, resposta or None, ficha_uuid or None, rid, para_login, list(pendentes)))
    return cur.rowcount


def cancelar_recado(db, rid, pendentes):
    cur = db.execute(
        "UPDATE recados SET status = 'cancelado' WHERE id = %s AND status = ANY(%s)",
        (rid, list(pendentes)))
    return cur.rowcount


def contagem_recados(db, para_login, pendentes):
    return db.execute("""
        SELECT COUNT(*) FILTER (WHERE cliente_codigo IS NULL) AS gerais,
               COUNT(*) FILTER (WHERE cliente_codigo IS NOT NULL) AS missoes
          FROM recados WHERE para_login = %s AND status = ANY(%s)""",
        (para_login, list(pendentes))).fetchone()


# --------------------------------------------------- precos da concorrencia

def precos_ultimos(db, concorrente=None, item=None, municipio=None, desde=None):
    """Ultimo preco de cada combinacao concorrente x item x municipio.

    DISTINCT ON e do Postgres: com o ORDER BY abaixo ele entrega a linha mais
    recente de cada grupo sem subconsulta.
    """
    filtros, args = [], []
    if concorrente:
        filtros.append("concorrente = %s"); args.append(concorrente)
    if item:
        filtros.append("item = %s"); args.append(item)
    if municipio:
        filtros.append("municipio = %s"); args.append(municipio)
    if desde:
        filtros.append("coletado_em >= %s"); args.append(desde)
    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    return [dict(r) for r in db.execute("""
        SELECT DISTINCT ON (concorrente, item, municipio)
               concorrente, item, municipio, rota, preco, coletado_em,
               usuario_login, condicao_pagamento, prazo_entrega
          FROM precos_concorrencia %s
         ORDER BY concorrente, item, municipio, coletado_em DESC""" % onde, args)]


def precos_serie(db, concorrente, item):
    return [dict(r) for r in db.execute("""
        SELECT LEFT(coletado_em, 7) AS mes, municipio,
               ROUND(AVG(preco), 2) AS media, COUNT(*) AS coletas
          FROM precos_concorrencia
         WHERE concorrente = %s AND item = %s
         GROUP BY mes, municipio ORDER BY mes DESC, municipio""",
        (concorrente, item))]


def precos_onde_atua(db):
    """Area de influencia observada: onde cada concorrente apareceu de fato,
    e nao onde alguem cadastrou que ele atua."""
    return [dict(r) for r in db.execute("""
        SELECT concorrente,
               COALESCE(NULLIF(TRIM(municipio),''),'sem cidade') AS municipio,
               COALESCE(NULLIF(TRIM(rota),''),'sem rota') AS rota,
               COUNT(*) AS coletas, MAX(coletado_em) AS visto_em
          FROM precos_concorrencia
         GROUP BY concorrente, municipio, rota
         ORDER BY concorrente, visto_em DESC""")]


def precos_opcoes(db):
    conc = [r["concorrente"] for r in db.execute(
        "SELECT DISTINCT concorrente FROM precos_concorrencia ORDER BY concorrente")]
    itens = [r["item"] for r in db.execute(
        "SELECT DISTINCT item FROM precos_concorrencia ORDER BY item")]
    cidades = [r["municipio"] for r in db.execute(
        "SELECT DISTINCT municipio FROM precos_concorrencia "
        "WHERE municipio IS NOT NULL AND TRIM(municipio) <> '' ORDER BY municipio")]
    return {"concorrentes": conc, "itens": itens, "municipios": cidades}
