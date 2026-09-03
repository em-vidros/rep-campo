# REP Campo — app de registro de visitas

App do representante comercial da **base Itz**. PWA (instala no celular),
**funciona sem internet** e sincroniza quando pega sinal.

Instrumento da metodologia descrita em
[EMVIDROS_REP_RELATORIOS_EVIDENCIAS.md](../EMVIDROS_REP_RELATORIOS_EVIDENCIAS.md).
Publicar: [PUBLICAR.md](docs/PUBLICAR.md) · Por que saiu do servidor:
[DEPLOY.md](docs/DEPLOY.md).

> Status: **em produção em `https://rep-campo.vercel.app`**, com banco no Neon e
> fotos no Vercel Blob desde 02/09/2026. Publicar é empurrar para a `main`, e a
> Vercel dispara o deploy sozinha.

---

## O que a v1 faz

- Ficha de visita com **7 tipos** (comercial, cordialidade, técnica, prospecção,
  preço, voz do cliente, evento) — campos mudam conforme o tipo
- **Offline-first**: grava no celular e sobe sozinho quando volta o sinal
- Check-in de localização e foto (comprimida no aparelho antes de subir)
- Busca de cliente sobre a carteira Itz (1.453 clientes, curva ABC)
- Rascunho automático — não perde o preenchimento se fechar o app
- Resumo do mês e lista das fichas

## Painel de gestão (`/painel` — só papel `gestor`)

**Cobertura da carteira** — a lista nominal do manual §7. Para cada cliente A/B:
última visita, dias desde então, e o ciclo esperado da praça
(Imperatriz 90 · Santa Inês e eixo Pindaré 120 · Pará 180 · demais 120).
Ordena por quem está mais abandonado, com desempate por faturamento — quem
nunca foi visitado aparece primeiro. Exporta CSV. No topo: % de cobertura no
ciclo, quantos venceram, quantos nunca receberam visita e **quanto de
faturamento 12m está sem cobertura**.

**Fichas de visita** — todas as fichas de todos os representantes, com filtro
por mês, tipo, município, representante, nível de evidência e busca livre no
relato. Abrindo a ficha: relato completo, próximo passo, campos do tipo, foto e
o check-in com link para o mapa.

O painel marca sozinho as fichas fracas: selo `sem próximo passo`, aviso de
relato curto e `sem localização registrada`. Não esconde nem descarta — mostra.

> `rep` que tentar acessar rota de gestão leva **403** na API e é devolvido ao
> app na tela. Representante nunca vê ficha de outro.

## Responsivo

Ambas as telas funcionam de 320 px a desktop.

| | App do representante | Painel de gestão |
|---|---|---|
| Desenho | mobile-first | desktop-first, adaptado |
| Celular (< 820 px) | layout nativo | tabela vira **cards em grade de 2 colunas** |
| Tablet (768 px) | 2 colunas | cards de resumo em 2 colunas |
| < 400 px | 1 coluna | cards de resumo em 1 coluna |

A tabela de cobertura tem 8 colunas — ilegível em 375 px. No celular cada linha
vira um card: nome e vendedor ocupam a largura toda, os demais campos ficam
pareados, e **"dias sem visita" sai em destaque** por ser o dado que decide a
rota. Cabem ~2,5 clientes por tela; como uma linha por card cabia menos de um,
rolar 376 clientes era inviável.

Filtros viram coluna com `font-size:16px` nos campos — abaixo disso o iOS dá
zoom automático ao focar o campo.

## O que a v1 **não** faz (fases seguintes)

Relatório semanal e mensal automáticos, scorecard com nota, cruzamento
automático com pedido do ERP. Ver §11 do manual.

---

## Stack

Flask + Postgres no Neon + PWA em JS puro (sem framework, sem build).
Publicado na Vercel. Para publicar, veja o `docs/PUBLICAR.md`.
Mesmo padrão do painel de metas e do ERP próprio.

```
app.py                 shim fino (o app mora em rep_campo/)
rep_campo/             backend e API (dominio, aplicacao, infra, web)
api/                   entrada da Vercel
scripts/               setup_db, carteira, usuarios, sync, rotas oficiais
tests/                 teste de fumaça contra Neon + Blob
tools/                 utilitários locais (gerar PDF)
docs/                  arquitetura, deploy, manuais
static/                app.js, sw.js, styles.css, manifest, ícones
templates/             index.html, login.html
dados/                 banco, fotos e chave — NÃO versionar
```

---

## Rodar no Mac (e testar no celular)

```bash
./rodar_local.sh
```

Recria o ambiente do zero (venv, banco, carteira), sobe o app e imprime o
endereço para abrir no celular pela rede local. O banco e as fotos existentes
**não são sobrescritos** — só o código é atualizado.

Trabalha em `~/.rep-campo-local` porque o app não roda direto do Google Drive:
processos filhos não têm permissão de leitura no CloudStorage (proteção do
macOS). O código-fonte continua sendo o desta pasta.

Para GPS e offline funcionarem no Android sem HTTPS, marcar a origem como segura
em `chrome://flags/#unsafely-treat-insecure-origin-as-secure` — ver
[docs/DEPLOY.md](docs/DEPLOY.md), Caminho A.

## Subir do zero (manual)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install flask
python scripts/importar_carteira.py          # cria o banco e carrega a carteira
python scripts/criar_usuario.py sipiao "Tiago Sipiao" rep
python scripts/criar_usuario.py ricardo "Ricardo Brum" gestor
python app.py                        # http://localhost:8010
```

A senha é pedida no terminal e gravada como **hash pbkdf2:sha256** — nunca em
texto claro. (`pbkdf2` explícito: o default do Werkzeug 3 é `scrypt`, que não
existe em builds do Python sem OpenSSL completo, caso do Python do macOS.)

Reimportar a carteira depois: `python scripts/importar_carteira.py` (idempotente, faz
upsert por código e recalcula a curva ABC).

### Apagar as fichas de demonstração

O banco local vem com 10 fichas de exemplo (uuid começando com `demo-`) só para
o painel não abrir vazio. Para removê-las antes de usar de verdade:

```bash
sqlite3 ~/.rep-campo-local/dados/rep_campo.db "DELETE FROM fichas WHERE uuid LIKE 'demo-%';"
```

---

## ⚠️ Pré-requisito de infra: HTTPS com certificado válido

O app **depende de HTTPS confiável** para funcionar no celular:

| Recurso | Exige |
|---|---|
| Service worker (offline) | contexto seguro |
| Geolocalização (check-in) | contexto seguro |
| Instalar na tela inicial | HTTPS válido + manifest |

O painel atual responde em `https://170.247.31.241:8002` com **certificado
autoassinado** (por isso o `curl -k`). Certificado autoassinado **não serve**:
o navegador do celular bloqueia o service worker e a geolocalização.

**Resolver antes do deploy** — um domínio com Let's Encrypt apontando para o
servidor (mesmo caminho já usado no DuckDNS de outros projetos). Sem isso o app
vira um site comum: sem offline e sem check-in, que são justamente as duas
funções que justificam ele existir.

---

## Modelo de dados

`fichas` guarda, além do preenchido: `nivel_evidencia` (forte/media/leve),
`conta_indicador` (tem próximo passo) e `relato_curto` (abaixo de 200 caracteres).

**Regra: o servidor nunca descarta ficha de campo — classifica.** Uma ficha
fraca entra marcada como fraca em vez de ser recusada. Dado coletado em campo,
às vezes em condição ruim, não se joga fora; ele aparece no indicador de
qualidade. Só é recusado o que não identifica cliente ou tipo.

Sync é **idempotente por uuid**: se o celular reenviar por falha de rede, o
servidor confirma sem duplicar.

---

## Testes executados (27/08/2026)

| Cenário | Resultado |
|---|---|
| `/saude` e carga da carteira | 1.453 clientes |
| Login com senha errada | volta ao formulário, sem sessão |
| Login correto | 302 para a home |
| POST sem autenticação | 401 |
| Payload malformado | 400 |
| Ficha com foto + geo | aceita, evidência **forte** |
| Ficha sem próximo passo | aceita, `conta_indicador=0`, evidência leve |
| Tipo inexistente / cliente vazio | recusadas com motivo |
| **Reenvio do mesmo lote** | **não duplicou** (2 fichas → 2 fichas) |
| Validação no celular | acusa os 5 campos, inclusive foto obrigatória |
| **Salvar sem internet** | foi para a fila, status "sem internet / 1 na fila" |
| **Voltar o sinal** | subiu sozinha, fila zerou, foto liberada do aparelho |
| Cliente de Santa Inês (migração) | reconhecido como `RAP-5322` |

Sem erro de JavaScript no console.

> **Dois recursos não puderam ser validados no navegador de teste** e dependem
> de um celular real (estão no [ROTEIRO_TESTE_CAMPO.md](docs/ROTEIRO_TESTE_CAMPO.md)):
>
> 1. **Geolocalização** — o navegador headless não concede permissão. O app
>    degradou como projetado: salvou como evidência **leve** em vez de travar.
> 2. **Service worker** — o registro falha com *"unknown error when fetching the
>    script"*. O servidor está correto: `/sw.js` responde 200 com
>    `Content-Type: application/javascript` e `Service-Worker-Allowed: /`, e a
>    própria página consegue baixar o arquivo. É restrição da webview de teste,
>    que não instala service workers.
>
> Consequência: a **fila offline está validada** (usa IndexedDB, testada com
> sucesso), mas **abrir o app sem rede** — que depende do service worker — ainda
> não foi comprovado. Testar no celular antes de considerar a v1 fechada.
