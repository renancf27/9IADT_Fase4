# Relatório de vídeo: queda_01

- Arquivo: `queda_01.mp4` (848x478, 30 fps, 44.9 s)
- Pessoa detectada em 100.0% dos quadros

**Conclusão:** 1 desvio detectado: queda às 10:32:00 (35.3 s do clipe), quadril no chão (0.22) por 9 s.

## Eventos

| Tipo | Instante no clipe | Horário fictício | Queda do quadril em 2 s | Altura final | Tronco | Permanência no chão |
|---|---|---|---|---|---|---|
| queda | 35.3 s | 2026-10-27 10:32:00 | 0.22 | 0.22 | 108° | 9 s |

### Quadros da queda 1

![antes](quadros/queda_01_queda1_antes.jpg)
![durante](quadros/queda_01_queda1_durante.jpg)
![depois](quadros/queda_01_queda1_depois.jpg)

## Medidas ao longo do clipe

![gráfico](queda_01.png)

## Parâmetros da regra

- `queda_delta_altura`: 0.15
- `queda_janela_s`: 2.0
- `limiar_chao`: 0.35
- `tronco_min_graus`: 60
- `confirmacao_s`: 5.0
- `permanencia_min_s`: 3.0
