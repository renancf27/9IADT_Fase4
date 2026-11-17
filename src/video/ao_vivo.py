import argparse
import os
import sys
import time
from collections import deque

import cv2
import numpy as np
import pandas as pd

from src.config import (DATA_DIR, INICIO_VIDEO, QUEDA_DELTA_ALTURA, QUEDA_JANELA_S,
                        QUEDA_PERMANENCIA_S)
from src.fusao.notificacao import notificar, reiniciar_log
from src.fusao.sistema import Sistema
from src.fusao.tempo_real import montar_feed, processar_grupos
from src.video.extrair_pose import MODELO, _numpy
from src.video.features import NOMES_KP
from src.video.online import DetectorQuedaOnline, FeaturesOnline
from src.video.relatorio import _texto, desenhar_esqueleto

VIDEOS = DATA_DIR / "videos"
JANELA = "Monitoramento do leito"
COR_ALERTA = {"PREVENTIVO": (0, 200, 255), "MÉDIO": (0, 140, 255), "ALTO": (0, 0, 230)}
NOME_ALERTA = {"PREVENTIVO": "PREVENTIVO", "MÉDIO": "MEDIO", "ALTO": "ALTO"}  # sem acento no desenho
BRANCO, VERDE, LARANJA, VERMELHO, AZUL = ((255, 255, 255), (80, 220, 80), (0, 165, 255),
                                          (70, 70, 255), (255, 220, 120))  # BGR


def _tem_tela() -> bool:
    """No Linux sem DISPLAY/WAYLAND_DISPLAY o OpenCV derruba o programa ao abrir a janela."""
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def _linha_do_resultado(r) -> dict:
    """Converte o resultado do YOLO (um quadro) no formato usado pelas medidas."""
    linha = {"detectou": False}
    if r.boxes is not None and len(r.boxes) > 0 and r.keypoints is not None:
        xyxy, confs = _numpy(r.boxes.xyxy), _numpy(r.boxes.conf)
        k = int(np.argmax((xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])))
        xy = _numpy(r.keypoints.xy)[k]
        kc = (_numpy(r.keypoints.conf)[k] if r.keypoints.conf is not None
              else np.ones(len(xy)))
        linha.update(detectou=True, box_x1=float(xyxy[k, 0]), box_y1=float(xyxy[k, 1]),
                     box_x2=float(xyxy[k, 2]), box_y2=float(xyxy[k, 3]),
                     box_conf=float(confs[k]))
        for j, nome in enumerate(NOMES_KP):
            linha[f"{nome}_x"], linha[f"{nome}_y"], linha[f"{nome}_c"] = (
                float(xy[j, 0]), float(xy[j, 1]), float(kc[j]))
    return linha


def _num(x: float, fmt: str) -> str:
    return "-" if x != x else format(x, fmt)  # NaN vira "-"


def _painel(img: np.ndarray, linhas: list[tuple[str, tuple]]) -> None:
    """Fundo escuro semitransparente com as linhas de texto (texto, cor)."""
    passo = 28
    h, w = 14 + passo * len(linhas), min(700, img.shape[1])
    original = img[0:h, 0:w].copy()
    cv2.rectangle(img, (0, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(img[0:h, 0:w], 0.55, original, 0.45, 0, img[0:h, 0:w])
    for i, (txt, cor) in enumerate(linhas):
        cv2.putText(img, txt, (14, 32 + i * passo), cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                    cor, 2, cv2.LINE_AA)


def _estado_texto(det: DetectorQuedaOnline, t: float, queda_ate: float):
    if t <= queda_ate:
        return "QUEDA CONFIRMADA", VERMELHO
    if det.estado == "candidato":
        return "DESCIDA RAPIDA: verificando se chega ao chao", LARANJA
    if det.estado == "no_chao":
        return (f"NO CHAO: confirmando {det.permanencia(t):.1f} / "
                f"{QUEDA_PERMANENCIA_S:.1f} s", LARANJA)
    return "MONITORANDO", VERDE


def _desenhar(img, linha, agora, t, info, det, queda_ate, resumo_queda, ultimo_alerta):
    desenhar_esqueleto(img, linha)
    estado, cor = _estado_texto(det, t, queda_ate)
    _painel(img, [
        (f"{agora:%H:%M:%S}   (clipe {t:5.1f} s)", BRANCO),
        ("ANALISE AO VIVO - YOLOv8-pose, quadro a quadro", AZUL),
        (f"quadro {info['idx']}/{info['n']} | {info['ms']:.0f} ms/quadro | "
         f"{info['fps']} | atraso {info['atraso']}", BRANCO),
        (f"quadril {_num(info['altura'], '.2f')} | tronco {_num(info['tronco'], '.0f')} graus", BRANCO),
        (f"descida em {QUEDA_JANELA_S:.0f} s: {det.queda_atual:.2f}  "
         f"(candidata se >= {QUEDA_DELTA_ALTURA})", BRANCO),
        (f"ESTADO: {estado}", cor),
    ])
    h, w = img.shape[:2]
    if t <= queda_ate:
        cv2.rectangle(img, (0, h - 110), (w, h), (0, 0, 200), -1)
        _texto(img, "QUEDA DETECTADA AO VIVO", (20, h - 62), escala=1.3)
        _texto(img, resumo_queda, (20, h - 20), escala=0.8)
    if ultimo_alerta and 0 <= (agora - ultimo_alerta["timestamp"]).total_seconds() <= 10:
        nivel = ultimo_alerta["severidade"]
        cv2.rectangle(img, (w - 360, 10), (w - 10, 70), COR_ALERTA[nivel], -1)
        _texto(img, f"ALERTA {NOME_ALERTA[nivel]}", (w - 345, 52), escala=1.0)


def executar(clipe: str = "queda_01", janela: bool = True, tempo_real: bool = True,
             velocidade_pre: float = 1200.0, velocidade_pos: float = 60.0,
             modelo=None, notificador=notificar, silencioso: bool = False) -> pd.DataFrame:
    """Demonstração: o vídeo toca, o YOLO roda a cada quadro, a queda é detectada na hora
    e entra na fusão junto com os vitais, as notas e as prescrições."""
    dizer = (lambda *a: None) if silencioso else print
    video = VIDEOS / f"{clipe}.mp4"
    if not video.exists():
        raise FileNotFoundError(f"vídeo não encontrado: {video}")
    if notificador is notificar:
        reiniciar_log()

    dizer("=== DEMONSTRAÇÃO AO VIVO ===")
    dizer("AO VIVO (calculado agora): pose do paciente (YOLOv8-pose) e detecção da queda, "
          "quadro a quadro.")
    dizer("SIMULADO (arquivos): sinais vitais, notas de enfermagem e prescrições. O relógio "
          "fictício liga o vídeo a esses dados.")

    sistema = Sistema(notificador, dizer)
    feed = montar_feed(incluir_video=False)
    antes = [x for x in feed if x[0] < INICIO_VIDEO]
    depois = [x for x in feed if x[0] >= INICIO_VIDEO]

    dizer(f"--- Antes do vídeo (até {INICIO_VIDEO:%H:%M:%S}) ---")
    processar_grupos(antes, sistema, velocidade_pre, espera_max_s=1.0)

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    altura_frame = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_quadros = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if modelo is None:
        from ultralytics import YOLO
        dizer(f"Carregando o modelo {MODELO}...")
        modelo = YOLO(MODELO)
    ok, quadro0 = cap.read()
    modelo(quadro0, verbose=False)  # aquecimento: a primeira inferência é mais lenta
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    dizer(f"--- Vídeo {clipe} (relógio fictício a partir de {INICIO_VIDEO:%H:%M:%S}) ---")
    feats, detector = FeaturesOnline(altura_frame), DetectorQuedaOnline()
    ponteiro, idx, analisados, queda_ate, resumo_queda = 0, 0, 0, -1.0, ""
    quedas_detectadas: list[dict] = []
    ms_recentes: deque = deque(maxlen=30)
    t0 = time.perf_counter()
    mostrar = janela and _tem_tela()
    if janela and not mostrar:
        dizer("(sem ambiente gráfico: seguindo só com o terminal)")
    while True:
        if tempo_real:
            decorrido = time.perf_counter() - t0
            if idx / fps > decorrido:                      # adiantado: espera o relógio
                time.sleep(idx / fps - decorrido)
            alvo = int((time.perf_counter() - t0) * fps)   # atrasado: pula quadros
            while idx < alvo:
                if not cap.grab():
                    break
                idx += 1
        ok, quadro = cap.read()
        if not ok:
            break
        t = idx / fps
        agora = INICIO_VIDEO + pd.Timedelta(seconds=t)

        # vitais, notas e prescrições que já "chegaram" neste instante
        while ponteiro < len(depois) and depois[ponteiro][0] <= agora:
            ts, gatilho = depois[ponteiro][0], False
            while ponteiro < len(depois) and depois[ponteiro][0] == ts:
                gatilho |= sistema.receber(ts, depois[ponteiro][1], depois[ponteiro][2])
                ponteiro += 1
            if gatilho:
                sistema.avaliar(ts)

        # pose -> medidas -> detector de queda (tudo calculado agora, neste quadro)
        inicio_inf = time.perf_counter()
        linha = _linha_do_resultado(modelo(quadro, verbose=False)[0])
        ms_recentes.append((time.perf_counter() - inicio_inf) * 1000)
        analisados += 1
        medidas = feats.atualizar(t, linha)
        evento = detector.atualizar(t, medidas["quadril_altura"], medidas["tronco_angulo"])
        if detector.mudanca:
            dizer(f"{agora:%H:%M:%S} [VÍDEO] {detector.mudanca}   (clipe {t:.1f} s)")
        if evento:
            lat = evento["emitido_em_s"] - evento["tempo_s"]
            resumo_queda = (f"inicio {evento['tempo_s']:.1f} s | confirmada {evento['emitido_em_s']:.1f} s "
                            f"(+{lat:.1f} s)")
            dizer(f"{agora:%H:%M:%S} [VÍDEO] QUEDA CONFIRMADA AO VIVO: {resumo_queda}")
            quedas_detectadas.append(evento)
            if sistema.receber(agora, "video", {"tipo": "queda"}):
                sistema.avaliar(agora)
            queda_ate = t + 6.0

        if mostrar:
            decorrido = time.perf_counter() - t0
            info = {
                "idx": idx, "n": n_quadros, "ms": float(np.mean(ms_recentes)),
                "fps": f"{analisados / max(decorrido, 1e-6):.0f} fps" if tempo_real else "-",
                "atraso": f"{max(decorrido - t, 0):.2f} s" if tempo_real else "-",
                "altura": medidas["quadril_altura"], "tronco": medidas["tronco_angulo"],
            }
            _desenhar(quadro, linha, agora, t, info, detector, queda_ate, resumo_queda,
                      sistema.alertas[-1] if sistema.alertas else None)
            try:
                cv2.imshow(JANELA, quadro)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            except cv2.error:
                dizer("(sem janela gráfica neste ambiente; seguindo só com o terminal)")
                mostrar = False
        idx += 1
    cap.release()

    if tempo_real:
        dizer(f"\nQuadros analisados: {analisados} de {idx} "
              f"({100 * analisados / max(idx, 1):.0f}%) | "
              f"{np.mean(ms_recentes) if ms_recentes else 0:.0f} ms por quadro")
    dizer(f"Quedas detectadas ao vivo neste clipe: {len(quedas_detectadas)}")
    dizer("--- Depois do vídeo ---")
    processar_grupos(depois[ponteiro:], sistema, velocidade_pos)
    if mostrar:
        dizer("Fim. Aperte qualquer tecla na janela do vídeo para fechar.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return sistema.tabela_alertas()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clipe", default="queda_01", help="clipe da demonstração")
    ap.add_argument("--sem-janela", action="store_true", help="só terminal, sem a janela do vídeo")
    ap.add_argument("--velocidade-pre", type=float, default=1200.0,
                    help="velocidade da parte anterior ao vídeo (segundos simulados por segundo)")
    ap.add_argument("--velocidade-pos", type=float, default=60.0,
                    help="velocidade da parte posterior ao vídeo")
    a = ap.parse_args()
    executar(a.clipe, janela=not a.sem_janela, velocidade_pre=a.velocidade_pre,
             velocidade_pos=a.velocidade_pos)
