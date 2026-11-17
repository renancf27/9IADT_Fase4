# Relatório técnico: monitoramento multimodal de pacientes internados, com detecção de queda e alertas em tempo real

**Tech Challenge Fase 4 | PosTech FIAP**
**Integrantes:** [preencher com os nomes do grupo]
**Data:** novembro de 2026

---

## Sumário

1. Resumo
2. Objetivo e escopo
3. Arquitetura e fluxo multimodal
4. Dados
5. Modelos e métodos por tipo de dado
6. Integração com o Azure
7. Resultados
8. Validação e testes
9. Limitações e riscos
10. Aspectos éticos e privacidade
11. Conclusão e trabalhos futuros
12. Reprodutibilidade
- Apêndice A: parâmetros
- Apêndice B: estrutura do repositório e arquivos de entrada e saída
- Referências

---

## 1. Resumo

Este relatório descreve um sistema de triagem que monitora um paciente internado e alerta a equipe médica antes e durante uma queda. O sistema cruza três fontes: o **vídeo** do leito (YOLOv8-pose e uma regra de detecção de queda), o **texto** das notas de enfermagem (Azure AI Language) e **dados estruturados** (sinais vitais e prescrições, com detecção de anomalias). Uma fusão por janelas de tempo combina as fontes e emite alertas de três níveis: PREVENTIVO, MÉDIO e ALTO.

Resultados principais:

- A regra de queda acertou os 4 clipes gravados: 2 de 2 quedas detectadas e 0 de 2 falsos alarmes.
- Na execução ao vivo, o YOLOv8-pose rodou a cerca de 30 ms por quadro em CPU, e a queda foi confirmada 3,6 s depois do início.
- A sequência de alertas da demonstração foi PREVENTIVO (prescrição, 09:00), PREVENTIVO (nota, 10:00), MÉDIO (queda, 10:31:56) e ALTO (vitais alterados, 10:32:00).
- O Azure AI Language classificou corretamente a certeza de 14 das 16 entidades de sintoma testadas. Os dois erros seguem um padrão (“sem fôlego” e “sem ar”) e foram corrigidos por uma regra.

Os vídeos são reais, com quedas simuladas e controladas. Os sinais vitais, as prescrições e as notas são simulados. A avaliação usa apenas 4 clipes, e os limiares foram calibrados nos mesmos clipes. O sistema é apoio à decisão e não tem validação clínica.

---

## 2. Objetivo e escopo

### 2.1 Objetivo

O enunciado propõe monitorar continuamente pacientes com dados multimodais para identificar sinais precoces de risco. Os objetivos técnicos são:

- analisar e fundir diferentes tipos de dado médico (texto, áudio e vídeo);
- usar serviços gerenciados em nuvem para ampliar a capacidade de processamento e inteligência;
- aplicar detecção de anomalias em tempo real para monitoramento preventivo.

### 2.2 Escopo adotado

O enunciado lista três modais. Conforme a orientação do professor, o grupo escolheu **dois: vídeo e texto**. A detecção de anomalias, que é um requisito separado, foi mantida. A tabela resume a situação de cada requisito obrigatório.

| Requisito do enunciado | Situação | Como foi tratado |
|---|---|---|
| Vídeo: processar vídeos clínicos | Atendido | Quatro clipes de um leito, com quedas simuladas e controladas |
| Vídeo: detectar eventos fora do padrão com OpenPose ou YOLOv8 | Atendido | YOLOv8-pose (o enunciado indica “modelos como”; OpenPose não foi usado) |
| Vídeo: relatórios automáticos de desvios | Atendido | Relatório JSON e Markdown por clipe, com quadros-chave e tabela de avaliação |
| Áudio: Azure Speech to Text e análise vocal | Fora do escopo | Modal não escolhido |
| Termos críticos e sentimentos com Azure Text Analytics | Atendido sobre texto | Azure AI Language aplicado às notas de enfermagem (e não à transcrição de áudio) |
| Anomalias em sinais vitais | Atendido | Z-score móvel e limites clínicos |
| Anomalias na evolução de prescrições | Atendido | Variação de dose e de frequência |
| Anomalias nos padrões de movimentação | Parcial | A queda detectada no vídeo é o evento de movimentação anômala; o z-score sobre uma série de movimento não foi implementado |
| Alertas automáticos à equipe | Atendido | Alertas em três níveis, no terminal e em log. O envio por Telegram existe no código, mas não foi demonstrado |
| Integração com serviços Azure | Atendido | Azure AI Language (plano gratuito F0) |
| Datasets sugeridos (PhysioNet e AudioSet) | Não usados | Dados simulados; ver a seção 4.3 |

---

## 3. Arquitetura e fluxo multimodal

### 3.1 Visão geral

```
Notas de enfermagem ──► Azure AI Language ──► regras ──► sintomas críticos ───┐
Vídeo do leito ───────► YOLOv8-pose ──► medidas ──► detector de queda ────────┤
Sinais vitais (CSV) ──► z-score móvel + limites clínicos ──► eventos ─────────┼──► Fusão ──► Alertas
Prescrições (CSV) ────► variação de dose e de frequência ──► eventos ─────────┘
```

O fluxo tem quatro etapas:

1. **Entrada.** Os dados chegam em ordem cronológica, cada um com seu horário: leituras de sinais vitais a cada 10 s, notas, prescrições e os quadros do vídeo.
2. **Processamento por fonte.** Cada fonte é analisada de forma independente e produz um evento ou um indicador: sintomas críticos, queda, vitais alterados ou prescrição anômala.
3. **Fusão.** Os eventos são combinados por janelas de tempo, uma por fonte, em uma pontuação que define a gravidade.
4. **Alerta.** O alerta é exibido no terminal, colorido por gravidade, e gravado em um arquivo de log.

### 3.2 Tempo real

O relógio da simulação é **fictício**: ele liga o vídeo aos dados simulados. Em cada instante, a decisão usa apenas o que já aconteceu naquele momento, então a mesma lógica funciona em tempo real. O sistema tem dois modos, que produzem os mesmos alertas (há uma verificação automática disso):

- **Modo em lote:** processa arquivos já calculados.
- **Modo ao vivo:** o vídeo toca, o YOLO roda a cada quadro e a queda é detectada na hora. Vitais, notas e prescrições chegam em seus horários. Se o computador ficar atrasado, o sistema pula quadros para acompanhar o relógio.

### 3.3 Módulos

| Pacote | Responsabilidade |
|---|---|
| `src/dados` | Geração e validação dos dados simulados e do gabarito |
| `src/texto` | Chamadas ao Azure AI Language, cache e regras de interpretação |
| `src/anomalias` | Detecção de anomalias em vitais e prescrições; experimento de robustez |
| `src/video` | Extração de pose, medidas, detector de queda (lote e ao vivo) e relatórios |
| `src/fusao` | Fusão, alertas, notificação, tempo real e análise de sensibilidade |

---

## 4. Dados

### 4.1 Vídeos

| Clipe | Duração | Quadros (30 fps) | Conteúdo |
|---|---|---|---|
| normal_01 | 34,7 s | 1038 | Deitado, levanta, caminha, senta na cama (27,8 s) e deita |
| normal_02 | 27,0 s | 811 | Movimentos na beira da cama, pegar água e voltar a deitar (~23 s) |
| queda_01 | 44,9 s | 1349 | Deitado, levanta com hesitação, queda controlada ao lado da cama (~35 s), permanece no chão |
| queda_02 | 44,3 s | 1330 | Mesma sequência, com a queda por volta de 33 s |

Os vídeos foram gravados por um integrante do grupo, com câmera fixa. As quedas foram feitas de forma controlada, sobre colchonete. O uso da imagem de quem aparece nos vídeos exige o consentimento da pessoa (seção 10).

### 4.2 Dados simulados

- **Sinais vitais.** Uma leitura a cada 10 s, de 10:00 a 10:40 (241 leituras), de frequência cardíaca (FC), pressão sistólica (PAS), pressão diastólica (PAD) e saturação de oxigênio (SpO₂). O paciente começa estável (FC 78, PAS 122, PAD 78, SpO₂ 97%), com ruído gaussiano (desvios de 2,0, 3,0, 2,0 e 0,6). Às 10:32:00 os valores mudam de uma vez, para FC ~118, PAS ~87, PAD ~53 e SpO₂ ~89%, ficam 60 s no pico e voltam ao normal em mais 60 s. A semente do ruído é fixa (42), então todo o grupo gera os mesmos dados.
- **Prescrições.** Seis registros: Losartana 50 mg em 25/10 e 26/10, e 150 mg em 27/10 às 09:00 (a dose triplicada); Dipirona 1000 mg nos três dias, como controle.
- **Notas de enfermagem.** Nove notas em português, escritas pelo grupo em estilo clínico, com sintomas afirmados, sintomas negados, um sintoma não crítico (dor leve no joelho) e uma expressão coloquial (“sem fôlego”).

| Horário fictício | Evento do cenário |
|---|---|
| 25/10 e 26/10, 09:00 | Losartana 50 mg e Dipirona 1000 mg |
| 27/10, 09:00 | Losartana passa para 150 mg (+200%) |
| 10:00 | Nota: paciente refere tontura e fraqueza ao levantar |
| 10:20 | Nota: paciente fica sem fôlego ao caminhar |
| ~10:31:52 | Queda no vídeo |
| 10:32:00 | Os sinais vitais ficam alterados |
| 10:35 | Nota: paciente encontrado no chão, referindo tontura |

Os valores do cenário ficam em um bloco de configuração chamado ROTEIRO SIMULADO, que só posiciona os dados simulados em relação ao vídeo. O detector de queda não lê nenhum desses valores.

### 4.3 Por que dados simulados

Os datasets sugeridos no enunciado não têm vídeo, sinais vitais e notas em português de um mesmo paciente. O cenário precisava casar a queda do vídeo com a alteração dos vitais e com notas anteriores, e os dados clínicos reais do PhysioNet exigem credenciamento. Por isso o grupo simulou vitais, prescrições e notas, com anomalias injetadas em instantes conhecidos, o que dá um gabarito para medir os acertos. A consequência é que os resultados mostram o comportamento das regras, e não o desempenho clínico.

---

## 5. Modelos e métodos por tipo de dado

### 5.1 Vídeo: YOLOv8-pose e regra de queda

O YOLOv8-pose (modelo nano, `yolov8n-pose.pt`, biblioteca ultralytics) roda na CPU e devolve, para cada quadro, a caixa da pessoa e 17 pontos do corpo com a confiança de cada um. Se houver mais de uma pessoa, usa-se a maior. Pontos com confiança abaixo de 0,3 são ignorados. Dos pontos, calculamos as medidas por quadro:

| Medida | Definição |
|---|---|
| Altura do quadril | Posição vertical do quadril como fração da altura da imagem (0 é a base, 1 é o topo) |
| Ângulo do tronco | Ângulo da linha quadril-ombro com a vertical (0° em pé, 90° deitado) |
| Razão da caixa | Largura dividida pela altura da pessoa (acima de 1, o corpo está na horizontal) |
| Velocidade de descida | Variação da altura do quadril por segundo |

As medidas são suavizadas com uma mediana de cerca de 0,2 s, e falhas de detecção de até 0,5 s são interpoladas. Como são frações da imagem, as medidas não dependem da resolução, mas dependem do enquadramento da câmera.

**Observações nos clipes gravados** (leitura dos gráficos, valores aproximados):

- Em pé ou deitado na cama, a altura do quadril fica entre ~0,47 e ~0,60, por causa do ângulo da câmera. Só nas quedas ela chega ao nível do chão (0,18 a 0,21).
- Deitar na cama e cair têm o tronco na horizontal nos dois casos (~77° a 83° na cama; 88° a 110° no chão), então o ângulo sozinho não separa as duas situações.
- As quedas gravadas são lentas: o quadril leva de 3 a 4 s para chegar ao chão.

**Regra de queda.** Uma queda é confirmada quando quatro condições acontecem em sequência:

1. **Candidata:** o quadril desce 0,15 ou mais em relação ao ponto mais alto dos últimos 2 s.
2. **No chão:** em até 5 s, o quadril fica abaixo de 0,35 e o tronco passa de 60°.
3. **Permanência:** o quadril continua abaixo de 0,35 por 3 s.
4. **Confirmação.** Depois, novos candidatos são ignorados por 10 s.

| Parâmetro | Valor | Justificativa | Medido nos clipes |
|---|---|---|---|
| Descida mínima | 0,15 | Separa movimento normal de queda | Normais até 0,09; quedas 0,22 a 0,26 |
| Janela da descida | 2 s | Escala de tempo de uma queda | |
| Altura do chão | 0,35 | Abaixo disso o quadril está no nível do chão | Quedas terminam em 0,18 a 0,21; normais não passam de 0,47 |
| Ângulo do tronco | 60° | Descarta agachar | Deitado na cama ~77° a 83°; no chão 88° a 110° |
| Tempo para chegar ao chão | 5 s | Cobre quedas lentas | |
| Permanência no chão | 3 s | Evita confundir com sentar no chão por um instante | É a maior parte do atraso de 3,6 s |
| Intervalo entre eventos | 10 s | Evita eventos duplicados | |

Os limiares foram escolhidos no meio da folga entre os dois grupos de clipes, e não encostados nos valores medidos.

**Detector ao vivo.** A mesma regra roda como máquina de estados, quadro a quadro, usando apenas o passado: monitorando, descida rápida, no chão e queda confirmada. Uma candidata é descartada se o quadril não chega ao chão em 5 s ou se a pessoa se levanta antes de 3 s. A janela do vídeo exibe, em texto, o que está sendo calculado: relógio fictício, quadro atual, milissegundos por quadro, fps, atraso, altura do quadril, ângulo do tronco, a descida em 2 s e o estado.

**Relatório automático.** Para cada clipe, o sistema gera um arquivo JSON e um Markdown com arquivo, resolução, fps, duração, percentual de quadros com a pessoa detectada, parâmetros da regra, medidas, eventos (instante no clipe, horário fictício, descida do quadril, altura final, tronco e permanência) e uma conclusão em texto. Para cada queda, salva três quadros (antes, durante e depois) com o esqueleto desenhado. Gera ainda a tabela de avaliação esperado × detectado e, opcionalmente, vídeos anotados.

### 5.2 Texto: Azure AI Language

**Serviços usados.** Azure AI Language, plano gratuito F0, região East US, pelo SDK azure-ai-textanalytics, com o idioma definido como português. Cada nota passa por dois recursos: o **Text Analytics for Health**, que extrai entidades médicas com indicação de certeza, e a **análise de sentimento**.

**Retorno do Azure.** Para cada entidade, o Health devolve:

| Campo | Significado | Exemplo |
|---|---|---|
| texto | O trecho encontrado | tontura |
| categoria | O tipo da entidade | SymptomOrSign, ConditionQualifier, Course |
| certeza | Afirmada ou negada | negative (negada) ou vazia (afirmada) |
| confiança | Confiança do modelo, de 0 a 1 | 1.00 |

O sentimento vem como positivo, negativo, neutro ou misto.

**Interpretação (regras do grupo).**

1. Ficam apenas as entidades da categoria sintoma ou sinal (SymptomOrSign).
2. Descartam-se as de certeza negative: “nega falta de ar” não é sintoma presente.
3. Das restantes, mantêm-se as que casam com a lista de sintomas críticos para queda: tontura, fraqueza, falta de ar ou de fôlego, dispneia, dor no peito, cansaço, taquicardia e desmaio. Por isso “dor leve no joelho” não ativa nada.
4. Se sobrar algum sintoma, a nota é **de risco** e vira contexto de risco por 2 horas.

A confiança é gravada, mas não entra na decisão.

**Correção de um erro sistemático.** Nos testes (seção 7.2), em “sem fôlego” e “sem ar” o Azure entendeu o “sem” como negação e marcou o sintoma como ausente, quando o paciente relata falta de ar. A regra do grupo: se o texto contém “sem fôlego” ou “sem ar”, registra-se dispneia, qualquer que seja a certeza devolvida, no formato `dispneia (sem fôlego)`. A regra cobre só esse padrão, para não inverter as negações corretas (“sem dor”, “sem febre”).

**Sentimento.** Foi inconsistente (por exemplo, “nega falta de ar e dor no peito” saiu negativo, e “sem dor e sem febre” saiu positivo). Ele reage ao vocabulário de sintomas, e não ao estado do paciente. O sentimento é registrado, mas **não é usado na decisão de risco**.

**Do retorno do Azure ao alerta.** Exemplo com a nota das 10:00:

| Etapa | Resultado |
|---|---|
| Azure devolve | tontura (sem certeza), fraqueza (sem certeza), dor no peito (negative) |
| Regras do grupo | tontura e fraqueza são críticas e presentes; dor no peito é descartada |
| Registro da nota | sintomas: tontura; fraqueza. Nota de risco: sim |
| Fusão | Contexto de risco ativo por 2 h (1 ponto) |
| Alerta | notas de risco ativas: 10:00 [tontura; fraqueza] |

**Cache.** Cada resposta do Azure é guardada em um arquivo de cache (JSON), indexada pelo texto da nota. Se a nota já está no cache, não há chamada nem custo; senão, o sistema chama o Azure e grava a resposta. Isso torna a execução reproduzível sem chave.

### 5.3 Sinais vitais

A detecção combina dois métodos, e basta um deles marcar a leitura (OU):

| Método | Como funciona | Parâmetros |
|---|---|---|
| Z-score móvel | Compara cada leitura com as 30 anteriores (5 min) do próprio paciente. Um valor a mais de 3 desvios padrão da média é estranho. Só marca a leitura quando 2 ou mais vitais estão estranhos ao mesmo tempo | janela 30; limiar 3; mínimo 2 vitais |
| Limites clínicos fixos | SpO₂ abaixo de 92; FC abaixo de 50 ou acima de 100; PAS abaixo de 90 | valores ilustrativos |

O z-score usa só o passado (a leitura atual fica fora da janela), então funciona leitura a leitura em tempo real. Cada vital tem um desvio padrão mínimo (FC 1,5; PAS 2,0; PAD 1,5; SpO₂ 0,5) para que uma série quase constante não gere z-scores enormes. Leituras alteradas a menos de 60 s uma da outra formam um único **evento**, com início, fim e quais vitais mudaram.

### 5.4 Prescrições

Cada prescrição é comparada com a anterior do mesmo medicamento. É marcada como anômala quando a dose varia mais de 50% ou quando a frequência muda. Uma prescrição anômala vira contexto de risco por 12 horas.

### 5.5 Fusão e alertas

Cada fonte tem um papel e uma janela de tempo:

| Fonte | Papel | Pontos | Janela |
|---|---|---|---|
| Nota de risco ou prescrição anômala | Contexto | 1 (conta uma vez) | Nota: 2 h; prescrição: 12 h |
| Queda no vídeo | Evento | 2 | 30 s |
| Vitais alterados | Confirmação | 2 | Durante o evento, mais 30 s |

A soma define o nível: **1 ponto = PREVENTIVO**; **2 a 4 = MÉDIO**; **5 ou mais = ALTO**. Todas as combinações:

| Contexto | Queda | Vitais | Pontos | Nível |
|---|---|---|---|---|
| sim | não | não | 1 | PREVENTIVO |
| não | sim | não | 2 | MÉDIO |
| não | não | sim | 2 | MÉDIO |
| sim | sim | não | 3 | MÉDIO |
| sim | não | sim | 3 | MÉDIO |
| não | sim | sim | 4 | MÉDIO |
| sim | sim | sim | 5 | ALTO |

A fusão é avaliada em cada gatilho: nota de risco, prescrição anômala, início de um evento de vitais ou queda. Em cada um, usa só o que já aconteceu naquele instante. Um alerta de gravidade igual ou menor que outro emitido nos últimos 30 minutos é suprimido, e só uma escalada gera novo alerta. A mensagem lista as fontes ativas: queda (horário), vitais alterados (quais e desde quando), notas de risco ativas (horário e sintomas) e a prescrição anômala. Os pesos e limiares são decisões do grupo, sem validação clínica.

---

## 6. Integração com o Azure

| Serviço | Uso no projeto | Plano e região | Observações |
|---|---|---|---|
| Azure AI Language: Text Analytics for Health | Extrai sintomas, categoria e certeza de cada nota | F0 (gratuito), East US | Idioma português |
| Azure AI Language: análise de sentimento | Sentimento de cada nota | F0 (gratuito), East US | Registrado, não usado na decisão |
| Azure Speech to Text | Não usado | | Modal de áudio fora do escopo |

- **Credenciais.** A chave e o endpoint ficam em um arquivo `.env`, que não vai para o repositório.
- **Custo.** O plano gratuito oferece 5.000 transações a cada 30 dias. Cada nota consome cerca de 2 (uma para o Health e uma para o sentimento).
- **Cache.** As respostas ficam em `data/azure_cache.json`. Com o cache presente, a demonstração roda sem internet e sem chave. Para mostrar a chamada real, basta apagar o cache antes da execução.
- **Chamada em tempo real.** No modo ao vivo, cada nota que chega é enviada ao Azure no momento em que chega, se ainda não estiver no cache.

---

## 7. Resultados

### 7.1 Vídeo

**Processamento em lote.** A extração de pose rodou em CPU (AMD Ryzen 5 5600, sem placa de vídeo dedicada) e detectou a pessoa em 100% dos quadros dos 4 clipes.

| Clipe | Quadros | Tempo de processamento | Quadros por segundo |
|---|---|---|---|
| normal_01 | 1038 | 37 s | 28,1 |
| normal_02 | 811 | 28 s | 28,8 |
| queda_01 | 1349 | 47 s | 29,0 |
| queda_02 | 1330 | 44 s | 30,0 |

**Detecção de queda.**

| Clipe | Esperado | Detectado | Maior descida em 2 s | Altura mínima | Instante |
|---|---|---|---|---|---|
| normal_01 | sem queda | não | 0,09 | 0,47 | - |
| normal_02 | sem queda | não | 0,04 | 0,53 | - |
| queda_01 | queda | sim | 0,26 | 0,18 | 35,3 s |
| queda_02 | queda | sim | 0,22 | 0,21 | 33,2 s |

Todos os 4 clipes foram classificados como esperado. As folgas são de cerca de 0,06 na descida (limiar 0,15, entre 0,09 e 0,22) e de cerca de 0,12 a 0,14 na altura do chão (limiar 0,35, entre 0,21 e 0,47). A descida é a folga menor, e o clipe normal_01 é o mais próximo de gerar um falso alarme.

**Execução ao vivo (queda_01).** O que o terminal mostrou, em ordem:

```
10:31:52 [VÍDEO] descida rápida do quadril (0.15 em 2 s): verificando se chega ao chão   (clipe 35.4 s)
10:31:53 [VÍDEO] quadril no nível do chão (0.33) e tronco deitado (62°): confirmando permanência de 3 s   (clipe 36.1 s)
10:31:56 [VÍDEO] QUEDA CONFIRMADA AO VIVO: inicio 35.4 s | confirmada 39.1 s (+3.6 s)
```

| Medida | Valor |
|---|---|
| Tempo de inferência | cerca de 30 ms por quadro |
| Quadros analisados | 1296 de 1349 (96%) |
| Instante da queda, ao vivo | 35,4 s do clipe |
| Instante da queda, em lote | 35,3 s do clipe |
| Atraso até a confirmação | cerca de 3,6 s (descida, chegada ao chão e 3 s de permanência) |

O modo ao vivo e o modo em lote concordam no instante da queda. Os 4% de quadros não analisados correspondem a momentos em que o computador ficou atrasado em relação ao relógio, e o sistema pulou quadros por projeto.

### 7.2 Texto

**Teste com 10 frases.** As frases foram enviadas ao Azure e comparadas com o esperado. Das 16 entidades de sintoma, 14 saíram com a certeza correta.

| # | Frase | Entidades de sintoma (certeza) | Avaliação | Sentimento |
|---|---|---|---|---|
| 1 | Paciente refere tontura e fraqueza ao levantar. | tontura, fraqueza (afirmadas) | correto | negativo |
| 2 | Paciente nega falta de ar e dor no peito. | falta de ar, dor no peito (negadas) | correto | negativo |
| 3 | Paciente relata que está sem fôlego e muito cansado. | fôlego (**negada**), cansado (afirmada) | **erro** em “fôlego” | negativo |
| 4 | Paciente sem dor e sem febre. | dor, febre (negadas) | correto | positivo |
| 5 | Paciente sem ar ao subir escadas. | ar (**negada**) | **erro** | negativo |
| 6 | Paciente refere falta de fôlego aos esforços. | falta de fôlego (afirmada) | correto | negativo |
| 7 | Paciente apresenta dispneia e taquicardia. | dispneia, taquicardia (afirmadas) | correto | negativo |
| 8 | Paciente nega tontura. Refere cansaço leve. | tontura (negada), cansaço (afirmada) | correto | negativo |
| 9 | Paciente sem queixas no momento. | queixas (negada) | correto | positivo |
| 10 | Queixa-se de tontura, mas sem queda. | tontura (afirmada); queda (negada, categoria Course) | correto | negativo |

Os dois erros seguem o mesmo padrão: em “sem fôlego” e “sem ar”, o Azure interpretou “sem” como negação. A regra de correção da seção 5.2 trata esse padrão. As negações “sem dor”, “sem febre”, “nega tontura” e “sem queixas” foram interpretadas corretamente. O sentimento foi inconsistente: as frases 2 e 8 são tranquilizadoras e saíram negativas, enquanto as frases 4 e 9 saíram positivas. Por isso ele não entra na decisão.

**Notas do cenário.** Nas execuções do sistema, as 9 notas foram classificadas como esperado:

| Horário | Nota (resumo) | Resultado do sistema | Contexto de risco |
|---|---|---|---|
| 26/10 20:00 | Estável, sem queixas | sem sintomas críticos | não |
| 27/10 06:30 | Dormiu bem; nega dor e febre | sem sintomas críticos | não |
| 27/10 08:00 | Nega tontura e falta de ar | sem sintomas críticos | não |
| 27/10 09:10 | Medicação conforme prescrição atualizada | sem sintomas críticos | não |
| 27/10 09:40 | Dor leve no joelho; nega tontura | sem sintomas críticos (sintoma não crítico) | não |
| 27/10 10:00 | Refere tontura e fraqueza ao levantar | tontura; fraqueza | **sim** |
| 27/10 10:15 | Orientado a não levantar sem auxílio | sem sintomas críticos | não |
| 27/10 10:20 | Fica sem fôlego ao caminhar | dispneia (sem fôlego), pela regra de correção | **sim** |
| 27/10 10:35 | Encontrado no chão, referindo tontura | tontura | **sim** |

### 7.3 Sinais vitais

**Evento detectado (semente 42).** O detector marcou um evento de 10:32:00 a 10:33:30 (10 leituras), com FC, PAD, PAS e SpO₂ alterados, atraso de 0 s em relação ao início da anomalia e nenhum falso alarme.

**Experimento de robustez.** Para verificar se a escolha do detector não depende de uma semente, repetimos a geração dos vitais com 200 sementes diferentes, em dois cenários: uma anomalia forte (a do projeto) e uma sutil, dentro dos limites clínicos normais (FC +15, PAS −5, PAD −3, SpO₂ −3). O experimento é reproduzível com `python -m src.anomalias.robustez`.

| Cenário | Método | Detectou | Falsos alarmes (total) | Atraso máximo (s) |
|---|---|---|---|---|
| Forte | Z-score (≥ 2 vitais) | 200/200 | 6 | 0 |
| Forte | Limites clínicos | 200/200 | 0 | 0 |
| Forte | Combinado | 200/200 | 6 | 0 |
| Sutil | Z-score (≥ 2 vitais) | 200/200 | 7 | 30 |
| Sutil | Limites clínicos | 0/200 | 0 | - |
| Sutil | Combinado | 200/200 | 7 | 30 |

Leitura dos resultados:

- Com uma anomalia forte, os limites clínicos sozinhos bastam, e o z-score só acrescenta falsos alarmes (6 em 200 simulações).
- Com uma anomalia sutil, que não ultrapassa nenhum limite fixo, só o z-score detecta, com atraso de até 30 s (3 leituras) quando o ruído mascara o início.
- A combinação cobre os dois casos. Os limites pegam o que é perigoso em termos absolutos, e o z-score pega a mudança atípica para aquele paciente. O custo são os falsos alarmes causados por ruído, que a exigência de 2 vitais ao mesmo tempo mantém baixos.

Os dados são sintéticos, com ruído gaussiano simples. Sinais vitais reais têm variações mais complexas.

### 7.4 Prescrições

Das 6 prescrições, apenas a Losartana de 27/10 às 09:00 foi marcada (dose de 50 para 150 mg, +200%). A Dipirona, estável em 1000 mg, não gerou alerta. Resultado: 1 de 1 anomalia detectada e 0 falsos alarmes.

### 7.5 Fusão e alertas

**Sequência da demonstração ao vivo.**

| Horário fictício | Alerta | Motivo |
|---|---|---|
| 09:00:00 | PREVENTIVO | Prescrição de Losartana com dose +200% |
| 10:00:00 | PREVENTIVO | Nota com tontura e fraqueza |
| 10:31:56 | MÉDIO | Queda confirmada ao vivo, com contexto de risco |
| 10:32:00 | ALTO | Os vitais se alteram e confirmam a queda |

Mensagem do alerta ALTO, como exibida no terminal e gravada no log:

```
[ALTO] 10:32:00 - queda detectada em vídeo às 10:31:56; sinais vitais alterados (FC, PAD, PAS, SpO2) desde 10:32:00; notas de risco ativas: 10:00 [tontura; fraqueza], 10:20 [dispneia (sem fôlego)]; prescrição das 09:00: Losartana 150 mg (dose +200%)
```

A nota das 10:35 não gerou novo alerta, porque não eleva a gravidade em relação ao ALTO emitido nos 30 minutos anteriores. No modo em lote, o MÉDIO sai no instante em que a queda é detectada (10:31:52); no modo ao vivo, sai na confirmação (10:31:56), porque a regra exige 3 s de permanência no chão.

**Sensibilidade à sincronia.** Para saber o quanto a fusão depende de a queda e os vitais coincidirem, movemos o instante em que o evento de queda chega (reproduzível com `python -m src.fusao.sensibilidade`). Com os vitais alterados de 10:32:00 a 10:33:30, a queda gera ALTO se o evento chegar **entre 10:31:30 e 10:34:00**, uma janela de 150 s em torno dos vitais. Fora dela, a queda gera só MÉDIO. Portanto o sistema não exige alinhamento ao segundo.

### 7.6 Exemplos de anomalias detectadas

| # | Fonte | Quando (fictício) | Anomalia | Evidência | Alerta |
|---|---|---|---|---|---|
| 1 | Prescrição | 27/10, 09:00 | Losartana de 50 para 150 mg | Variação de +200%, acima do limite de 50% | PREVENTIVO às 09:00 |
| 2 | Texto | 10:00 | Tontura e fraqueza ao levantar | Azure Health: dois sintomas afirmados | PREVENTIVO às 10:00 |
| 3 | Texto | 10:20 | Falta de ar ao caminhar | “Sem fôlego”, corrigido pela regra | Entra como contexto no ALTO |
| 4 | Vídeo | ~10:31:52 (clipe 35,4 s) | Queda ao lado do leito | Descida 0,15 em 2 s; quadril a 0,33; tronco 62°; 3 s no chão | MÉDIO às 10:31:56 |
| 5 | Sinais vitais | 10:32:00 a 10:33:30 | FC, PAD, PAS e SpO₂ alterados | Z-score e limites clínicos | ALTO às 10:32:00 |
| 6 | Texto | 10:35 | Paciente encontrado no chão, com tontura | Azure Health: sintoma afirmado | Sem novo alerta (suprimido) |

---

## 8. Validação e testes

| Teste | O que cobre | Verificações | Resultado esperado |
|---|---|---|---|
| `tests.test_regras_texto` | Regras de interpretação do Azure, com as 10 frases reais | 10 | 10/10 |
| `tests.test_detector_queda` | Detector em lote: queda lenta, deitar na cama, abaixar, agachar, cair e levantar, descida muito lenta e duas quedas | 7 | 7/7 |
| `tests.test_online` | Detector ao vivo igual ao em lote, medidas a partir de keypoints e mensagens de estado | 12 | 12/12 |
| `tests.test_fusao` | Combinações de contexto, queda e vitais, escalada, janelas e supressão | 9 | 9/9 |
| `src.dados.validar_dados` | Coerência entre vitais, prescrições, notas e gabarito | 16 | 16/16 |
| `src.fusao.tempo_real --verificar` | O modo em tempo real gera os mesmos alertas do modo em lote | 1 | `[OK]` |
| `src.video.verificar_online` | O detector ao vivo acha as mesmas quedas do modo em lote nos clipes reais, sem rodar o YOLO | 4 clipes | `[OK]` em todos |

Os testes de queda usam séries sintéticas parecidas com os gráficos dos clipes e cobrem os casos em que a regra pode errar. Os de texto usam saídas reais do Azure.

---

## 9. Limitações e riscos

- **Poucos clipes.** São 4 clipes, e os limiares foram calibrados nos mesmos clipes em que foram avaliados. Acertar os 4 mostra que a regra separa esses clipes, mas não prova que ela generalize. Uma pessoa, uma cama e uma câmera.
- **Faltam clipes difíceis.** Não há clipes de agachar, sentar no chão de propósito ou se curvar para pegar algo no chão. É onde a regra pode errar, e esses casos só foram testados com séries sintéticas.
- **Quedas simuladas.** São controladas e sobre colchonete. Quedas reais são mais rápidas e variadas.
- **Dependência do enquadramento.** Os limiares de altura valem para este ângulo de câmera. Com outra posição, o limiar do chão precisa de ajuste.
- **Casos fora da regra, por projeto.** Descidas muito lentas até o chão e quedas em que a pessoa se levanta em menos de 3 s não são detectadas. A exigência de 3 s de permanência é a maior parte do atraso de cerca de 3,6 s.
- **Dados simulados.** Vitais, prescrições e notas são simulados. Os limites clínicos e os pesos da fusão não têm validação clínica.
- **Azure.** Erra expressões coloquiais como “sem fôlego”. A correção cobre esse padrão, mas outros podem existir. As notas foram escritas em estilo clínico, onde o serviço funcionou melhor, o que favorece o resultado.
- **Movimentação.** O z-score sobre uma série de movimento não foi implementado. A movimentação anômala é coberta pela detecção de queda.
- **Alertas.** O envio por Telegram existe no código, mas não foi demonstrado.
- **Áudio.** O modal de áudio não foi desenvolvido.

---

## 10. Aspectos éticos e privacidade

- **Dados fictícios.** Os sinais vitais, as prescrições e as notas não vêm de pessoas reais.
- **Imagem.** O vídeo de uma pessoa é dado pessoal. O uso da imagem de quem aparece nos vídeos, inclusive na publicação do vídeo de demonstração no YouTube ou Vimeo, exige o consentimento da pessoa. Se preferir, a gravação pode ser feita com o rosto fora do quadro.
- **Triagem, não diagnóstico.** O sistema gera alertas de risco para apoiar a decisão da equipe. Ele não diagnostica e não substitui o julgamento clínico.
- **Vieses.** A detecção de pose pode funcionar de forma desigual com pessoas de mobilidade reduzida, uso de cadeira de rodas, roupas largas ou iluminação ruim, o que não foi avaliado.
- **Falsos alarmes e omissões.** Falsos alarmes causam fadiga de alerta. Omissões (quedas não detectadas) são o risco mais grave em um uso real.
- **Segredos.** A chave do Azure fica em um arquivo `.env` fora do repositório. As respostas do Azure guardadas no cache não contêm a chave.

---

## 11. Conclusão e trabalhos futuros

O sistema demonstrou o fluxo completo do enunciado para os modais de vídeo e texto: análise de vídeo com YOLOv8-pose, uso do Azure AI Language, detecção de anomalias em vitais e prescrições, fusão multimodal e alertas em tempo real, com a queda sendo detectada ao vivo. Os resultados mostram que as regras separam os clipes gravados e que a fusão produz uma escalada coerente de alertas. Eles não são evidência de desempenho clínico.

Trabalhos futuros:

1. Gravar mais clipes, com mais pessoas, ângulos e quedas variadas, e incluir casos difíceis (agachar, sentar no chão). Separar clipes de calibração e de avaliação.
2. Implementar o modal de áudio (Azure Speech to Text e características acústicas de fala) e analisar a série de movimento do vídeo com z-score.
3. Substituir os dados simulados por dados reais ou públicos (por exemplo, sinais vitais do PhysioNet e datasets de quedas), com os cuidados de privacidade.
4. Detectar automaticamente a região do chão e da cama, em vez de limiares de altura fixos.
5. Validar os limiares e os pesos da fusão com profissionais de saúde.
6. Integrar o envio de alertas a canais reais (Telegram, e-mail ou sistema hospitalar).

---

## 12. Reprodutibilidade

O passo a passo de instalação está no `README.md`. Resumo dos comandos, depois de criar o ambiente virtual e instalar as dependências:

```
python -m src.dados.gerar_dados
python -m src.dados.validar_dados
python -m src.texto.analisar_notas         # cria o cache do Azure
python -m src.video.ao_vivo                # demonstração ao vivo
```

Para reproduzir as tabelas deste relatório:

```
python -m src.video.extrair_pose           # pose em cada clipe
python -m src.video.detector_queda         # tabela da seção 7.1
python -m src.anomalias.detectar           # eventos de vitais e prescrições
python -m src.anomalias.robustez           # tabela da seção 7.3
python -m src.fusao.sensibilidade          # janela de sincronia da seção 7.5
python -m src.fusao.tempo_real --verificar
python -m src.video.verificar_online
python -m src.video.relatorio --anotar     # relatórios por clipe e vídeos anotados
```

Os dados simulados usam uma semente fixa, então os resultados dos vitais, das prescrições e das notas são reproduzíveis exatamente. Os resultados do vídeo dependem dos arquivos de vídeo do projeto.

---

## Apêndice A: parâmetros (`src/config.py`)

| Grupo | Parâmetro | Valor |
|---|---|---|
| Roteiro simulado | Vitais alteram em | 27/10/2026 10:32:00 |
| | Segundo do clipe em que os vitais alteram | 43 (início fictício do clipe: 10:31:17) |
| Notas e vitais | Janela do contexto de uma nota | 2 h |
| | Tolerância de confirmação dos vitais | 30 s |
| | Período dos vitais | 10:00 a 10:40, uma leitura a cada 10 s |
| | Semente do ruído | 42 |
| Anomalias | Janela do z-score | 30 leituras |
| | Limiar do z-score | 3,0 |
| | Mínimo de vitais estranhos | 2 |
| | Limites clínicos | SpO₂ < 92; FC < 50 ou > 100; PAS < 90 |
| | Variação de dose brusca | > 50% |
| | Tolerância para juntar leituras em um evento | 60 s |
| Fusão | Contexto de uma prescrição | 12 h |
| | Coincidência entre queda e vitais | 30 s |
| | Supressão de alertas repetidos | 30 min |
| | Pontos: contexto, queda, vitais | 1, 2, 2 |
| | Limiar de MÉDIO e de ALTO | 2 e 5 |
| Queda no vídeo | Descida mínima | 0,15 |
| | Janela da descida | 2,0 s |
| | Altura do chão | 0,35 |
| | Ângulo mínimo do tronco | 60° |
| | Tempo para chegar ao chão | 5,0 s |
| | Permanência no chão | 3,0 s |
| | Intervalo entre eventos | 10,0 s |

---

## Apêndice B: estrutura do repositório e arquivos de entrada e saída

```
TechChallenge4/
├── README.md
├── RELATORIO_TECNICO.md
├── requirements.txt
├── src/
│   ├── config.py
│   ├── dados/       gerar_dados.py, gerar_vitais.py, gerar_prescricoes.py, gerar_notas.py, validar_dados.py
│   ├── texto/       regras.py, analisar_notas.py
│   ├── anomalias/   detectores.py, detectar.py, robustez.py
│   ├── video/       features.py, extrair_pose.py, detector_queda.py, online.py, ao_vivo.py,
│   │                relatorio.py, verificar_online.py
│   └── fusao/       motor.py, sistema.py, executar.py, tempo_real.py, notificacao.py, sensibilidade.py
├── tests/
├── data/
└── reports/
```

**Demonstração ao vivo (`src.video.ao_vivo`).**

| Tipo | Arquivo | Papel |
|---|---|---|
| Entrada | `data/videos/queda_01.mp4` | Vídeo analisado quadro a quadro |
| Entrada | `data/vitais.csv`, `data/notas.csv`, `data/prescricoes.csv` | Dados simulados |
| Entrada | `data/azure_cache.json` | Respostas do Azure; atualizado se chegar uma nota nova |
| Entrada | `.env` | Chave e endpoint do Azure (só se houver chamada) |
| Saída | `data/alertas_tempo_real.jsonl` | Log dos alertas, um por linha |

**Preparação e relatórios.**

| Comando | Gera |
|---|---|
| `gerar_dados` | `data/vitais.csv`, `data/prescricoes.csv`, `data/notas.csv`, `data/gabarito.csv` |
| `extrair_pose` | `data/video/<clipe>_keypoints.csv`, `data/video/<clipe>_features.csv`, `reports/video/<clipe>.png` |
| `detector_queda` | `data/video/eventos_por_clipe.csv`, `data/eventos_video.csv` |
| `anomalias.detectar` | `data/anomalias_vitais.csv`, `data/eventos_vitais.csv`, `data/eventos_prescricoes.csv` |
| `analisar_notas` | `data/azure_cache.json`, `data/analise_notas.csv` |
| `fusao.executar` | `data/alertas.csv` |
| `video.relatorio` | `reports/video/<clipe>.json`, `reports/video/<clipe>.md`, `reports/video/quadros/`, `reports/video/avaliacao.md` e `.csv`; com `--anotar`, `data/video/anotados/<clipe>_anotado.mp4` |

---

## Referências

- Enunciado do Tech Challenge Fase 4, PosTech FIAP.
- Ultralytics, documentação do YOLOv8 (modelos de pose).
- Microsoft, documentação do Azure AI Language (Text Analytics for Health e análise de sentimento).
- PhysioNet: https://physionet.org/
- AudioSet: https://research.google.com/audioset/
