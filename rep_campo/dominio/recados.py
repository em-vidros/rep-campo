# -*- coding: utf-8 -*-
"""Recado do gestor para quem esta em campo. Puro: sem banco, sem Flask.

Dois formatos, e a diferenca entre eles e o que faz a coisa funcionar:

- **recado geral**: sem cliente. Vale para o dia a dia ("essa semana foque em
  orcamento parado"). Aparece numa faixa no topo do app ate ser lido.
- **missao em cliente**: amarrada ao codigo do ERP. Nao depende de o
  representante lembrar de abrir lista nenhuma: o cliente sobe ao topo da
  sugestao de visitas, a missao aparece no cartao dele na hora de preencher a
  ficha, e ao salvar o app pergunta se cumpriu.
"""

ABERTO = "aberto"
LIDO = "lido"
CONCLUIDO = "concluido"
CANCELADO = "cancelado"

STATUS = (ABERTO, LIDO, CONCLUIDO, CANCELADO)
# aberto e lido sao os dois estados em que o recado ainda cobra alguma coisa
PENDENTES = (ABERTO, LIDO)

MAX_TEXTO = 600
MAX_RESPOSTA = 600

# Acima de tudo que a sugestao pontua hoje (o maior e 120, de quem parou de
# comprar). Pedido direto do gestor nao disputa lugar com heuristica.
PESO_MISSAO = 200


def texto_valido(texto):
    """Devolve o texto limpo, ou None se nao da para mandar."""
    t = (texto or "").strip()
    if len(t) < 3:
        return None
    return t[:MAX_TEXTO]


def pode_concluir(status):
    return status in PENDENTES


def motivo_missao(quantas, de_quem=None):
    """Frase que a sugestao de visitas mostra. Sempre diz de quem partiu."""
    quem = (de_quem or "").split()[0] if de_quem else ""
    if quantas > 1:
        return "%d recados de %s" % (quantas, quem) if quem else "%d recados do gestor" % quantas
    return "recado de %s" % quem if quem else "recado do gestor"
