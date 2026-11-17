import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from src.config import (DATA_DIR, INICIO_VIDEO, QUEDA_CONFIRMACAO_S, QUEDA_DELTA_ALTURA,
                        QUEDA_JANELA_S, QUEDA_LIMIAR_CHAO, QUEDA_PERMANENCIA_S,
                        QUEDA_TRONCO_MIN, RAIZ)
from src.video.features import CONF_MIN, NOMES_KP, resumo

VIDEOS = DATA_DIR / "videos"
PASTA = DATA_DIR / "video"
RELATORIOS = RAIZ / "reports" / "video"
ANOTADOS = PASTA / "anotados"

PARAMETROS = {
    "queda_delta_altura": QUEDA_DELTA_ALTURA, "queda_janela_s": QUEDA_JANELA_S,
    "limiar_chao": QUEDA_LIMIAR_CHAO, "tronco_min_graus": QUEDA_TRONCO_MIN,
    "confirmacao_s": QUEDA_CONFIRMACAO_S, "permanencia_min_s": QUEDA_PERMANENCIA_S,
}
# Ligações do esqueleto (índices na ordem de NOMES_KP)
OSSOS = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12),
         (11, 13), (13, 15), (12, 14), (14, 16), (0, 1), (0, 2), (1, 3), (2, 4)]


# ---------- desenho ----------
def desenhar_esqueleto(img: np.ndarray, linha: dict | None) -> None:
    if not linha or not linha.get("detectou"):
        return
    pts = {}
    for j, nome in enumerate(NOMES_KP):
        if linha[f"{nome}_c"] >= CONF_MIN:
            pts[j] = (int(linha[f"{nome}_x"]), int(linha[f"{nome}_y"]))
    for a, b in OSSOS:
        if a in pts and b in pts:
            cv2.line(img, pts[a], pts[b], (0, 220, 0), 3, cv2.LINE_AA)
    for p in pts.values():
        cv2.circle(img, p, 5, (0, 120, 255), -1, cv2.LINE_AA)


def _texto(img, txt, pos, cor=(255, 255, 255), escala=0.9):
    cv2.putText(img, txt, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, txt, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, cor, 2, cv2.LINE_AA)


def _linhas_por_quadro(raw: pd.DataFrame) -> dict[int, dict]:
    return {int(r["quadro"]): r for r in raw.to_dict("records")}


def _altura_no_quadro(feat: pd.DataFrame, quadro: int) -> float:
    i = (feat["quadro"] - quadro).abs().idxmin()
    return float(feat.loc[i, "quadril_altura"])


# ---------- quadros-chave ----------
def salvar_quadros_chave(video: Path, nome: str, ev: dict, k: int, raw, feat, fps: float):
    """Três imagens por queda: antes, durante e depois, com o esqueleto desenhado."""
    pasta = RELATORIOS / "quadros"
    pasta.mkdir(parents=True, exist_ok=True)
    por_quadro = _linhas_por_quadro(raw)
    tempos = {"antes": max(0.0, ev["tempo_s"] - 1.5),
              "durante": (ev["tempo_s"] + ev["confirmado_em_s"]) / 2,
              "depois": ev["confirmado_em_s"] + 2.0}
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    caminhos = {}
    for rotulo, t in tempos.items():
        idx = min(int(round(t * fps)), n - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, img = cap.read()
        if not ok:
            continue
        desenhar_esqueleto(img, por_quadro.get(idx))
        _texto(img, f"{rotulo.upper()}  t={idx / fps:.1f}s", (20, 40))
        _texto(img, f"altura do quadril: {_altura_no_quadro(feat, idx):.2f}", (20, 80))
        arq = pasta / f"{nome}_queda{k}_{rotulo}.jpg"
        cv2.imwrite(str(arq), img)
        caminhos[rotulo] = f"quadros/{arq.name}"
    cap.release()
    return caminhos


# ---------- vídeo anotado (para a demonstração) ----------
def anotar_video(video: Path, nome: str, eventos: list[dict], raw, feat) -> Path:
    ANOTADOS.mkdir(parents=True, exist_ok=True)
    saida = ANOTADOS / f"{nome}_anotado.mp4"
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    larg, alt = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    escritor = cv2.VideoWriter(str(saida), cv2.VideoWriter_fourcc(*"mp4v"), fps, (larg, alt))
    por_quadro = _linhas_por_quadro(raw)
    idx = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        t = idx / fps
        desenhar_esqueleto(img, por_quadro.get(idx))
        relogio = INICIO_VIDEO + pd.Timedelta(seconds=t)
        _texto(img, f"{relogio:%H:%M:%S}", (20, 40))
        _texto(img, f"quadril: {_altura_no_quadro(feat, idx):.2f}", (20, 80))
        for ev in eventos:
            if ev["tempo_s"] <= t <= ev["tempo_s"] + 4.0:
                cv2.rectangle(img, (0, alt - 90), (larg, alt), (0, 0, 200), -1)
                _texto(img, "QUEDA DETECTADA", (20, alt - 30), escala=1.4)
        escritor.write(img)
        idx += 1
    cap.release()
    escritor.release()
    return saida


# ---------- relatório ----------
def esperado_do_clipe(nome: str) -> int:
    """Usa data/videos/clipes.csv (coluna evento); sem ele, o prefixo do nome."""
    caminho = VIDEOS / "clipes.csv"
    if caminho.exists():
        c = pd.read_csv(caminho)
        linha = c[c["arquivo"].str.removesuffix(".mp4") == nome]
        if len(linha):
            return 1 if str(linha.iloc[0]["evento"]).strip().lower() == "queda" else 0
    return 1 if nome.startswith("queda") else 0


def conclusao(eventos: list[dict]) -> str:
    if not eventos:
        return "Nenhum desvio detectado: o movimento ficou dentro do padrão esperado."
    partes = [f"queda às {e['inicio_ficticio'][11:]} ({e['tempo_s']:.1f} s do clipe), "
              f"quadril no chão ({e['altura_final']:.2f}) por {e['permanencia_s']:.0f} s"
              for e in eventos]
    n = len(eventos)
    return (f"{n} desvio detectado: " if n == 1 else f"{n} desvios detectados: ") \
        + "; ".join(partes) + "."


def escrever_markdown(rel: dict, caminho: Path) -> None:
    L = [f"# Relatório de vídeo: {rel['clipe']}", "",
         f"- Arquivo: `{rel['arquivo']}` ({rel['resolucao']}, {rel['fps']:.0f} fps, "
         f"{rel['duracao_s']:.1f} s)",
         f"- Pessoa detectada em {rel['deteccao_pessoa_pct']:.1f}% dos quadros", "",
         f"**Conclusão:** {rel['conclusao']}", ""]
    if rel["eventos"]:
        L += ["## Eventos", "",
              "| Tipo | Instante no clipe | Horário fictício | Queda do quadril em 2 s | "
              "Altura final | Tronco | Permanência no chão |",
              "|---|---|---|---|---|---|---|"]
        for e in rel["eventos"]:
            L.append(f"| {e['tipo']} | {e['tempo_s']:.1f} s | {e['inicio_ficticio']} | "
                     f"{e['queda_altura']:.2f} | {e['altura_final']:.2f} | "
                     f"{e['tronco_final']:.0f}° | {e['permanencia_s']:.0f} s |")
        for k, e in enumerate(rel["eventos"], 1):
            if e.get("quadros"):
                L += ["", f"### Quadros da queda {k}", ""]
                for rotulo in ("antes", "durante", "depois"):
                    if rotulo in e["quadros"]:
                        L.append(f"![{rotulo}]({e['quadros'][rotulo]})")
    L += ["", "## Medidas ao longo do clipe", "", f"![gráfico]({rel['clipe']}.png)", "",
          "## Parâmetros da regra", ""]
    L += [f"- `{k}`: {v}" for k, v in rel["parametros"].items()]
    caminho.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(anotar: bool = False) -> None:
    arquivos = sorted(PASTA.glob("*_features.csv"))
    if not arquivos:
        print(f"Nenhum *_features.csv em {PASTA}. Rode antes o extrator e o detector.")
        return
    RELATORIOS.mkdir(parents=True, exist_ok=True)
    ev_todos = pd.read_csv(PASTA / "eventos_por_clipe.csv") \
        if (PASTA / "eventos_por_clipe.csv").exists() else pd.DataFrame(columns=["clipe"])

    avaliacao = []
    for arq in arquivos:
        nome = arq.name.removesuffix("_features.csv")
        feat = pd.read_csv(arq)
        cache_kp = PASTA / f"{nome}_keypoints.csv"
        raw = pd.read_csv(cache_kp) if cache_kp.exists() else None
        video = VIDEOS / f"{nome}.mp4"

        info = {"fps": 30.0, "resolucao": "?", "duracao_s": float(feat["tempo_s"].max())}
        if video.exists():
            cap = cv2.VideoCapture(str(video))
            info["fps"] = cap.get(cv2.CAP_PROP_FPS) or 30.0
            info["resolucao"] = (f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
                                 f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            cap.release()

        eventos = []
        for k, e in enumerate(ev_todos[ev_todos["clipe"] == nome].to_dict("records"), 1):
            ev = {c: (float(e[c]) if c not in ("clipe", "tipo", "inicio") else e[c])
                  for c in e}
            ev["inicio_ficticio"] = f"{INICIO_VIDEO + pd.Timedelta(seconds=round(ev['tempo_s'])):%Y-%m-%d %H:%M:%S}"
            ev.pop("clipe"); ev.pop("inicio")
            if video.exists() and raw is not None:
                ev["quadros"] = salvar_quadros_chave(video, nome, ev, k, raw, feat, info["fps"])
            eventos.append(ev)

        rel = {
            "clipe": nome, "arquivo": f"{nome}.mp4", **info,
            "deteccao_pessoa_pct": round(100 * float(raw["detectou"].mean()), 1) if raw is not None else None,
            "parametros": PARAMETROS,
            "medidas": {k: round(v, 3) for k, v in resumo(feat).items()},
            "eventos": eventos, "conclusao": conclusao(eventos),
        }
        (RELATORIOS / f"{nome}.json").write_text(
            json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
        if rel["deteccao_pessoa_pct"] is None:
            rel["deteccao_pessoa_pct"] = float("nan")
        escrever_markdown(rel, RELATORIOS / f"{nome}.md")

        if anotar and video.exists() and raw is not None:
            print(f"{nome}: gerando vídeo anotado...")
            print(f"  -> {anotar_video(video, nome, eventos, raw, feat)}")

        esperado = esperado_do_clipe(nome)
        avaliacao.append({
            "clipe": nome, "esperado": esperado, "detectado": len(eventos),
            "acerto": (len(eventos) > 0) == bool(esperado),
            "instante_s": eventos[0]["tempo_s"] if eventos else None,
            "horario_ficticio": eventos[0]["inicio_ficticio"] if eventos else None,
            "altura_final": eventos[0]["altura_final"] if eventos else None,
            "permanencia_s": eventos[0]["permanencia_s"] if eventos else None,
        })

    av = pd.DataFrame(avaliacao)
    av.to_csv(RELATORIOS / "avaliacao.csv", index=False)
    pos, neg = av[av["esperado"] == 1], av[av["esperado"] == 0]
    verd_pos = int((pos["detectado"] > 0).sum())
    falsos = int((neg["detectado"] > 0).sum())
    L = ["# Avaliação da detecção de queda em vídeo", "",
         "| Clipe | Esperado | Detectado | Acerto | Instante | Horário fictício |",
         "|---|---|---|---|---|---|"]
    for r in avaliacao:
        inst = f"{r['instante_s']:.1f} s" if r["instante_s"] is not None else "-"
        L.append(f"| {r['clipe']} | {'queda' if r['esperado'] else 'sem queda'} | "
                 f"{r['detectado']} | {'sim' if r['acerto'] else 'NÃO'} | {inst} | "
                 f"{r['horario_ficticio'] or '-'} |")
    L += ["", f"- Quedas detectadas: {verd_pos} de {len(pos)}",
          f"- Falsos alarmes (clipes sem queda com detecção): {falsos} de {len(neg)}", "",
          "## Limitações", "",
          f"- Apenas {len(av)} clipes, e os limiares foram calibrados nos mesmos clipes avaliados.",
          "- Quedas simuladas e controladas; quedas reais são mais rápidas e variadas.",
          "- Os limiares de altura valem para este enquadramento de câmera.",
          "- Não há clipes de agachar ou sentar no chão; são os casos em que a regra pode errar."]
    (RELATORIOS / "avaliacao.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"Relatórios em {RELATORIOS}")
    print(f"Quedas detectadas: {verd_pos}/{len(pos)} | falsos alarmes: {falsos}/{len(neg)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anotar", action="store_true",
                    help="também gera os vídeos anotados (esqueleto, relógio e aviso de queda)")
    main(ap.parse_args().anotar)
