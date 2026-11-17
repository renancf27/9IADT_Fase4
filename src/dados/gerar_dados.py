import pandas as pd

from src.config import DATA_DIR, INICIO_VIDEO, INSTANTE_VITAIS
from src.dados.gerar_notas import gabarito_notas, gerar_notas
from src.dados.gerar_prescricoes import gabarito_prescricoes, gerar_prescricoes
from src.dados.gerar_vitais import gabarito_vitais, gerar_vitais

COLUNAS_GABARITO = [
    "fonte", "timestamp", "descricao",
    "sintomas_presentes", "sintomas_negados", "ativa_contexto",
]


def montar_gabarito() -> pd.DataFrame:
    registros = (gabarito_vitais()
                 + gabarito_prescricoes() + gabarito_notas())
    df = pd.DataFrame(registros)
    df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return df.reindex(columns=COLUNAS_GABARITO)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    vitais = gerar_vitais()
    prescricoes = gerar_prescricoes()
    notas = gerar_notas()
    gabarito = montar_gabarito()

    vitais.to_csv(DATA_DIR / "vitais.csv", index=False)
    prescricoes.to_csv(DATA_DIR / "prescricoes.csv", index=False)
    notas.to_csv(DATA_DIR / "notas.csv", index=False)
    gabarito.to_csv(DATA_DIR / "gabarito.csv", index=False)

    print(f"Vitais alteram em: {INSTANTE_VITAIS:%d/%m/%Y %H:%M:%S} | "
          f"início do clipe (relógio fictício): {INICIO_VIDEO:%H:%M:%S}")
    print(f"vitais.csv      : {len(vitais)} linhas")
    print(f"prescricoes.csv : {len(prescricoes)} linhas")
    print(f"notas.csv       : {len(notas)} notas")
    print(f"gabarito.csv    : {len(gabarito)} registros")


if __name__ == "__main__":
    main()
