import pandas as pd

from src.config import (JANELA_ZSCORE, LIMIAR_DOSE_PCT, LIMIAR_ZSCORE,
                        LIMITES_CLINICOS, MIN_VITAIS_ZSCORE,
                        TOLERANCIA_EVENTO_S)

VITAIS = ["fc", "pas", "pad", "spo2"]
# Desvio mínimo por vital, para a série quase constante não gerar z gigante
DESVIO_MIN = {"fc": 1.5, "pas": 2.0, "pad": 1.5, "spo2": 0.5}


def zscore_movel(serie: pd.Series, janela: int = JANELA_ZSCORE,
                 desvio_min: float = 0.0) -> pd.Series:
    """z-score de cada ponto contra as `janela` leituras ANTERIORES.

    O shift(1) deixa o próprio ponto fora da janela, e só usa o passado,
    então a mesma lógica funciona linha a linha em tempo real.
    """
    media = serie.rolling(janela).mean().shift(1)
    desvio = serie.rolling(janela).std().shift(1).clip(lower=desvio_min)
    return (serie - media) / desvio


def _variaveis_alteradas(linha: pd.Series) -> list[str]:
    alteradas = [v for v in VITAIS if abs(linha[f"z_{v}"]) > LIMIAR_ZSCORE]
    L = LIMITES_CLINICOS
    if linha["spo2"] < L["spo2_min"] and "spo2" not in alteradas:
        alteradas.append("spo2")
    if (linha["fc"] < L["fc_min"] or linha["fc"] > L["fc_max"]) and "fc" not in alteradas:
        alteradas.append("fc")
    if linha["pas"] < L["pas_min"] and "pas" not in alteradas:
        alteradas.append("pas")
    return alteradas


def detectar_vitais(df: pd.DataFrame) -> pd.DataFrame:
    """Marca leituras anômalas: estatística (>=2 vitais com |z| alto)
    OU violação de limite clínico fixo."""
    out = df.copy()
    for v in VITAIS:
        out[f"z_{v}"] = zscore_movel(out[v], desvio_min=DESVIO_MIN[v])
    z_alto = out[[f"z_{v}" for v in VITAIS]].abs() > LIMIAR_ZSCORE
    out["anom_estatistica"] = z_alto.sum(axis=1) >= MIN_VITAIS_ZSCORE
    L = LIMITES_CLINICOS
    out["anom_limite"] = ((out["spo2"] < L["spo2_min"])
                          | (out["fc"] < L["fc_min"]) | (out["fc"] > L["fc_max"])
                          | (out["pas"] < L["pas_min"]))
    out["anomalia"] = out["anom_estatistica"] | out["anom_limite"]
    out["variaveis"] = out.apply(
        lambda r: ";".join(_variaveis_alteradas(r)) if r["anomalia"] else "", axis=1)
    return out


def agrupar_eventos(df: pd.DataFrame,
                    tolerancia_s: int = TOLERANCIA_EVENTO_S) -> pd.DataFrame:
    """Junta leituras anômalas próximas em eventos (início, fim, variáveis)."""
    eventos: list[dict] = []
    for _, r in df[df["anomalia"]].iterrows():
        vars_r = set(filter(None, r["variaveis"].split(";")))
        if eventos and (r["timestamp"] - eventos[-1]["fim"]).total_seconds() <= tolerancia_s:
            eventos[-1]["fim"] = r["timestamp"]
            eventos[-1]["variaveis"] |= vars_r
            eventos[-1]["leituras"] += 1
        else:
            eventos.append({"inicio": r["timestamp"], "fim": r["timestamp"],
                            "variaveis": set(vars_r), "leituras": 1})
    out = pd.DataFrame(eventos, columns=["inicio", "fim", "variaveis", "leituras"])
    out["variaveis"] = out["variaveis"].apply(lambda s: ";".join(sorted(s)))
    return out


def detectar_prescricoes(df: pd.DataFrame) -> pd.DataFrame:
    """Marca prescrições com dose alterada bruscamente ou frequência trocada."""
    out = df.sort_values(["medicamento", "timestamp"]).copy()
    g = out.groupby("medicamento")
    out["variacao_pct"] = g["dose_mg"].pct_change() * 100
    freq_ant = g["frequencia"].shift(1)
    out["mudou_frequencia"] = freq_ant.notna() & (freq_ant != out["frequencia"])
    out["anom_dose"] = out["variacao_pct"].abs() > LIMIAR_DOSE_PCT
    out["anomalia"] = out["anom_dose"] | out["mudou_frequencia"]

    def motivo(r):
        m = []
        if r["anom_dose"]:
            m.append(f"dose {r['variacao_pct']:+.0f}%")
        if r["mudou_frequencia"]:
            m.append("frequência alterada")
        return "; ".join(m)

    out["motivo"] = out.apply(motivo, axis=1)
    return out.sort_values("timestamp").reset_index(drop=True)