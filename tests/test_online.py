"""O modo em tempo real deve achar as mesmas quedas do modo em lote."""
import numpy as np
import pandas as pd

from src.video.detector_queda import detectar_quedas
from src.video.features import NOMES_KP, calcular_features
from src.video.online import DetectorQuedaOnline, FeaturesOnline
from tests.test_detector_queda import CASOS

FPS, W, H = 30, 1280, 720


def rodar_detector_online(t, alt, tronco):
    det, eventos = DetectorQuedaOnline(), []
    for ti, a, g in zip(t, alt, tronco):
        e = det.atualizar(float(ti), float(a), float(g))
        if e:
            eventos.append(e)
    return eventos


def teste_detector_igual_ao_modo_em_lote():
    resultados = []
    for nome, f, esperado in CASOS:
        lote = detectar_quedas(f)
        vivo = rodar_detector_online(f["tempo_s"], f["quadril_altura"], f["tronco_angulo"])
        ok = (len(lote) == len(vivo) == esperado
              and all(abs(a["tempo_s"] - b["tempo_s"]) < 0.1 for a, b in zip(lote, vivo)))
        resultados.append((f"detector online == em lote: {nome}", ok))
    return resultados


def keypoints_sinteticos(alt_pts, ang_pts, duracao=45):
    t = np.arange(0, duracao, 1 / FPS)
    alt, ang = np.interp(t, *zip(*alt_pts)), np.radians(np.interp(t, *zip(*ang_pts)))
    linhas = []
    for i, ti in enumerate(t):
        u = np.array([np.sin(ang[i]), -np.cos(ang[i])])
        quad = np.array([500.0, (1 - alt[i]) * H])
        P = {"quadril": quad, "ombro": quad + 150 * u}
        P["nariz"] = P["olho"] = P["orelha"] = P["ombro"] + 70 * u
        P["cotovelo"], P["pulso"] = P["ombro"] - 70 * u, P["ombro"] - 130 * u
        P["joelho"], P["tornozelo"] = quad - 110 * u, quad - 220 * u
        r, pts = {"quadro": i, "tempo_s": ti, "detectou": True}, []
        for n in NOMES_KP:
            p = P[n.split("_")[0]] + (8 if n.endswith("_e") else -8 if n.endswith("_d") else 0)
            r[f"{n}_x"], r[f"{n}_y"], r[f"{n}_c"] = float(p[0]), float(p[1]), 0.9
            pts.append(p)
        pts = np.array(pts)
        r.update(box_x1=pts[:, 0].min() - 30, box_y1=pts[:, 1].min() - 30,
                 box_x2=pts[:, 0].max() + 30, box_y2=pts[:, 1].max() + 30, box_conf=0.9)
        linhas.append(r)
    return pd.DataFrame(linhas)


def teste_medidas_e_quedas_a_partir_dos_keypoints():
    raw = keypoints_sinteticos([(0, .54), (34.4, .55), (38.5, .19), (45, .19)],
                               [(0, 77), (10, 77), (12, 3), (35.2, 8), (36.6, 110), (45, 108)])
    # falhas de detecção: 6 quadros (0,2 s) e depois 30 quadros (1 s)
    cols = [c for c in raw.columns if c.endswith(("_x", "_y", "_c"))]
    raw.loc[300:305, cols] = np.nan
    raw.loc[300:305, "detectou"] = False
    raw.loc[600:629, cols] = np.nan
    raw.loc[600:629, "detectou"] = False

    lote_f = calcular_features(raw, H, FPS)
    feats, det, vivo_f, eventos = FeaturesOnline(H), DetectorQuedaOnline(), [], []
    for linha in raw.to_dict("records"):
        m = feats.atualizar(linha["tempo_s"], linha)
        vivo_f.append(m["quadril_altura"])
        e = det.atualizar(linha["tempo_s"], m["quadril_altura"], m["tronco_angulo"])
        if e:
            eventos.append(e)
    dif = np.nanmax(np.abs(np.array(vivo_f) - lote_f["quadril_altura"].to_numpy()))
    lote = detectar_quedas(lote_f)
    return [
        (f"medidas online parecidas com as em lote (diferença máxima {dif:.3f})", dif < 0.06),
        ("queda achada nos dois modos, com instantes próximos (< 0,5 s)",
         len(lote) == len(eventos) == 1 and abs(lote[0]["tempo_s"] - eventos[0]["tempo_s"]) < 0.5),
        (f"queda confirmada {eventos[0]['emitido_em_s'] - eventos[0]['tempo_s']:.1f} s depois do início",
         bool(eventos) and 2 < eventos[0]["emitido_em_s"] - eventos[0]["tempo_s"] < 8),
    ]


def teste_mensagens_de_estado():
    """O detector explica em texto cada etapa, para aparecer na tela durante a demonstração."""
    nome, f, _ = CASOS[0]  # queda lenta e controlada
    det, msgs, evento = DetectorQuedaOnline(), [], None
    for ti, a, g in zip(f["tempo_s"], f["quadril_altura"], f["tronco_angulo"]):
        e = det.atualizar(float(ti), float(a), float(g))
        if det.mudanca:
            msgs.append(det.mudanca)
        evento = evento or e
    ordem = (len(msgs) == 2 and msgs[0].startswith("descida rápida")
             and msgs[1].startswith("quadril no nível do chão"))

    det2, msgs2 = DetectorQuedaOnline(), []   # agachar: desce rápido mas o tronco não deita
    nome2, f2, _ = CASOS[3]
    for ti, a, g in zip(f2["tempo_s"], f2["quadril_altura"], f2["tronco_angulo"]):
        det2.atualizar(float(ti), float(a), float(g))
        if det2.mudanca:
            msgs2.append(det2.mudanca)
    return [("mensagens de estado na ordem: descida -> chão -> confirmação", ordem and evento is not None),
            ("agachar gera 'descida' e depois 'descartada', sem confirmar queda",
             len(msgs2) == 2 and msgs2[1].endswith("descartada"))]


if __name__ == "__main__":
    resultados = (teste_detector_igual_ao_modo_em_lote()
                  + teste_medidas_e_quedas_a_partir_dos_keypoints()
                  + teste_mensagens_de_estado())
    for nome, ok in resultados:
        print(f"[{'OK' if ok else 'FALHA'}] {nome}")
    falhas = sum(not ok for _, ok in resultados)
    print(f"\n{len(resultados) - falhas}/{len(resultados)} verificações passaram")
    raise SystemExit(1 if falhas else 0)
