import pandas as pd

from src.anomalias.detectores import detectar_prescricoes, detectar_vitais
from src.config import JANELA_ZSCORE, TOLERANCIA_EVENTO_S
from src.fusao.motor import NOMES_VITAIS, avaliar_gatilho
from src.texto.analisar_notas import obter_analise
from src.texto.regras import sintomas_presentes


def _df(linhas: list[dict], colunas: list[str], datas: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=colunas)
    for c in datas:
        df[c] = pd.to_datetime(df[c])
    return df


class AcumuladorVitais:
    """Recebe uma leitura por vez e mantém os eventos de vitais alterados."""

    def __init__(self) -> None:
        self.linhas: list[dict] = []
        self.eventos: list[dict] = []

    def adicionar(self, linha: dict) -> bool:
        """True se esta leitura INICIA um novo evento de vitais alterados."""
        self.linhas.append(linha)
        # A janela do z-score precisa só das últimas JANELA_ZSCORE leituras + a atual
        df = pd.DataFrame(self.linhas[-(JANELA_ZSCORE + 1):])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        r = detectar_vitais(df).iloc[-1]
        if not r["anomalia"]:
            return False
        ts = r["timestamp"]
        variaveis = set(filter(None, r["variaveis"].split(";")))
        if self.eventos and (ts - self.eventos[-1]["fim"]).total_seconds() <= TOLERANCIA_EVENTO_S:
            self.eventos[-1]["fim"] = ts
            self.eventos[-1]["variaveis"] |= variaveis
            return False
        self.eventos.append({"inicio": ts, "fim": ts, "variaveis": variaveis})
        return True

    def eventos_df(self) -> pd.DataFrame:
        linhas = [{"inicio": e["inicio"], "fim": e["fim"],
                   "variaveis": ";".join(sorted(e["variaveis"]))} for e in self.eventos]
        return _df(linhas, ["inicio", "fim", "variaveis"], ["inicio", "fim"])


class Sistema:
    """Estado do monitoramento: recebe os dados um a um e dispara os alertas.

    Usado pela simulação (tempo_real.py) e pela demonstração ao vivo (ao_vivo.py).
    """

    def __init__(self, notificador, dizer=print, mostrar_leituras: bool = False) -> None:
        self.notificador, self.dizer, self.mostrar_leituras = notificador, dizer, mostrar_leituras
        self.acum = AcumuladorVitais()
        self.notas_risco: list[dict] = []
        self.ev_prescr: list[dict] = []
        self.quedas: list[dict] = []
        self.prescr_vistas: list[dict] = []
        self.alertas: list[dict] = []

    def receber(self, ts, tipo: str, d: dict) -> bool:
        """Processa um dado que chegou. Devolve True se vale reavaliar o risco."""
        dizer = self.dizer
        if tipo == "vitais":
            inicio = self.acum.adicionar(d)
            if self.mostrar_leituras:
                dizer(f"{ts:%H:%M:%S} [VITAIS] FC {d['fc']} | PA {d['pas']}/{d['pad']} "
                      f"| SpO2 {d['spo2']}%")
            if inicio:
                nomes = ", ".join(NOMES_VITAIS[v] for v in sorted(self.acum.eventos[-1]["variaveis"]))
                dizer(f"{ts:%H:%M:%S} [VITAIS] anomalia detectada: {nomes}")
            return inicio

        if tipo == "nota":
            analise = obter_analise(d["texto"])
            presentes = sintomas_presentes(d["texto"], analise["entidades"])
            resumo = d["texto"] if len(d["texto"]) <= 62 else d["texto"][:59] + "..."
            dizer(f"{ts:%d/%m %H:%M:%S} [NOTA] \"{resumo}\" -> "
                  + (f"sintomas críticos: {'; '.join(presentes)}" if presentes
                     else "sem sintomas críticos"))
            if presentes:
                self.notas_risco.append({"timestamp": ts,
                                         "sintomas_presentes": "; ".join(presentes)})
            return bool(presentes)

        if tipo == "prescricao":
            self.prescr_vistas.append(d)
            det = detectar_prescricoes(pd.DataFrame(self.prescr_vistas))
            linha = det[(det["timestamp"] == ts)
                        & (det["medicamento"] == d["medicamento"])].iloc[-1]
            if linha["anomalia"]:
                dizer(f"{ts:%d/%m %H:%M:%S} [PRESCRIÇÃO] {d['medicamento']} "
                      f"{d['dose_mg']} mg ({linha['motivo']})")
                self.ev_prescr.append({"timestamp": ts, "medicamento": d["medicamento"],
                                       "dose_mg": d["dose_mg"], "motivo": linha["motivo"]})
                return True
            return False

        if tipo == "video" and d["tipo"] == "queda":
            dizer(f"{ts:%H:%M:%S} [VÍDEO] queda detectada")
            self.quedas.append({"inicio": ts, "tipo": "queda"})
            return True
        return False

    def avaliar(self, ts) -> dict | None:
        alerta = avaliar_gatilho(
            ts,
            _df(self.notas_risco, ["timestamp", "sintomas_presentes"], ["timestamp"]),
            _df(self.ev_prescr, ["timestamp", "medicamento", "dose_mg", "motivo"], ["timestamp"]),
            _df(self.quedas, ["inicio", "tipo"], ["inicio"]),
            self.acum.eventos_df(),
            self.alertas,
        )
        if alerta:
            self.alertas.append(alerta)
            self.notificador(alerta)
        return alerta

    def tabela_alertas(self) -> pd.DataFrame:
        return pd.DataFrame(self.alertas, columns=[
            "timestamp", "severidade", "score", "queda", "vitais",
            "contexto_nota", "contexto_prescricao", "mensagem"])
