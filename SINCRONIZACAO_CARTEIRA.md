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
python3 sincronizar_carteira.py            # sincroniza
python3 sincronizar_carteira.py --simular  # mostra o que faria, sem gravar
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
0 4 * * * cd /home/ricardo/rep-campo && ./.venv/bin/python sincronizar_carteira.py >> /home/ricardo/logs/sync-carteira.log 2>&1
```

O servidor precisa de: Python com `psycopg`, a `DATABASE_URL` do Neon num `.env`
com permissão `600`, e acesso de leitura à carteira.

> **Alternativa se a TI preferir não guardar a credencial do Neon no servidor:**
> exportar a carteira para um arquivo e deixar a Vercel puxar por cron job. Sai
> mais caro em partes móveis, e por isso não é a primeira opção.

## O que ainda falta definir

1. **O endereço do endpoint** no painel de clientes, e o formato do JSON
   (o leitor já aceita `codigo`/`ID`/`cli_id` e `nome`/`Nome`).
2. **Onde a rotina roda** — servidor interno é a recomendação.
3. **Quem avisa se falhar.** Sincronização silenciosa que quebra é pior que
   nenhuma: a base congela e ninguém percebe. Mínimo: alerta no Telegram, no
   mesmo caminho do boletim diário.
