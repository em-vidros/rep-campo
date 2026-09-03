# Roteiro de teste em campo — REP Campo v1

> Criado em 01/09/2026. Para o Ricardo rodar **antes** de entregar ao Sipião.

**Faça você primeiro.** Um app de campo entregue sem o gestor ter preenchido
uma ficha de verdade chega como imposição. Depois de você rodar uma manhã, os
ajustes vêm da sua mão, não do reclame dele.

---

## 0. Preparar (10 minutos)

```bash
cd "…/em-vidros-raposa/app-rep-campo"
./rodar_local.sh
```

1. Anote o endereço que o script imprime (ex.: `http://192.168.15.154:8010`)
2. **Troque a senha do Sipião** — hoje está uma provisória:
   ```
   REP_DB=~/.rep-campo-local/dados/rep_campo.db \
   ~/.rep-campo-local/venv/bin/python scripts/criar_usuario.py sipiao "Tiago Sipiao" rep
   ```
3. No Android: `chrome://flags/#unsafely-treat-insecure-origin-as-secure` →
   adicionar o endereço → **Enabled** → reiniciar o Chrome
4. Abrir o endereço, menu → **Adicionar à tela inicial**
5. Abrir pelo ícone (não pela aba) — é assim que o Sipião vai usar

> Só funciona dentro da rede do escritório/casa. Fora dela, precisa do HTTPS
> ([DEPLOY.md](DEPLOY.md)). Para este teste, tudo bem.

---

## 1. As cinco perguntas que valem mais que o resto

Responda depois de **cada** ficha preenchida em situação real:

| # | Pergunta | Por que decide |
|---|---|---|
| 1 | **Deu pra preencher na frente do cliente sem quebrar a conversa?** | Se não, ele vai preencher tudo à noite, de memória — e aí o check-in morre e o dado vira ficção |
| 2 | Quanto tempo levou? | Acima de 2–3 min por ficha, não sobrevive a uma rota de 6 visitas |
| 3 | Deu pra usar **com uma mão**, em pé? | Campo é em pé, com prancheta, café ou amostra na outra mão |
| 4 | Deu pra **ler sob sol**? | Testar do lado de fora, não dentro do carro |
| 5 | Teve campo que você **não soube responder na hora**? | Campo que exige consulta a sistema não pode ser obrigatório |

---

## 2. O que olhar em cada tipo

### 🤝 Comercial
- "Valor estimado" — você consegue estimar **na hora** ou só depois de orçar?
  Se só depois, o campo tem que aceitar vazio sem incomodar.
- Falta algo entre "houve oportunidade" e o encaminhamento? Ex.: concorrente
  que está levando, motivo da recusa.
- O campo "Encaminhar para" tem que ter **lista de vendedores**, não texto
  livre? (hoje é texto livre — se você digitar o nome errado, o cruzamento
  com o pedido não fecha)

### ☕ Cordialidade
- O termômetro 1–5 sai natural ou você trava pensando?
- "Percebi risco de perder o cliente" — você marcaria **sim** de verdade, ou é
  um campo que ninguém preenche por parecer denúncia? Se ninguém marca, ele
  não serve; melhor virar pergunta na reunião de sexta.

### 🔧 Técnica / reclamação
- **Você tem o número do pedido/NF na hora?** Provavelmente não — está no ERP.
  Se for esse o caso, é o primeiro candidato a integração com o Webglass.
- Dá pra fotografar o defeito **com o cliente olhando** sem constranger?
- "Prazo prometido ao cliente" — você promete na hora ou precisa consultar o
  PCP? Se precisa consultar, o campo devia ser "prazo a confirmar".

### 🔍 Prospecção
- **CNPJ na hora é realista?** Em vidraçaria pequena, dificilmente. Talvez o
  certo seja foto da fachada + nome, e o CNPJ entra depois no cadastro.
- Já tem campo suficiente pra o vendedor dar sequência sem te ligar?

### 💰 Pesquisa de preço — o tipo mais delicado
- **O concorrente te passa orçamento?** Se a coleta é indireta (cliente mostra,
  você vê tabela no balcão), a "foto do orçamento" pode ser impossível — e aí
  a exigência de foto trava a ficha.
- Decidir agora: mantém foto obrigatória, ou aceita "sem foto + de onde veio o
  preço"? **Preço sem origem registrada não serve pra decisão de tabela.**
- A cesta de itens é fixa? Hoje é livre. Se cada mês vier item diferente, não
  dá pra comparar mês a mês — que é o objetivo do radar.

### 📣 Voz do cliente
- Dá pra perguntar "de 0 a 10" sem soar pesquisa formal no meio da visita?
- O verbatim: você digita as palavras do cliente ou resume? **Resumo perde o
  valor** — se digitar for inviável, o caminho é ditar por voz.

### 🎪 Evento
- Preenche durante ou depois? Se for depois, o check-in não vale — e aí talvez
  esse tipo devesse aceitar registro fora da janela sem penalizar.

---

## 3. Testes de estresse (faça de propósito)

| Teste | Como | O que tem que acontecer |
|---|---|---|
| **Sem sinal** | Modo avião, preencher 2 fichas, salvar | Salva e mostra "sem internet / 2 na fila" |
| **Volta o sinal** | Desligar modo avião, esperar | Sobem sozinhas, a fila zera |
| **App fechado no meio** | Preencher metade, fechar, reabrir | Volta com "Rascunho recuperado" |
| **Foto pesada** | 5 fotos seguidas | Não trava nem estoura memória |
| **Cliente fora da carteira** | Digitar nome inventado | Avisa "será registrado como cliente novo" |
| **Salvar vazio** | Enviar sem preencher | Lista os campos que faltam, inclusive foto |
| **Bateria** | Uma manhã de uso | Anotar o consumo — GPS puxa bateria |
| **Duas fichas do mesmo cliente** | Mesmo cliente, tipos diferentes | Aceita as duas, sem confundir |

---

## 4. O que anotar (folha simples)

Para cada ficha: **tipo · minutos · o que travou · campo que faltou · campo que sobrou**

No fim do dia, três respostas:

1. Qual campo eu **não soube responder** na hora?
2. Qual campo eu **preenchi de qualquer jeito** só pra passar? *(esse é o campo
   a matar — campo preenchido no chute é pior que campo ausente)*
3. O que eu **quis registrar e não tinha onde**?

---

## 5. Critério de aprovação

O app está pronto pro Sipião quando:

- [ ] Ficha comercial em **até 2 minutos**
- [ ] Preenchida **na frente do cliente** sem quebrar a conversa
- [ ] Nenhum campo obrigatório exige consulta a outro sistema
- [ ] Legível sob sol, operável com uma mão
- [ ] Ciclo offline → online funcionou **num celular real**
- [ ] Rascunho sobreviveu a fechar o app
- [ ] Nenhum campo que você preencheu no chute

Se algum item falhar, é ajuste no app — **não** treinamento do usuário.
Formulário que precisa de treinamento pra ser preenchido em campo é formulário
mal desenhado.

---

## 6. Depois do teste

Me traga as anotações da seção 4 que eu ajusto o formulário. A ordem provável de
mudança, pelo que já dá pra prever:

1. Lista de vendedores no "Encaminhar para" (hoje texto livre quebra o cruzamento)
2. Regra da foto na pesquisa de preço
3. Número do pedido na ficha técnica — puxar do ERP ou aceitar vazio
4. Cesta fixa de itens no radar de preço
