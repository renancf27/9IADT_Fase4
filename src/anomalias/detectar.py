import pandas as pd

from src.anomalias.detectores import (agrupar_eventos, detectar_prescricoes,
                                      detectar_vitais)
from src.config import DATA_DIR, INSTANTE_VITAIS, JANELA_CONFIRMACAO_VITAIS
from src.dados.gerar_vitais import DURACAO_PICO_S, DURACAO_RECUPERACAO_S

DURACAO_EPISODIO_S = DURACAO_PICO_S + DURACAO_RECUPERACAO_S


def avaliar_vitais(eventos: pd.DataFrame) -> dict:
    """Evento verdadeiro: intersecta o episódio injetado (com folga de confirmação)."""
    ini = INSTANTE_VITAIS - JANELA_CONFIRMACAO_VITAIS
    fim = INSTANTE_VITAIS + pd.Timedelta(seconds=DURACAO_EPISODIO_S) + JANELA_CONFIRMACAO_VITAIS
    verdadeiros = eventos[(eventos["inicio"] <= fim) & (eventos["fim"] >= ini)]
    falsos = len(eventos) - len(verdadeiros)
    atraso = None
    if len(verdadeiros):
        atraso = (verdadeiros["inicio"].min() - INSTANTE_VITAIS).total_seconds()
    return {"detectado": len(verdadeiros) > 0, "atraso_s": atraso, "falsos_alarmes": falsos}


def avaliar_prescricoes(df: pd.DataFrame, gab_ts) -> dict:
    flag = df[df["anomalia"]]
    acerto = flag[flag["timestamp"] == gab_ts]
    return {"detectado": len(acerto) > 0, "falsos_alarmes": len(flag) - len(acerto)}


def main() -> None:
    vitais = pd.read_csv(DATA_DIR / "vitais.csv", parse_dates=["timestamp"])
    prescr = pd.read_csv(DATA_DIR / "prescricoes.csv", parse_dates=["timestamp"])
    gab = pd.read_csv(DATA_DIR / "gabarito.csv", parse_dates=["timestamp"])

    det_v = detectar_vitais(vitais)
    ev_v = agrupar_eventos(det_v)
    det_p = detectar_prescricoes(prescr)

    det_v.round({c: 2 for c in det_v.columns if c.startswith("z_")}).to_csv(DATA_DIR / "anomalias_vitais.csv", index=False)
    ev_v.to_csv(DATA_DIR / "eventos_vitais.csv", index=False)
    det_p[det_p["anomalia"]].to_csv(DATA_DIR / "eventos_prescricoes.csv", index=False)

    print("=== Sinais vitais ===")
    for _, e in ev_v.iterrows():
        print(f"  evento {e['inicio']:%H:%M:%S} a {e['fim']:%H:%M:%S} "
              f"({e['leituras']} leituras) variáveis: {e['variaveis']}")
    av = avaliar_vitais(ev_v)
    print(f"  detectado: {av['detectado']} | atraso: {av['atraso_s']} s | "
          f"falsos alarmes: {av['falsos_alarmes']}")

    print("\n=== Prescrições ===")
    for _, r in det_p[det_p["anomalia"]].iterrows():
        print(f"  {r['timestamp']:%d/%m %H:%M} {r['medicamento']} "
              f"{r['dose_mg']} mg ({r['motivo']})")
    ts_gab = gab[gab["fonte"] == "prescricao"]["timestamp"].iloc[0]
    avp = avaliar_prescricoes(det_p, ts_gab)
    print(f"  detectado: {avp['detectado']} | falsos alarmes: {avp['falsos_alarmes']}")


if __name__ == "__main__":
    main()
