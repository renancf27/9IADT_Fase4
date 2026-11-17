"""Testes das regras de texto, usando saídas REAIS do Azure (teste_azure.py)."""
from src.texto.regras import sintomas_presentes


def ent(texto, certeza=None, categoria="SymptomOrSign"):
    return {"texto": texto, "categoria": categoria, "certeza": certeza, "confianca": 1.0}


CASOS = [
    ("Paciente refere tontura e fraqueza ao levantar.",
     [ent("tontura"), ent("fraqueza")], ["tontura", "fraqueza"]),
    ("Paciente nega falta de ar e dor no peito.",
     [ent("falta de ar", "negative"), ent("dor no peito", "negative")], []),
    ("Paciente relata que está sem fôlego e muito cansado.",
     [ent("fôlego", "negative"), ent("muito", None, "ConditionQualifier"), ent("cansado")],
     ["cansado", "dispneia (sem fôlego)"]),
    ("Paciente sem dor e sem febre.",
     [ent("dor", "negative"), ent("febre", "negative")], []),
    ("Paciente sem ar ao subir escadas.",
     [ent("ar", "negative")], ["dispneia (sem ar)"]),
    ("Paciente refere falta de fôlego aos esforços.",
     [ent("falta de fôlego aos")], ["falta de fôlego aos"]),
    ("Paciente apresenta dispneia e taquicardia.",
     [ent("dispneia"), ent("taquicardia")], ["dispneia", "taquicardia"]),
    ("Paciente nega tontura. Refere cansaço leve.",
     [ent("tontura", "negative"), ent("cansaço"), ent("leve", None, "ConditionQualifier")],
     ["cansaço"]),
    ("Paciente sem queixas no momento.",
     [ent("queixas", "negative")], []),
    ("Queixa-se de tontura, mas sem queda.",
     [ent("tontura"), ent("queda", "negative", "Course")], ["tontura"]),
]

if __name__ == "__main__":
    falhas = 0
    for nota, entidades, esperado in CASOS:
        obtido = sintomas_presentes(nota, entidades)
        ok = obtido == esperado
        falhas += not ok
        print(f"[{'OK' if ok else 'FALHA'}] {nota}" + ("" if ok else f"  -> {obtido}"))
    print(f"\n{len(CASOS) - falhas}/{len(CASOS)} casos passaram")
    raise SystemExit(1 if falhas else 0)