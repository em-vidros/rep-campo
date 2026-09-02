# Guia de revisão do código — REP Campo

**Para:** Henrique (TI) · **De:** Ricardo · 01/09/2026

Este guia existe para você não precisar ler 700 linhas para achar o que importa.
Aponto direto os trechos que decidem segurança, com o número da linha.

---

## Tamanho do projeto

| Arquivo | Linhas | O que é |
|---|---|---|
| `app.py` | ~690 | Backend inteiro: rotas, API, banco |
| `static/app.js` | 463 | App do celular (fila offline, formulário) |
| `static/painel.js` | 177 | Painel de gestão |
| `templates/*.html` | 264 | Três telas |
| `static/sw.js` | 45 | Service worker (cache do app) |

Python + Flask + SQLite. **Sem framework de frontend, sem build, sem dependência
externa além do Flask.** Mesma stack do painel de metas.

---

## Os 9 pontos que valem sua atenção (`app.py`)

| Linha | O que olhar |
|---|---|
| **72** | `app.config.update` — limite de 12 MB por requisição e flags do cookie de sessão (`HttpOnly`, `Secure`, `SameSite=Lax`) |
| **82** | `LIMITES_TEXTO` — teto de caracteres por campo, para não inflarem o banco |
| **91** | `RE_UUID` — o regex que valida o identificador vindo do celular. **É ele que impede path traversal**, porque o nome do arquivo da foto deriva daí |
| **176** | `init_db()` — criação e migração de schema idempotente (`PRAGMA table_info` + `ALTER TABLE`) |
| **199 / 210** | `login_obrigatorio` e `gestor_obrigatorio` — os dois decoradores de acesso. Toda rota usa um dos dois, exceto `/login` e `/saude` |
| **237 / 248** | Freio de força bruta: 8 tentativas por origem, janela de 15 min, resposta 429 |
| **348 / 351** | `ASSINATURAS` e `_salvar_foto` — o tipo do arquivo é decidido pela **assinatura binária**, não pelo que o cliente declara; e o caminho final é conferido contra a pasta de destino antes de gravar |
| **414** | `api_receber_fichas` — a única rota que grava dados. Idempotente por uuid, valida tipo e cliente, classifica em vez de descartar |
| **661** | `/foto/<nome>` — regex no nome do arquivo antes de servir |

---

## Perguntas que você provavelmente vai fazer

**"Tem SQL injection?"**
Não. Todas as consultas usam parâmetros (`?`). Não há concatenação de valor em
SQL em lugar nenhum — vale conferir com `grep -n "execute(" app.py`.

**"Onde ficam as senhas?"**
Só o hash, na tabela `usuarios`, gerado com `pbkdf2:sha256`
(`criar_usuario.py`). A senha é digitada no terminal e nunca é gravada nem
trafegada em texto. Não existe senha no código.

**"E a chave de sessão?"**
Gerada com `secrets.token_hex(32)` na primeira execução e salva em
`dados/secret.key` com permissão `600` (linha ~52). **Não vai neste pacote** —
é gerada no servidor. Pode ser trocada por variável de ambiente (`REP_SECRET_KEY`)
se você preferir.

**"Alguma rota aberta?"**
Duas: `/login` e `/saude`. O `/saude` devolve apenas `{"ok": true, "clientes": N}`
— serve de health check. Se preferir que nem isso fique exposto, eu removo ou
protejo.

**"O app escreve fora da pasta dele?"**
Não. Só em `dados/` (banco, `secret.key` e `fotos/`). Todos os caminhos saem de
`BASE_DIR`, que é a pasta do próprio arquivo — o app não depende do diretório de
onde foi iniciado.

**"Executa comando do sistema?"**
Não. Não há `os.system`, `subprocess` nem `eval` no `app.py`. O único
`subprocess` do projeto está em `gerar_pdf.py`, que é utilitário local para
gerar documento e **não roda no servidor**.

---

## O que **não** vai neste pacote (de propósito)

- **Banco de dados** — tem a carteira de clientes real. Não é necessário para
  revisar código. É criado vazio no servidor com `importar_carteira.py`.
- **`secret.key`** — gerada na primeira execução, no próprio servidor.
- **Fotos** — não há; a pasta nasce vazia.
- **Backups do código antigo** — deixei de fora justamente porque contêm as
  versões **anteriores às correções de segurança**.

---

## Como rodar para testar

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install flask
python importar_carteira.py       # cria o banco (precisa da carteira; sem ela, o banco nasce vazio)
python criar_usuario.py teste "Teste" gestor
python app.py                      # http://localhost:8010
```

Para rodar sem HTTPS no teste local, use `REP_INSECURE_COOKIE=1` — é o que
desliga a flag `Secure` do cookie. **Em produção não use essa variável.**

---

## Como eu pretendo publicar

`scp` dos arquivos para a pasta do app + comando de restart. O banco fica em
`dados/` e não é tocado no deploy. Detalhe em `DEPLOY.md`.

Se você preferir outro fluxo — repositório Git, seu próprio pipeline, ou você
mesmo fazendo as publicações — me diz que eu me adapto.

Qualquer coisa que você queira mudar no código antes de subir, eu faço.
