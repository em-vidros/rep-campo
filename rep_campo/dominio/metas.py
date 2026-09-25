# -*- coding: utf-8 -*-
"""Meta de interacoes do representante. Pura: recebe contagens, devolve situacao.

A meta e diaria em numero e SEMANAL em cobranca. O dia mede ritmo; a semana e o
compromisso. Quem viaja perde a manha na estrada e recupera a tarde ou no dia
seguinte - cobrar por dia transformaria estrada em falta.

Sabado nao tem meta de visita de proposito: e o dia de organizar a semana e
fechar o planejamento das viagens. Mas visita feita no sabado CONTA na semana -
serve para recuperar o que ficou para tras.
"""

META_DIA_UTIL = 8
DIAS_UTEIS = 5
META_SEMANA = META_DIA_UTIL * DIAS_UTEIS


def meta_do_dia(data):
    """Segunda a sexta tem meta; sabado e domingo, nao."""
    return META_DIA_UTIL if data.weekday() < DIAS_UTEIS else 0


def situacao(feitas_hoje, feitas_semana, data):
    alvo_dia = meta_do_dia(data)
    dias_corridos = min(data.weekday() + 1, DIAS_UTEIS)   # seg=1 ... sex+=5
    # o esperado ate aqui: so conta dia util ja vivido
    esperado = META_DIA_UTIL * dias_corridos
    return {
        "meta_dia": alvo_dia,
        "meta_semana": META_SEMANA,
        "hoje": feitas_hoje,
        "semana": feitas_semana,
        "falta_hoje": max(alvo_dia - feitas_hoje, 0),
        "falta_semana": max(META_SEMANA - feitas_semana, 0),
        "esperado_ate_hoje": esperado,
        "pct_semana": round(100.0 * feitas_semana / META_SEMANA) if META_SEMANA else None,
        # em dia = alcancou o que se esperava ate este ponto da semana, mesmo que
        # o dia de hoje ainda esteja em aberto
        "em_dia": feitas_semana >= esperado,
        "dia_de_planejamento": alvo_dia == 0,
        # sabado sem meta, mas com semana em aberto: da para recuperar
        "pode_compensar": alvo_dia == 0 and feitas_semana < META_SEMANA,
    }
