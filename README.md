# Tech Challenge Fase 4: monitoramento multimodal de paciente internado

Sistema de triagem que acompanha um paciente internado e alerta a equipe médica **antes e durante uma queda**. Ele cruza três fontes:

- **Vídeo** do leito: o YOLOv8-pose extrai a postura e uma regra detecta a queda, quadro a quadro.
- **Texto**: notas de enfermagem analisadas pelo Azure AI Language (Text Analytics for Health e sentimento).
- **Sinais vitais e prescrições**: detecção de anomalias (z-score móvel, limites clínicos e variação de dose).

Uma fusão combina as fontes por tempo e gera alertas **PREVENTIVO**, **MÉDIO** e **ALTO**. É apoio à decisão, não diagnóstico.

> **O que é real e o que é simulado.** Os vídeos são reais (quedas simuladas e controladas). A pose e a detecção da queda são calculadas na hora. Os sinais vitais, as prescrições e as notas são **simulados**. As respostas do Azure vêm de chamadas reais, guardadas em cache.

---

## 1. Antes de começar

| Item | Detalhe |
|---|---|
| Sistema | Windows 10/11, Linux ou macOS |
| Python | **3.10 a 3.12 é o mais seguro.** O projeto foi desenvolvido e testado em Ubuntu com Python 3.14. No Windows, prefira 3.11 ou 3.12 |
| Espaço em disco | cerca de 3 GB (PyTorch e dependências) |
| Internet | Necessária na instalação e na primeira execução (o modelo do YOLO é baixado) |
| Placa de vídeo | **Não é necessária.** Tudo roda na CPU |
| Conta Azure | **Opcional.** Veja o passo 7 |

> **Aviso de teste.** Os comandos foram executados em Ubuntu. Os comandos para Windows seguem o procedimento padrão, mas não foram executados em uma máquina Windows pelo grupo. Se algo falhar, veja a seção **Problemas comuns** (item 11).

### Conferir o Python

Windows (PowerShell ou Prompt de comando):

```
python --version
py -0
```

Linux ou macOS:

```
python3 --version
```

Se não houver Python instalado, baixe em https://www.python.org/downloads/ e, no instalador do Windows, **marque a opção "Add python.exe to PATH"**.

---

## 2. Obter o projeto

Com o Git:

```
git clone <URL-DO-REPOSITORIO>
cd TechChallenge4
```

Ou baixe o ZIP do repositório, extraia e entre na pasta. **Todos os comandos deste README devem ser executados dentro da pasta raiz do projeto** (a que contém `src`, `data` e `tests`).

Confira se a estrutura está completa:

```
TechChallenge4/
├── README.md
├── requirements.txt
├── src/
│   ├── config.py
│   ├── dados/        (geração e validação dos dados simulados)
│   ├── texto/        (Azure AI Language e regras das notas)
│   ├── anomalias/    (vitais e prescrições)
│   ├── video/        (YOLOv8-pose, detector de queda, modo ao vivo, relatórios)
│   └── fusao/        (fusão, alertas e tempo real)
├── tests/
└── data/
    ├── videos/       (queda_01.mp4, queda_02.mp4, normal_01.mp4, normal_02.mp4, clipes.csv)
    └── azure_cache.json   (se fornecido pelo grupo)
```

Se a pasta `data/videos/` estiver vazia, peça os vídeos ao grupo. Sem eles, a análise de vídeo não roda.

---

## 3. Criar o ambiente virtual

O ambiente virtual isola as bibliotecas do projeto. Na raiz do projeto:

**Windows (PowerShell):**

```
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Se aparecer um erro de "execução de scripts desabilitada", rode uma vez e ative de novo:

```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
```

**Windows (Prompt de comando):**

```
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux ou macOS:**

```
python3 -m venv .venv
source .venv/bin/activate
```

Se você tiver várias versões do Python no Windows, escolha uma: `py -3.12 -m venv .venv`.

Quando ativado, o prompt mostra `(.venv)` no início. **Toda vez que abrir um terminal novo, ative o ambiente de novo.** Para conferir:

```
python -c "import sys; print(sys.executable)"
```

O caminho impresso deve estar dentro da pasta `.venv`.

---

## 4. Atualizar o pip

```
python -m pip install --upgrade pip
```

---

## 5. Instalar as dependências

A **ordem importa**. Instale primeiro o PyTorch na versão para CPU (menor e sem exigir placa de vídeo) e depois o restante.

```
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

O conteúdo do `requirements.txt` é:

```
ultralytics
opencv-python
pandas
numpy
azure-ai-textanalytics
python-dotenv
```

> Use `opencv-python` (e não `opencv-python-headless`): a versão sem "headless" é a que abre a janela do vídeo.

Isso pode levar alguns minutos. Quando terminar, confira:

```
python -c "import cv2, torch, ultralytics, pandas, azure.ai.textanalytics; print('opencv', cv2.__version__, '| torch', torch.__version__, '| ultralytics', ultralytics.__version__)"
```

Deve imprimir as três versões, e a do torch deve terminar em `+cpu`. Se aparecer `ModuleNotFoundError`, o ambiente virtual não está ativo (volte ao passo 3) ou um pacote não foi instalado.

---

## 6. Baixar o modelo do YOLO (uma vez)

O modelo `yolov8n-pose.pt` (cerca de 6 MB) é baixado sozinho na primeira execução. Para não esperar na hora da demonstração, baixe agora:

```
python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt'); print('modelo ok')"
```

O arquivo fica na pasta de onde você rodou o comando (a raiz do projeto). Se a rede bloquear o download, baixe o arquivo em outra máquina e copie para a raiz.

---

## 7. Configurar o Azure (escolha uma opção)

O projeto analisa as notas com o **Azure AI Language**. As respostas ficam guardadas em `data/azure_cache.json`.

### Opção A: usar o cache do grupo (sem chave)

Se o arquivo `data/azure_cache.json` estiver na pasta, **não é preciso conta nem chave**. As notas são lidas do cache, sem internet. Esta é a forma mais simples.

### Opção B: usar a sua própria conta Azure

1. Crie uma conta em https://azure.microsoft.com/free (ou Azure for Students, se tiver e-mail acadêmico).
2. No portal, crie um recurso **Language** (Language service) no plano **Free F0**, região **East US**, e copie a **KEY 1** e o **Endpoint** em *Keys and Endpoint*.
3. Crie um arquivo chamado `.env` na raiz do projeto com este conteúdo:

```
AZURE_LANGUAGE_KEY=cole_a_chave_aqui
AZURE_LANGUAGE_ENDPOINT=https://nome-do-seu-recurso.cognitiveservices.azure.com/
```

> **Atenção no Windows:** o Bloco de Notas pode salvar o arquivo como `.env.txt`. Prefira o VS Code (`code .env`) ou, no Bloco de Notas, escolha **Salvar como > Tipo: Todos os arquivos**. O nome deve ser exatamente `.env`.

> **Nunca envie o `.env` para o repositório.** A chave dá acesso à sua conta.

Sem o cache e sem o `.env`, a demonstração falha ao processar a primeira nota.

---

## 8. Gerar os dados simulados

```
python -m src.dados.gerar_dados
python -m src.dados.validar_dados
```

O primeiro cria `data/vitais.csv`, `data/prescricoes.csv`, `data/notas.csv` e `data/gabarito.csv`. A saída termina assim:

```
vitais.csv      : 241 linhas
prescricoes.csv : 6 linhas
notas.csv       : 9 notas
gabarito.csv    : 11 registros
```

O segundo deve terminar com `16/16 verificações passaram`. Os dados são gerados com uma semente fixa, então todo o grupo obtém exatamente os mesmos arquivos.

Se você usa a **Opção B** (sem cache), gere agora as respostas do Azure:

```
python -m src.texto.analisar_notas
```

Isso chama o Azure para cada nota (cerca de 2 transações do plano gratuito por nota) e cria o `data/azure_cache.json`. A saída termina com uma linha `Contexto de risco: 9/9 notas conforme o gabarito`.

---

## 9. Rodar a demonstração

```
python -m src.video.ao_vivo
```

O que acontece:

1. O terminal mostra o que é **ao vivo** e o que é **simulado**.
2. Os eventos de antes do vídeo passam rápido: prescrição de Losartana (+200%) às 09:00, notas de enfermagem e o alerta PREVENTIVO das 10:00.
3. O modelo carrega e uma **janela de vídeo** abre, com um painel de texto: relógio fictício, quadro atual, milissegundos por quadro, altura do quadril, ângulo do tronco, "descida em 2 s" e o **estado** (MONITORANDO, DESCIDA RAPIDA, NO CHAO, QUEDA CONFIRMADA).
4. Quando a queda é confirmada, aparece a faixa vermelha e o alerta MÉDIO. Depois, os sinais vitais alteram e sai o alerta **ALTO**.

Sequência esperada de alertas:

| Horário fictício | Alerta |
|---|---|
| 09:00:00 | PREVENTIVO |
| 10:00:00 | PREVENTIVO |
| ~10:31:56 | MÉDIO (queda confirmada) |
| 10:32:00 | ALTO (vitais alterados) |

O resumo final mostra os quadros analisados (por volta de 96% em um Ryzen 5 5600) e `Quedas detectadas ao vivo neste clipe: 1`.

**Teclas:** `q` fecha a janela durante o vídeo. No final, qualquer tecla fecha a janela.

### Opções

| Opção | Efeito |
|---|---|
| `--clipe queda_02` | Usa outro clipe (deve estar em `data/videos/`) |
| `--clipe normal_01` | Clipe sem queda: não deve detectar nenhuma queda |
| `--sem-janela` | Só o terminal, sem abrir a janela de vídeo |
| `--velocidade-pre 3000` | Encurta a parte anterior ao vídeo |

> O computador não precisa acompanhar 30 quadros por segundo: se ficar atrasado, o sistema pula quadros para manter o tempo real e informa a porcentagem analisada no final.

### Arquivos gerados na demonstração

- `data/alertas_tempo_real.jsonl`: o log dos alertas, um por linha. É recriado a cada execução.
- `data/azure_cache.json`: só é atualizado se chegar uma nota que ainda não estava no cache.

---

## 10. Conferir a instalação (recomendado, uma vez)

Testes automatizados, que não precisam de internet nem de chave:

```
python -m tests.test_regras_texto
python -m tests.test_detector_queda
python -m tests.test_fusao
python -m tests.test_online
```

Resultados esperados: `10/10 casos passaram`, `7/7 cenários passaram`, `9/9 verificações passaram` e `12/12 verificações passaram`.

### Pipeline completo e relatórios (opcional)

Para reproduzir as tabelas do relatório técnico, com os vídeos em `data/videos/`:

```
python -m src.video.extrair_pose
python -m src.video.detector_queda
python -m src.anomalias.detectar
python -m src.fusao.tempo_real --verificar
python -m src.video.verificar_online
python -m src.video.relatorio --anotar
```

- `extrair_pose` roda o YOLO em cada vídeo (cerca de 30 a 50 s por clipe em uma CPU de uso geral) e imprime uma tabela com detecção de pessoa de 100%.
- `detector_queda` deve marcar `OK` nos 4 clipes: `queda_01` e `queda_02` com 1 queda, `normal_01` e `normal_02` com 0.
- `tempo_real --verificar` deve terminar com `[OK] os dois modos geram os mesmos alertas`.
- `relatorio --anotar` gera os relatórios em `reports/video/` e os vídeos anotados em `data/video/anotados/`.

---

## 11. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `ModuleNotFoundError: No module named 'cv2'` (ou outro pacote) | Ambiente virtual desativado ou pacote não instalado | Ative o `.venv` (passo 3) e repita o passo 5 |
| `No module named 'src'` | Comando rodado fora da raiz do projeto | Entre na raiz e use `python -m src...` |
| Erro ao instalar o `torch` | Versão do Python não suportada | Use Python 3.11 ou 3.12 (passo 1) e recrie o `.venv` |
| Script `Activate.ps1` bloqueado | Política de execução do PowerShell | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` |
| `KeyError: 'AZURE_LANGUAGE_ENDPOINT'` | Sem `.env` e sem cache de notas | Siga o passo 7 |
| Erro 401 do Azure | Chave ou endpoint errados | Copie de novo em *Keys and Endpoint*, sem espaços |
| A janela de vídeo não abre | Ambiente sem tela, ou Qt no Linux com Wayland | Rode com `--sem-janela`; no Linux, tente `QT_QPA_PLATFORM=xcb python -m src.video.ao_vivo` |
| Avisos `QFontDatabase` no Linux | Pasta de fontes do Qt ausente | Inofensivo. Opcional: `ln -s /usr/share/fonts/truetype/dejavu .venv/lib/python3.X/site-packages/cv2/qt/fonts` (troque `3.X` pela sua versão) |
| Acentos estranhos no terminal do Windows | Codificação do console | `chcp 65001`, ou `$env:PYTHONUTF8 = "1"` (PowerShell) / `set PYTHONUTF8=1` (cmd) |
| Cores do terminal aparecem como códigos | Console antigo do Windows | Use o Windows Terminal ou o PowerShell atual |
| `FileNotFoundError` para o vídeo | Falta o `.mp4` em `data/videos/` | Copie os vídeos do grupo para essa pasta |
| Muito lento | CPU fraca | O sistema pula quadros sozinho. Feche outros programas |

Se o problema persistir, copie a mensagem de erro completa e envie ao grupo.

---

## 12. Onde mudar os parâmetros

Todos os parâmetros ficam em `src/config.py`, com comentários. Para a primeira execução, **não altere nada**. Os valores já estão ajustados para os vídeos do projeto. Os principais grupos:

- **Roteiro simulado:** posiciona os dados simulados em relação ao vídeo. O detector de queda não os lê.
- **Detecção de anomalias:** janelas e limites dos vitais e das prescrições.
- **Fusão:** pesos e janelas que definem PREVENTIVO, MÉDIO e ALTO.
- **Detecção de queda:** os limiares da regra no vídeo, calibrados para o enquadramento dos nossos clipes.

Se trocar os vídeos por outros com enquadramento diferente, o limiar do nível do chão (`QUEDA_LIMIAR_CHAO`) pode precisar de ajuste.

---

## 13. Limitações

- Apenas 4 clipes, e os limiares foram calibrados nos mesmos clipes em que são avaliados.
- Vitais, prescrições e notas são simulados. Os limites clínicos e os pesos da fusão não têm validação clínica.
- As quedas dos vídeos são simuladas e controladas.
- O Azure erra algumas expressões coloquiais (como "sem fôlego"); há uma correção para esse padrão.
- O envio de alertas por Telegram existe no código, mas não foi demonstrado. Por padrão, os alertas saem no terminal e no log.
- Quem aparece nos vídeos precisa ter consentido o uso da imagem.

---

## Sugestão de `.gitignore`

```
.venv/
.env
__pycache__/
*.pt
data/video/anotados/
```
