# Migração do REP Campo para Vercel e Neon

Escrito em 02/09/2026 pela TI, a pedido do Henrique, depois de ler o commit
`246264f`. É a especificação da migração. Quem executa é o Claude do Ricardo.

## Para o Ricardo, em duas linhas

O app não vai rodar no servidor da empresa. Ele vai rodar na Vercel, e o banco
de dados vai para o Neon, que é um Postgres na nuvem. A razão é o certificado
HTTPS: sem ele o celular não libera GPS nem funcionamento offline, e o
certificado do servidor não tem conserto rápido. Na Vercel o certificado vem
pronto.

O app continua sendo o seu, em Python e Flask, com as mesmas telas. O que muda é
onde ele guarda as coisas. Guardava num arquivo no disco, passa a guardar num
banco na nuvem. As quatro proteções que você testou em 01/09 continuam valendo,
e este documento existe em parte para garantir que elas não se percam no caminho.

## Antes de tudo: risco de credencial aberto

O `.gitignore` não ignora `.env`. Se alguém criar um `.env` com a URL do banco e
o token do Blob e rodar `git add`, as três credenciais vão para o GitHub no
mesmo commit. A TI já acrescentou a linha. Confira que ela está lá antes de
criar o arquivo.

Se um `.env` já foi commitado em algum momento, avise a TI. Apagar o arquivo
num commit novo não resolve, porque o histórico guarda. Nesse caso as
credenciais têm que ser trocadas no Neon e na Vercel.

## Por que o deploy falhou

Três motivos, e o primeiro sozinho já basta.

O repositório não tem `requirements.txt`, `vercel.json` nem pasta `api/`. A
Vercel olhou o repositório, não achou nenhuma função para executar nem nenhuma
dependência para instalar, e parou. Do ponto de vista dela o projeto está vazio.

Mesmo com esses arquivos no lugar, o app quebraria ao iniciar. O `app.py`
escreve em disco três vezes durante a importação do módulo, nas linhas 31, 60 e
676: cria a pasta de fotos, grava `dados/secret.key` e cria o banco SQLite. Na
Vercel o sistema de arquivos é somente leitura, com exceção de `/tmp`. As três
chamadas dão erro antes de a primeira requisição chegar.

E o SQLite não sobreviveria de qualquer jeito. Cada requisição na Vercel pode
cair numa instância diferente, com disco próprio e descartável. Uma ficha
gravada numa requisição sumiria na seguinte.

## O que não pode mudar

O Ricardo revisou a segurança em 01/09 e testou quatro ataques. As quatro
defesas têm que atravessar a migração intactas. Se alguma delas ficar mais
fraca depois do port, o port está errado.

1. Nome de arquivo de foto validado por `RE_UUID` e caminho final conferido
   contra a pasta de destino. Impede escrever arquivo em caminho arbitrário.
2. Tipo da foto decidido pela assinatura binária, JPEG e PNG apenas, nunca pelo
   que o cliente declara. Impede subir executável disfarçado de foto.
3. Bloqueio de força bruta no login, 8 tentativas por origem em janela de 15
   minutos, resposta 429.
4. Limite de tamanho por campo de texto, com `relato` em 5.000 caracteres e os
   demais entre 20 e 600. Impede inflar o banco de propósito.

A defesa 3 é a que mais corre risco na migração, e o motivo está na seção do
freio de força bruta abaixo. Leia com atenção.

## Arquivos novos

### `requirements.txt`

```
flask
psycopg[binary]
requests
python-dotenv
```

### `vercel.json`

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index" }]
}
```

### `api/index.py`

```python
from app import app
```

A Vercel procura uma variável WSGI chamada `app` nesse arquivo. O `rewrites`
manda toda rota para lá, inclusive `/static/...` e `/sw.js`. Isso faz cada
arquivo estático virar uma invocação de função, o que é desperdício em geral e
irrelevante aqui com 3 usuários. Não otimize agora.

O `/sw.js` precisa continuar sendo servido na raiz do site, não em
`/static/sw.js`. A rota da linha 299 já faz isso e continua funcionando através
do rewrite. Se o service worker for servido de dentro de `/static/`, o escopo
dele encolhe e o offline para de valer para o resto do app.

### `setup_db.py`

Roda uma vez, do Mac, contra o Neon. Cria as três tabelas, a tabela nova de
tentativas de login e os índices. É o `init_db()` de hoje, tirado do `app.py` e
convertido para Postgres. Não deixe criação de tabela rodando a cada
requisição: é lento na partida a frio e duas instâncias subindo juntas brigam
pelo mesmo `CREATE`.

## Mudanças no `app.py`

### Escritas em disco durante a importação

Apague o `os.makedirs(FOTOS_DIR, exist_ok=True)` da linha 31. Não há mais pasta
de fotos local.

O `.env` não se carrega sozinho. O Flask não lê arquivo `.env`, e o `app.py` só
consulta `os.environ`. Para o teste local funcionar, acrescente no topo do
arquivo, antes de qualquer `os.environ`:

```python
from dotenv import load_dotenv
load_dotenv()
```

Na Vercel isso não faz efeito, porque lá não existe `.env` e as variáveis já
chegam pelo ambiente do projeto. Serve só para o Mac.

Troque o `_secret_key()` inteiro por uma leitura de variável de ambiente, sem
plano B:

```python
def _secret_key():
    chave = os.environ.get("REP_SECRET_KEY")
    if not chave:
        raise RuntimeError("REP_SECRET_KEY nao definida")
    return chave
```

O plano B de hoje gera uma chave nova quando não acha o arquivo. Na Vercel isso
seria pior do que quebrar: cada instância geraria a sua, e o usuário seria
deslogado sem explicação toda vez que caísse numa instância diferente. Falhar
alto é melhor. `REP_SECRET_KEY` tem que estar nas variáveis de ambiente do
projeto na Vercel, e um `.env` local não chega lá.

Apague a chamada `init_db()` da linha 676. Quem cria o schema agora é o
`setup_db.py`.

### SQLite para Postgres

```python
import psycopg
from psycopg.rows import dict_row

def get_db():
    if "db" not in g:
        g.db = psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)
    return g.db
```

Use a URL com `-pooler` no nome do host, que é o endpoint agrupado do Neon.
Sem ele cada requisição abre uma conexão nova no Postgres, com handshake TLS
inteiro, e isso aparece como lentidão na abertura do app.

O `PRAGMA foreign_keys = ON` sai. O Postgres sempre respeita chave estrangeira.

Na conversão do SQL, seis armadilhas concretas:

**Todo `?` vira `%s`.** São dezenas de ocorrências, incluindo dentro dos
`filtros.append(...)` do painel do gestor.

**Formatação de string com `%` colide com o placeholder.** Depois da troca
acima, um `"SELECT ... %s ..." % onde` tenta substituir o placeholder junto com
a parte estrutural e o SQL sai quebrado. Vale para a linha 579 e para o
`% marcadores` da cobertura. Passe as duas para f-string.

**A cláusula `IN` da cobertura fica mais limpa com `ANY`.** Em vez de montar
`",".join("?" * len(curvas))`, escreva `c.curva = ANY(%s)` e passe a lista
`curvas` como um único parâmetro. Some o `marcadores` inteiro.

**`LIKE` vira `ILIKE` na busca.** No SQLite o `LIKE` ignora maiúscula por
padrão, no Postgres não. Se passar batido, a busca do painel simplesmente para
de achar coisa e ninguém entende por quê. Linha 573.

**As três consultas de `opcoes` indexam por posição.** Os `[x[0] for x in ...]`
das linhas 595 a 600 quebram com `dict_row`, que devolve dicionário. Dê um
apelido a cada coluna, por exemplo `SELECT DISTINCT substr(recebido_em,1,7) AS
mes`, e indexe por nome.

**`INTEGER PRIMARY KEY AUTOINCREMENT` vira `GENERATED ALWAYS AS IDENTITY`.** Só
na tabela `usuarios`.

Deixe as datas como texto ISO, do jeito que estão hoje. É tentador converter
para `timestamptz`, mas aí o `substr(recebido_em,1,7)` do filtro por mês e o
`datetime.fromisoformat` da cobertura teriam que ser reescritos junto, e não há
ganho nenhum nisso agora. Os campos `prospect`, `ativo`, `conta_indicador` e
`relato_curto` também continuam inteiros usados como 0 e 1. Menos mudança,
menos chance de erro.

Opcional, e bom: a checagem de duplicata da linha 436 seguida do `INSERT`
pode virar um `INSERT ... ON CONFLICT (uuid) DO NOTHING RETURNING uuid` único. A idempotência do sync passa a valer mesmo se o celular mandar o mesmo
lote duas vezes ao mesmo tempo.

### Fotos

A `_salvar_foto` guarda no Vercel Blob em vez do disco. Mantenha, sem tocar, a
validação de `RE_UUID`, o teto de 6 MB e a checagem de assinatura binária. Só a
última linha muda, a que hoje abre o arquivo e escreve. O `foto_arquivo` no
banco passa a guardar o caminho no Blob.

O SDK oficial do Blob é em JavaScript. Em Python, use a API HTTP direto com
`requests`, mandando um PUT para `https://blob.vercel-storage.com/<caminho>` com
o cabeçalho `Authorization: Bearer $BLOB_READ_WRITE_TOKEN`. Confira o formato
atual na documentação da Vercel antes de escrever, porque essa API mudou de
versão no passado. Existe um pacote `vercel_blob` no PyPI que embrulha isso, mas
ele é de comunidade, então leia antes de confiar.

A rota `/foto/<nome>` da linha 659 continua com `@login_obrigatorio` e passa a
buscar do Blob e devolver o conteúdo. Não troque por redirecionamento para a URL
pública do Blob. São fotos de cliente com coordenada de GPS junto, e uma URL
pública é pública mesmo que ninguém adivinhe o endereço.

Se a API do Blob em Python der trabalho demais, o plano B é um bucket S3 pelo
`boto3`, que em Python é caminho batido. Guardar foto como `bytea` no Neon não
serve: pela conta abaixo, o volume enche a franquia do banco em uns três meses.

### Freio de força bruta

Este é o ponto perigoso da migração, porque o código continua parecendo
funcionar depois de quebrado.

O `TENTATIVAS = {}` da linha 228 é um dicionário na memória do processo. Na
Vercel cada instância tem a memória dela, e as instâncias nascem e morrem o
tempo todo. Um atacante que mande requisições em sequência cai em instâncias
diferentes e encontra o contador zerado em cada uma. O teste do Ricardo, que
bloqueou na nona tentativa, passaria a não bloquear nunca, sem erro nenhum
aparecendo em lugar algum.

Mova o contador para uma tabela no Postgres:

```sql
CREATE TABLE IF NOT EXISTS tentativas_login (
    origem TEXT PRIMARY KEY,
    falhas INTEGER NOT NULL DEFAULT 0,
    ultima TIMESTAMPTZ NOT NULL
);
```

As funções `_bloqueado` e `_registrar_falha` passam a ler e escrever nela,
mantendo os mesmos 8 e os mesmos 15 minutos. São umas vinte linhas.

Um detalhe do `_origem()` da linha 234: na Vercel o `request.remote_addr` é o IP
da borda da plataforma, não o do celular. Todos os usuários compartilhariam o
mesmo contador, e um bloqueio derrubaria o login de todo mundo junto. Leia o
primeiro endereço do cabeçalho `X-Forwarded-For`, com o `remote_addr` como
reserva.

### Tamanho do lote de sincronização

O app manda 10 fichas por vez, com a foto em base64 dentro do JSON, no
`static/app.js`. A foto sai redimensionada para 1280px em qualidade 0,7, o que
dá uns 250 KB, e o base64 infla isso em um terço. Dez fichas com foto chegam
perto de 4 MB, e o limite de corpo de requisição da Vercel é 4,5 MB.

Baixe o lote para 3 no `static/app.js`, e ajuste o `payload["fichas"][:50]` da
linha 415 para o mesmo número. A fila offline continua funcionando igual, só
manda em mais viagens.

No mesmo movimento, baixe o `MAX_CONTENT_LENGTH` de 12 MB para 4 MB. Hoje ele
está acima do limite da plataforma, então nunca dispara, e o usuário receberia
um erro opaco da Vercel em vez da recusa limpa do app.

Confira também o limite de duração de função da conta. Três fotos subindo para
o Blob uma depois da outra levam alguns segundos, e a franquia é curta.

### Cache do service worker

O `static/sw.js` guarda o app com a chave `rep-campo-v1`. Depois de publicar uma
versão nova, o celular que já tem o app instalado continua servindo a antiga do
cache. Suba para `rep-campo-v2` no mesmo commit da migração, senão o Ricardo vai
testar a versão velha achando que é a nova.

## Scripts que continuam rodando no Mac

O `importar_carteira.py` e o `criar_usuario.py` continuam no Mac dele, porque a
carteira em CSV mora no Google Drive. Os dois trocam `sqlite3` por `psycopg` e
`?` por `%s`, e passam a ler `DATABASE_URL` em vez de `REP_DB`. A lógica da
curva ABC e da migração de municípios não muda em nada.

O `rodar_local.sh` continua útil para testar no Mac. Aponte para uma branch do
Neon, não para o banco de produção, senão um teste no Mac escreve ficha de
mentira no banco real. O Neon cria branch de banco em segundos e a franquia
gratuita inclui isso. É o melhor uso da ferramenta nesse projeto.

## Documentos que ficam errados

O `DEPLOY.md` descreve o deploy no servidor, com `scp` para `/home/ricardo` e
pedido de systemd para a TI. Depois desta migração ele está errado do começo ao
fim. Reescreva ou marque como histórico no topo. Um runbook errado é pior que
runbook nenhum, porque alguém segue.

O `DOC_TECNICO_TI.md` também fala em rodar no servidor. Vale uma nota no topo
dizendo o que mudou e em que data.

## Ordem de execução

1. Confirme que `.env` está no `.gitignore`.
2. Crie `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN` e `REP_SECRET_KEY` nas variáveis
   de ambiente do projeto na Vercel. As três, não duas. Um `.env` no Mac não
   chega na Vercel. Chave de administração da conta do Neon não entra nessa
   lista: o app não usa, e guardá-la junto só aumenta o estrago se o arquivo
   vazar.
3. Escreva o `setup_db.py` e rode do Mac. Confira as quatro tabelas no Neon.
4. Converta o `app.py`, seguindo as seções acima na ordem em que aparecem.
5. Adicione `requirements.txt`, `vercel.json` e `api/index.py`.
6. Ajuste o lote e o `MAX_CONTENT_LENGTH` no `app.py` e no `static/app.js`.
7. Suba a versão do cache no `static/sw.js`.
8. Converta `criar_usuario.py` e `importar_carteira.py`, rode os dois do Mac
   para criar o usuário e carregar a carteira.
9. Publique e teste.

## Como verificar que deu certo

Abra `/saude` na URL da Vercel. Tem que responder com a contagem de clientes
importados. Se responder erro, o banco não está conectado e nada mais adianta
testar.

Depois, os quatro ataques que o Ricardo já rodou em 01/09, agora contra a URL
nova. O de força bruta é o que mais importa, porque é o que a arquitetura nova
quebra em silêncio. Erre a senha nove vezes seguidas e confira que a nona
devolve 429. Se a nona passar, o contador ainda está na memória.

Por último, no celular de verdade: instalar na tela inicial, registrar uma
visita com foto e GPS no modo avião, voltar para a rede e ver a ficha subir.
É esse teste que justifica a migração inteira, porque é o que o certificado do
servidor impedia.

## Conta de volume, para referência

Três usuários, umas 30 fichas por dia no pior caso, foto de 250 KB. Dá 7,5 MB
por dia e uns 150 MB por mês de dias úteis. É por isso que a foto não cabe no
banco, e é o número para comparar com a franquia do Blob quando ela for
conferida.

## Quem decide o quê

O código é do Ricardo e a decisão de produto é dele. A TI decidiu a hospedagem,
por causa do certificado, e escreveu esta especificação. Dúvida sobre o app fala
com o Ricardo. Dúvida sobre Vercel, Neon ou credencial fala com o Henrique.
