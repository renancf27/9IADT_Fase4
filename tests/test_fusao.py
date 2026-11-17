"""Cenários da fusão multimodal (dados construídos à mão)."""
import pandas as pd

from src.fusao.motor import fundir

T = pd.Timestamp


def notas(*itens):
    return pd.DataFrame(itens, columns=["timestamp", "ativa_contexto", "sintomas_presentes"]) \
        if itens else pd.DataFrame(columns=["timestamp", "ativa_contexto", "sintomas_presentes"])


def vitais(*itens):
    return pd.DataFrame(itens, columns=["inicio", "fim", "variaveis"]) \
        if itens else pd.DataFrame(columns=["inicio", "fim", "variaveis"])


def prescr(*itens):
    return pd.DataFrame(itens, columns=["timestamp", "medicamento", "dose_mg", "motivo"]) \
        if itens else pd.DataFrame(columns=["timestamp", "medicamento", "dose_mg", "motivo"])


def video(*itens):
    return pd.DataFrame([{"inicio": i, "tipo": "queda"} for i in itens],
                        columns=["inicio", "tipo"])


Q = T("2026-10-27 10:32:00")
V = (Q, Q + pd.Timedelta(seconds=90), "fc;spo2")
NOTA = (T("2026-10-27 10:00:00"), True, "tontura; fraqueza")
PRES = (T("2026-10-27 09:00:00"), "Losartana", 150, "dose +200%")


def niveis(df):
    return list(zip(df["timestamp"].dt.strftime("%H:%M:%S"), df["severidade"]))


CASOS = [
    ("cenário completo (prescrição, nota, queda, vitais)",
     fundir(notas(NOTA), vitais(V), prescr(PRES), video(Q)),
     [("09:00:00", "PREVENTIVO"), ("10:00:00", "PREVENTIVO"), ("10:32:00", "ALTO")]),
    ("só a nota de risco",
     fundir(notas(NOTA), vitais(), prescr(), video()),
     [("10:00:00", "PREVENTIVO")]),
    ("queda + vitais, sem nota nem prescrição",
     fundir(notas(), vitais(V), prescr(), video(Q)),
     [("10:32:00", "MÉDIO")]),
    ("queda sem vitais, com nota",
     fundir(notas(NOTA), vitais(), prescr(), video(Q)),
     [("10:00:00", "PREVENTIVO"), ("10:32:00", "MÉDIO")]),
    ("vitais sozinhos, sem contexto",
     fundir(notas(), vitais(V), prescr(), video()),
     [("10:32:00", "MÉDIO")]),
    ("vitais começam 20 s depois da queda (escala de MÉDIO para ALTO)",
     fundir(notas(NOTA), vitais((Q + pd.Timedelta(seconds=20), Q + pd.Timedelta(seconds=110), "fc")),
            prescr(), video(Q)),
     [("10:00:00", "PREVENTIVO"), ("10:32:00", "MÉDIO"), ("10:32:20", "ALTO")]),
    ("vitais começam 60 s depois da queda (fora da janela de coincidência)",
     fundir(notas(NOTA), vitais((Q + pd.Timedelta(seconds=60), Q + pd.Timedelta(seconds=150), "fc")),
            prescr(), video(Q)),
     [("10:00:00", "PREVENTIVO"), ("10:32:00", "MÉDIO")]),
    ("nota de risco repetida 20 min depois (suprimida)",
     fundir(notas(NOTA, (T("2026-10-27 10:20:00"), True, "dispneia")), vitais(), prescr(), video()),
     [("10:00:00", "PREVENTIVO")]),
]

def teste_mensagem_lista_todas_as_notas():
    outra = (T("2026-10-27 10:20:00"), True, "dispneia (sem fôlego)")
    df = fundir(notas(NOTA, outra), vitais(V), prescr(PRES), video(Q))
    msg = df.iloc[-1]["mensagem"]
    return ("10:00 [tontura; fraqueza]" in msg
            and "10:20 [dispneia (sem fôlego)]" in msg
            and "notas de risco ativas" in msg)

if __name__ == "__main__":
    falhas = 0
    for nome, df, esperado in CASOS:
        obtido = niveis(df)
        ok = obtido == esperado
        falhas += not ok
        print(f"[{'OK' if ok else 'FALHA'}] {nome}" + ("" if ok else f"\n   esperado {esperado}\n   obtido   {obtido}"))
    ok = teste_mensagem_lista_todas_as_notas()
    falhas += not ok
    print(f"[{'OK' if ok else 'FALHA'}] mensagem do alerta lista todas as notas de risco ativas")
    print(f"\n{len(CASOS) + 1 - falhas}/{len(CASOS) + 1} verificações passaram")
    raise SystemExit(1 if falhas else 0)