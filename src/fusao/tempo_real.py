import argparse
import time
from itertools import groupby

import pandas as pd

from src.fusao.executar import eventos_video, ler
from src.fusao.motor import fundir
from src.fusao.notificacao import notificar, reiniciar_log
from src.fusao.sistema import Sistema


def montar_feed(incluir_video: bool = True) -> list[tuple]:
    """Tudo o que 'chega' ao sistema, em ordem cronológica: (instante, tipo, dados)."""
    itens = []
    for r in ler("vitais.csv", ["timestamp"]).to_dict("records"):
        itens.append((r["timestamp"], "vitais", r))
    for r in ler("notas.csv", ["timestamp"]).to_dict("records"):
        itens.append((r["timestamp"], "nota", r))
    for r in ler("prescricoes.csv", ["timestamp"]).to_dict("records"):
        itens.append((r["timestamp"], "prescricao", r))
    if incluir_video:
        for r in eventos_video().to_dict("records"):
            itens.append((r["inicio"], "video", r))
    itens.sort(key=lambda x: x[0])
    return itens


def processar_grupos(itens: list[tuple], sistema: Sistema, velocidade: float,
                     espera_max_s: float = 1.5, anterior=None):
    """Entrega os dados ao sistema na ordem do tempo, esperando entre um instante e outro.

    velocidade: segundos simulados por segundo real (0 = sem esperar).
    """
    for ts, grupo in groupby(itens, key=lambda x: x[0]):
        if velocidade > 0 and anterior is not None:
            time.sleep(min((ts - anterior).total_seconds() / velocidade, espera_max_s))
        anterior = ts
        gatilho = False
        for _, tipo, d in grupo:
            gatilho |= sistema.receber(ts, tipo, d)
        if gatilho:
            sistema.avaliar(ts)
    return anterior


def executar(velocidade: float = 60.0, mostrar_leituras: bool = False,
             notificador=notificar, silencioso: bool = False) -> pd.DataFrame:
    """Simula a chegada dos dados no tempo e dispara os alertas (evento de vídeo já detectado)."""
    if notificador is notificar:
        reiniciar_log()
    sistema = Sistema(notificador, (lambda *a: None) if silencioso else print, mostrar_leituras)
    processar_grupos(montar_feed(), sistema, velocidade)
    return sistema.tabela_alertas()


def verificar() -> int:
    """O modo em tempo real deve gerar os MESMOS alertas do modo em lote."""
    ao_vivo = executar(velocidade=0, notificador=lambda a: None, silencioso=True)
    lote = fundir(ler("analise_notas.csv", ["timestamp"]),
                  ler("eventos_vitais.csv", ["inicio", "fim"]),
                  ler("eventos_prescricoes.csv", ["timestamp"]),
                  eventos_video())
    a = list(zip(ao_vivo["timestamp"], ao_vivo["severidade"]))
    b = list(zip(lote["timestamp"], lote["severidade"]))
    print(f"tempo real: {[(f'{t:%H:%M:%S}', s) for t, s in a]}")
    print(f"em lote   : {[(f'{t:%H:%M:%S}', s) for t, s in b]}")
    ok = a == b
    print("[OK] os dois modos geram os mesmos alertas" if ok
          else "[FALHA] os modos divergem")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--velocidade", type=float, default=60.0,
                    help="segundos simulados por segundo real (0 = sem esperar)")
    ap.add_argument("--mostrar-leituras", action="store_true",
                    help="imprime cada leitura de sinais vitais")
    ap.add_argument("--verificar", action="store_true",
                    help="compara o modo em tempo real com o modo em lote")
    args = ap.parse_args()
    if args.verificar:
        raise SystemExit(verificar())
    executar(args.velocidade, args.mostrar_leituras)
