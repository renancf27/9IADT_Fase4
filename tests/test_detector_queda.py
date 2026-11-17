"""Cenários do detector de queda, com séries SINTÉTICAS parecidas com os gráficos dos clipes."""
import numpy as np
import pandas as pd

from src.video.detector_queda import detectar_quedas

DT = 1 / 30
T = np.arange(0, 60, DT)


def serie(altura_pts, tronco_pts):
    return pd.DataFrame({
        "tempo_s": T,
        "quadril_altura": np.interp(T, *zip(*altura_pts)),
        "tronco_angulo": np.interp(T, *zip(*tronco_pts)),
    })


CASOS = [
    ("queda lenta e controlada (como queda_01)",
     serie([(0, .54), (34.4, .55), (38.5, .19), (60, .19)],
           [(0, 5), (35.2, 10), (36.6, 110), (60, 108)]), 1),
    ("deitar na cama (quadril alto, tronco horizontal)",
     serie([(0, .53), (27, .52), (28, .50), (31, .55), (60, .55)],
           [(0, 5), (29, 8), (31, 80), (60, 80)]), 0),
    ("caminhar e abaixar um pouco (queda de 0,08)",
     serie([(0, .55), (11, .55), (11.7, .47), (14, .52), (60, .52)],
           [(0, 5), (60, 5)]), 0),
    ("agachar rápido (quadril baixo, tronco em pé)",
     serie([(0, .55), (20, .55), (21, .33), (23, .33), (24, .55), (60, .55)],
           [(0, 5), (20, 5), (21, 35), (23, 35), (24, 5), (60, 5)]), 0),
    ("cai e levanta em 1 s (sem permanência)",
     serie([(0, .55), (20, .55), (20.5, .25), (21.5, .25), (22.5, .55), (60, .55)],
           [(0, 5), (20, 5), (20.5, 90), (21.5, 90), (22.5, 5), (60, 5)]), 0),
    ("descida muito lenta até o chão (0,09 em 2 s)",
     serie([(0, .55), (10, .55), (20, .15), (60, .15)],
           [(0, 5), (10, 5), (20, 90), (60, 90)]), 0),
    ("duas quedas separadas por 30 s",
     serie([(0, .54), (10, .54), (12, .20), (20, .20), (22, .54), (40, .54), (42, .20), (60, .20)],
           [(0, 5), (10, 5), (12, 90), (20, 90), (22, 5), (40, 5), (42, 90), (60, 90)]), 2),
]

if __name__ == "__main__":
    falhas = 0
    for nome, f, esperado in CASOS:
        eventos = detectar_quedas(f)
        ok = len(eventos) == esperado
        falhas += not ok
        inst = [e["tempo_s"] for e in eventos]
        print(f"[{'OK' if ok else 'FALHA'}] {nome}: {len(eventos)} queda(s) {inst}")
    print(f"\n{len(CASOS) - falhas}/{len(CASOS)} cenários passaram")
    raise SystemExit(1 if falhas else 0)