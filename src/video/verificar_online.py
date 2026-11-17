"""Confere, nos clipes reais, se o detector em tempo real acha as mesmas quedas do modo
em lote. Não roda o YOLO: usa os keypoints já extraídos (data/video/*_keypoints.csv)."""
import sys

import pandas as pd

from src.config import DATA_DIR
from src.video.detector_queda import detectar_quedas
from src.video.extrair_pose import info_video
from src.video.online import DetectorQuedaOnline, FeaturesOnline

VIDEOS = DATA_DIR / "videos"
PASTA = DATA_DIR / "video"


def reproduzir(raw: pd.DataFrame, altura_frame: int) -> list[dict]:
    """Passa os quadros um a um pelo mesmo caminho do modo ao vivo."""
    feats, detector, eventos = FeaturesOnline(altura_frame), DetectorQuedaOnline(), []
    for linha in raw.to_dict("records"):
        m = feats.atualizar(linha["tempo_s"], linha)
        e = detector.atualizar(linha["tempo_s"], m["quadril_altura"], m["tronco_angulo"])
        if e:
            eventos.append(e)
    return eventos


def main() -> int:
    arquivos = sorted(PASTA.glob("*_keypoints.csv"))
    if not arquivos:
        print(f"Nenhum *_keypoints.csv em {PASTA}. Rode antes: python -m src.video.extrair_pose")
        return 1
    falhas = 0
    for arq in arquivos:
        nome = arq.name.removesuffix("_keypoints.csv")
        video = VIDEOS / f"{nome}.mp4"
        altura = info_video(video)[1] if video.exists() else 720
        raw = pd.read_csv(arq)
        lote = detectar_quedas(pd.read_csv(PASTA / f"{nome}_features.csv"))
        vivo = reproduzir(raw, altura)
        ok = (len(lote) == len(vivo)
              and all(abs(a["tempo_s"] - b["tempo_s"]) < 0.5 for a, b in zip(lote, vivo)))
        falhas += not ok
        t_lote = [f"{e['tempo_s']:.1f}s" for e in lote] or ["-"]
        t_vivo = [f"{e['tempo_s']:.1f}s" for e in vivo] or ["-"]
        atraso = ", ".join(f"{e['emitido_em_s'] - e['tempo_s']:.1f}s" for e in vivo) or "-"
        print(f"[{'OK' if ok else 'DIVERGE'}] {nome}: em lote {t_lote} | ao vivo {t_vivo} "
              f"| confirmação após o início da queda: {atraso}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
