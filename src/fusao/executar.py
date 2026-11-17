import pandas as pd

from src.config import DATA_DIR
from src.fusao.motor import fundir


def ler(nome: str, colunas_data: list[str]) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / nome, parse_dates=colunas_data)


def eventos_video() -> pd.DataFrame:
    """Usa data/eventos_video.csv (gerado pelo detector de queda). Sem ele, não há eventos de vídeo."""
    caminho = DATA_DIR / "eventos_video.csv"
    if caminho.exists():
        return ler("eventos_video.csv", ["inicio"])
    print("AVISO: data/eventos_video.csv não existe (rode: python -m src.video.detector_queda); "
          "seguindo sem eventos de vídeo\n")
    return pd.DataFrame({"inicio": pd.to_datetime([]), "tipo": []})


def main() -> None:
    notas = ler("analise_notas.csv", ["timestamp"])
    ev_vitais = ler("eventos_vitais.csv", ["inicio", "fim"])
    ev_prescr = ler("eventos_prescricoes.csv", ["timestamp"])
    ev_video = eventos_video()

    alertas = fundir(notas, ev_vitais, ev_prescr, ev_video)
    alertas.to_csv(DATA_DIR / "alertas.csv", index=False)

    print(f"{len(alertas)} alerta(s) gerado(s):\n")
    for _, a in alertas.iterrows():
        print(a["mensagem"])
    print(f"\nSalvo em {DATA_DIR / 'alertas.csv'}")


if __name__ == "__main__":
    main()
