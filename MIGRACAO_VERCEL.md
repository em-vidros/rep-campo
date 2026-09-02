# Migração do REP Campo para Vercel e Neon

Escrito pela TI em 02/09/2026, a pedido do Henrique, contra o commit `7f3dc5c`,
com o `app.py` em 1.570 linhas. Os 169 números de linha citados aqui foram
conferidos por script contra o arquivo. Depois de cada push seu eles saem do
lugar, e o `verificar_citacoes.py`, na raiz do repositório, reencontra o código
citado e reescreve os números. Rode ele antes de confiar em qualquer linha daqui.

Quem executa a migração é o Claude do Ricardo.

## Para o Ricardo, em duas linhas

O app não vai rodar no servidor da empresa. Vai rodar na Vercel, e o banco vai
para o Neon, que é um Postgres na nuvem. O motivo é o certificado HTTPS que você
mesmo apontou no `DEPLOY.md`. Sem ele o celular não libera GPS nem o
funcionamento offline, e consertar isso no servidor depende de uma correção de
rede sem prazo. Na Vercel o certificado já vem pronto.

O app continua sendo o seu, em Python e Flask, com as mesmas telas. Muda onde ele
guarda os dados e as fotos.

Uma coisa antes de começar. Boa parte deste documento trata de coisas que passam
a funcionar errado sem dar erro, que é o tipo de problema que ninguém descobre
até alguém reclamar.

## Conserte antes de migrar

### Resolvido pelo Ricardo em 02/09

O `app.py` usava `SENHA_MIN` em quatro lugares e chamava `_hash()` em três, e
nenhum dos dois existia no repositório. As três telas de usuário da v2 devolviam
500 desde a publicação, e o `static/usuarios.js` mostrava a mesma mensagem
genérica para qualquer falha, então a causa não aparecia.

O commit `d86b0f9` definiu os dois, com `SENHA_MIN = 8` e o `_hash` chamando
`generate_password_hash` com `pbkdf2:sha256`, o mesmo método do
`criar_usuario.py`. Fica registrado porque o teste de aceite lá embaixo cobre as
três telas, e porque a escolha do pbkdf2 tem que ser mantida no port.

### O login do usuário entra dentro do texto do SQL

A linha 1450 monta o filtro da lista de viagens assim:

```python
onde = "" if session.get("papel") == "gestor" else \
    "WHERE responsavel = '%s' OR criada_por = '%s'" % (session["login"], session["login"])
```

O login entra entre aspas, sem passar por parâmetro. Um login com apóstrofo já
derruba a tela "Minhas viagens" com 500. Um login escolhido de propósito lê ou
apaga o que quiser no banco. Quem cria login é o gestor, na tela de usuários, o
que reduz o alcance mas não fecha o buraco.

Escreva `WHERE responsavel = ? OR criada_por = ?` e passe o login duas vezes na
lista de parâmetros. Depois da conversão viram dois `%s`.

### Qualquer representante mexe na viagem de qualquer outro

A rota `/api/viagens/<int:vid>` só confere dono no DELETE, na linha 1474. O GET,
o PATCH, o `POST /clientes` da linha 1503 e o `DELETE /clientes/<cid>` da linha
1532 exigem só estar logado. Trocando o número na URL, um representante lê o
roteiro do outro, renomeia a viagem, troca o responsável, marca como concluída e
apaga clientes do roteiro. O `api_viagem_remove` nem confere se a viagem existe.

O filtro por `responsavel` da linha 1450 dá a impressão de que há isolamento por
usuário. Não há. Ele só esconde a viagem alheia da lista.

Escreva uma função que carrega a viagem e exige `papel == 'gestor'`, ou
`criada_por == login`, ou `responsavel == login`. Chame nas quatro rotas.

### O app engole todo erro de sincronização

O `static/app.js`, na linha 600, tem um `catch` com o comentário "offline ou
servidor fora, a fila continua guardada". Ele captura qualquer falha, inclusive
resposta 4xx e 5xx do servidor, e não mostra nada.

Junte com a linha 532, que manda sempre `fila.slice(0, 10)`, ou seja, a mesma
cabeça de fila em toda tentativa. Uma ficha que o servidor recusa trava a fila
para sempre. O app tenta a cada 60 segundos, falha a cada 60 segundos, e o
representante vê só um número de fila que não desce. Ele continua registrando
visitas por cima, e nenhuma sobe.

Hoje isso quase não acontece, porque o servidor local aceita quase tudo. Depois
da migração aparecem quatro jeitos novos de o servidor recusar uma ficha: o 413
da Vercel por corpo grande demais, o 504 por estouro de duração, a falha de
upload no Blob e o erro de transação da seção seguinte.

Faça o `sincronizar()` distinguir três casos antes de migrar. Sem rede, deixa na
fila e fica quieto. Resposta 4xx, mostra o motivo e põe aquela ficha de lado para
não travar as outras. Resposta 5xx, tenta de novo com espera crescente e avisa na
tela depois de algumas falhas.

Sem isso você migra às cegas. Todo defeito desta lista vira "não aconteceu nada".

## O que não pode mudar

Você revisou a segurança em 01/09 e testou quatro ataques. As quatro defesas
atravessam a migração, mas duas mudam de forma.

1. Nome do arquivo de foto validado por `RE_UUID`, linha 236, e caminho final
   conferido contra a pasta de destino, linhas 659 e 660. Com a foto indo para o
   Blob não existe mais caminho de arquivo, então a conferência de pasta perde o
   sentido e o `RE_UUID` passa a ser a única defesa sobre o nome. Não relaxe ele.
2. Tipo da foto decidido pela assinatura binária, linhas 632 e 654, JPEG e PNG
   apenas. Atravessa sem mudança.
3. Bloqueio de força bruta, 8 tentativas em 15 minutos. Esta quebra. Está na
   seção dos silêncios.
4. Limite de tamanho por campo de texto, linhas 226 a 231. Atravessa sem
   mudança.

## Por que o primeiro deploy falhou

O repositório não tem `requirements.txt`, `vercel.json` nem pasta `api/`. A
Vercel não achou função para executar nem dependência para instalar, e parou.

Mesmo com esses arquivos, o app quebraria ao subir. O `app.py` escreve em disco
durante a importação do módulo, nas linhas 31, 204, 206 e 1553: cria a pasta de
fotos, grava e ajusta permissão de `dados/secret.key`, e cria o banco SQLite. Na
Vercel o sistema de arquivos é somente leitura fora de `/tmp`. Qualquer uma
dessas derruba a partida da instância, e aí toda requisição dela devolve 500.

## Os silêncios da migração

Esta é a parte que importa. Sete coisas continuam parecendo certas no código
depois da migração e param de funcionar sem erro.

### 1. Um erro no meio do lote apaga o lote inteiro

No `sqlite3`, um `execute` que falha não estraga a conexão, e o laço de
`api_receber_fichas`, linhas 750 a 862, seguiria para a próxima ficha. No
psycopg é diferente: o primeiro erro aborta a transação, e todo `execute`
seguinte levanta `InFailedSqlTransaction`. O `db.commit()` da linha 864 nunca
roda. As dez fichas do lote se perdem, inclusive as que já tinham passado.

Combinado com o `catch` do cliente, o representante não vê nada.

Trate ficha a ficha. Use um savepoint por ficha, ou capture a exceção dentro do
laço e faça `rollback` só daquela, empurrando o `uuid` para a lista de
rejeitadas. Assim uma ficha ruim é recusada com motivo e as outras nove entram.

O laço cresceu com os commits de 02/09. Além dos dois `INSERT` de antes, cada
ficha agora grava até 12 linhas em `experiencia`, a partir da linha 842, um
`UPDATE` em `viagem_clientes` na linha 856 e até 8 linhas em `anexos` na linha
861. São até 21 instruções por ficha, todas dentro da mesma transação. Uma nota
fora de faixa numa delas apaga o lote de dez.

O mesmo vale para `api_atualizar_ocorrencia`, linhas 1109 a 1131, que faz até
quatro `UPDATE` antes do `commit`. Se o primeiro falhar, os outros levantam
`InFailedSqlTransaction` e a rota devolve 500 escondendo o erro real.

E vale para `api_viagem_add`, linha 1503, que faz até 200 `INSERT` antes do
`commit` da linha 1526. Um erro no meio derruba os seguintes, a rota devolve 500,
e o usuário fica com uma viagem criada e vazia, porque o POST de criação já
tinha commitado na linha 1447.

### 2. O número da ocorrência passa a colidir

O `_proxima_ocorrencia`, linha 706, lê o último número do ano e soma 1. Depois, a
linha 814 grava com `INSERT OR IGNORE`. Ler e depois gravar, sem trava no meio.

No SQLite isso é seguro por acidente, porque existe um processo só. No Postgres
com várias instâncias, duas sincronizações simultâneas leem o mesmo último número
e as duas calculam `OC-2026-0007`. A primeira grava. A segunda cai no `IGNORE` e
é descartada sem erro. Só que a linha 808 já gravou esse número na ficha da
segunda, e a linha 826 devolve o número para o celular, que mostra "Ocorrencia
aberta: OC-2026-0007".

Uma reclamação técnica some do painel, e a ficha dela aponta para o problema de
outro cliente. Pior ainda: a linha 1119 faz `UPDATE fichas SET ocorrencia_status =
'resolvida' WHERE ocorrencia_num = ?`, então o gestor resolvendo uma ocorrência
fecha duas fichas.

O conserto é uma tabela de contador com incremento atômico:

```sql
CREATE TABLE IF NOT EXISTS contador_ocorrencias (
    ano TEXT PRIMARY KEY,
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

Troque os dois `INSERT OR IGNORE`, das linhas 423 e 814, por `ON CONFLICT (...)
DO NOTHING`, que é a sintaxe do Postgres.

Há a mesma corrida na idempotência por `uuid`. A linha 763 verifica se a ficha já
existe e a 630 insere. Duas sincronizações do mesmo aparelho, que o `setInterval`
da linha 775 do `app.js` e o evento de volta da rede podem disparar juntas,
passam as duas pela verificação e a segunda bate em violação de chave. Use
`INSERT ... ON CONFLICT (uuid) DO NOTHING` e trate a ficha como aceita de
qualquer jeito.

### 3. O roteiro da viagem duplica cliente

A `api_viagem_add`, linha 1503, lê os clientes que já estão no roteiro na linha
1513 e insere os que faltam logo abaixo. Não há trava entre a leitura e a
escrita, e a tabela `viagem_clientes` não tem índice único em
`(viagem_id, cliente_codigo)`.

O `viagens.js` dispara esse POST logo depois do POST que cria a viagem. Um toque
duplo no botão já manda duas requisições. No servidor de hoje elas se enfileiram
no mesmo processo. Na Vercel caem em processos diferentes, as duas leem o roteiro
vazio e as duas inserem tudo. O roteiro aparece com cada cliente duas vezes, e a
aderência sai dividida pelo denominador errado.

Crie o índice único e escreva `INSERT ... ON CONFLICT DO NOTHING`. Aí a leitura
da linha 1513 deixa de ser necessária, e some junto o `r[0]` que quebra com
`dict_row`.

### 4. O freio de força bruta para de bloquear

O `TENTATIVAS = {}` da linha 497 é um dicionário na memória do processo. O
comentário das linhas 495 e 496 é honesto sobre isso: "em memoria: o app tem 2-3
usuarios e um so processo". Na Vercel cada instância tem a sua memória, e elas
nascem e morrem o tempo todo. Quem tenta senha em sequência cai em instâncias
diferentes e acha o contador zerado em cada uma. O teste que bloqueou na nona
tentativa passaria a não bloquear nunca.

```sql
CREATE TABLE IF NOT EXISTS tentativas_login (
    origem TEXT PRIMARY KEY,
    falhas INTEGER NOT NULL DEFAULT 0,
    ultima TIMESTAMPTZ NOT NULL
);
```

O `_bloqueado`, o `_registrar_falha` e o `TENTATIVAS.pop` da linha 536 passam a
usar a tabela, com os mesmos 8 e os mesmos 15 minutos.

Junto disso, o `_origem()` da linha 503 devolve `request.remote_addr`, que na
Vercel é o IP da borda da plataforma, não o do celular. Todo mundo dividiria o
mesmo contador, e um ataque bloquearia o login de todos os representantes ao
mesmo tempo. Leia o primeiro endereço de `X-Forwarded-For`, com `remote_addr`
como reserva. Se um dia alguma rota precisar do esquema ou da URL externa
corretos, aí instale o `ProxyFix` do Werkzeug. Nenhuma rota de hoje precisa.

### 5. `REAL` no Postgres perde metade da precisão

Esta é a única desta lista que corrompe dado sem volta.

A linha 277 declara `vol_12m REAL`, e as linhas 371 a 373 declaram `lat`, `lon` e
`precisao` como `REAL`. No SQLite, `REAL` é ponto flutuante de 8 bytes. No
Postgres, `REAL` é `float4`, 4 bytes, uns 6 dígitos decimais.

Copiar o DDL literal para o `setup_db.py` faz um cliente com R$ 1.234.567,89
virar cerca de 1.234.568. A linha 1055 soma isso sobre todos os clientes vencidos
e o painel mostra como faturamento sem cobertura. O número sai errado e continua
parecendo certo. Em coordenada de GPS, 6 dígitos significativos comem a precisão
que o check-in existe para ter.

Use `double precision` nas quatro colunas.

### 6. A busca do painel para de achar

O `LIKE` da linha 970 ignora maiúscula no SQLite e não ignora no Postgres. O
gestor digita "vidros" e não acha "Vidros". Devolve zero fichas, sem erro. Use
`ILIKE` ali.

Deixe `LIKE` na linha 715. Aquele compara contra um prefixo que o próprio
servidor gerou, sempre na mesma caixa, e `ILIKE` não mudaria resultado nenhum e
impediria o índice de ser usado.

### 7. A média da pesquisa vira texto no JSON

As linhas 1153, 1159 e 1182 fazem `ROUND(AVG(nota),1) media`. No Postgres, `AVG`
sobre inteiro devolve `numeric`, e o psycopg entrega isso como `Decimal`. O Flask
não estoura, ele converte para string. A média sai como `"8.5"` em vez de `8.5`.

Na tela de hoje ninguém percebe, porque o `painel.js` só imprime o valor. Mas o
tipo mudou no contrato da API, e a primeira conta que alguém fizer sobre esse
campo no cliente vira concatenação de texto.

Converta para `float` no Python antes do `jsonify`. O mesmo cuidado vale se
alguma coluna virar `numeric`: o `painel.js` chama `f.lat.toFixed(5)` na linha
144, e string não tem `toFixed`, então a lista de fichas ficaria vazia com erro
só no console.

## Arquivos novos

### `requirements.txt`

Fixe as versões. Um build daqui a seis meses pega uma major diferente e você
descobre em produção.

```
flask==3.1.*
psycopg[binary]==3.2.*
requests==2.32.*
python-dotenv==1.0.*
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
toda rota para lá, inclusive `/static/...` e `/sw.js`.

Confira que a pasta `static/` entra no pacote da função. Se não entrar,
`/static/app.js` dá 404 e o app abre em branco, e o registro do service worker na
linha 777 do `app.js` engole o erro com um `catch` vazio. Pior: um celular que já
tem o app instalado continua servindo do cache e parece funcionar, enquanto um
aparelho novo abre em branco. Use `includeFiles` no `vercel.json`, ou sirva
`static/` fora da função.

O `/sw.js` continua servido na raiz do site, não em `/static/sw.js`. A rota da
linha 568 já faz isso e segue funcionando pelo rewrite. Service worker servido de
dentro de `/static/` perde escopo, e o offline para de valer no resto do app.

### `.vercelignore`

Ponha `gerar_pdf.py`, `docs/`, os `.md` e a pasta `dados/`. O `gerar_pdf.py`
aponta para o Chrome do Mac numa linha fixa e não é importado pelo app, então só
engorda o pacote.

### `setup_db.py`

Roda uma vez, do Mac, contra o Neon. Cria as oito tabelas do `SCHEMA`, as duas
deste documento, as dez colunas de `COLUNAS_EXTRA` e os dez índices. É o
`init_db()` das linhas 406 a 462 convertido.

Quatro tabelas nasceram nos commits de 02/09 e pedem atenção no `setup_db.py`.

A `viagens`, linha 285, e a `viagem_clientes`, linha 298, guardam datas como
texto, igual às outras. Mantenha. A `viagem_clientes` precisa de duas coisas que
não estão no código de hoje. Uma é o índice único de `(viagem_id,
cliente_codigo)` do silêncio 3. A outra é o `ON DELETE CASCADE` para `viagem_id`,
porque o DELETE da linha 1476 limpa as duas tabelas na mão e deixa órfão se
falhar no meio. O `visitado` da linha 306 é 0 ou 1 e tem que continuar inteiro,
porque a linha 1455 faz `SUM(visitado)`.

A `experiencia`, linha 311, guarda a nota como inteiro. Some com a média que vira
`Decimal`, no silêncio 7. Ela também precisa de um índice em `cliente_codigo`,
que hoje não existe, pelo motivo do item de duração da função lá embaixo. A
coluna `unidade` está declarada duas vezes, na linha 320 e em `COLUNAS_EXTRA` na
linha 388. Em banco novo, escreva uma vez só.

A `anexos`, linha 325, guarda em `arquivo` o caminho da evidência, que passa a
ser o caminho no Blob. Sem restrição única em `(ficha_uuid, arquivo)`, uma
sincronização repetida grava a mesma evidência de novo.

Uma armadilha em `clientes`. A consulta de sugestão, linha 1370, faz
`GROUP BY c.codigo` e seleciona `c.nome`, `c.cidade` e outras colunas. No
Postgres isso só é válido porque `codigo` é a chave primária da tabela. Se o
`setup_db.py` trocar por `UNIQUE NOT NULL`, ou acrescentar um `id` serial como
chave, a consulta passa a dar `column "c.nome" must appear in the GROUP BY
clause`. Deixe `codigo TEXT PRIMARY KEY`.

Índices que o `init_db()` cria e o `setup_db.py` tem que repetir, nas linhas 451
a 460: `ix_vc_viagem`, `ix_vc_cliente`, `ix_exp_ficha`, `ix_exp_metrica`,
`ix_anexos_ficha`, `ix_oc_status`, `ix_oc_cliente`, `ix_fichas_usuario`,
`ix_fichas_data` e `ix_clientes_nome`.

Não deixe criação de tabela rodando a cada requisição. No Postgres, DDL toma
trava exclusiva, e duas instâncias frias subindo juntas se travam. O
`CREATE INDEX` sem `CONCURRENTLY` ainda bloqueia escrita.

Três trechos não se convertem direto. O `PRAGMA table_info` da linha 413 vira
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, que o Postgres tem nativo, e some com
ele o `row[1]` da linha 414. O `fetchone()[0]` da linha 421 indexa por posição,
então dê apelido à contagem. E o backfill das linhas 422 a 433 só faz sentido se
houver dado antigo em SQLite para trazer. Banco novo e vazio no Neon dispensa o
bloco inteiro, que aliás tem a mesma corrida do item 2 acima.

## Mudanças no `app.py`

### Escritas em disco durante a importação

Apague o `os.makedirs(FOTOS_DIR, exist_ok=True)` da linha 31.

O `.env` não se carrega sozinho. O Flask não lê arquivo `.env`, e o `app.py` só
consulta `os.environ`. Para o teste local funcionar, acrescente no topo, antes de
qualquer leitura de ambiente:

```python
from dotenv import load_dotenv
load_dotenv()
```

Na Vercel isso não faz efeito, porque lá não existe `.env` e as variáveis chegam
pelo ambiente do projeto. Serve só para o Mac.

Troque o `_secret_key()` das linhas 196 a 207 por uma leitura de ambiente, sem
plano B:

```python
def _secret_key():
    chave = os.environ.get("REP_SECRET_KEY")
    if not chave:
        raise RuntimeError("REP_SECRET_KEY nao definida")
    return chave
```

O plano B de hoje gera uma chave nova quando não acha o arquivo. Se alguém
"consertar" a escrita apontando para `/tmp`, cada instância passa a ter a sua
chave, e o cookie assinado por uma é rejeitado por outra. O usuário cai na tela
de login em requisições aleatórias e vai achar que errou a senha. Falhar alto é
melhor.

Apague a chamada `init_db()` da linha 1565. Junto dela, ou apague as constantes
`SCHEMA`, linhas 257 a 382, e `COLUNAS_EXTRA`, linhas 385 a 403, ou ponha um
comentário grande na linha 257 dizendo que o esquema real mora no `setup_db.py`.
Deixadas como estão, elas viram documentação mentirosa, e a próxima coluna nova
vai ser acrescentada no arquivo errado e não vai aplicar.

Some também o `import sqlite3` da linha 16.

### Conexão com o Postgres

```python
import psycopg
from psycopg.rows import dict_row

def get_db():
    if "db" not in g:
        g.db = psycopg.connect(os.environ["DATABASE_URL"],
                               row_factory=dict_row, autocommit=True)
    return g.db
```

Use a URL com `-pooler` no nome do host, que é o endpoint agrupado do Neon. Sem
ele, cada requisição abre conexão nova no Postgres com handshake TLS inteiro, e o
rewrite manda até `/static/styles.css` pela função. Sob qualquer concorrência
isso estoura o limite de conexões, e o sintoma é 500 só quando duas pessoas usam
ao mesmo tempo.

O `autocommit=True` importa porque nenhuma rota de leitura chama `commit` nem
`rollback`. O `sqlite3` não liga. O psycopg abre transação implícita no primeiro
`execute` e a conexão fica ociosa dentro de transação até o `close_db` da linha
195, o que segura conexão do pooler à toa. Nas rotas de escrita, abra transação
explícita em volta do bloco que precisa ser tudo ou nada.

O pooler do Neon é PgBouncer em modo transação. O psycopg 3 prepara consultas
automaticamente depois de 5 execuções, e conforme a versão do PgBouncer isso dá
erro intermitente de prepared statement duplicado, que aparece sob carga e some
quando você vai olhar. Se acontecer, abra a conexão com `prepare_threshold=None`.

O `PRAGMA foreign_keys = ON` da linha 246 sai. É código morto de qualquer jeito,
porque nenhuma tabela do esquema declara chave estrangeira.

### Conversão do SQL

**Todo `?` de SQL vira `%s`.** São 147 no arquivo.

Não faça busca e troca cega. O arquivo tem 157 sinais de interrogação, e 10 não
são placeholder. Sete estão no texto das perguntas da pesquisa, linhas 123 a 129,
e virariam `recomendaria%s` na tela do cliente. Um está na linha 503, no
`return request.remote_addr or "?"`. Os das linhas 1015 e 1356 montam
placeholders, e somem na troca por `ANY`. Converta consulta por consulta.

**Formatação de string com `%` colide com o placeholder.** Depois da troca, um
`"%s = ?" % campo` vira `"%s = %s" % campo` e o Python levanta `TypeError` antes
de tocar no banco. Vale para as linhas 966, 976, 1024, 1069, 1357, 1378 e 1487,
mais a 308 que some com o `setup_db.py`. Passe todas para f-string.

A da linha 1487 é a que dói mais, porque derruba todo PATCH de viagem, ou seja,
mudar nome, data, rota, observação e responsável. O `campo` ali vem de uma tupla
escrita no código, então f-string não abre porta para injeção.

**As duas cláusulas `IN` ficam melhores com `ANY`.** A linha 1015, na cobertura,
faz `",".join("?" * len(curvas))`. Isso funciona por acidente, porque o `join`
itera os caracteres da string e `"?" * 3` dá três caracteres. Com `%s` o mesmo
código produz `%,s,%,s,%,s`, que é SQL inválido, não erro de Python. Escreva
`c.curva = ANY(%s)` e passe a lista `curvas` como um parâmetro só.

A linha 1356, nas rotas da carteira, repete o mesmo padrão com `cidades`. Trate
igual. O `c.cidade LIKE ?` da linha 1360, logo abaixo, cai no problema de caixa
da seção 6 e precisa de `ILIKE`, porque a cidade vem digitada pelo usuário.

**Dez lugares indexam resultado por posição** e quebram com `dict_row`, que só
aceita nome. No `app.py` são as linhas 421, 439, 718, 720, 995, 997, 999, 1087,
1093 e 1513.
No `importar_carteira.py` são as linhas 134, 152, 160 e 163, incluindo dois
desempacotamentos de tupla. Dê apelido a cada coluna, por exemplo
`SELECT DISTINCT substr(recebido_em,1,7) AS mes`, e leia por nome.

**`INTEGER PRIMARY KEY AUTOINCREMENT` vira `GENERATED ALWAYS AS IDENTITY`.** Em
cinco tabelas, nas linhas 260, 286, 299, 312 e 326.

**`cur.lastrowid` não existe no psycopg 3.** A linha 1448 devolve o id da viagem
recém-criada com `cur.lastrowid`, e isso vira `AttributeError`, ou seja, 500 no
POST de `/api/viagens`. O `viagens.js` faz `await r.json()` sobre a página de
erro do Flask, a promessa rejeita, e o botão de criar viagem não faz nada, sem
mensagem na tela. Escreva `INSERT ... RETURNING id` e leia `row["id"]`.

**`REAL` vira `double precision`** nas linhas 277, 371, 372 e 373, pelo motivo do
silêncio 5.

**`int()` sem guarda em parâmetro de URL.** As linhas 872, 974 e 1350 fazem
`int(request.args.get("limite", ...))`. Um `?limite=abc` dá 500. Vale hoje e
depois, e é uma linha para consertar.

O `substr(recebido_em,1,7)` das linhas 891, 960 e 996 funciona igual no
Postgres. Não mexa.

Deixe as datas como texto ISO. Converter para `timestamptz` obrigaria a
reescrever junto o filtro por mês e os dois `datetime.fromisoformat`, das linhas
839 e 887, que passariam a receber objeto em vez de texto. Pior: a linha 1034 só
captura `ValueError`, então a cobertura devolveria 500, enquanto a linha 1082
captura também `TypeError` e falharia calada, deixando `dias_aberta` em nulo. Aí
o cartão "abertas há mais de 7 dias" do painel mostra zero para sempre e nenhuma
ocorrência ganha selo de atrasada. O indicador que existe para cobrar prazo
passaria a dizer que está tudo em dia.

Pelo mesmo motivo, os campos `prospect`, `ativo`, `conta_indicador` e
`relato_curto` seguem inteiros 0 e 1, e `prox_data` e `prazo` seguem TEXT. O
`_texto` das linhas 690 a 695 devolve string vazia, não nulo, quando o campo
chega vazio do celular, e string vazia contra coluna `date` no Postgres é erro.

A ordenação de texto muda com a collation. O SQLite compara byte a byte e põe
"Ávila" depois de "Zebra", o Postgres põe antes. Muda a ordem da lista de
clientes da linha 592, dos municípios da 804 e dos usuários da 1047. Não quebra
nada, o gestor só vê a lista em outra ordem. No `importar_carteira.py`, linha
150, o `ORDER BY curva` com curva nula troca a linha "sem dado" do topo para o
rodapé, porque os dois bancos ordenam nulo em pontas opostas.

### Fotos

A `_salvar_foto` da linha 635 guarda no Vercel Blob em vez do disco. Mantenha,
sem tocar, a validação de `RE_UUID`, o teto de 6 MB da linha 650 e a checagem de
assinatura binária. Só a escrita da linha 662 muda. O `foto_arquivo` passa a
guardar o caminho no Blob, nas tabelas `fichas` e `ocorrencias`.

A `_salvar_anexos` da linha 670 chama a mesma `_salvar_foto`, até 8 vezes por
ficha, uma por evidência. É uma segunda porta para o mesmo `open(destino, "wb")`,
e não tem `try` em volta. Na Vercel a primeira evidência levanta
`OSError: Read-only file system`, a requisição inteira morre, e o lote de fichas
se perde junto. Migre as duas funções na mesma leva.

Apontar `FOTOS_DIR` para `/tmp` não resolve, piora. A gravação passa, a linha
entra na tabela `anexos` com o nome do arquivo, e a foto some quando a instância
morre. O painel do gestor renderiza imagem quebrada e o banco continua afirmando
que a evidência existe.

Um detalhe do formato do caminho. A rota `/foto/<nome>` valida com
`re.fullmatch(r"[A-Za-z0-9_\-]+\.(jpg|png)", nome)` na linha 1551, e esse padrão
não aceita barra. Se o caminho no Blob virar `fotos/<uuid>-anexo0.jpg`, a rota
devolve 404 para toda foto, calada. Ou o Blob guarda com nome sem barra, ou a
rota muda junto.

O SDK oficial do Blob é em JavaScript. Em Python, use a API HTTP com `requests`,
mandando um PUT para `https://blob.vercel-storage.com/<caminho>` com o cabeçalho
`Authorization: Bearer $BLOB_READ_WRITE_TOKEN`. Confira o formato atual na
documentação da Vercel, porque essa API já mudou de versão. Existe um pacote
`vercel_blob` no PyPI que embrulha isso, mas é de comunidade.

Antes de escrever, confirme uma coisa: se o Blob da conta só oferece o modo
público, ele não serve para este caso. São fotos de cliente com coordenada de GPS
na mesma ficha, e URL pública é pública mesmo que ninguém adivinhe o endereço.
Nesse caso o bucket S3 com URL assinada deixa de ser plano B e vira o caminho.

A rota `/foto/<nome>` da linha 1548 continua com `@login_obrigatorio` e passa a
buscar do Blob e devolver o conteúdo, sem redirecionar para URL pública. Enquanto
ela não for migrada, o `painel.js` renderiza imagem quebrada nas linhas 171 e
232, e nenhuma das duas tem tratamento de erro, então a foto some da tela sem
aviso.

Guardar foto como `bytea` no Neon não serve. Pela conta no fim deste documento, o
volume enche a franquia do banco em uns três meses.

### Tamanho do lote de sincronização

O `static/app.js` manda 10 fichas por vez na linha 582, com a foto em base64
dentro do JSON. A foto sai em 1280px e qualidade 0,7, uns 250 KB, e o base64
infla um terço. Dez fichas com foto chegam perto de 4 MB, e o limite de corpo de
requisição da Vercel é 4,5 MB.

Essa conta é de antes das evidências. Hoje uma ficha carrega a foto principal
mais até 8 anexos, cada um comprimido do mesmo jeito. São 9 fotos, umas 333 KB
cada depois do base64, perto de 3 MB numa ficha só. Duas fichas com evidência
estouram o limite, e lote de 3 não salva.

Baixe o lote para 3 na linha 532 e ajuste o `payload["fichas"][:50]` da linha 750
para o mesmo número. Junto disso, baixe o `MAX_ANEXOS` da linha 667 de 8 para 3,
ou mande a ficha com anexo sozinha na requisição. O teto de 6 MB por foto da
linha 650 permite, no papel, 54 MB numa ficha. A fila offline continua igual, só
manda em mais viagens.

Baixe o `MAX_CONTENT_LENGTH` da linha 217 de 12 MB para 4 MB. Hoje ele está acima
do limite da plataforma, então nunca dispara, e quem recusa é a borda da Vercel,
com um 413 que o Flask nem vê. O teto de 6 MB por foto da linha 650 também está
acima do limite de requisição, sozinho.

### Cache do service worker

O `static/sw.js` guarda o app com a chave `rep-campo-v1` na linha 2, e os
arquivos do shell não têm hash no nome. Suba para `rep-campo-v2` no mesmo commit
da migração, senão o celular que já tem o app instalado continua servindo a
versão antiga e você testa a velha achando que é a nova.

O `static/viagens.js` não está na lista do shell do `sw.js`, e a tela `/viagens`
é nova. Ponha ele lá, e confirme que `viagens.js`, `viagens.html`, `painel.css` e
`styles.css` entram no `includeFiles` do `vercel.json`. Tela sem o JS dela abre
uma casca morta, sem erro nenhum na tela.

## Limites da plataforma

**Tamanho da resposta.** A rota `/api/gestor/cobertura`, linhas 1016 a 1056,
devolve todos os clientes de curva A e B sem `LIMIT`, e o painel só corta em 400
na hora de desenhar. A `/api/bootstrap`, linha 590, devolve a carteira ativa
inteira em toda abertura do app. A `/api/gestor/fichas` com `limite=500` e
`relato` de até 5.000 caracteres pode passar de 2 MB só de texto. Se a resposta
for cortada, o `r.json()` do painel levanta e a tela fica em branco, sem
mensagem, e o botão de baixar CSV exporta só o que chegou. Ponha `LIMIT` no
servidor e paginação, ou pelo menos meça o tamanho real com a carteira do Ricardo
antes de publicar.

**Uma consulta por ficha, dentro do laço.** A linha 986 busca os anexos de cada
ficha separadamente, e o `limite` da linha 974 chega a 500. No SQLite isso é
memória e ninguém nota. No Neon são 500 idas e voltas pelo pooler, somadas ao
cold start. A rota estoura o tempo, devolve 504, e o painel do gestor abre em
branco porque o `r.json()` levanta. Faça uma consulta só, com
`WHERE ficha_uuid = ANY(%s)` e a lista de uuids, e agrupe em Python. O mesmo
padrão, em escala menor, está na linha 1455, com 1 mais 60 consultas para contar
a aderência de cada viagem. Ali um `LEFT JOIN` com `GROUP BY` resolve.

**A sugestão de visita varre a carteira inteira.** A consulta da linha 1370 não
tem `LIMIT` no servidor, porque o `total` devolvido precisa do conjunto todo, e
tem duas subconsultas correlacionadas por linha. Uma delas filtra
`experiencia.cliente_codigo`, que não tem índice. Crie `ix_exp_cliente`, ou troque
as duas subconsultas por `LEFT JOIN` agregado. É a consulta que a tela de viagens
chama a cada busca.

**Duração da função.** Por ficha, o `api_receber_fichas` decodifica base64,
manda a foto para o Blob e faz dois `INSERT`, tudo em série com ida e volta de
rede a cada instrução. Some o cold start da Vercel e a conexão nova ao Neon. Com
a fila cheia, o teto da conta gratuita é alcançável, e o timeout devolve 504 que
o cliente engole.

**Suspensão do Neon.** A franquia gratuita desliga o compute depois de alguns
minutos parado. A primeira consulta da manhã paga o tempo de acordar o banco em
cima do cold start. Meça isso antes de escolher o timeout da função.

## Segurança

**A rota `/saude` passa a vazar dado de infraestrutura.** As linhas 1556 a 1562
não exigem login e, no `except`, devolvem `str(exc)` para quem pedir. Hoje isso
mostra um caminho de arquivo local. Depois da migração, uma exceção do psycopg
carrega host, porta, nome do banco e às vezes o usuário do Neon, no corpo de uma
resposta pública na internet. Devolva `{"ok": false}` e mande o detalhe para o
log. É a única regressão de segurança que a migração cria por si.

**Desativar usuário não desloga ninguém.** A autorização lê `session.get("papel")`,
gravado no cookie no login, e o `ativo` só é conferido na linha 533, no login. Um
gestor rebaixado continua gestor por até 7 dias, e um usuário desativado continua
entrando. Já era assim. Muda que o único jeito de forçar logout geral passa a ser
girar `REP_SECRET_KEY` no painel da Vercel, o que derruba todo mundo junto. Como
a rota já abre conexão de qualquer forma, vale conferir `ativo` e `papel` no
banco dentro do decorador.

**Cuidado com cabeçalho de cache.** O `vercel.json` manda `/(.*)` para a função.
Basta alguém acrescentar uma regra de `headers` com `s-maxage` casando esse mesmo
padrão para o `/api/bootstrap` de um usuário ser servido a outro pela CDN. Se for
mexer em cache, exclua `/api/` explicitamente.

**Confira a lista de variáveis do projeto.** Se o `REP_INSECURE_COOKIE` do teste
local for copiado para a Vercel com valor `1`, o cookie de sessão deixa de exigir
HTTPS.

## Bugs que já existem, e a migração não cria

Nenhum destes é culpa da mudança. Ficam registrados porque quem for mexer no
código vai passar por eles.

**A nota da pesquisa nunca é exigida.** No `static/app.js`, o `return` da linha
330 acontece quando há erros, e a validação que empurra "Dê a nota da experiência
do cliente" está na linha 510, depois dele. Nada mais lê a lista de erros. A
ficha salva sem nota e o representante nunca vê o aviso. A pesquisa de
experiência, que é a novidade da v2, é opcional na prática.

**A aba de experiência zera se ganhar filtro de mês.** Nas linhas 1157 e 1163, a
ordem dos parâmetros no texto do SQL é corte, detrator, mês, métrica, e a ordem
fornecida é corte, detrator, métrica, mês. Com o mês preenchido, o banco compara
o mês contra a métrica e devolve zero linhas, sem erro. Hoje não aparece porque o
painel nunca manda o mês. No dia em que alguém puser esse filtro, NPS, CSAT e CES
aparecem zerados e ninguém acha a causa.

**Trocar de usuário no mesmo aparelho troca o dono da ficha.** O `logout` limpa a
sessão do servidor e não limpa o IndexedDB nem a Cache API. O usuário B vê as
fichas de A em "Minhas fichas", e o sincronizador dispara sozinho a cada 60
segundos e manda as fichas de A com a sessão de B, porque a linha 796 tira o
autor da sessão e não da ficha. O painel do gestor mostra o representante errado.
Limpe o IndexedDB e a Cache API no logout.

**O service worker pode nunca instalar.** O `sw.js` põe `/` na lista do shell, e
`/` para quem não está logado responde com redirecionamento. O `addAll` rejeita
em resposta não-ok e o install falha inteiro.

**`extra_json` é cortado no meio.** A linha 804 corta em 20.000 bytes sem olhar
onde, e a leitura cai no `except` e devolve `{}`. O gestor perde o bloco de
detalhes do tipo de visita. Corte os campos antes de serializar, não o JSON
pronto.

**As regras de negócio só existem no cliente.** O `app.js` valida cliente,
município, objetivo, próximo passo e foto obrigatória. O servidor só exige
`uuid`, `tipo` e `cliente_nome`. Um POST montado à mão passa por cima de tudo.

**A visita de um marca o roteiro de todos.** O `UPDATE viagem_clientes` da linha
856 casa por `cliente_codigo` e por status da viagem, sem filtrar de quem é o
roteiro. Quando o representante A registra a visita, o cliente aparece como
visitado em toda viagem aberta que o tenha, inclusive nas de B e C. A aderência
de B sobe porque A trabalhou. Filtre pelo dono da viagem, ou pelo `viagem_id` que
o app já sabe.

**A carteira inteira ficou aberta para o representante.** As rotas `/api/rotas`,
linha 1308, e `/api/sugestao`, linha 1338, exigem só estar logado e devolvem
`vol_12m`, `curva` e `vendedor` de todo cliente ativo. Antes desses commits esse
recorte só saía por `/api/gestor/cobertura`. Pode ser decisão de produto do
Ricardo, e não é problema da migração. Fica escrito porque um representante que
sai da empresa leva o faturamento por cliente da carteira toda.

**O filtro mensal usa UTC.** Uma ficha registrada às 21h30 de 31/08 em Imperatriz
é 00h30 de 01/09 em UTC e cai no mês seguinte.

## Scripts que continuam rodando no Mac

O `importar_carteira.py` e o `criar_usuario.py` continuam no Mac, porque a
carteira em CSV mora no Google Drive. Trocam `sqlite3` por `psycopg` e `?` por
`%s`, passam a ler `DATABASE_URL`, e precisam das quatro correções de indexação
por posição já citadas. O `ON CONFLICT ... DO UPDATE` que os dois já usam é
sintaxe do Postgres e passa direto.

Depois da migração, o `criar_usuario.py` serve só para criar o primeiro gestor no
banco vazio. Todo o resto passa pela tela, uma vez consertado o `SENHA_MIN`.

O `rodar_local.sh` continua útil. Aponte para uma branch do Neon, não para o
banco de produção, senão um teste no Mac escreve ficha de mentira no banco real.
O Neon cria branch de banco em segundos e a franquia gratuita inclui isso.

## Documentos que ficam errados

O `DEPLOY.md` descreve o deploy no servidor, com `scp` para `/home/ricardo` e
pedido de systemd para a TI. Depois desta migração ele está errado do começo ao
fim. Reescreva ou marque como histórico no topo. Runbook errado é pior que
runbook nenhum, porque alguém segue.

O `DOC_TECNICO_TI.md` e o `ARQUITETURA.md` também falam em rodar no servidor.
Vale uma nota no topo dizendo o que mudou e em que data.

## Ordem de execução

1. Conserte o tratamento de erro do `sincronizar()` no `static/app.js`, o login
   dentro do SQL da linha 1450 e a permissão das quatro rotas de viagem. Os três
   valem no servidor de hoje e não dependem da migração.
2. Confirme que `.env` está no `.gitignore`.
3. Crie `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN` e `REP_SECRET_KEY` nas variáveis
   de ambiente do projeto na Vercel. As três, não duas. Um `.env` no Mac não
   chega na Vercel. Chave de administração da conta do Neon não entra nessa
   lista, porque o app não usa e guardá-la junto só aumenta o estrago se o
   arquivo vazar.
4. Escreva o `setup_db.py`, com `double precision` no lugar de `REAL`, e rode do
   Mac. Confira as dez tabelas no Neon.
5. Converta o `app.py`, seguindo as seções acima na ordem em que aparecem. As
   rotas de viagem e de sugestão são as mais novas e as menos cobertas por uso
   real, então teste elas com dois usuários diferentes.
6. Adicione `requirements.txt`, `vercel.json`, `api/index.py` e `.vercelignore`.
7. Ajuste o lote, o `MAX_ANEXOS` e o `MAX_CONTENT_LENGTH`.
8. Suba a versão do cache no `static/sw.js` e ponha o `viagens.js` no shell.
9. Converta `criar_usuario.py` e `importar_carteira.py`, e rode os dois do Mac
   para criar o primeiro gestor e carregar a carteira.
10. Publique e teste.

## Como verificar que deu certo

Abra `/saude`. Tem que responder com a contagem de clientes importados. Se der
erro, o banco não conectou e nada mais adianta testar.

Troque a própria senha em `/conta`, crie um usuário e redefina a senha dele. São
as três telas que o commit `d86b0f9` acabou de consertar, e o port passa por
elas.

Erre a senha nove vezes seguidas. A nona tem que devolver 429. Se passar, o
contador ainda está na memória.

Registre duas visitas técnicas de clientes diferentes e sincronize as duas
juntas. Os dois números de ocorrência têm que ser diferentes, e as duas
ocorrências têm que aparecer no painel. Se aparecer uma só, o contador ainda tem
a corrida.

Mande um lote com uma ficha inválida no meio. As outras têm que entrar, e a
inválida tem que voltar na lista de rejeitadas com motivo na tela. Se a fila
inteira ficar parada, o tratamento de transação por ficha não está lá.

Registre uma visita com três evidências além da foto principal. As quatro têm
que abrir no painel do gestor. Se abrir só a principal, os anexos ainda estão
indo para o disco.

Crie uma viagem, ponha clientes nela pelo botão duas vezes seguidas e abra o
roteiro. Cada cliente tem que aparecer uma vez só.

Entre com outro representante e tente abrir a viagem do primeiro pela URL,
trocando o número. Tem que dar 403.

Busque no painel por um nome em minúsculas que está gravado com maiúscula. Tem
que achar. Faça o mesmo na busca de cidade da tela de viagens.

Confira no painel um cliente de volume alto. O valor precisa bater com o CSV até
os centavos. Se arredondou, a coluna ficou `REAL`.

Por último, no celular de verdade: instalar na tela inicial, registrar uma visita
com foto e GPS no modo avião, voltar para a rede e ver a ficha subir. É esse
teste que justifica a migração inteira, porque é o que o certificado do servidor
impedia.

## Conta de volume, para referência

Três usuários, umas 30 fichas por dia no pior caso, foto de 250 KB. Dá 7,5 MB por
dia e uns 150 MB por mês de dias úteis. É por isso que a foto não cabe no banco,
e é o número para comparar com a franquia do Blob.

## Quem decide o quê

O código é do Ricardo e a decisão de produto é dele. A TI decidiu a hospedagem,
por causa do certificado, e escreveu esta especificação. Dúvida sobre o app fala
com o Ricardo. Dúvida sobre Vercel, Neon ou credencial fala com o Henrique.
