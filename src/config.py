from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATA_DIR = RAIZ / "data"

# Estes valores só posicionam os dados SIMULADOS (vitais, notas, prescrição) em relação ao
# vídeo. O detector de queda NÃO lê nenhum deles: ele analisa o vídeo quadro a quadro.
INSTANTE_VITAIS = datetime(2026, 10, 27, 10, 32, 0)  # os vitais simulados alteram aqui
VITAIS_ALTERAM_NO_CLIPE_S = 43                       # segundo do clipe em que isso ocorre
INICIO_VIDEO = INSTANTE_VITAIS - timedelta(seconds=VITAIS_ALTERAM_NO_CLIPE_S)  # relógio do clipe

JANELA_CONTEXTO_NOTA = timedelta(hours=2)
JANELA_CONFIRMACAO_VITAIS = timedelta(seconds=30)

# Prescrição com dose alterada bruscamente (antes da queda)
PRESCRICAO_ALTERADA_EM = datetime(2026, 10, 27, 9, 0)

# Sinais vitais: janela e frequência de amostragem
INICIO_VITAIS = datetime(2026, 10, 27, 10, 0, 0)
FIM_VITAIS = datetime(2026, 10, 27, 10, 40, 0)
INTERVALO_VITAIS_S = 10

# Detecção de anomalias
JANELA_ZSCORE = 30            # leituras na janela móvel
LIMIAR_ZSCORE = 3.0
MIN_VITAIS_ZSCORE = 2         # quantos vitais fora do padrão ao mesmo tempo
LIMITES_CLINICOS = {"spo2_min": 92, "fc_min": 50, "fc_max": 100, "pas_min": 90}
LIMIAR_DOSE_PCT = 50          # variação de dose considerada brusca
TOLERANCIA_EVENTO_S = 60      # leituras alteradas a menos disso formam um evento

# Fusão multimodal
JANELA_CONTEXTO_PRESCRICAO = timedelta(hours=12)  # prescrição anômala segue como contexto
JANELA_COINCIDENCIA = timedelta(seconds=30)       # queda e vitais "no mesmo momento"
JANELA_SUPRESSAO = timedelta(minutes=30)          # evita repetir alerta de mesma gravidade
PONTOS = {"contexto": 1, "queda": 2, "vitais": 2}
LIMIAR_MEDIO = 2
LIMIAR_ALTO = 5

# Detecção de queda no vídeo (calibrada nos 4 clipes gravados; depende do enquadramento)
QUEDA_DELTA_ALTURA = 0.15     # queda mínima da altura do quadril dentro da janela curta
QUEDA_JANELA_S = 2.0
QUEDA_LIMIAR_CHAO = 0.35      # abaixo disso o quadril está "no nível do chão"
QUEDA_TRONCO_MIN = 60         # graus: tronco deitado
QUEDA_CONFIRMACAO_S = 5.0     # tempo para o corpo chegar ao chão e deitar
QUEDA_PERMANENCIA_S = 3.0     # tempo mínimo parado no chão
QUEDA_INTERVALO_MIN_S = 10.0  # ignora novos candidatos logo após uma queda

SEED = 42