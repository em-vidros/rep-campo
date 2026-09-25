

# --------------------------------------------------- aderencia ao roteiro

MIN_JUSTIFICATIVA = 10


def justificativa_valida(texto):
    """Motivo curto demais nao e motivo. Sem isso, "nao deu" viraria o padrao."""
    t = (texto or "").strip()
    return t[:400] if len(t) >= MIN_JUSTIFICATIVA else None


def desempenho(planejados, visitados_do_plano, justificados, extras):
    """As duas leituras que o Ricardo pediu, e a diferenca entre elas importa.

    - `plano`: cumpriu o que se comprometeu a fazer. Nao aceita desculpa: e o
      numero que mede planejamento realista.
    - `ajustado`: descontado so o que teve motivo ESCRITO (cliente fechado,
      estrada interditada), quanto do plano que sobrou ele executou.
    - `extras`: quem ele visitou sem estar no plano. Nao entra na aderencia -
      substituir nao e cumprir -, mas aparece, porque trabalho feito e trabalho
      feito.

    Os dois juntos contam a historia: plano baixo com ajustado alto e problema
    de planejamento; os dois baixos e problema de execucao.
    """
    p = max(int(planejados or 0), 0)
    v = max(int(visitados_do_plano or 0), 0)
    j = min(max(int(justificados or 0), 0), max(p - v, 0))
    restante = p - j
    return {
        "planejados": p,
        "visitados_do_plano": v,
        "justificados": j,
        "sem_justificativa": max(p - v - j, 0),
        "extras": max(int(extras or 0), 0),
        "realizado_total": v + max(int(extras or 0), 0),
        "aderencia_plano": round(100.0 * v / p) if p else None,
        "aderencia_ajustada": round(100.0 * v / restante) if restante else (100 if p else None),
    }
