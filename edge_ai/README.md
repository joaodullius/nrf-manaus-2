# Dias 1–2 — Inteligência Artificial Embarcada (Edge AI) — 10h

Criação e implantação de modelos de IA embarcada no Zephyr RTOS: inferência via CPU (tinyML/Neuton) e via acelerador dedicado (NPU + TensorFlow Lite).

**Hardware:** nRF54LM20-DK (+ nRF54L15-TAG como fonte de IMU, microfone PDM MEMS).

## Exemplos no repositório

Os exemplos ficam **dentro deste repositório**, em pastas numeradas, para o aluno
trabalhar a partir da base do repo em vez de garimpar no SDK. São cópias literais do
**Edge AI Add-on v2.3.0**, com a origem registrada no cabeçalho dos arquivos principais
e a licença Nordic preservada em cada pasta.

| Pasta | Descrição | Kit | Status |
|-------|-----------|-----|--------|
| [`01_gesture_recognition/`](01_gesture_recognition/) | Gestos com IMU e modelo Neuton na CPU; vira teclado BLE HID. Base dos três atos da sessão de Neuton AI: demo pronto → modo de coleta → modelo próprio | nRF54L15-TAG | ✅ copiado e compilado |
| `02_ww_kws/` | Wake word e comandos de voz via microfone PDM (TFLite → compilador → inferência na NPU) | nRF54LM20-DK + mic PDM | ⏳ a copiar |
| `03_benchmark_npu_vs_cpu/` | Medição comparativa de latência/energia por inferência: NPU vs. CPU | nRF54LM20-DK | ⏳ a montar |

Cada pasta tem seu próprio `README.md` com os comandos de build e o que estudar.

## Tópicos teóricos

- Introdução ao Edge AI: processamento local vs. nuvem; banda, energia e latência; casos de uso em IoT
- Modelos tinyML (Neuton) no Cortex-M33 sem NPU dedicada
- Pipeline NPU + TensorFlow Lite no Zephyr: modelo TFLite → compilador → alocação RAM/Flash → inferência acelerada (até 15x mais rápida/eficiente que via CPU)
