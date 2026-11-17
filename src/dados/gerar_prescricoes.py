from datetime import datetime

import pandas as pd

from src.config import DATA_DIR, PRESCRICAO_ALTERADA_EM

# (timestamp, medicamento, dose_mg, via, frequencia)
REGISTROS = [
    # Losartana: dose estável por dois dias e depois triplicada (anomalia)
    (datetime(2026, 10, 25, 9, 0), "Losartana", 50, "oral", "24/24h"),
    (datetime(2026, 10, 26, 9, 0), "Losartana", 50, "oral", "24/24h"),
    (PRESCRICAO_ALTERADA_EM,       "Losartana", 150, "oral", "24/24h"),
    # Dipirona: dose estável o tempo todo (controle, não deve gerar alerta)
    (datetime(2026, 10, 25, 9, 0), "Dipirona", 1000, "oral", "6/6h"),
    (datetime(2026, 10, 26, 9, 0), "Dipirona", 1000, "oral", "6/6h"),
    (datetime(2026, 10, 27, 9, 0), "Dipirona", 1000, "oral", "6/6h"),
]


def gerar_prescricoes() -> pd.DataFrame:
    df = pd.DataFrame(
        REGISTROS,
        columns=["timestamp", "medicamento", "dose_mg", "via", "frequencia"],
    )
    return df.sort_values(["timestamp", "medicamento"]).reset_index(drop=True)


def gabarito_prescricoes() -> list[dict]:
    """Anomalia injetada, para a avaliação (item 5 da etapa 3)."""
    return [{
        "fonte": "prescricao",
        "timestamp": PRESCRICAO_ALTERADA_EM,
        "descricao": "Dose de Losartana alterada de 50 mg para 150 mg (3x)",
    }]


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = gerar_prescricoes()
    caminho = DATA_DIR / "prescricoes.csv"
    df.to_csv(caminho, index=False)
    print(f"Salvo em {caminho}")
    print(df.to_string(index=False))