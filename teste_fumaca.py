#!/usr/bin/env python3
"""Passa por todas as telas e rotas do app contra o banco e o Blob de verdade.

    python3 teste_fumaca.py

Cria os proprios usuarios com senha sorteada na hora, manda um lote de fichas com
foto e evidencia, monta uma viagem e confere as respostas. Tudo que ele grava
carrega a marca do teste e sai no fim, inclusive os usuarios.

Rode depois de mexer no app.py e antes de publicar. Ele fala com o Neon e com o
Blob de producao, entao nao rode com o Ricardo usando o app no mesmo minuto.
"""
import base64
import os
import secrets
import sys
import uuid as uuidlib

# o cookie de sessao exige HTTPS em producao; no cliente de teste nao ha TLS
os.environ["REP_INSECURE_COOKIE"] = "1"

import app as appmod
from werkzeug.security import generate_password_hash

SENHA = secrets.token_urlsafe(16)

PNG = base64.b64encode(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)).decode()
FOTO = "data:image/png;base64," + PNG

falhas = []


def checa(nome, condicao, detalhe=""):
    print(("  ok  " if condicao else "FALHA ") + nome + (" | " + str(detalhe) if detalhe and not condicao else ""))
    if not condicao:
        falhas.append(nome)


def entrar(cli, login, senha=SENHA):
    r = cli.post("/login", data={"login": login, "senha": senha},
                 follow_redirects=False)
    return r.status_code in (302, 303)


def main():
    appmod.app.config["TESTING"] = True
    marca = "t" + uuidlib.uuid4().hex[:12]
    contas = {"g." + marca[1:9]: "gestor", "r." + marca[1:9]: "rep",
              "o." + marca[1:9]: "rep"}
    with appmod.app.app_context():
        db = appmod.get_db()
        for login, papel in contas.items():
            db.execute("INSERT INTO usuarios (login, nome, senha_hash, papel, base,"
                       " ativo, criado_em) VALUES (%s,%s,%s,%s,'ITZ',1,%s)",
                       (login, "Teste " + papel,
                        generate_password_hash(SENHA, method="pbkdf2:sha256"),
                        papel, appmod._agora()))
        db.commit()
    lgestor, lrep, loutro = list(contas)

    gestor = appmod.app.test_client()
    rep = appmod.app.test_client()

    checa("login do gestor", entrar(gestor, lgestor))
    checa("login do rep", entrar(rep, lrep))

    r = appmod.app.test_client().post("/login", data={"login": lgestor, "senha": "errada"})
    checa("senha errada nao entra", r.status_code == 200 and b"invalidos" in r.data)

    checa("saude", appmod.app.test_client().get("/saude").get_json().get("ok") is True)
    checa("bootstrap", rep.get("/api/bootstrap").status_code == 200)
    checa("tela inicial", rep.get("/").status_code == 200)
    checa("tela de viagens", rep.get("/viagens").status_code == 200)
    checa("painel so para gestor", rep.get("/api/gestor/fichas").status_code == 403)
    r = appmod.app.test_client().get("/sw.js")
    checa("service worker na raiz", r.status_code == 200 and b"rep-campo-v" in r.data, r.status_code)
    checa("manifest", appmod.app.test_client().get("/manifest.webmanifest").status_code == 200)
    checa("arquivo estatico", rep.get("/static/app.js").status_code == 200)
    checa("tela do painel", gestor.get("/painel").status_code == 200)
    checa("tela da conta", rep.get("/conta").status_code == 200)
    checa("tela de usuarios so do gestor", rep.get("/usuarios").status_code in (302, 403))

    # lote com uma ficha boa, uma tecnica com evidencia e uma invalida no meio
    uuid_ok = marca + "-ok"
    uuid_tec = marca + "-tec"
    lote = {"fichas": [
        {"uuid": uuid_ok, "tipo": "comercial", "cliente_nome": "Cliente Teste A",
         "cliente_codigo": marca[:20], "municipio": "Imperatriz/MA",
         "relato": "visita de teste", "lat": -5.5236, "lon": -47.4822,
         "precisao": 8.5, "foto": FOTO,
         "experiencia": [{"etapa": "Atendimento comercial", "nota": 9},
                         {"etapa": "Atendimento da expedicao", "nota": 7,
                          "unidade": "Imperatriz"}]},
        {"uuid": "x", "tipo": "comercial", "cliente_nome": "uuid curto demais"},
        {"uuid": uuid_tec, "tipo": "tecnica", "cliente_nome": "Cliente Teste B",
         "cliente_codigo": marca[:20], "problema_tipo": "Arranhao",
         "relato": "reclamacao de teste", "foto": FOTO,
         "anexos": [{"foto": FOTO, "tipo": "peca", "descricao": "evidencia 1"},
                    {"foto": FOTO, "tipo": "nota", "descricao": "evidencia 2"}]},
    ]}
    r = rep.post("/api/fichas", json=lote)
    j = r.get_json() or {}
    checa("lote aceito", r.status_code == 200, r.status_code)
    checa("duas fichas entraram", sorted(j.get("aceitas", [])) == sorted([uuid_ok, uuid_tec]), j.get("aceitas"))
    checa("a invalida foi recusada com motivo",
          len(j.get("rejeitadas", [])) == 1 and j["rejeitadas"][0].get("motivo"), j.get("rejeitadas"))
    numero = (j.get("ocorrencias") or [{}])[0].get("numero", "")
    checa("ocorrencia numerada", numero.startswith("OC-"), numero)

    r = rep.post("/api/fichas", json=lote)
    checa("reenvio nao duplica", len((r.get_json() or {}).get("aceitas", [])) == 2)

    j = rep.get("/api/fichas").get_json()
    checa("rep ve as proprias fichas", any(f["uuid"] == uuid_ok for f in j["fichas"]))
    checa("a foto ficou registrada",
          next(f for f in j["fichas"] if f["uuid"] == uuid_ok)["foto_arquivo"] == uuid_ok + ".png")

    r = rep.get("/foto/" + uuid_ok + ".png")
    checa("a foto volta do Blob", r.status_code == 200 and len(r.data) > 0, r.status_code)
    checa("foto inexistente da 404", rep.get("/foto/naoexiste.png").status_code == 404)

    j = gestor.get("/api/gestor/fichas?limite=500").get_json()
    ficha_tec = next((f for f in j["fichas"] if f["uuid"] == uuid_tec), None)
    checa("o gestor ve a ficha tecnica", ficha_tec is not None)
    checa("as duas evidencias vieram juntas", ficha_tec and len(ficha_tec["anexos"]) == 2,
          ficha_tec and len(ficha_tec["anexos"]))

    j = gestor.get("/api/gestor/fichas?busca=cliente+teste+a").get_json()
    checa("busca ignora maiuscula", any(f["uuid"] == uuid_ok for f in j["fichas"]))
    checa("limite invalido nao derruba",
          gestor.get("/api/gestor/fichas?limite=abc").status_code == 200)

    j = gestor.get("/api/gestor/experiencia").get_json()
    checa("media da pesquisa e numero", isinstance(j["csat"]["media"], (float, int, type(None))),
          type(j["csat"]["media"]).__name__)
    checa("expedicao agrupada por unidade", isinstance(j.get("expedicao"), list))
    j = gestor.get("/api/gestor/experiencia?mes=2026-09").get_json()
    checa("filtro por mes nao zera", j["csat"]["n"] >= 1, j["csat"]["n"])

    checa("cobertura responde", gestor.get("/api/gestor/cobertura").status_code == 200)
    checa("ocorrencias respondem", gestor.get("/api/gestor/ocorrencias").status_code == 200)
    checa("resumo responde", rep.get("/api/resumo").status_code == 200)
    checa("rotas respondem", rep.get("/api/rotas").status_code == 200)
    checa("sugestao responde", rep.get("/api/sugestao").status_code == 200)

    r = rep.post("/api/viagens", json={"nome": "Viagem " + marca})
    vid = (r.get_json() or {}).get("id")
    checa("viagem criada com id", isinstance(vid, int), r.get_json())

    clientes = {"clientes": [{"codigo": marca[:20], "nome": "Cliente Teste A",
                              "cidade": "Imperatriz/MA", "motivo": "teste"}]}
    a1 = rep.post("/api/viagens/%d/clientes" % vid, json=clientes).get_json()
    a2 = rep.post("/api/viagens/%d/clientes" % vid, json=clientes).get_json()
    checa("primeiro envio inclui", a1.get("adicionados") == 1, a1)
    checa("toque duplo nao duplica", a2.get("adicionados") == 0, a2)
    roteiro = rep.get("/api/viagens/%d" % vid).get_json()
    checa("o roteiro tem um cliente so", len(roteiro["clientes"]) == 1, len(roteiro["clientes"]))

    checa("o gestor abre qualquer viagem", gestor.get("/api/viagens/%d" % vid).status_code == 200)
    outro = appmod.app.test_client()
    entrar(outro, loutro)
    checa("outro rep nao le a viagem", outro.get("/api/viagens/%d" % vid).status_code == 403,
          outro.get("/api/viagens/%d" % vid).status_code)
    checa("outro rep nao renomeia",
          outro.patch("/api/viagens/%d" % vid, json={"nome": "invadida"}).status_code == 403)
    checa("outro rep nao poe cliente",
          outro.post("/api/viagens/%d/clientes" % vid, json={"clientes": []}).status_code == 403)
    checa("outro rep nao apaga cliente",
          outro.delete("/api/viagens/%d/clientes/1" % vid).status_code == 403)
    r = rep.patch("/api/viagens/%d" % vid, json={"nome": "renomeada"})
    checa("dono renomeia", r.status_code == 200, r.status_code)

    # as tres telas de usuario que o commit d86b0f9 consertou
    novo_login = "u" + marca[1:9]
    r = gestor.post("/api/gestor/usuarios",
                    json={"login": novo_login, "nome": "Criado no teste",
                          "senha": "senha-de-teste-1", "papel": "rep"})
    checa("gestor cria usuario", r.status_code == 200, r.get_json())
    checa("senha curta e recusada",
          gestor.post("/api/gestor/usuarios",
                      json={"login": novo_login + "x", "nome": "X", "senha": "123"}
                      ).status_code == 400)
    lista = gestor.get("/api/gestor/usuarios").get_json()
    criado = next((u for u in lista["usuarios"] if u["login"] == novo_login), None)
    checa("o usuario novo aparece na lista", criado is not None)
    if criado:
        checa("gestor redefine a senha",
              gestor.patch("/api/gestor/usuarios/%d" % criado["id"],
                           json={"senha": "outra-senha-1"}).status_code == 200)
        novo_cli = appmod.app.test_client()
        checa("entra com a senha nova", entrar(novo_cli, novo_login, "outra-senha-1"))
        checa("troca a propria senha",
              novo_cli.post("/conta", data={"atual": "outra-senha-1",
                                            "nova": "terceira-senha-1",
                                            "confirma": "terceira-senha-1"}
                            ).status_code in (200, 302))
        checa("gestor desativa o usuario",
              gestor.patch("/api/gestor/usuarios/%d" % criado["id"],
                           json={"ativo": False}).status_code == 200)
        checa("desativado nao entra", not entrar(appmod.app.test_client(),
                                                novo_login, "terceira-senha-1"))

    if numero:
        r = gestor.patch("/api/gestor/ocorrencia/" + numero,
                         json={"status": "resolvida", "resolucao": "teste"})
        checa("gestor resolve a ocorrencia", r.status_code == 200, r.status_code)

    trava = appmod.app.test_client()
    for _ in range(9):
        ultima = trava.post("/login", data={"login": loutro, "senha": "errada"})
    checa("nona tentativa e barrada", ultima.status_code == 429, ultima.status_code)
    with appmod.app.app_context():
        db = appmod.get_db()
        db.execute("DELETE FROM tentativas_login")
        db.commit()

    j = rep.get("/api/viagens").get_json()
    minha = next((v for v in j["viagens"] if v["id"] == vid), None)
    checa("a viagem aparece na lista", minha is not None)
    checa("aderencia calculada", minha and minha["planejados"] == 1, minha and minha.get("planejados"))

    checa("apaga a viagem", rep.delete("/api/viagens/%d" % vid).status_code == 200)

    # limpeza
    with appmod.app.app_context():
        db = appmod.get_db()
        db.execute("DELETE FROM anexos WHERE ficha_uuid LIKE %s", (marca + "%",))
        db.execute("DELETE FROM experiencia WHERE ficha_uuid LIKE %s", (marca + "%",))
        db.execute("DELETE FROM ocorrencias WHERE ficha_uuid LIKE %s", (marca + "%",))
        db.execute("DELETE FROM fichas WHERE uuid LIKE %s", (marca + "%",))
        db.execute("DELETE FROM viagem_clientes WHERE cliente_codigo = %s", (marca[:20],))
        db.execute("DELETE FROM usuarios WHERE login LIKE %s", ("%" + marca[1:9],))
        db.execute("DELETE FROM usuarios WHERE login LIKE %s", ("u" + marca[1:9] + "%",))
        db.commit()

    print()
    if falhas:
        print("%d falha(s): %s" % (len(falhas), ", ".join(falhas)))
        return 1
    print("tudo passou")
    return 0


if __name__ == "__main__":
    sys.exit(main())
