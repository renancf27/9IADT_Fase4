from datetime import timedelta

import pandas as pd

from src.config import DATA_DIR, INICIO_VITAIS, INSTANTE_VITAIS


def _hm(h: int, m: int):
    """Horário no mesmo dia do paciente fictício."""
    return INICIO_VITAIS.replace(hour=h, minute=m, second=0)


def _registros():
    # (timestamp, texto, presentes, negados, ativa_contexto)
    return [
        (_hm(20, 0) - timedelta(days=1),
         "Paciente estável, sem queixas no momento. Sinais vitais dentro dos parâmetros.",
         "", "", False),
        (_hm(6, 30),
         "Paciente dormiu bem. Nega dor e nega febre. Aceitou a dieta.",
         "", "dor; febre", False),
        (_hm(8, 0),
         "Paciente nega tontura e nega falta de ar. Deambula sem auxílio.",
         "", "tontura; falta de ar", False),
        (_hm(9, 10),
         "Medicação administrada conforme prescrição atualizada. Paciente sem queixas.",
         "", "", False),
        # Sintoma NÃO crítico: não deve ativar o contexto de risco
        (_hm(9, 40),
         "Paciente refere dor leve no joelho há dois dias, sem alteração. Nega tontura.",
         "dor no joelho", "tontura", False),
        # Nota principal: ativa o contexto de risco (alerta preventivo)
        (_hm(10, 0),
         "Paciente refere tontura e fraqueza ao levantar. Nega dor no peito.",
         "tontura; fraqueza", "dor no peito", True),
        # Sem sintomas novos: o contexto continua ativo pela janela de tempo
        (_hm(10, 15),
         "Orientado a não levantar sem auxílio. Mantido em observação.",
         "", "", False),
        # Linguagem coloquial: o Azure inverte "sem fôlego"; a regra corrige
        (_hm(10, 20),
         "Paciente refere que fica sem fôlego ao caminhar até o banheiro.",
         "dispneia (sem fôlego)", "", True),
        # Nota posterior ao evento
        (INSTANTE_VITAIS + timedelta(minutes=3),
         "Paciente encontrado no chão ao lado do leito, "
         "consciente, referindo tontura. Equipe médica acionada.",
         "tontura", "", True),
    ]


def gerar_notas() -> pd.DataFrame:
    df = pd.DataFrame(_registros(), columns=[
        "timestamp", "texto", "presentes", "negados", "ativa_contexto"])
    return (df[["timestamp", "texto"]]
            .sort_values("timestamp").reset_index(drop=True))


def gabarito_notas() -> list[dict]:
    """Resultado esperado por nota (avaliação da análise de texto)."""
    return [{
        "fonte": "nota",
        "timestamp": ts,
        "descricao": texto,
        "sintomas_presentes": presentes,
        "sintomas_negados": negados,
        "ativa_contexto": ativa,
    } for ts, texto, presentes, negados, ativa in _registros()]


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = gerar_notas()
    caminho = DATA_DIR / "notas.csv"
    df.to_csv(caminho, index=False)
    print(f"Salvo em {caminho} ({len(df)} notas)")
    for _, r in df.iterrows():
        print(f"{r.timestamp:%d/%m %H:%M}  {r.texto}")
