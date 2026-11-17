import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (DATA_DIR, INICIO_VIDEO, INSTANTE_VITAIS, QUEDA_CONFIRMACAO_S,
                        QUEDA_DELTA_ALTURA, QUEDA_INTERVALO_MIN_S,
                        QUEDA_JANELA_S, QUEDA_LIMIAR_CHAO, QUEDA_PERMANENCIA_S,
                        QUEDA_TRONCO_MIN)

PASTA = DATA_DIR / "video"


ATRASO_SUGERIDO_S = 8  # os vitais simulados reagem uns segundos depois da queda


def queda_na_janela(f: pd.DataFrame) -> pd.Series:
    """Quanto o quadril desceu em relação ao ponto mais alto dos últimos QUEDA_JANELA_S."""
    passo = float(np.median(np.diff(f["tempo_s"])))
    n = max(1, int(round(QUEDA_JANELA_S / passo)))
    alt = f["quadril_altura"]
    return alt.rolling(n, min_periods=1).max() - alt


def detectar_quedas(f: pd.DataFrame) -> list[dict]:
    """Queda = descida rápida do quadril + chegada ao nível do chão com o tronco
    deitado + permanência no chão.

    f: colunas tempo_s, quadril_altura, tronco_angulo (saída de calcular_features).
    """
    t = f["tempo_s"].to_numpy()
    alt = f["quadril_altura"].to_numpy()
    tronco = f["tronco_angulo"].to_numpy()
    queda = queda_na_janela(f).to_numpy()

    eventos: list[dict] = []
    ultimo = -np.inf
    for i in range(len(t)):
        if not np.isfinite(queda[i]) or queda[i] < QUEDA_DELTA_ALTURA:
            continue
        if t[i] - ultimo < QUEDA_INTERVALO_MIN_S:
            continue

        # 1) em até QUEDA_CONFIRMACAO_S o quadril chega ao chão e o tronco deita
        janela = (t >= t[i]) & (t <= t[i] + QUEDA_CONFIRMACAO_S)
        chegou = janela & (alt < QUEDA_LIMIAR_CHAO) & (tronco > QUEDA_TRONCO_MIN)
        if not chegou.any():
            continue
        t_conf = float(t[chegou][0])

        # 2) permanece no chão: tempo contínuo com o quadril abaixo do limiar
        depois = (t >= t_conf)
        acima = np.where(depois & ~(alt < QUEDA_LIMIAR_CHAO))[0]
        t_fim = float(t[acima[0]]) if len(acima) else float(t[-1])
        permanencia = t_fim - t_conf
        if permanencia < QUEDA_PERMANENCIA_S:
            continue

        final = (t >= t_conf) & (t <= t_conf + 3)
        eventos.append({
            "tempo_s": round(float(t[i]), 2),
            "confirmado_em_s": round(t_conf, 2),
            "queda_altura": round(float(np.nanmax(queda[(t >= t[i]) & (t <= t_conf)])), 2),
            "altura_final": round(float(np.nanmedian(alt[final])), 2),
            "tronco_final": round(float(np.nanmedian(tronco[final])), 0),
            "permanencia_s": round(permanencia, 1),
        })
        ultimo = t[i]
    return eventos


def main(clipe_demo: str = "queda_01") -> None:
    arquivos = sorted(PASTA.glob("*_features.csv"))
    if not arquivos:
        print(f"Nenhum *_features.csv em {PASTA}. Rode antes: python -m src.video.extrair_pose")
        return

    linhas, todos = [], []
    for arq in arquivos:
        nome = arq.name.removesuffix("_features.csv")
        f = pd.read_csv(arq)
        eventos = detectar_quedas(f)
        esperado = 1 if nome.startswith("queda") else 0
        q = queda_na_janela(f)
        linhas.append({
            "clipe": nome, "esperado": esperado, "detectado": len(eventos),
            "max_queda_2s": round(float(q.max()), 2),
            "altura_min": round(float(f["quadril_altura"].min()), 2),
            "instantes": ", ".join(f"{e['tempo_s']:.1f}s" for e in eventos) or "-",
        })
        for e in eventos:
            todos.append({"clipe": nome, "tipo": "queda",
                          "inicio": INICIO_VIDEO + pd.Timedelta(seconds=round(e["tempo_s"])), **e})

    print("clipe | esperado | detectado | maior queda em 2 s | altura mínima | instantes")
    for r in linhas:
        ok = "OK     " if r["esperado"] == r["detectado"] else "DIVERGE"
        print(f"{ok} {r['clipe']} | {r['esperado']} | {r['detectado']} | "
              f"{r['max_queda_2s']} | {r['altura_min']} | {r['instantes']}")

    eventos_df = pd.DataFrame(todos, columns=[
        "clipe", "tipo", "inicio", "tempo_s", "confirmado_em_s", "queda_altura",
        "altura_final", "tronco_final", "permanencia_s"])
    eventos_df.to_csv(PASTA / "eventos_por_clipe.csv", index=False)

    demo = eventos_df[eventos_df["clipe"] == clipe_demo]
    if demo.empty:
        print(f"\nAVISO: nenhuma queda detectada em '{clipe_demo}'; "
              "data/eventos_video.csv não foi gerado.")
        return
    demo[["inicio", "tipo"]].to_csv(DATA_DIR / "eventos_video.csv", index=False)
    t = float(demo.iloc[0]["tempo_s"])
    print(f"\nClipe da demonstração: {clipe_demo} | queda detectada em {t:.1f} s "
          f"-> data/eventos_video.csv")
    seg = round(t) + ATRASO_SUGERIDO_S
    inicio = INSTANTE_VITAIS - pd.Timedelta(seconds=seg)
    print(f"Roteiro simulado: para os vitais alterarem uns {ATRASO_SUGERIDO_S} s depois da queda "
          f"vista no vídeo, em src/config.py use:")
    print(f"  VITAIS_ALTERAM_NO_CLIPE_S = {seg}   e rode: python -m src.dados.gerar_dados")
    print(f"(o início fictício do clipe passa a ser {inicio:%Y-%m-%d %H:%M:%S}; "
          "atualize o inicio_ficticio no clipes.csv)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clipe-demo", default="queda_01",
                    help="clipe cuja queda alimenta a fusão (padrão: queda_01)")
    main(ap.parse_args().clipe_demo)
