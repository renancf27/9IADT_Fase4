import numpy as np
import pandas as pd

NOMES_KP = ["nariz", "olho_e", "olho_d", "orelha_e", "orelha_d", "ombro_e", "ombro_d",
            "cotovelo_e", "cotovelo_d", "pulso_e", "pulso_d", "quadril_e", "quadril_d",
            "joelho_e", "joelho_d", "tornozelo_e", "tornozelo_d"]
CONF_MIN = 0.3          # abaixo disso o ponto é ignorado
LACUNA_MAX_S = 0.5      # lacunas de detecção até este tamanho são interpoladas


def colunas_keypoints() -> list[str]:
    return [f"{n}_{c}" for n in NOMES_KP for c in ("x", "y", "c")]


def _ponto_medio(raw: pd.DataFrame, a: str, b: str):
    """Média de dois pontos (ex.: ombro esquerdo e direito), só com confiança suficiente."""
    xs, ys = [], []
    for nome in (a, b):
        ok = raw[f"{nome}_c"] >= CONF_MIN
        xs.append(raw[f"{nome}_x"].where(ok))
        ys.append(raw[f"{nome}_y"].where(ok))
    return pd.concat(xs, axis=1).mean(axis=1), pd.concat(ys, axis=1).mean(axis=1)


def calcular_features(raw: pd.DataFrame, altura_frame: int, fps: float) -> pd.DataFrame:
    """Transforma os keypoints brutos em medidas por quadro.

    quadril_altura : 0 = base do quadro, 1 = topo (sobe e desce com o quadril)
    vel_descida    : alturas-de-quadro por segundo; positivo = quadril descendo
    tronco_angulo  : graus em relação à vertical (0 = em pé, 90 = deitado)
    box_razao      : largura / altura da caixa da pessoa (> 1 = corpo horizontal)
    """
    ombro_x, ombro_y = _ponto_medio(raw, "ombro_e", "ombro_d")
    quad_x, quad_y = _ponto_medio(raw, "quadril_e", "quadril_d")
    largura = raw["box_x2"] - raw["box_x1"]
    altura = raw["box_y2"] - raw["box_y1"]

    f = pd.DataFrame({
        "quadro": raw["quadro"].values,
        "tempo_s": raw["tempo_s"].values,
        "quadril_altura": (1 - quad_y / altura_frame).values,
        "tronco_angulo": np.degrees(np.arctan2(np.abs(ombro_x - quad_x),
                                               -(ombro_y - quad_y))).values,
        "box_razao": (largura / altura).values,
    })

    passo = float(np.median(np.diff(f["tempo_s"]))) if len(f) > 1 else 1 / fps
    limite = max(1, int(LACUNA_MAX_S / passo))
    janela = max(3, int(round(0.2 / passo)) | 1)  # ~0,2 s, sempre ímpar
    for col in ("quadril_altura", "tronco_angulo", "box_razao"):
        s = f[col].interpolate(limit=limite, limit_area="inside")
        f[col] = s.rolling(janela, center=True, min_periods=1).median()

    f["vel_descida"] = -np.gradient(f["quadril_altura"].ffill().bfill().values,
                                    f["tempo_s"].values)
    f.loc[f["quadril_altura"].isna(), "vel_descida"] = np.nan
    f["vel_descida"] = f["vel_descida"].rolling(janela, center=True, min_periods=1).median()
    return f


def plotar(f: pd.DataFrame, titulo: str, caminho) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    painéis = [("quadril_altura", "Altura do quadril"),
               ("vel_descida", "Velocidade de descida"),
               ("tronco_angulo", "Ângulo do tronco (°)"),
               ("box_razao", "Largura / altura da caixa")]
    fig, eixos = plt.subplots(len(painéis), 1, figsize=(10, 8), sharex=True)
    for ax, (col, rotulo) in zip(eixos, painéis):
        ax.plot(f["tempo_s"], f[col], lw=1.2)
        ax.set_ylabel(rotulo, fontsize=9)
        ax.grid(alpha=0.3)
    eixos[-1].set_xlabel("tempo (s)")
    fig.suptitle(titulo)
    fig.tight_layout()
    fig.savefig(caminho, dpi=110)
    plt.close(fig)


def resumo(f: pd.DataFrame) -> dict:
    """Números para comparar clipes de queda e normais.

    Olha o instante de maior descida do quadril e compara 3 s antes e 3 s depois.
    """
    v = f["vel_descida"]
    if not v.notna().any():
        return {}
    pico_t = float(f.loc[v.idxmax(), "tempo_s"])
    antes = f[(f["tempo_s"] >= pico_t - 3) & (f["tempo_s"] < pico_t)]
    depois = f[(f["tempo_s"] > pico_t) & (f["tempo_s"] <= pico_t + 3)]
    return {
        "pico_descida": float(v.max()),
        "pico_descida_em_s": pico_t,
        "quadril_antes": float(antes["quadril_altura"].median()),
        "quadril_depois": float(depois["quadril_altura"].median()),
        "tronco_depois": float(depois["tronco_angulo"].median()),
        "box_razao_depois": float(depois["box_razao"].median()),
    }