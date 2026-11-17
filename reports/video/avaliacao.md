# Avaliação da detecção de queda em vídeo

| Clipe | Esperado | Detectado | Acerto | Instante | Horário fictício |
|---|---|---|---|---|---|
| normal_01 | sem queda | 0 | sim | - | - |
| normal_02 | sem queda | 0 | sim | - | - |
| queda_01 | queda | 1 | sim | 35.3 s | 2026-10-27 10:32:00 |
| queda_02 | queda | 1 | sim | 33.2 s | 2026-10-27 10:31:58 |

- Quedas detectadas: 2 de 2
- Falsos alarmes (clipes sem queda com detecção): 0 de 2

## Limitações

- Apenas 4 clipes, e os limiares foram calibrados nos mesmos clipes avaliados.
- Quedas simuladas e controladas; quedas reais são mais rápidas e variadas.
- Os limiares de altura valem para este enquadramento de câmera.
- Não há clipes de agachar ou sentar no chão; são os casos em que a regra pode errar.
