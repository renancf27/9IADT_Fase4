import numpy as np
import pandas as pd

from src.config import (DATA_DIR, FIM_VITAIS, INICIO_VITAIS, INSTANTE_VITAIS,
                        INTERVALO_VITAIS_S, SEED)

# Valores basais (média, desvio do ruído)
BASAL = {
    "fc":   (78, 2.0),    # batimentos por minuto
    "pas":  (122, 3.0),   # pressão sistólica (mmHg)
    "pad":  (78, 2.0),    # pressão diastólica (mmHg)
    "spo2": (97, 0.6),    # saturação de oxigênio (%)
}

# Variação máxima durante o episódio da queda
DELTA = {"fc": +40, "pas": -35, "pad": -25, "spo2": -8}

DURACAO_PICO_S = 60        # tempo no pico, a partir da alteração
DURACAO_RECUPERACAO_S = 60 # volta linear ao basal


def _fator(t: pd.Timestamp) -> float:
    """0 = normal, 1 = pico do episódio. Começa de forma abrupta em INSTANTE_VITAIS."""
    dt = (t - INSTANTE_VITAIS).total_seconds()
    if dt < 0:
        return 0.0
    if dt <= DURACAO_PICO_S:
        return 1.0
    if dt <= DURACAO_PICO_S + DURACAO_RECUPERACAO_S:
        return 1.0 - (dt - DURACAO_PICO_S) / DURACAO_RECUPERACAO_S
    return 0.0


def gerar_vitais() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    tempos = pd.date_range(INICIO_VITAIS, FIM_VITAIS,
                           freq=f"{INTERVALO_VITAIS_S}s")
    linhas = []
    for t in tempos:
        f = _fator(t)
        linha = {"timestamp": t}
        for nome, (media, desvio) in BASAL.items():
            valor = media + DELTA[nome] * f + rng.normal(0, desvio)
            linha[nome] = round(valor)
        linha["spo2"] = min(linha["spo2"], 100)
        linhas.append(linha)
    return pd.DataFrame(linhas)


def gabarito_vitais() -> list[dict]:
    """Anomalia injetada, para a avaliação (item 5 da etapa 3)."""
    return [{
        "fonte": "vitais",
        "timestamp": INSTANTE_VITAIS,
        "descricao": (f"SpO2 ~{BASAL['spo2'][0] + DELTA['spo2']}%, "
                      f"FC ~{BASAL['fc'][0] + DELTA['fc']}, "
                      f"PA ~{BASAL['pas'][0] + DELTA['pas']}/"
                      f"{BASAL['pad'][0] + DELTA['pad']} a partir da alteração"),
    }]


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = gerar_vitais()
    caminho = DATA_DIR / "vitais.csv"
    df.to_csv(caminho, index=False)
    print(f"Salvo em {caminho} ({len(df)} linhas)")
