# -*- coding: utf-8 -*-
"""Manda um e-mail de TESTE, para provar o canal antes de depender dele.

A mensagem se identifica como teste e pede para quem receber avisar o gerente
comercial - assim a confirmacao volta por um caminho humano, sem depender de
mais nenhum sistema.

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


ASSUNTO = "[TESTE] REP Campo - alerta de correcao de cadastro"

CORPO = """Esta mensagem e um TESTE. Nao e um pedido de correcao de verdade.

Estamos ligando um aviso automatico: toda vez que um representante em campo
encontrar o cadastro de um cliente desatualizado (endereco, cidade, telefone,
contato ou razao social), vai chegar neste e-mail uma mensagem como esta, com
o numero da ocorrencia, o cliente e o dado novo.

PEDIMOS O SEGUINTE: se voce recebeu este e-mail, por favor AVISE O GERENTE
COMERCIAL RICARDO que a mensagem chegou. E so isso - e para confirmarmos que
o caminho esta funcionando.

Obrigado.

--
Um alerta de verdade chega assim:

Ocorrencia:  OC-2026-0005
Cliente:     VIDRACARIA EXEMPLO LTDA (cod RAP-000)
Municipio:   Sao Luis
O que mudou: Cidade
Aberta por:  Islanno (representante)
ATENCAO: mudou de cidade para Timon - muda rota e tabela.

hoje no sistema: Rua Velha, 5 - Sao Luis/MA
passa a ser:    Av. Brasil, 100 - Centro, Timon/MA

Fila completa: https://rep-campo.vercel.app/painel (aba Ocorrencias)
"""


def main():
    carregar_env()
    if len(sys.argv) > 1:
        os.environ["ALERTA_CADASTRO_PARA"] = sys.argv[1]

    para = email.destinatarios("ALERTA_CADASTRO_PARA")
    canal = ("Resend" if email.conf("RESEND_API_KEY")
             else "SMTP %s" % email.conf("SMTP_HOST") if email.conf("SMTP_HOST")
             else "NENHUM")
    origem = "ambiente" if os.environ.get("SMTP_HOST") else "banco (config_email)"
    print("[i] canal configurado: %s  [vindo do %s]" % (canal, origem))
    print("[i] destinatarios....: %s" % (", ".join(para) or "(nenhum)"))
    print("[i] remetente........: %s" % (email.conf("EMAIL_REMETENTE") or "(padrao)"))
    if canal == "NENHUM" or not para:
        print("\n[--] falta configuracao. Abaixo vai o texto que seria enviado.\n")

    ok = email.enviar(ASSUNTO, CORPO, para)
    print("\n[%s] envio devolveu %s" % ("OK" if ok else "--", ok))
    if ok:
        print("     Confira a caixa de entrada (e o spam) de: %s" % ", ".join(para))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
