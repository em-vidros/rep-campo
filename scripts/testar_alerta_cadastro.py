# -*- coding: utf-8 -*-
"""Manda um alerta de cadastro de mentira, para provar o canal de e-mail.

Nao toca no banco: nenhuma ficha, nenhuma ocorrencia. So monta o mesmo texto
que o app mandaria e tenta enviar pelo canal configurado.

Uso:  python scripts/testar_alerta_cadastro.py
      python scripts/testar_alerta_cadastro.py outro@endereco.com
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rep_campo.config import carregar_env
from rep_campo.infra import alertas, email


EXEMPLO = {
    "numero": "OC-TESTE-0000",
    "cliente": "VIDRACARIA EXEMPLO LTDA",
    "cliente_codigo": "RAP-000",
    "municipio": "Sao Luis",
    "o_que_mudou": "Cidade",
    "cidade_nova": "Timon",
    "aberta_por": "teste do sistema",
    "descricao": ("hoje no sistema: Rua Velha, 5 - Sao Luis/MA | "
                  "passa a ser: Av. Brasil, 100 - Centro, Timon/MA | "
                  "cidade nova: Timon | informado por: teste"),
}


def main():
    carregar_env()
    if len(sys.argv) > 1:
        os.environ["ALERTA_CADASTRO_PARA"] = sys.argv[1]

    para = email.destinatarios("ALERTA_CADASTRO_PARA")
    canal = ("Resend" if os.environ.get("RESEND_API_KEY")
             else "SMTP %s" % os.environ.get("SMTP_HOST") if os.environ.get("SMTP_HOST")
             else "NENHUM")
    print("[i] canal configurado: %s" % canal)
    print("[i] destinatarios....: %s" % (", ".join(para) or "(nenhum)"))
    print("[i] remetente........: %s" % (os.environ.get("EMAIL_REMETENTE") or "(padrao)"))
    if canal == "NENHUM" or not para:
        print("\n[--] falta configuracao. Abaixo vai o texto que seria enviado.\n")

    ok = alertas.alertar_cadastro(EXEMPLO)
    print("\n[%s] alertar_cadastro devolveu %s" % ("OK" if ok else "--", ok))
    if ok:
        print("     Confira a caixa de entrada (e o spam) de: %s" % ", ".join(para))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
