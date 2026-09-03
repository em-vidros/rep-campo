# Publicar o REP Campo na Vercel

O app saiu do servidor da empresa. Ele roda na Vercel, o banco é um Postgres no
Neon e as fotos ficam no Vercel Blob. O motivo está no `DEPLOY.md`: o certificado
do servidor é autoassinado e não bate com o endereço público, e sem certificado
válido o celular não libera GPS nem funcionamento offline.

O código continua sendo o seu, em Python e Flask, com as mesmas telas.

## O que já está pronto

A TI converteu o app em 02/09/2026 e testou contra o Neon e o Blob de verdade,
não contra imitação. O `teste_fumaca.py` faz 60 verificações e todas passam.

As tabelas já existem no Neon. As três variáveis de ambiente já estão no projeto
da Vercel. O que falta é você criar o primeiro usuário, carregar a carteira e
apertar Deploy.

## Os três passos

### 1. Ponha o `.env` no projeto, no seu Mac

O arquivo não vai para o GitHub, de propósito. Peça as quatro linhas para o
Henrique e salve como `.env` na raiz do projeto:

```
DATABASE_URL=postgresql://...
BLOB_STORE_ID=store_...
BLOB_READ_WRITE_TOKEN=vercel_blob_rw_...
REP_SECRET_KEY=...
```

### 2. Crie o primeiro gestor e carregue a carteira

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/setup_db.py                       # idempotente, pode rodar de novo
venv/bin/python scripts/criar_usuario.py ricardo "Ricardo Brum" gestor
venv/bin/python scripts/importar_carteira.py
```

O `setup_db.py` cria as dez tabelas. O `criar_usuario.py` pede a senha no
terminal e guarda só o hash. O `importar_carteira.py` lê a planilha e grava os
clientes no Neon.

### 3. Publique

Empurre para a `main` no GitHub. A Vercel publica sozinha.

Depois abra `/saude`. Ele responde com a contagem de clientes. Se der erro, o
banco não conectou e nada mais adianta testar.

## Testar antes de publicar

```bash
venv/bin/python tests/teste_fumaca.py
```

Ele cria os próprios usuários com senha sorteada, manda um lote de fichas com
foto e evidência, monta uma viagem, confere as 60 respostas e apaga tudo que
criou. Fala com o Neon e o Blob de produção, então não rode com alguém usando o
app no mesmo minuto.

Para rodar o app no seu Mac:

```bash
./rodar_local.sh
```

Ele usa o mesmo banco do Neon, não um banco local. Quer um banco separado para
brincar, sem medo de estragar dado real? Crie um branch no Neon pelo painel e
troque a `DATABASE_URL` do `.env`.

## O teste que justifica a mudança

No celular de verdade, com o endereço da Vercel: instale na tela inicial,
registre uma visita com foto e GPS no modo avião, volte para a rede e veja a
ficha subir. É isso que o certificado do servidor impedia.

## O que mudou por dentro, e por quê

**O banco.** SQLite virou Postgres. A Vercel não tem disco que sobreviva entre
requisições, então um arquivo de banco não serviria.

**As fotos.** Saíram do disco e foram para o Vercel Blob, que está configurado
como privado. Quem pedir o endereço da foto sem estar logado recebe 403. Isso
importa porque a foto vem com a coordenada de GPS do cliente na mesma ficha.

**O lote de sincronização.** Caiu de 10 fichas para 3, e o limite de evidências
por ficha caiu de 8 para 3. A Vercel recusa requisição acima de 4,5 MB, e uma
ficha com nove fotos passava disso sozinha.

**Uma ficha por transação.** No Postgres o primeiro erro derruba a transação
inteira. Antes, uma ficha ruim no meio do lote levava junto as que já tinham
entrado. Agora cada ficha entra sozinha, e a recusada volta com motivo e aparece
em "Minhas fichas".

**O número da ocorrência.** Saía de um `SELECT` do maior número seguido de soma.
Duas instâncias da Vercel geravam o mesmo número. Agora sai de um contador no
banco, incrementado dentro do próprio comando.

**O freio de senha errada.** Vivia na memória do processo. Como cada requisição
pode cair num processo diferente, o contador nunca chegava ao limite. Foi para
uma tabela.

**Três correções de segurança**, que já valiam no servidor de hoje. O login do
usuário entrava dentro do texto do SQL na lista de viagens. As rotas de viagem só
conferiam dono no apagar, então trocar o número na URL dava acesso ao roteiro de
qualquer outro representante. E a visita de um marcava o cliente como visitado no
roteiro aberto de todo mundo.

O detalhamento linha a linha está no `MIGRACAO_VERCEL.md`.

## O que ficou de fora

Estes são bugs que já existiam e a migração não criou. Ficam registrados porque
alguém vai esbarrar neles.

Trocar de usuário no mesmo aparelho troca o dono da ficha, porque o logout não
limpa o banco local do navegador.

A nota da pesquisa nunca é exigida, porque a validação está depois do `return`
que encerra a função.

O filtro mensal usa UTC, então uma ficha das 21h30 do dia 31 cai no mês seguinte.

As regras de negócio só existem no celular. O servidor exige apenas uuid, tipo e
nome do cliente.
