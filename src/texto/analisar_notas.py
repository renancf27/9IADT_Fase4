import argparse
import json
import os

import pandas as pd
from dotenv import load_dotenv

from src.config import DATA_DIR
from src.texto.regras import SEM_AR_FOLEGO, sintomas_presentes

CACHE = DATA_DIR / "azure_cache.json"
SAIDA = DATA_DIR / "analise_notas.csv"
LOTE = 10  # documentos por chamada, abaixo do limite do serviço


def _cliente():
    from azure.ai.textanalytics import TextAnalyticsClient
    from azure.core.credentials import AzureKeyCredential

    load_dotenv()
    return TextAnalyticsClient(
        os.environ["AZURE_LANGUAGE_ENDPOINT"],
        AzureKeyCredential(os.environ["AZURE_LANGUAGE_KEY"]),
    )


def consultar_azure(textos: list[str]) -> dict:
    """Sentimento + entidades de saúde. Devolve {texto: {sentimento, entidades}}."""
    client = _cliente()
    saida = {}
    for i in range(0, len(textos), LOTE):
        lote = textos[i:i + LOTE]
        sentimentos = {int(r.id): r for r in
                       client.analyze_sentiment(lote, language="pt")}
        saude = {int(r.id): r for r in
                 client.begin_analyze_healthcare_entities(lote, language="pt").result()}
        for j, texto in enumerate(lote):
            s, h = sentimentos[j], saude[j]
            if s.is_error or h.is_error:
                erro = s.error if s.is_error else h.error
                raise RuntimeError(f"Azure retornou erro: {erro.code} {erro.message}")
            saida[texto] = {
                "sentimento": s.sentiment,
                "entidades": [{
                    "texto": e.text,
                    "categoria": e.category,
                    "certeza": getattr(e.assertion, "certainty", None) if e.assertion else None,
                    "confianca": round(e.confidence_score, 2),
                } for e in h.entities],
            }
    return saida


def _ler_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


def main(forcar: bool = False) -> None:
    notas = pd.read_csv(DATA_DIR / "notas.csv", parse_dates=["timestamp"])
    cache = {} if forcar else _ler_cache()

    faltando = [t for t in notas["texto"] if t not in cache]
    if faltando:
        print(f"Consultando o Azure para {len(faltando)} nota(s)...")
        cache.update(consultar_azure(faltando))
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    else:
        print("Todas as notas já estão no cache (use --forcar para consultar o Azure).")

    linhas = []
    for _, n in notas.iterrows():
        r = cache[n["texto"]]
        presentes = sintomas_presentes(n["texto"], r["entidades"])
        linhas.append({
            "timestamp": n["timestamp"],
            "texto": n["texto"],
            "sentimento": r["sentimento"],
            "sintomas_presentes": "; ".join(presentes),
            "ativa_contexto": bool(presentes),
            "correcao_aplicada": bool(SEM_AR_FOLEGO.search(n["texto"])),
            "entidades": json.dumps(r["entidades"], ensure_ascii=False),
        })
    analise = pd.DataFrame(linhas)
    analise.to_csv(SAIDA, index=False)

    # --- Avaliação contra o gabarito ---
    gab = pd.read_csv(DATA_DIR / "gabarito.csv", parse_dates=["timestamp"])
    gab = gab[gab["fonte"] == "nota"][["timestamp", "ativa_contexto"]]
    gab = gab.rename(columns={"ativa_contexto": "esperado"})
    gab["esperado"] = gab["esperado"].astype(bool)
    av = analise.merge(gab, on="timestamp")

    print("\nHorário | esperado | previsto | sintomas presentes")
    for _, r in av.iterrows():
        marca = "OK     " if r["esperado"] == r["ativa_contexto"] else "DIVERGE"
        print(f"{marca} {r['timestamp']:%d/%m %H:%M} | {str(r['esperado']):5} | "
              f"{str(r['ativa_contexto']):5} | {r['sintomas_presentes'] or '-'}")

    acertos = int((av["esperado"] == av["ativa_contexto"]).sum())
    print(f"\nContexto de risco: {acertos}/{len(av)} notas conforme o gabarito")
    print(f"Correções da regra aplicadas: {int(av['correcao_aplicada'].sum())}")
    print(f"Salvo em {SAIDA}")

def obter_analise(texto: str) -> dict:
    """Análise de UMA nota (para o tempo real): usa o cache ou consulta o Azure."""
    cache = _ler_cache()
    if texto not in cache:
        cache.update(consultar_azure([texto]))
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    return cache[texto]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--forcar", action="store_true",
                    help="ignora o cache e consulta o Azure de novo")
    main(ap.parse_args().forcar)