# Dias 1–2 — Inteligência Artificial Embarcada (Edge AI) — 10h

Criação e implantação de modelos de IA embarcada no Zephyr RTOS: inferência via CPU (tinyML/Neuton) e via acelerador dedicado (NPU + TensorFlow Lite).

**Hardware:** nRF54LM20-DK (+ nRF54L15-TAG como fonte de IMU, microfone PDM MEMS).

## Labs planejados

| Lab | Descrição | Kit |
|-----|-----------|-----|
| `neuton_gesture/` | Reconhecimento de gesto/anomalia de movimento via acelerômetro com modelo Neuton (coleta de dados → geração do modelo → flash → validação) | nRF54LM20-DK + IMU |
| `npu_wake_word/` | Wake word e comandos de voz via microfone PDM, pipeline da Nordic Edge AI Lab (TFLite → compilador → inferência na NPU) | nRF54LM20-DK + mic PDM |
| `benchmark_npu_vs_cpu/` | Medição comparativa de latência/energia por inferência: NPU vs. CPU | nRF54LM20-DK |

## Tópicos teóricos

- Introdução ao Edge AI: processamento local vs. nuvem; banda, energia e latência; casos de uso em IoT
- Modelos tinyML (Neuton) no Cortex-M33 sem NPU dedicada
- Pipeline NPU + TensorFlow Lite no Zephyr: modelo TFLite → compilador → alocação RAM/Flash → inferência acelerada (até 15x mais rápida/eficiente que via CPU)
