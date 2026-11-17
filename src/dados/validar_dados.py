import sys

import pandas as pd

from src.config import (DATA_DIR, INSTANTE_VITAIS, INTERVALO_VITAIS_S,
                        JANELA_CONFIRMACAO_VITAIS, JANELA_CONTEXTO_NOTA,
                        PRESCRICAO_ALTERADA_EM)

# Limites clínicos fixos usados só nesta validação (ilustrativos)
SPO2_MIN, FC_MIN, FC_MAX, PAS_MIN = 92, 50, 100, 90

resultados: list[tuple[bool, str]] = []


def checar(ok: bool, descricao: str) -> None:
    resultados.append((bool(ok), descricao))
    print(f"[{'OK' if ok else 'FALHA'}] {descricao}")


def ler(nome: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / nome, parse_dates=["timestamp"])


def main() -> int:
    vitais = ler("vitais.csv")
    prescr = ler("prescricoes.csv")
    notas = ler("notas.csv")
    gab = ler("gabarito.csv")

    # --- Estrutura e ordem ---
    checar(list(vitais.columns) == ["timestamp", "fc", "pas", "pad", "spo2"],
           "vitais.csv: colunas esperadas")
    checar(vitais["timestamp"].is_monotonic_increasing,
           "vitais.csv: timestamps em ordem")
    passos = vitais["timestamp"].diff().dropna().dt.total_seconds().unique()
    checar(len(passos) == 1 and passos[0] == INTERVALO_VITAIS_S,
           f"vitais.csv: intervalo regular de {INTERVALO_VITAIS_S} s")
    checar(prescr["timestamp"].is_monotonic_increasing,
           "prescricoes.csv: timestamps em ordem")
    checar(notas["timestamp"].is_monotonic_increasing,
           "notas.csv: timestamps em ordem")

    # --- Queda dentro da série de vitais ---
    checar(vitais["timestamp"].min() <= INSTANTE_VITAIS <= vitais["timestamp"].max(),
           "alteração dos vitais está dentro do período dos vitais")

    # --- Vitais: normais antes, alterados na queda ---
    def fora_do_limite(df: pd.DataFrame) -> pd.Series:
        return ((df["spo2"] < SPO2_MIN) | (df["fc"] > FC_MAX)
                | (df["fc"] < FC_MIN) | (df["pas"] < PAS_MIN))

    antes = vitais[vitais["timestamp"] < INSTANTE_VITAIS]
    checar(not fora_do_limite(antes).any(),
           "vitais: nenhuma leitura fora dos limites clínicos antes da alteração")

    janela = vitais[(vitais["timestamp"] >= INSTANTE_VITAIS)
                    & (vitais["timestamp"] <= INSTANTE_VITAIS + JANELA_CONFIRMACAO_VITAIS)]
    checar(len(janela) > 0 and fora_do_limite(janela).all(),
           f"vitais: todas as leituras dos {int(JANELA_CONFIRMACAO_VITAIS.total_seconds())} s "
           "após a alteração estão alteradas")

    # --- Prescrições: uma única variação brusca, antes da queda ---
    prescr["variacao_pct"] = prescr.groupby("medicamento")["dose_mg"].pct_change() * 100
    bruscas = prescr[prescr["variacao_pct"].abs() > 50]
    checar(len(bruscas) == 1, "prescricoes: exatamente uma variação brusca (>50%)")
    if len(bruscas) == 1:
        checar(bruscas.iloc[0]["timestamp"] == PRESCRICAO_ALTERADA_EM,
               "prescricoes: a variação está no horário configurado")
        checar(bruscas.iloc[0]["timestamp"] < INSTANTE_VITAIS,
               "prescricoes: a alteração ocorre antes da alteração dos vitais")

    # --- Notas: contexto de risco antes da queda e dentro da janela ---
    gab_notas = gab[gab["fonte"] == "nota"]
    checar(set(gab_notas["timestamp"]) == set(notas["timestamp"]),
           "gabarito: mesmas notas (horários) do notas.csv")
    ctx = gab_notas[(gab_notas["ativa_contexto"] == True)  # noqa: E712
                    & (gab_notas["timestamp"] < INSTANTE_VITAIS)]
    checar(len(ctx) > 0, "notas: existe nota de risco antes da alteração")
    if len(ctx):
        ultimo = ctx["timestamp"].max()
        checar(INSTANTE_VITAIS - ultimo <= JANELA_CONTEXTO_NOTA,
               "notas: a última nota de risco está dentro da janela de contexto")

    # --- Gabarito: eventos nos horários certos ---
    for fonte, instante in (("vitais", INSTANTE_VITAIS),):
        linha = gab[gab["fonte"] == fonte]
        checar(len(linha) == 1 and linha.iloc[0]["timestamp"] == instante,
               f"gabarito: evento '{fonte}' no instante esperado")
    checar((gab["fonte"] == "prescricao").sum() == 1,
           "gabarito: uma anomalia de prescrição")

    falhas = [d for ok, d in resultados if not ok]
    print(f"\n{len(resultados) - len(falhas)}/{len(resultados)} verificações passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
