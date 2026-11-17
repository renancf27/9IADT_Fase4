import argparse
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from src.config import DATA_DIR, RAIZ
from src.video.features import (NOMES_KP, calcular_features, colunas_keypoints,
                                plotar, resumo)

VIDEOS = DATA_DIR / "videos"
SAIDA = DATA_DIR / "video"
RELATORIOS = RAIZ / "reports" / "video"
MODELO = "yolov8n-pose.pt"


def _numpy(x) -> np.ndarray:
    return x.cpu().numpy() if hasattr(x, "cpu") else np.asarray(x)


def info_video(caminho: Path) -> tuple[float, int, int]:
    cap = cv2.VideoCapture(str(caminho))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    altura = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return fps, altura, n


def extrair_keypoints(caminho: Path, modelo, fps: float, stride: int = 1) -> pd.DataFrame:
    """Roda o YOLOv8-pose quadro a quadro e guarda os keypoints da pessoa maior."""
    colunas = (["quadro", "tempo_s", "detectou", "box_x1", "box_y1", "box_x2",
                "box_y2", "box_conf"] + colunas_keypoints())
    linhas = []
    for i, r in enumerate(modelo(str(caminho), stream=True, verbose=False,
                                 vid_stride=stride)):
        quadro = i * stride
        linha = dict.fromkeys(colunas, np.nan)
        linha.update(quadro=quadro, tempo_s=quadro / fps, detectou=False)
        if r.boxes is not None and len(r.boxes) > 0 and r.keypoints is not None:
            xyxy, confs = _numpy(r.boxes.xyxy), _numpy(r.boxes.conf)
            areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
            k = int(np.argmax(areas))  # a maior pessoa do quadro
            xy = _numpy(r.keypoints.xy)[k]
            kc = (_numpy(r.keypoints.conf)[k] if r.keypoints.conf is not None
                  else np.ones(len(xy)))
            linha.update(detectou=True, box_x1=float(xyxy[k, 0]), box_y1=float(xyxy[k, 1]),
                         box_x2=float(xyxy[k, 2]), box_y2=float(xyxy[k, 3]),
                         box_conf=float(confs[k]))
            for j, nome in enumerate(NOMES_KP):
                linha[f"{nome}_x"] = float(xy[j, 0])
                linha[f"{nome}_y"] = float(xy[j, 1])
                linha[f"{nome}_c"] = float(kc[j])
        linhas.append(linha)
    return pd.DataFrame(linhas, columns=colunas)


def main(videos: list[Path] | None = None, stride: int = 1, refazer: bool = False,
         modelo=None) -> None:
    videos = videos or sorted(VIDEOS.glob("*.mp4"))
    if not videos:
        print(f"Nenhum .mp4 encontrado em {VIDEOS}")
        return
    SAIDA.mkdir(parents=True, exist_ok=True)
    RELATORIOS.mkdir(parents=True, exist_ok=True)

    tabela = []
    for caminho in videos:
        nome = caminho.stem
        fps, altura, n_quadros = info_video(caminho)
        cache = SAIDA / f"{nome}_keypoints.csv"

        if cache.exists() and not refazer:
            raw = pd.read_csv(cache)
            print(f"{nome}: keypoints já extraídos (use --refazer para repetir)")
        else:
            if modelo is None:
                from ultralytics import YOLO  # só carrega se for preciso
                modelo = YOLO(MODELO)
            print(f"{nome}: {n_quadros} quadros a {fps:.0f} fps, extraindo pose...")
            t0 = time.time()
            raw = extrair_keypoints(caminho, modelo, fps, stride)
            seg = time.time() - t0
            print(f"  concluído em {seg:.0f} s ({len(raw) / max(seg, 1e-6):.1f} quadros/s)")
            raw.to_csv(cache, index=False)

        feat = calcular_features(raw, altura, fps)
        feat.to_csv(SAIDA / f"{nome}_features.csv", index=False)
        plotar(feat, nome, RELATORIOS / f"{nome}.png")

        r = resumo(feat)
        r.update(video=nome, duracao_s=round(float(raw["tempo_s"].max()), 1),
                 deteccao_pct=round(100 * float(raw["detectou"].mean()), 1))
        tabela.append(r)

    print("\nvídeo | dur(s) | detecção | pico descida (em s) | quadril antes→depois "
          "| tronco depois | caixa l/a depois")
    for r in tabela:
        if "pico_descida" not in r:
            print(f"{r['video']} | sem dados")
            continue
        print(f"{r['video']} | {r['duracao_s']} | {r['deteccao_pct']}% | "
              f"{r['pico_descida']:.2f} (em {r['pico_descida_em_s']:.1f}) | "
              f"{r['quadril_antes']:.2f}→{r['quadril_depois']:.2f} | "
              f"{r['tronco_depois']:.0f}° | {r['box_razao_depois']:.2f}")
    print(f"\nGráficos em {RELATORIOS}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="*", type=Path,
                    help="arquivos .mp4 (padrão: todos de data/videos)")
    ap.add_argument("--stride", type=int, default=1,
                    help="processa 1 a cada N quadros (2 = mais rápido)")
    ap.add_argument("--refazer", action="store_true",
                    help="ignora os keypoints guardados e roda o YOLO de novo")
    a = ap.parse_args()
    main(a.videos or None, a.stride, a.refazer)