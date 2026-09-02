# Arquitetura e premissa de coerência

> Definido pelo Ricardo em 02/09/2026, como **premissa de projeto** — não como
> desejo futuro. Vale para tudo que for construído daqui em diante.

---

## A premissa

> *"Tenho o painel de monitoramento e lá há o link para um painel de gestão de
> carteiras, e estou criando essa solução agora para os representantes e queria
> que os mesmos se mantivessem coerentes. Isso deve ser uma premissa e as
> informações precisam estar interligadas, assim como as pesquisas."*

Três sistemas hoje falam do mesmo cliente: **Painel de Metas**, **Gestão de
Carteira** e **REP Campo**. Mais as **pesquisas de satisfação**. Se cada um
tiver sua própria noção de quem é o cliente, o que é churn ou qual a curva ABC,
a empresa passa a ter três verdades — e nenhuma confiável.

**Regra:** cada informação tem **um dono**. Os demais consomem, nunca redigitam.

---

## Quem é dono de quê

| Informação | Dono (fonte da verdade) | Quem consome |
|---|---|---|
| Cadastro do cliente, rota, vendedor | ERP / pipeline de carteira | REP Campo, painéis |
| Curva ABC, volume 12m | Pipeline de carteira | REP Campo (importa) |
| Faturamento, meta, positivação, churn | Painel de Metas | ARM, scorecard do REP |
| Definição de "ativo", churn 1 mês | `EMVIDROS_REGRAS_NEGOCIO.md` | todos |
| Base de cada loja (recorte pós-Sti) | `EMVIDROS_COMERCIAL_ESTRUTURA.md` | todos |
| Visitas, ocorrências, experiência | **REP Campo** | painéis, ARM |
| Planejamento de viagem e roteiro | **REP Campo** | scorecard (aderência) |
| NPS relacional amostral | Pesquisa CX formal | — |
| CSAT/CES transacional contínuo | **REP Campo** | — |

**O REP Campo é dono de exatamente três coisas:** o que aconteceu na visita, a
ocorrência do cliente e a percepção dele. Todo o resto ele **lê de fora**.

### O que ainda não está coerente

| Ponto | Hoje | Onde precisa chegar |
|---|---|---|
| Carteira | importada de CSV, manual | mesma base/API do pipeline de carteira |
| Cruzamento visita × pedido | manual | consulta ao ERP pelo código do cliente |
| Curva ABC | recalculada aqui | vem pronta do pipeline |
| Link entre painéis | não existe | REP Campo linkado no Painel de Monitoramento |

O caminho depende de onde o app vai rodar (servidor da empresa ou nuvem) —
decisão em aberto, ver `MIGRACAO_VERCEL.md` e `DEPLOY.md`.

---

## Preparado para o escopo maior

> *"Talvez possamos mais pra frente ampliar o escopo deste site para uma gestão
> de ocorrências de outros colaboradores — vendas, recepção e até setores que
> têm alguma relação com o cliente."*

Isso mudou o modelo de dados **agora**, não depois. A ocorrência deixou de ser
um campo dentro da ficha de visita e virou **entidade própria** (tabela
`ocorrencias`), porque:

- ocorrência de balcão ou telefone **não tem visita** para morar dentro;
- separar depois, com histórico acumulado, custaria migração de dados;
- separar agora, com 3 registros, custou uma migração automática e idempotente.

### O que o modelo já aceita

| Campo | Valores previstos |
|---|---|
| `canal` | Visita do representante · Balcão da loja · Telefone · WhatsApp · E-mail · Entrega · Outro |
| `setor` | Comercial · Recepção · Expedição · Produção · Qualidade · Financeiro · Assistência técnica |
| `status` | aberta → em_andamento → resolvida |
| `aberta_por` | qualquer usuário do sistema |
| `ficha_uuid` | opcional — preenchido só quando nasceu de uma visita |

Hoje só a visita do REP abre ocorrência. **Nenhuma linha de código precisa
mudar** para a recepção passar a abrir: falta apenas a tela de registro e os
usuários dos outros setores — que a gestão de usuários já cria.

### O que falta para o escopo ampliado

1. Tela simples de abrir ocorrência sem visita (recepção, vendedor de balcão)
2. Notificação ao responsável quando a ocorrência é encaminhada
3. Prazo/SLA por tipo de ocorrência
4. Visão por setor, para cada área ver o que é dela
5. Histórico de ocorrências **por cliente** — alimenta a visita do REP:
   *"este cliente teve 3 ocorrências nos últimos 6 meses"*

O item 5 é o que fecha o círculo da coerência: a ocorrência registrada pela
recepção aparece para o representante antes da visita.

---

## Planejamento de viagem alimenta o indicador sozinho

A aderência ao roteiro (indicador A1 da metodologia) não tem digitação própria:
o representante monta o roteiro antes de viajar e, quando a ficha de visita
chega, o cliente é marcado como visitado automaticamente pelo código do ERP.

A sugestão de quem visitar cruza o que o sistema já sabe, nesta ordem de peso:

| Sinal | Peso | De onde vem |
|---|---|---|
| Ocorrência em aberto | 100 | tabela `ocorrencias` |
| Nota ≤ 6 em pesquisa | 60 | tabela `experiencia` |
| Nunca recebeu visita | 50 | fichas × carteira |
| Ciclo vencido | 40 | ciclo da praça (§6 da metodologia) |
| Curva A / B | 25 / 12 | carteira |
| Volume 12m | até 25 | carteira |

**Cada sugestão vem com o motivo escrito.** Lista sem o porquê não ajuda
ninguém a montar rota — e é o motivo que faz o representante concordar ou
discordar da sugestão.

---

## Regras que não devem ser quebradas

1. **Cliente é sempre identificado pelo código do ERP**, nunca por nome
   digitado. Nome livre só para prospect ainda não cadastrado.
2. **Nenhum indicador é recalculado aqui se já existe dono.** Se o Painel de
   Metas diz que o faturamento foi X, é X.
3. **Ocorrência nunca é apagada** — muda de status e guarda quem resolveu,
   quando e como.
4. **Toda métrica declara o que é.** NPS, CSAT e CES são coisas diferentes e
   não entram na mesma média (ver metodologia, §4-B2).
5. **O app não é dono do cadastro.** Correção de cadastro se faz no ERP e volta
   pela importação — nunca direto aqui.
