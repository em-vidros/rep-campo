# Runbook de deploy — REP Campo

> Criado em 27/08/2026. **Nada foi executado em produção.**
> Regra da casa: produção só com backup e rollback documentados, e fora do
> horário comercial.

---

## ⛔ Dois bloqueios reais antes de qualquer deploy

### 1. Certificado HTTPS inválido — verificado em 27/08/2026

```
subject = /C=BR/ST=MA/L=Imperatriz/O=EM Vidros/CN=192.168.14.32
issuer  = /C=BR/ST=MA/L=Imperatriz/O=EM Vidros/CN=192.168.14.32   <- autoassinado
validade= 05/05/2026 a 02/05/2036
erro TLS= 18 (self signed certificate)
```

São **dois defeitos, não um**:

| Defeito | Efeito |
|---|---|
| Emissor é ele mesmo (autoassinado) | Navegador não confia |
| `CN = 192.168.14.32` (IP **interno**), mas o acesso é por `170.247.31.241` | Não bate com o host nem se fosse confiável |

Consequência direta: **Chrome e Safari não registram service worker nem liberam
geolocalização** numa origem com erro de certificado — nem se o usuário aceitar
a exceção manualmente. Sem isso o app perde **offline e check-in**, que são as
duas razões de ele existir.

### 2. O sudo do `ricardo` no servidor é restrito a dois comandos

```
(ALL) NOPASSWD: /usr/local/bin/emv-painel-metas, /bin/cp
```

Ou seja, **não dá para**: criar um serviço systemd novo, instalar/renovar
certificado, configurar nginx, ou abrir porta. Publicar o REP Campo como app
separado **exige a TI**.

---

## Caminho A — testar no celular JÁ, sem esperar a TI (recomendado agora)

Serve para validar geolocalização, câmera e offline num aparelho real antes de
mobilizar terceiros. Roda na rede local, sem tocar em produção.

1. Subir o app numa máquina da rede (o próprio MacBook serve):
   ```
   python app.py     # escuta em 0.0.0.0:8010
   ```
2. Descobrir o IP da máquina na LAN: `ipconfig getifaddr en0`
3. No **Chrome do Android**, abrir `chrome://flags/#unsafely-treat-insecure-origin-as-secure`,
   incluir `http://<IP-da-maquina>:8010`, marcar **Enabled** e reiniciar o navegador.
   Isso faz o Chrome tratar aquela origem como contexto seguro — service worker e
   GPS passam a funcionar.
4. Abrir o endereço, instalar na tela inicial e rodar uma visita de verdade.

> Só para teste, em aparelho controlado. **Não é caminho de produção** — a flag
> é por aparelho e some quando o navegador é reinstalado.
> No iPhone/Safari não há equivalente: o teste em iOS depende do HTTPS válido.

---

## Caminho B — produção como app separado (precisa da TI)

Pedido à TI em [PEDIDO_TI.md](PEDIDO_TI.md).

Depois de a TI entregar domínio + certificado + serviço:

```bash
# 1. BACKUP (sempre primeiro)
ssh emhub "sudo cp -r /home/ricardo/rep-campo /home/ricardo/rep-campo.bak_$(date +%Y%m%d_%H%M)"
ssh emhub "sudo cp /home/ricardo/rep-campo/dados/rep_campo.db /home/ricardo/rep-campo/dados/rep_campo.db.bak_$(date +%Y%m%d_%H%M)"

# 2. SUBIR o código (o banco NUNCA é sobrescrito)
scp -i ~/.ssh/id_ed25519_ricardo app.py importar_carteira.py criar_usuario.py \
    emhub:/home/ricardo/rep-campo/
scp -i ~/.ssh/id_ed25519_ricardo -r static templates emhub:/home/ricardo/rep-campo/

# 3. RESTART
ssh emhub "sudo emv-rep-campo restart"

# 4. VERIFICAR (obrigatório - nao pular)
curl -s https://<dominio>/saude          # {"ok":true,"clientes":1453}
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
     -H 'Content-Type: application/json' -d '{"fichas":[]}' https://<dominio>/api/fichas
     # tem que dar 401 - se der 200, a autenticacao quebrou: ROLLBACK
```

### Rollback

```bash
ssh emhub "sudo cp -r /home/ricardo/rep-campo.bak_<carimbo>/. /home/ricardo/rep-campo/"
ssh emhub "sudo emv-rep-campo restart"
curl -s https://<dominio>/saude
```

O banco fica em `dados/` e **não é tocado** pelo deploy — o rollback do código
não perde ficha nenhuma. Se precisar voltar o banco também, restaurar o
`.bak_<carimbo>` correspondente.

---

## Caminho C — embutir no painel de metas (evita criar serviço, NÃO resolve o HTTPS)

O painel já roda com gunicorn na 8002 e o Ricardo **tem** permissão para o fluxo
`scp` → `sudo cp` → `sudo emv-painel-metas restart`. Dá para registrar o REP
Campo como blueprint dentro do `app.py` do painel, sob o prefixo `/rep`.

- ✅ Dispensa a TI para criar serviço
- ✅ Usa um caminho de deploy já testado
- ❌ **Continua sem resolver o certificado** — offline e check-in seguem bloqueados
- ❌ Mexe num app de produção que a diretoria usa todo dia

> Só faz sentido se a TI resolver o certificado mas não quiser criar serviço novo.
> Nunca como atalho para pular o HTTPS.

---

## Checklist de corte

- [ ] Certificado válido respondendo no domínio novo
- [ ] `curl https://<dominio>/saude` → `ok:true`
- [ ] POST sem sessão → **401**
- [ ] Service worker registrado (DevTools → Application → Service Workers)
- [ ] Instalação na tela inicial funciona em Android **e** iPhone
- [ ] Uma visita real gravada offline e sincronizada num celular
- [ ] Usuários criados com senha definida pelo dono (nunca a de teste)
- [ ] Carteira importada e conferida (1.453 clientes + curva ABC)
- [ ] Backup do banco agendado
- [ ] Deploy feito **fora do horário comercial**
