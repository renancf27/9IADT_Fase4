import re

# Sintomas que ativam o contexto de risco de queda (ajustar com o grupo)
CRITICOS = re.compile(
    r"tontur|fraquez|falta de (ar|fôlego|folego)|dispneia|dor no peito"
    r"|cansa|taquicardia|desmai",
    re.I,
)

# O Azure inverte estas expressões: "sem fôlego" vira sintoma NEGADO,
# quando na verdade o paciente está relatando dispneia.
SEM_AR_FOLEGO = re.compile(r"\bsem\s+(fôlego|folego|ar)\b", re.I)


def sintomas_presentes(nota: str, entidades: list[dict]) -> list[str]:
    """Sintomas críticos presentes na nota.

    entidades: lista de dicts com texto, categoria, certeza e confianca,
    como devolvida pelo Azure Text Analytics for Health.
    Só a certeza 'negative' é tratada como ausência do sintoma.
    """
    presentes: list[str] = []
    for e in entidades:
        if e["categoria"] != "SymptomOrSign":
            continue
        if e["certeza"] == "negative":
            continue
        if CRITICOS.search(e["texto"]) and e["texto"] not in presentes:
            presentes.append(e["texto"])
    m = SEM_AR_FOLEGO.search(nota)
    if m:
        expressao = " ".join(m.group(0).lower().split())
        presentes.append(f"dispneia ({expressao})")
    return presentes