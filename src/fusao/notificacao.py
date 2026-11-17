import json
import os
import urllib.parse
import urllib.request

from dotenv import load_dotenv

from src.config import DATA_DIR

if os.name == "nt":
    os.system("")  # habilita as cores (sequências ANSI) no console do Windows 10+

LOG = DATA_DIR / "alertas_tempo_real.jsonl"
CORES = {"PREVENTIVO": "\033[33m", "MÉDIO": "\033[38;5;208m", "ALTO": "\033[1;31m"}
RESET = "\033[0m"


def reiniciar_log() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG.write_text("", encoding="utf-8")


def _telegram(texto: str) -> None:
    """Envia ao Telegram se TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID estiverem no .env."""
    load_dotenv()
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    dados = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", dados, timeout=5)
    except Exception as erro:  # a notificação nunca deve derrubar o monitoramento
        print(f"  (falha ao enviar ao Telegram: {erro})")


def notificar(alerta: dict) -> None:
    """Notifica a equipe: terminal colorido, log em arquivo e Telegram (opcional)."""
    nivel = alerta["severidade"]
    linha = "=" * 78
    print(f"{CORES[nivel]}{linha}\nALERTA {nivel} | {alerta['timestamp']:%d/%m/%Y %H:%M:%S}"
          f"\n{alerta['mensagem']}\n{linha}{RESET}")
    registro = {"timestamp": f"{alerta['timestamp']:%Y-%m-%d %H:%M:%S}",
                "severidade": nivel, "score": int(alerta["score"]),
                "mensagem": alerta["mensagem"]}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    _telegram(f"ALERTA {nivel}\n{alerta['mensagem']}")
