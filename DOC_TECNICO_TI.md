# REP Campo — documento técnico para a TI

**Para:** Henrique Pereira — TI
**De:** Ricardo Brum
**Data:** 01/09/2026

> Sobre a sua pergunta: *"de um jeito que não prejudique o servidor e nem abra
> portas para possíveis invasões"*. Este documento responde exatamente isso —
> o que precisa ser exposto, o que **não** precisa, como o app fica isolado, e
> o que eu já tratei no código. O código-fonte está disponível para você
> revisar antes de qualquer publicação.

---

## 1. O que é

App web interno para o representante comercial registrar visitas pelo celular.
Python + Flask + SQLite — **mesma stack do painel de metas** que já roda no
servidor. Sem banco de dados novo, sem serviço externo, sem dependência de nuvem.

Usuários previstos: **2 a 3 pessoas**.

---

## 2. Por que precisa de HTTPS válido (e não é preciosismo)

Duas funções do app são bloqueadas pelo navegador fora de um contexto seguro:

| Função | Por que precisa |
|---|---|
| **Funcionar sem internet** (service worker) | O navegador só instala service worker em origem segura |
| **Registrar o local da visita** (GPS) | Geolocalização exige origem segura |

Origem segura = HTTPS com **certificado confiável** e **nome batendo com o
endereço**. O certificado atual falha nos dois: é autoassinado e traz
`CN = 192.168.14.32` (IP interno) enquanto o acesso é por `170.247.31.241`.

Isso não se resolve aceitando a exceção na mão — o Chrome recusa registrar
service worker em origem com erro de certificado, mesmo após o usuário aceitar.

**Importante:** hospedar o app dentro do painel de metas **não** resolve. O
problema é o certificado, não onde o app roda.

---

## 3. Superfície de exposição — três opções, você escolhe

Listadas da mais conservadora para a mais simples. **A opção A não abre nenhuma
porta nova.**

### Opção A — nenhuma porta nova (mais conservadora)

- Certificado emitido por **desafio DNS-01** — validação por registro TXT no DNS, **sem abrir porta**, sem o servidor precisar responder na internet
- App publicado numa **porta alta já liberada** no firewall, se houver
- Renovação automática também por DNS-01

### Opção B — só a 443

- Certificado por DNS-01 (sem porta 80)
- Proxy reverso na **443**, padrão de HTTPS
- Fecha a 8002 externamente no futuro, se quiser consolidar

### Opção C — caminho mais comum

- Certificado por **HTTP-01**, que exige a **porta 80** aberta
- A porta 80 serve **só o redirecionamento 301 para HTTPS** — não serve o app em momento nenhum
- Proxy reverso na 443

> Em todas: **uma única porta atende o app**, e nada além do subdomínio fica
> acessível. Sem acesso a shell, sem painel de administração exposto, sem
> banco acessível de fora.

---

## 4. Isolamento no servidor

O que peço, com a intenção de cada item:

| Item | Por quê |
|---|---|
| Serviço systemd próprio, usuário sem privilégio | O app não compartilha processo nem permissão com o painel |
| Gunicorn ouvindo em **127.0.0.1:8011** | A porta do app **não** é acessível de fora — só o proxy conversa com ela |
| Pasta `/home/ricardo/rep-campo` isolada | Banco e fotos separados do painel; um não enxerga o outro |
| Restart liberado no meu sudo | Para eu publicar atualização sem te acionar — mesmo modelo do `emv-painel-metas` |

Se o app apresentar qualquer problema, **parar o serviço resolve** e nada mais
no servidor é afetado. Não há alteração no painel de metas nem no banco dele.

---

## 5. O que já está tratado no código

Fiz uma revisão de segurança em 01/09/2026 antes de te mandar isto. Encontrei e
**corrigi** dois problemas, e testei os quatro cenários de ataque abaixo:

| Risco | Tratamento | Testado |
|---|---|---|
| **Gravar arquivo fora da pasta** (path traversal pelo nome do arquivo) | Nome do arquivo validado por regex + caminho final conferido contra a pasta de destino | ✅ recusado |
| **Subir executável disfarçado de foto** | Tipo verificado pela **assinatura binária** do arquivo (só JPEG e PNG), não pelo que o cliente declara | ✅ recusado |
| **Força bruta no login** | Bloqueio após 8 tentativas por origem, janela de 15 min (HTTP 429) | ✅ bloqueado na 9ª |
| **Inflar o banco com texto gigante** | Limite por campo (relato 5.000 caracteres, demais 20–600) e 12 MB por requisição | ✅ cortado |
| SQL injection | Todas as consultas parametrizadas — nenhuma concatenação de valor | — |
| Senha | Hash **pbkdf2:sha256**; nunca gravada nem trafegada em texto | — |
| Sessão | Cookie `HttpOnly`, `Secure`, `SameSite=Lax`; sessão renovada a cada login | — |
| Acesso indevido entre usuários | Representante não vê ficha de outro; rota de gestão devolve **403** para quem não é gestor | ✅ testado |
| Upload | Máx. 6 MB por foto, 12 MB por requisição | — |
| Rotas abertas | **Nenhuma.** Toda rota exige login, exceto `/login` e `/saude` (health check, devolve só `ok` e a contagem de clientes) | — |

---

## 6. O que eu **não** implementei — sua avaliação

Prefiro listar do que deixar você descobrir:

1. **Fail2ban / WAF** — o freio de força bruta é da aplicação e zera quando o
   serviço reinicia. Se você quiser bloqueio no nível do servidor, faz sentido.
2. **Cabeçalhos de segurança** (HSTS, CSP, X-Frame-Options) — o lugar natural
   é o proxy reverso. Não configurei nada disso.
3. **Log de auditoria de acesso** — hoje há só o log padrão do gunicorn.
4. **Segundo fator** — não há. São 2–3 usuários internos.
5. **Backup** — por isso o pedido de incluir `dados/` na rotina; o app não faz
   backup sozinho.

Se algum desses for pré-requisito seu, me diz que eu ajusto antes de publicar.

---

## 7. Consumo de recursos

Bem abaixo do painel de metas:

| | Estimativa |
|---|---|
| Usuários simultâneos | 1 a 3 |
| Requisições | dezenas por dia (registro de visita, não navegação) |
| Banco | SQLite, arquivo único, poucos MB |
| Fotos | ~250 KB cada (comprimidas **no celular** antes de subir) |
| Crescimento em disco | ~10 MB/mês, ~100 MB/ano |
| Processo | gunicorn com 2 workers |

As fotos são reduzidas no aparelho antes do envio — o servidor não faz
processamento de imagem.

---

## 8. Publicação e rollback

Deploy: eu envio os arquivos por `scp` para a pasta do app e chamo o restart.
O banco fica em `dados/` e **não é tocado** no deploy.

Rollback: restaurar a cópia anterior e reiniciar — nenhum registro se perde.

Verificação após publicar:
- `GET /saude` deve responder `ok`
- `POST /api/fichas` **sem sessão** deve responder **401** (se responder 200, a
  autenticação quebrou e eu volto a versão na hora)

---

## 9. Resumo do pedido

1. Subdomínio com certificado confiável e renovação automática — **na opção de
   exposição que você achar mais segura** (seção 3)
2. Pasta `/home/ricardo/rep-campo` com escrita para o meu usuário
3. Serviço rodando o app em `127.0.0.1:8011`, com o subdomínio apontando pra ele
4. Um comando de restart liberado no meu sudo
5. `/home/ricardo/rep-campo/dados/` incluído no backup

Fico à disposição para revisar o código junto com você antes de publicar.
