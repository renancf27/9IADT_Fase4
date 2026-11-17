import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

load_dotenv()
client = TextAnalyticsClient(
    os.environ["AZURE_LANGUAGE_ENDPOINT"],
    AzureKeyCredential(os.environ["AZURE_LANGUAGE_KEY"]),
)

notas = [
"Paciente refere tontura e fraqueza ao levantar.",
    "Paciente nega falta de ar e dor no peito.",
    "Paciente relata que está sem fôlego e muito cansado.",
    "Paciente sem dor e sem febre.",
    "Paciente sem ar ao subir escadas.",
    "Paciente refere falta de fôlego aos esforços.",
    "Paciente apresenta dispneia e taquicardia.",
    "Paciente nega tontura. Refere cansaço leve.",
    "Paciente sem queixas no momento.",
    "Queixa-se de tontura, mas sem queda.",
]

print("=== Sentimento ===")
for nota, r in zip(notas, client.analyze_sentiment(notas, language="pt")):
    print(f"{r.sentiment:9} | {nota}")

print("\n=== Entidades de saúde ===")
poller = client.begin_analyze_healthcare_entities(notas, language="pt")
for nota, doc in zip(notas, poller.result()):
    print(f"\n> {nota}")
    if doc.is_error:
        print("  ERRO:", doc.error.code, doc.error.message)
        continue
    if not doc.entities:
        print("  (nenhuma entidade encontrada)")
    for e in doc.entities:
        a = e.assertion
        certeza = getattr(a, "certainty", None) if a else None
        print(f"  {e.text!r:20} {e.category:18} certeza={certeza} conf={e.confidence_score:.2f}")
