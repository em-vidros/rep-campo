# Migração do REP Campo para Vercel e Neon

Escrito pela TI em 02/09/2026, a pedido do Henrique. Reescrito no mesmo dia
contra o commit `026c5a7`, depois que o Ricardo publicou a v2 e o `app.py` passou
de 681 para 1.111 linhas. Todo número de linha citado aqui vale para essa versão.
Se o arquivo mudou de novo, confira antes de confiar no número.

Quem executa a migração é o Claude do Ricardo.

## Para o Ricardo, em duas linhas

O app não vai rodar no servidor da empresa. Vai rodar na Vercel, e o banco vai
para o Neon, que é um Postgres na nuvem. O motivo é o certificado HTTPS que você
mesmo apontou no `DEPLOY.md`. Sem ele o celular não libera GPS nem o
funcionamento offline, e consertar isso no servidor depende de uma correção de
rede sem prazo. Na Vercel o certificado já vem pronto.

O app continua sendo o seu, em Python e Flask, com as mesmas telas. Muda onde ele
guarda os dados e as fotos. Guardava num arquivo no disco da máquina, passa a
guardar num banco na nuvem.

Três coisas que hoje funcionam parariam de funcionar em silêncio depois da
mudança, sem mensagem de erro nenhuma. Estão nas seções marcadas abaixo. São
elas que justificam este documento existir.

## O que não pode mudar

Você revisou a segurança em 01/09 e testou quatro ataques. As quatro defesas
atravessam a migração intactas. Se alguma sair mais fraca, o port está errado.

1. Nome do arquivo de foto validado por `RE_UUID`, e caminho final conferido
   contra a pasta de destino. Impede escrever arquivo em caminho arbitrário.
2. Tipo da foto decidido pela assinatura binária, JPEG e PNG apenas, nunca pelo
   que o cliente declara. Impede subir executável disfarçado de foto.
3. Bloqueio de força bruta no login, 8 tentativas por origem em 15 minutos,
   resposta 429.
4. Limite de tamanho por campo de texto, `relato` em 5.000 caracteres e os
   demais entre 20 e 600.

A defesa 3 é a que quebra na migração. Está na seção do freio de força bruta.

## Por que o primeiro deploy falhou

O repositório não tem `requirements.txt`, `vercel.json` nem pasta `api/`. A
Vercel não achou função para executar nem dependência para instalar, e parou.

Mesmo com esses arquivos, o app quebraria ao subir. O `app.py` escreve em disco
três vezes durante a importação do módulo, nas linhas 31, 149 e 1106: cria a
pasta de fotos, grava `dados/secret.key` e cria o banco SQLite. Na Vercel o
sistema de arquivos é somente leitura fora de `/tmp`.

E o SQLite não sobreviveria. Cada requisição pode cair numa instância diferente,
com disco próprio e descartável.

## Os três silêncios

Esta é a parte que importa. Três coisas continuam parecendo certas no código
depois da migração, e param de funcionar sem erro.

### 1. O número da ocorrência passa a colidir

O `_proxima_ocorrencia` da linha 550 lê o último número do ano e soma 1. Depois,
na linha 658, o `INSERT OR IGNORE` grava a ocorrência nova. Ler e depois gravar,
sem trava no meio.

No SQLite isso é seguro por acidente, porque existe um processo só e a escrita é
serializada. No Postgres com várias instâncias, duas sincronizações ao mesmo
tempo leem o mesmo último número e as duas calculam `OC-2026-0007`. A primeira
grava. A segunda cai no `IGNORE` e é descartada sem erro. A ficha da segunda fica
com `ocorrencia_num = OC-2026-0007` apontando para a reclamação do outro cliente.

O estrago é uma reclamação técnica que some e um representante vendo o problema
de outro cliente sob o número dele. Nada aparece em log.

O conserto é uma tabela de contador, com incremento atômico:

```sql
CREATE TABLE IF NOT EXISTS contador_ocorrencias (
    ano  TEXT PRIMARY KEY,
    ultimo INTEGER NOT NULL DEFAULT 0
);
```

```python
def _proxima_ocorrencia(db):
    ano = datetime.now(timezone.utc).strftime("%Y")
    row = db.execute(
        "INSERT INTO contador_ocorrencias (ano, ultimo) VALUES (%s, 1) "
        "ON CONFLICT (ano) DO UPDATE SET ultimo = contador_ocorrencias.ultimo + 1 "
        "RETURNING ultimo", (ano,)).fetchone()
    return "OC-%s-%04d" % (ano, row["ultimo"])
```

O Postgres resolve a disputa dentro da própria instrução. Duas chamadas
simultâneas recebem números diferentes, sempre.

Troque também o `INSERT OR IGNORE` da linha 658 por `ON CONFLICT (numero) DO
NOTHING`, que é a sintaxe do Postgres. E o `INSERT OR IGNORE` da linha 314, na
migração das ocorrências antigas.

### 2. O freio de força bruta para de bloquear

O `TENTATIVAS = {}` da linha 369 é um dicionário na memória do processo. Na
Vercel cada instância tem a sua, e elas nascem e morrem o tempo todo. Quem tenta
senha em sequência cai em instâncias diferentes e acha o contador zerado em cada
uma. O teste que bloqueou na nona tentativa passaria a não bloquear nunca.

Vai para uma tabela:

```sql
CREATE TABLE IF NOT EXISTS tentativas_login (
    origem TEXT PRIMARY KEY,
    falhas INTEGER NOT NULL DEFAULT 0,
    ultima TIMESTAMPTZ NOT NULL
);
```

O `_bloqueado`, o `_registrar_falha` e o `TENTATIVAS.pop` da linha 408 passam a
ler e escrever nela, com os mesmos 8 e os mesmos 15 minutos.

Junto disso, o `_origem()` da linha 375 devolve `request.remote_addr`, que na
Vercel é o IP da borda da plataforma, não o do celular. Todo mundo dividiria o
mesmo contador, e um bloqueio derrubaria o login de todos ao mesmo tempo. Leia o
primeiro endereço de `X-Forwarded-For`, com `remote_addr` como reserva.

### 3. A busca do painel para de achar

O `LIKE` das linhas 559 e 779 ignora maiúscula no SQLite e não ignora no
Postgres. A busca do painel do gestor simplesmente devolve vazio para quem
digitar com outra caixa, e ninguém entende por quê. Use `ILIKE` nas duas.

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

A Vercel procura uma variável WSGI chamada `app` nesse arquivo. O rewrite manda
toda rota para lá, inclusive `/static/...` e `/sw.js`. Cada arquivo estático vira
uma invocação de função, o que é desperdício em geral e irrelevante com 3
usuários. Não otimize agora.

O `/sw.js` continua servido na raiz do site, não em `/static/sw.js`. A rota da
linha 440 já faz isso e segue funcionando pelo rewrite. Service worker servido de
dentro de `/static/` perde escopo, e o offline para de valer no resto do app.

### `setup_db.py`

Roda uma vez, do Mac, contra o Neon. Cria as quatro tabelas do `SCHEMA`, as duas
novas deste documento, as colunas de `COLUNAS_EXTRA` e os cinco índices. É o
`init_db()` das linhas 297 a 334 convertido para Postgres.

Não deixe criação de tabela rodando a cada requisição. É lento na partida a frio,
e duas instâncias subindo juntas brigam pelo mesmo `CREATE`.

Dentro dele, três trechos não se convertem direto:

O `PRAGMA table_info` da linha 304 vira `ALTER TABLE ... ADD COLUMN IF NOT
EXISTS`, que o Postgres tem nativo. Some o laço de conferência inteiro, e some
com ele o `row[1]` da linha 305.

O `fetchone()[0]` da linha 312 indexa por posição. Dê um apelido à contagem e
leia por nome.

A migração das ocorrências antigas, das linhas 313 a 324, só faz sentido se
houver dado antigo em SQLite para trazer. Se o banco do Neon nasce vazio, não
copie esse bloco.

## Mudanças no `app.py`

### Escritas em disco durante a importação

Apague o `os.makedirs(FOTOS_DIR, exist_ok=True)` da linha 31. Não há mais pasta
de fotos local.

O `.env` não se carrega sozinho. O Flask não lê arquivo `.env`, e o `app.py` só
consulta `os.environ`. Para o teste local funcionar, acrescente no topo, antes de
qualquer leitura de ambiente:

```python
from dotenv import load_dotenv
load_dotenv()
```

Na Vercel isso não faz efeito, porque lá não existe `.env` e as variáveis chegam
pelo ambiente do projeto. Serve só para o Mac.

Troque o `_secret_key()` das linhas 141 a 152 por uma leitura de ambiente, sem
plano B:

```python
def _secret_key():
    chave = os.environ.get("REP_SECRET_KEY")
    if not chave:
        raise RuntimeError("REP_SECRET_KEY nao definida")
    return chave
```

O plano B de hoje gera uma chave nova quando não acha o arquivo. Na Vercel isso
seria pior do que quebrar: cada instância geraria a sua, e o usuário cairia para
a tela de login sem explicação toda vez que trocasse de instância. Falhar alto é
melhor.

Apague a chamada `init_db()` da linha 1106.

### Conexão com o Postgres

```python
import psycopg
from psycopg.rows import dict_row

def get_db():
    if "db" not in g:
        g.db = psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)
    return g.db
```

Use a URL com `-pooler` no nome do host, que é o endpoint agrupado do Neon. Sem
ele cada requisição abre conexão nova com handshake TLS inteiro, e isso aparece
como lentidão na abertura do app.

O `PRAGMA foreign_keys = ON` da linha 191 sai. O Postgres sempre respeita chave
estrangeira.

### Conversão do SQL

**Todo `?` vira `%s`.** São 52 ocorrências no arquivo, incluindo as de dentro dos
`filtros.append(...)`.

**Formatação de string com `%` colide com o placeholder.** Depois da troca acima,
um `"SELECT ... %s ..." % onde` tenta substituir o placeholder junto com a parte
estrutural, e o SQL sai quebrado. Vale para as linhas 775, 780, 785, 830 e 875.
Passe todas para f-string.

**A cláusula `IN` da cobertura fica melhor com `ANY`.** Em vez de montar
`marcadores` e interpolar na linha 830, escreva `c.curva = ANY(%s)` e passe a
lista `curvas` como um parâmetro só.

**Cinco lugares indexam resultado por posição** e quebram com `dict_row`, que
devolve dicionário. São as linhas 562 e 564 no gerador de ocorrência, 801, 803 e
805 nas opções do painel, e 893 e 899 nas contagens de ocorrência por status e
por canal. Dê apelido a cada coluna, por exemplo `SELECT DISTINCT
substr(recebido_em,1,7) AS mes`, e leia por nome.

**`INTEGER PRIMARY KEY AUTOINCREMENT` vira `GENERATED ALWAYS AS IDENTITY`.** Só
na tabela `usuarios`, linha 205.

O `substr(recebido_em,1,7)` das linhas 700, 769, 802 e 954 funciona igual no
Postgres. Não mexa.

Deixe as datas como texto ISO, do jeito que estão. Converter para `timestamptz`
obrigaria a reescrever junto o filtro por mês e o `datetime.fromisoformat` da
cobertura, sem ganho nenhum agora. Os campos `prospect`, `ativo`,
`conta_indicador` e `relato_curto` também seguem como inteiros 0 e 1. Menos
mudança, menos erro.

### Fotos

A `_salvar_foto` da linha 502 guarda no Vercel Blob em vez do disco. Mantenha,
sem tocar, a validação de `RE_UUID`, o teto de 6 MB e a checagem de assinatura
binária. Só a escrita da linha 529 muda. O `foto_arquivo` no banco passa a
guardar o caminho no Blob, tanto na tabela `fichas` quanto na `ocorrencias`.

O SDK oficial do Blob é em JavaScript. Em Python, use a API HTTP direto com
`requests`, mandando um PUT para `https://blob.vercel-storage.com/<caminho>` com
o cabeçalho `Authorization: Bearer $BLOB_READ_WRITE_TOKEN`. Confira o formato
atual na documentação da Vercel antes de escrever, porque essa API já mudou de
versão. Existe um pacote `vercel_blob` no PyPI que embrulha isso, mas é de
comunidade, então leia antes de confiar.

A rota `/foto/<nome>` da linha 1089 continua com `@login_obrigatorio` e passa a
buscar do Blob e devolver o conteúdo. Não troque por redirecionamento para a URL
pública. São fotos de cliente com coordenada de GPS junto, e URL pública é
pública mesmo que ninguém adivinhe o endereço.

Se a API do Blob em Python der trabalho demais, o plano B é um bucket S3 pelo
`boto3`, caminho batido em Python. Guardar foto como `bytea` no Neon não serve:
pela conta no fim deste documento, o volume enche a franquia do banco em uns três
meses.

### Tamanho do lote de sincronização

O `static/app.js` manda 10 fichas por vez na linha 404, com a foto em base64
dentro do JSON. A foto sai em 1280px e qualidade 0,7, uns 250 KB, e o base64
infla isso em um terço. Dez fichas com foto chegam perto de 4 MB, e o limite de
corpo de requisição da Vercel é 4,5 MB.

Baixe o lote para 3 na linha 404, e ajuste o `payload["fichas"][:50]` da linha 594
para o mesmo número. A fila offline continua igual, só manda em mais viagens.

No mesmo movimento, baixe o `MAX_CONTENT_LENGTH` da linha 162 de 12 MB para 4 MB.
Hoje ele está acima do limite da plataforma, então nunca dispara, e o usuário
receberia um erro opaco da Vercel em vez da recusa limpa do app.

Confira o limite de duração de função da conta. Três fotos subindo para o Blob
uma depois da outra levam alguns segundos.

### Cache do service worker

O `static/sw.js` guarda o app com a chave `rep-campo-v1` na linha 2. Depois de
publicar, o celular que já tem o app instalado continua servindo a versão antiga
do cache. Suba para `rep-campo-v2` no mesmo commit da migração, senão você vai
testar a versão velha achando que é a nova.

## Sobre a v2 que você acabou de publicar

A gestão de usuários das linhas 1031 a 1088 cria e edita usuário pelo próprio
app. Depois da migração, o `criar_usuario.py` serve só para criar o primeiro
gestor no banco vazio. Todo o resto passa pela tela.

A troca de senha em `/conta`, linha 996, e a criação de usuário na linha 1040 são
escritas comuns no Postgres. Nada de especial nelas além do `?` virando `%s`.

O `INSERT OR IGNORE` da linha 658 já está coberto na seção do número da
ocorrência. É o mesmo conserto.

## Scripts que continuam rodando no Mac

O `importar_carteira.py` e o `criar_usuario.py` continuam no Mac, porque a
carteira em CSV mora no Google Drive. Os dois trocam `sqlite3` por `psycopg` e
`?` por `%s`, e passam a ler `DATABASE_URL` em vez de `REP_DB`. A lógica da curva
ABC e da migração de municípios não muda em nada.

O `rodar_local.sh` continua útil. Aponte para uma branch do Neon, não para o
banco de produção, senão um teste no Mac escreve ficha de mentira no banco real.
O Neon cria branch de banco em segundos e a franquia gratuita inclui isso. É o
melhor uso da ferramenta neste projeto.

## Documentos que ficam errados

O `DEPLOY.md` descreve o deploy no servidor, com `scp` para `/home/ricardo` e
pedido de systemd para a TI. Depois desta migração ele está errado do começo ao
fim. Reescreva ou marque como histórico no topo. Runbook errado é pior que
runbook nenhum, porque alguém segue.

O `DOC_TECNICO_TI.md` e o `ARQUITETURA.md` também falam em rodar no servidor.
Vale uma nota no topo dizendo o que mudou e em que data.

## Ordem de execução

1. Confirme que `.env` está no `.gitignore`.
2. Crie `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN` e `REP_SECRET_KEY` nas variáveis
   de ambiente do projeto na Vercel. As três, não duas. Um `.env` no Mac não
   chega na Vercel. Chave de administração da conta do Neon não entra nessa
   lista: o app não usa, e guardá-la junto só aumenta o estrago se o arquivo
   vazar.
3. Escreva o `setup_db.py` e rode do Mac. Confira as seis tabelas no Neon.
4. Converta o `app.py`, seguindo as seções acima na ordem em que aparecem.
5. Adicione `requirements.txt`, `vercel.json` e `api/index.py`.
6. Ajuste o lote e o `MAX_CONTENT_LENGTH`.
7. Suba a versão do cache no `static/sw.js`.
8. Converta `criar_usuario.py` e `importar_carteira.py`, rode os dois do Mac para
   criar o primeiro gestor e carregar a carteira.
9. Publique e teste.

## Como verificar que deu certo

Abra `/saude` na URL da Vercel. Tem que responder com a contagem de clientes
importados. Se der erro, o banco não conectou e nada mais adianta testar.

Depois, os quatro ataques de 01/09, agora contra a URL nova. O de força bruta é o
que mais importa. Erre a senha nove vezes seguidas e confira que a nona devolve
429. Se a nona passar, o contador ainda está na memória.

Para o número da ocorrência, o teste é registrar duas visitas técnicas de
clientes diferentes e sincronizar as duas juntas. Os dois números têm que ser
diferentes, e as duas ocorrências têm que aparecer no painel. Se aparecer uma só,
o contador ainda tem a corrida da seção 1.

Por último, no celular de verdade: instalar na tela inicial, registrar uma visita
com foto e GPS no modo avião, voltar para a rede e ver a ficha subir. É esse
teste que justifica a migração inteira, porque é o que o certificado do servidor
impedia.

## Conta de volume, para referência

Três usuários, umas 30 fichas por dia no pior caso, foto de 250 KB. Dá 7,5 MB por
dia e uns 150 MB por mês de dias úteis. É por isso que a foto não cabe no banco,
e é o número para comparar com a franquia do Blob quando ela for conferida.

## Quem decide o quê

O código é do Ricardo e a decisão de produto é dele. A TI decidiu a hospedagem,
por causa do certificado, e escreveu esta especificação. Dúvida sobre o app fala
com o Ricardo. Dúvida sobre Vercel, Neon ou credencial fala com o Henrique.
