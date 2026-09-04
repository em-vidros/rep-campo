# -*- coding: utf-8 -*-
"""Ponto de entrada local. O app mora em `rep_campo.create_app()`.

`api/index.py` (Vercel) importa de `rep_campo` direto. Este arquivo existe
para `python app.py` e compatibilidade histórica — sem re-exportar constantes
de domínio (importe de `rep_campo.dominio.catalogos` quem precisar).
"""
import os

from rep_campo import create_app

app = create_app()

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8010))
    print("[rep-campo] iniciando em http://127.0.0.1:%d" % porta)
    app.run(host="0.0.0.0", port=porta, debug=False)
