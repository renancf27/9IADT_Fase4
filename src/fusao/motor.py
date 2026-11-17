import pandas as pd

from src.config import (JANELA_COINCIDENCIA, JANELA_CONTEXTO_NOTA,
                        JANELA_CONTEXTO_PRESCRICAO, JANELA_SUPRESSAO,
                        LIMIAR_ALTO, LIMIAR_MEDIO, PONTOS)

ORDEM = {"NENHUM": 0, "PREVENTIVO": 1, "MÉDIO": 2, "ALTO": 3}
NOMES_VITAIS = {"fc": "FC", "pas": "PAS", "pad": "PAD", "spo2": "SpO2"}
COLUNAS_ALERTA = ["timestamp", "severidade", "score", "queda", "vitais",
                  "contexto_nota", "contexto_prescricao", "mensagem"]


def severidade(score: int) -> str:
    if score >= LIMIAR_ALTO:
        return "ALTO"
    if score >= LIMIAR_MEDIO:
        return "MÉDIO"
    if score >= 1:
        return "PREVENTIVO"
    return "NENHUM"


def _hm(ts) -> str:
    return f"{ts:%H:%M}"


def _mensagem(nivel, t, nota_ativa, presc_ativa, quedas, vitais) -> str:
    partes = []
    if len(quedas):
        partes.append(f"queda detectada em vídeo às {quedas['inicio'].max():%H:%M:%S}")
    if len(vitais):
        v = vitais.iloc[-1]
        nomes = ", ".join(NOMES_VITAIS.get(x, x) for x in v["variaveis"].split(";") if x)
        partes.append(f"sinais vitais alterados ({nomes}) desde {v['inicio']:%H:%M:%S}")
    if len(nota_ativa):
        itens = ", ".join(f"{_hm(n['timestamp'])} [{n['sintomas_presentes']}]"
                          for _, n in nota_ativa.iterrows())
        rotulo = "nota de risco ativa" if len(nota_ativa) == 1 else "notas de risco ativas"
        partes.append(f"{rotulo}: {itens}")
    if len(presc_ativa):
        p = presc_ativa.iloc[-1]
        partes.append(f"prescrição das {_hm(p['timestamp'])}: "
                      f"{p['medicamento']} {p['dose_mg']} mg ({p['motivo']})")
    return f"[{nivel}] {t:%H:%M:%S} - " + "; ".join(partes)


def avaliar_gatilho(t, notas_risco, ev_prescr, quedas_todas, ev_vitais,
                    alertas: list[dict]) -> dict | None:
    """Avalia UM instante usando só as fontes conhecidas até t.

    Devolve o alerta (dict) ou None, se não há risco ou se o alerta seria
    repetido (mesma gravidade nos últimos JANELA_SUPRESSAO).
    Usado pelo modo em lote (fundir) e pelo modo em tempo real.
    """
    nota_ativa = notas_risco[(notas_risco["timestamp"] <= t)
                             & (notas_risco["timestamp"] > t - JANELA_CONTEXTO_NOTA)]
    presc_ativa = ev_prescr[(ev_prescr["timestamp"] <= t)
                            & (ev_prescr["timestamp"] > t - JANELA_CONTEXTO_PRESCRICAO)]
    quedas = quedas_todas[(quedas_todas["inicio"] <= t)
                          & (quedas_todas["inicio"] >= t - JANELA_COINCIDENCIA)]
    vitais = ev_vitais[(ev_vitais["inicio"] <= t)
                       & (ev_vitais["fim"] + JANELA_COINCIDENCIA >= t)]

    contexto = len(nota_ativa) > 0 or len(presc_ativa) > 0
    score = (PONTOS["contexto"] * contexto
             + PONTOS["queda"] * (len(quedas) > 0)
             + PONTOS["vitais"] * (len(vitais) > 0))
    nivel = severidade(score)
    if nivel == "NENHUM":
        return None

    recentes = [a for a in alertas if t - a["timestamp"] <= JANELA_SUPRESSAO]
    maior_recente = max((ORDEM[a["severidade"]] for a in recentes), default=0)
    if ORDEM[nivel] <= maior_recente:
        return None  # suprimido: não escala a gravidade

    return {
        "timestamp": t,
        "severidade": nivel,
        "score": score,
        "queda": len(quedas) > 0,
        "vitais": len(vitais) > 0,
        "contexto_nota": len(nota_ativa) > 0,
        "contexto_prescricao": len(presc_ativa) > 0,
        "mensagem": _mensagem(nivel, t, nota_ativa, presc_ativa, quedas, vitais),
    }


def fundir(notas: pd.DataFrame, ev_vitais: pd.DataFrame,
           ev_prescr: pd.DataFrame, ev_video: pd.DataFrame) -> pd.DataFrame:
    """Modo em lote: percorre todos os gatilhos e gera os alertas.

    notas: timestamp, ativa_contexto, sintomas_presentes
    ev_vitais: inicio, fim, variaveis
    ev_prescr: timestamp, medicamento, dose_mg, motivo
    ev_video: inicio, tipo
    """
    # Garante colunas de data mesmo quando alguma fonte está vazia
    notas = notas.assign(timestamp=pd.to_datetime(notas["timestamp"]))
    ev_vitais = ev_vitais.assign(inicio=pd.to_datetime(ev_vitais["inicio"]),
                                 fim=pd.to_datetime(ev_vitais["fim"]))
    ev_prescr = ev_prescr.assign(timestamp=pd.to_datetime(ev_prescr["timestamp"]))
    ev_video = ev_video.assign(inicio=pd.to_datetime(ev_video["inicio"]))

    notas_risco = notas[notas["ativa_contexto"].astype(bool)]
    quedas_todas = ev_video[ev_video["tipo"] == "queda"]

    gatilhos = sorted(set(notas_risco["timestamp"]) | set(ev_prescr["timestamp"])
                      | set(ev_vitais["inicio"]) | set(quedas_todas["inicio"]))

    alertas: list[dict] = []
    for t in gatilhos:
        alerta = avaliar_gatilho(t, notas_risco, ev_prescr, quedas_todas,
                                 ev_vitais, alertas)
        if alerta:
            alertas.append(alerta)
    return pd.DataFrame(alertas, columns=COLUNAS_ALERTA)