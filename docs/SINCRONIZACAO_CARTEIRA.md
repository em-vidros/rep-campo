# Sincronização diária da carteira

> Decidido pelo Ricardo em 02/09/2026: **a base de clientes vem do painel de
> clientes, que puxa do sistema.** O REP Campo é espelho, nunca dono.

---

## Por que automático

A importação manual de CSV foi muleta de partida. Cadastro corrigido no ERP
precisa chegar aqui sozinho, senão em duas semanas o representante visita com
vendedor errado, rota errada e cliente que já saiu.

## O que a rotina faz

```bash
python3 scripts/sincronizar_carteira.py            # sincroniza
python3 scripts/sincronizar_carteira.py --simular  # mostra o que faria, sem gravar
```

- insere quem entrou
- atualiza nome, cidade, rota, vendedor e volume de quem mudou
- recalcula a curva ABC
- **inativa quem sumiu da fonte** — a base não pode só crescer
- **nunca apaga**: cliente inativado guarda o histórico de visitas e ocorrências

### Duas travas

| Situação | O que acontece |
|---|---|
| A fonte devolve **zero** cliente (painel fora do ar) | **Aborta.** Não inativa a base inteira por falha de rede |
| Cliente some da fonte | Vira inativo, não é apagado — some da sugestão, mas o histórico fica |

## De onde lê

Nesta ordem:

1. **`CARTEIRA_URL`** — endpoint do painel devolvendo JSON. É o desenho final.
   Com `CARTEIRA_TOKEN` opcional para autenticação.
2. **Arquivos locais** em `../gestao-carteira/dados` — o que roda hoje.

Trocar de um para outro é só definir a variável de ambiente. Nenhuma linha muda.

## Onde agendar

O app vive na Vercel, e o painel de clientes vive no servidor interno. A rotina
deve rodar **de dentro para fora**: o servidor lê a carteira e escreve no Neon.

Assim o servidor interno **não precisa aceitar conexão de fora** — o que era
justamente a preocupação que levou o app para a nuvem.

```cron
# 04h, fora do horário comercial
0 4 * * * cd /home/ricardo/rep-campo && ./.venv/bin/python scripts/sincronizar_carteira.py >> /home/ricardo/logs/sync-carteira.log 2>&1
```

O servidor precisa de: Python com `psycopg`, a `DATABASE_URL` do Neon num `.env`
com permissão `600`, e acesso de leitura à carteira.

> **Alternativa se a TI preferir não guardar a credencial do Neon no servidor:**
> exportar a carteira para um arquivo e deixar a Vercel puxar por cron job. Sai
> mais caro em partes móveis, e por isso não é a primeira opção.

## Quando falha, tenta sozinha antes de incomodar

Falha de rede e de banco costuma passar sozinha. Um alerta que toca todo dia
vira ruído e para de ser lido.

- **4 tentativas**, com espera de 30s, 2min e 5min entre elas
- recuperou no meio do caminho? segue em frente e registra em qual tentativa
- **esgotou as quatro?** aí sim manda o alerta no Telegram do Ricardo

A mensagem diz o que quebrou, quantas vezes tentou e — o que importa — que
**a base de clientes está congelada**: o representante segue vendo a carteira
da última sincronização, sem saber que está desatualizada.

### Configurar o canal

No `.env` do servidor, uma das duas formas:

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

ou, para reaproveitar o n8n que já manda o boletim diário:

```
SYNC_ALERTA_WEBHOOK=https://.../webhook/rep-campo-alerta
```

Sem nenhuma das duas, a rotina escreve o alerta no log e avisa que não há canal
configurado — nunca falha em silêncio.

---

## Atualizar as rotas pela tela — sem tocar no servidor

**Decidido em 02/09/2026.** O app roda fora do servidor da empresa. Em vez de
abrir porta no servidor (para o app puxar) ou guardar a senha do banco lá (para
o servidor empurrar), **o admin sobe a planilha pela tela** em `/importar`.

Nada é exposto dos dois lados: nenhuma porta, nenhuma credencial fora do lugar,
nenhuma conexão automática entre o servidor interno e a nuvem.

### Como funciona

1. Exporta a planilha **CIDADES, ROTAS E TABELAS** de onde ela estiver atualizada
2. Em `/importar`, envia o arquivo — o app lê e mostra quantas cidades e rotas achou
3. Clica em **Aplicar** — cada cliente é conferido contra a planilha

**Nenhum cliente é apagado.** Só a rota e a tabela de preço mudam. O resultado
mostra o que mudou, quais cidades não estavam na planilha (rota mantida) e quais
a planilha atribui a outra base.

### Por que a comparação é tolerante a grafia

A planilha e a carteira escrevem a mesma cidade de formas diferentes: a planilha
abrevia estado (*"Campestre do MA"*), abrevia título (*"Gov. Edison Lobão"*) e
tem erro de digitação (*"Araguaíina"*, com um "i" a mais). Sem normalizar os dois
lados, Araguaína — uma das cidades mais importantes da rota Balsas — ficava fora
do mapa por detalhe de escrita.

### O que continua valendo para a carteira de clientes

A rotina diária (`sincronizar_carteira.py`) segue sendo o caminho para o
**cadastro dos clientes**, que muda todo dia. A tela de importação é para a
**planilha de rotas**, que muda poucas vezes por ano.

---

## Sobre o endpoint: a recomendação é não criar

A primeira ideia era o painel expor `/api/carteira` e a rotina consumir por
HTTP. **Não vale a pena**, por três razões:

1. A rotina roda **no próprio servidor** onde a carteira já está. Ler um arquivo
   local é mais simples e mais confiável que subir uma chamada HTTP para si mesmo.
2. Criar rota nova no painel é **mudança em produção** num sistema que a
   diretoria usa todo dia — precisa de aprovação, backup e rollback, para
   resolver algo que um `open()` resolve.
3. Endpoint é superfície nova. A decisão do Junior foi reduzir exposição do
   servidor, não aumentar.

**O desenho recomendado:** a rotina lê a saída que o pipeline de carteira já
gera no servidor e escreve no Neon. Sem HTTP, sem rota, sem porta.

O suporte a `CARTEIRA_URL` fica no código para o caso de a carteira um dia
morar em outro lugar — mas não é o caminho para agora.

## O campo que mais importa: a data da última compra

A fonte precisa mandar **quando o cliente comprou pela última vez**. Sem isso o
app não distingue quem nunca comprou de quem comprava e parou — e o segundo é o
cliente mais urgente de visitar.

O leitor já aceita os nomes prováveis: `ultima_compra`, `Ultima Compra`,
`ultima_venda` ou `dt_ultima_compra`. Também aproveita `pedidos_12m` /
`Pedidos ERP` se vier.

Com esse dado, a sugestão passa a pesar assim:

| Situação | Peso |
|---|---|
| Sem comprar há mais de 90 dias | 120 |
| Sem comprar há mais de 30 dias | 80 |
| Sem compra nos últimos 12 meses (sem data, volume zero) | 45 |

Trinta dias é a régua de churn da casa: vidraçaria compra toda semana.

## O que ainda falta definir

1. **Qual arquivo o pipeline de carteira gera no servidor** e onde ele fica —
   é o que a rotina vai ler.
2. **Se a `DATABASE_URL` do Neon pode ficar no servidor interno** (permissão 600).
3. **O token do Telegram** ou a URL do webhook do n8n para o alerta.
