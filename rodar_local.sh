#!/bin/bash
# Sobe o REP Campo no Mac para teste - inclusive no celular pela rede local.
#
#   ./rodar_local.sh
#
# O codigo-fonte vive no Google Drive, mas o app NAO roda de la: processos
# filhos nao tem permissao de leitura no CloudStorage (protecao do macOS).
# Por isso o script copia para uma pasta de trabalho local e roda de la.
set -e

ORIGEM="$(cd "$(dirname "$0")" && pwd)"
TRAB="$HOME/.rep-campo-local"
VENV="$TRAB/venv"

echo "[1/5] preparando pasta de trabalho em $TRAB"
mkdir -p "$TRAB"
# o banco e as fotos NAO sao sobrescritos - so o codigo
rsync -a --exclude 'dados/rep_campo.db' --exclude 'dados/secret.key' \
      --exclude 'dados/fotos' --exclude 'venv' "$ORIGEM/" "$TRAB/"
mkdir -p "$TRAB/dados/fotos"

echo "[2/5] ambiente Python"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet flask
fi

echo "[3/5] banco e carteira"
if [ ! -f "$TRAB/dados/rep_campo.db" ]; then
  cd "$TRAB" && "$VENV/bin/python" -c "import app" >/dev/null   # cria o schema
  # a carteira mora no Drive; le de la e grava no banco local
  REP_DB="$TRAB/dados/rep_campo.db" "$VENV/bin/python" "$ORIGEM/importar_carteira.py"
  echo
  echo ">> Nenhum usuario existe ainda. Crie o seu:"
  echo "   REP_DB=$TRAB/dados/rep_campo.db $VENV/bin/python $ORIGEM/criar_usuario.py <login> \"<Nome>\" rep"
  echo
else
  echo "     banco ja existe - preservado"
fi

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")
echo "[4/5] endereco"
echo "     neste Mac ....... http://localhost:8010"
[ -n "$IP" ] && echo "     no celular ...... http://$IP:8010"
echo
echo "     Para GPS e offline no Android, marque a origem como segura em:"
echo "       chrome://flags/#unsafely-treat-insecure-origin-as-secure"
[ -n "$IP" ] && echo "       adicione: http://$IP:8010"
echo

echo "[5/5] subindo (ctrl+C para parar)"
cd "$TRAB"
REP_DB="$TRAB/dados/rep_campo.db" PORT=8010 exec "$VENV/bin/python" app.py
