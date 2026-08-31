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
| [`02_anomaly/`](02_anomaly/) | Detecção de anomalia (saúde de engrenagem por vibração): terceira tarefa da engine, FFT no binário, score + limiar. Sem sensor — vetores embarcados | nRF54LM20-DK | ✅ copiado e compilado |
| [`03_central_uart/`](03_central_uart/) | Ponte NUS -> UART para a coleta de dados: recebe as amostras do IMU do tag em modo de coleta e joga na serial do PC. Filtra pelo endereco BLE do tag do aluno | nRF54L15-DK (+ nRF54L15-TAG) | ✅ copiado e compilado |
| [`04_data_forwarder/`](04_data_forwarder/) | **Alternativa ao 03:** coleta pelo caminho oficial da Nordic (CBOR/COBS por NUS) + GUI do Data Forwarder Host. Traz contorno de um bug do zcbor no Windows | nRF54L15-TAG | ✅ compilado e validado |
| [`05_classify_led/`](05_classify_led/) | App minima: IMU → inferencia → LED RGB. Onde o modelo proprio do aluno entra. Vem com o modelo de exemplo da Nordic como andaime | nRF54L15-TAG | ✅ compilado e rodando |
| `06_ww_kws/` | Wake word e comandos de voz via microfone PDM (TFLite → compilador → inferência na NPU) | nRF54LM20-DK + mic PDM | ⏳ a copiar |
| `07_benchmark_npu_vs_cpu/` | Medição comparativa de latência/energia por inferência: NPU vs. CPU | nRF54LM20-DK | ⏳ a montar |

Cada pasta tem seu próprio `README.md` com os comandos de build e o que estudar.

### Ordem de ensino (não é a ordem dos números)

Os números identificam a pasta; a sequência da aula é outra:

```
01  demo pronto (HID)                     "isto funciona"
03  coletar com a ponte simples           "de onde vem o dado"
    -> treinar no Edge AI Lab             "como vira modelo"
01  modelo proprio no app de gestos       fecha o loop 1
05  a engine sozinha, com o modelo         "o framework, sem o resto"
    de exemplo da Nordic
04  coletar pelo caminho oficial          gestos escolhidos pelo aluno
    -> treinar
05  modelo proprio na app minima          fecha o loop 2
```

O **05 vem antes do 04** na explicação: mostrar a engine isolada — quatro chamadas, LED
acendendo — antes de pedir que o aluno colete e treine de novo. Ele já funciona sem treino
nenhum, com o modelo de exemplo da Nordic.

> **[`NOTAS_MATERIAL.md`](NOTAS_MATERIAL.md)** — armadilhas descobertas no hardware durante o
> preparo, com medições. Insumo para os slides: cada item é algo que falha em silêncio ou
> contradiz a intuição.

## Tópicos teóricos

- Introdução ao Edge AI: processamento local vs. nuvem; banda, energia e latência; casos de uso em IoT
- Modelos tinyML (Neuton) no Cortex-M33 sem NPU dedicada
- Pipeline NPU + TensorFlow Lite no Zephyr: modelo TFLite → compilador → alocação RAM/Flash → inferência acelerada (até 15x mais rápida/eficiente que via CPU)
