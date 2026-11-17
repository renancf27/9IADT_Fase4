"""Versão em tempo real das medidas e do detector de queda: recebe um quadro por vez
e usa só o passado (janelas que olham para trás)."""
import math
from collections import deque

import numpy as np

from src.config import (QUEDA_CONFIRMACAO_S, QUEDA_DELTA_ALTURA, QUEDA_INTERVALO_MIN_S,
                        QUEDA_JANELA_S, QUEDA_LIMIAR_CHAO, QUEDA_PERMANENCIA_S,
                        QUEDA_TRONCO_MIN)
from src.video.features import CONF_MIN, LACUNA_MAX_S

JANELA_SUAVIZACAO_S = 0.2
CHAVES = ("quadril_altura", "tronco_angulo", "box_razao")
VAZIO = {k: float("nan") for k in CHAVES}


def _medio(linha: dict, a: str, b: str):
    xs, ys = [], []
    for nome in (a, b):
        if linha[f"{nome}_c"] >= CONF_MIN:  # NaN >= 0.3 é False
            xs.append(linha[f"{nome}_x"])
            ys.append(linha[f"{nome}_y"])
    return (float(np.mean(xs)), float(np.mean(ys))) if xs else None


def medidas_do_quadro(linha: dict | None, altura_frame: int) -> dict | None:
    """Mesmas medidas do modo em lote, de um quadro só (sem suavização)."""
    if not linha or not linha.get("detectou"):
        return None
    quad = _medio(linha, "quadril_e", "quadril_d")
    if quad is None:
        return None
    ombro = _medio(linha, "ombro_e", "ombro_d")
    alt_caixa = linha["box_y2"] - linha["box_y1"]
    return {
        "quadril_altura": 1 - quad[1] / altura_frame,
        "tronco_angulo": (math.degrees(math.atan2(abs(ombro[0] - quad[0]), -(ombro[1] - quad[1])))
                          if ombro else float("nan")),
        "box_razao": (linha["box_x2"] - linha["box_x1"]) / alt_caixa if alt_caixa > 0 else float("nan"),
    }


class FeaturesOnline:
    """Suaviza as medidas com a mediana dos últimos 0,2 s e segura o último valor
    em lacunas curtas de detecção."""

    def __init__(self, altura_frame: int) -> None:
        self.altura_frame = altura_frame
        self.janela: deque = deque()
        self.ultimo = None  # (instante, medidas) da última detecção real

    def atualizar(self, t: float, linha: dict | None) -> dict:
        m = medidas_do_quadro(linha, self.altura_frame)
        if m is not None:
            self.ultimo = (t, m)
        elif self.ultimo is not None and t - self.ultimo[0] <= LACUNA_MAX_S:
            m = self.ultimo[1]
        if m is not None:
            self.janela.append((t, m))
        while self.janela and self.janela[0][0] < t - JANELA_SUAVIZACAO_S:
            self.janela.popleft()
        if not self.janela:
            return dict(VAZIO)
        saida = {}
        for k in CHAVES:
            valores = [x[1][k] for x in self.janela if not math.isnan(x[1][k])]
            saida[k] = float(np.median(valores)) if valores else float("nan")
        return saida


class DetectorQuedaOnline:
    """Mesma regra do modo em lote, como máquina de estados:
    ocioso -> candidato (desceu rápido) -> no chão (quadril baixo e tronco deitado)
    -> queda confirmada (ficou no chão pelo tempo mínimo)."""

    def __init__(self) -> None:
        self.janela: deque = deque()  # (t, altura) dos últimos QUEDA_JANELA_S
        self.estado = "ocioso"
        self.ultimo = -math.inf
        self.t_cand = self.t_conf = None
        self.max_queda = 0.0
        self.no_chao: list[tuple[float, float]] = []
        self.queda_atual = 0.0   # descida do quadril na janela, para mostrar na tela
        self.mudanca: str | None = None  # texto da última mudança de estado (o chamador lê)

    def permanencia(self, t: float) -> float:
        """Tempo seguido no chão até agora (0 se não está no estado 'no_chao')."""
        return t - self.t_conf if self.estado == "no_chao" else 0.0

    def _zerar(self) -> None:
        self.estado, self.t_cand, self.t_conf, self.no_chao = "ocioso", None, None, []

    def atualizar(self, t: float, altura: float, tronco: float) -> dict | None:
        """Devolve o evento de queda no instante em que ela fica confirmada."""
        self.mudanca = None
        if math.isnan(altura):
            return None
        self.janela.append((t, altura))
        while self.janela[0][0] < t - QUEDA_JANELA_S:
            self.janela.popleft()
        queda = max(a for _, a in self.janela) - altura
        self.queda_atual = queda

        if self.estado == "ocioso":
            if queda >= QUEDA_DELTA_ALTURA and t - self.ultimo >= QUEDA_INTERVALO_MIN_S:
                self.estado, self.t_cand, self.max_queda = "candidato", t, queda
                self.mudanca = (f"descida rápida do quadril ({queda:.2f} em {QUEDA_JANELA_S:.0f} s): "
                                "verificando se chega ao chão")

        elif self.estado == "candidato":
            self.max_queda = max(self.max_queda, queda)
            if altura < QUEDA_LIMIAR_CHAO and tronco > QUEDA_TRONCO_MIN:
                self.estado, self.t_conf, self.no_chao = "no_chao", t, [(altura, tronco)]
                self.mudanca = (f"quadril no nível do chão ({altura:.2f}) e tronco deitado "
                                f"({tronco:.0f}°): confirmando permanência de {QUEDA_PERMANENCIA_S:.0f} s")
            elif t - self.t_cand > QUEDA_CONFIRMACAO_S:
                self.mudanca = "descida sem chegar ao chão: descartada"
                self._zerar()

        elif self.estado == "no_chao":
            if altura >= QUEDA_LIMIAR_CHAO:
                self.mudanca = "voltou a levantar antes do tempo mínimo: descartada"
                self._zerar()  # levantou antes do tempo mínimo: não é queda
            else:
                self.no_chao.append((altura, tronco))
                if t - self.t_conf >= QUEDA_PERMANENCIA_S:
                    evento = {
                        "tempo_s": round(self.t_cand, 2),
                        "confirmado_em_s": round(self.t_conf, 2),
                        "emitido_em_s": round(t, 2),
                        "queda_altura": round(self.max_queda, 2),
                        "altura_final": round(float(np.median([a for a, _ in self.no_chao])), 2),
                        "tronco_final": round(float(np.nanmedian([g for _, g in self.no_chao])), 0),
                        "permanencia_s": round(t - self.t_conf, 1),
                    }
                    self.ultimo = self.t_cand
                    self._zerar()
                    return evento
        return None
