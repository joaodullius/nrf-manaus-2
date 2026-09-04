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
| [`03_central_uart/`](03_central_uart/) | Ponte NUS -> UART para a coleta de dados: recebe as amostras do IMU do tag em modo de coleta e joga na serial do PC. Filtra pelo endereco BLE do tag do aluno | nRF54LM20-DK (+ nRF54L15-TAG) | ✅ copiado e compilado |
| [`04_classify_led/`](04_classify_led/) | App minima: IMU → inferencia → LED RGB. Onde o modelo proprio do aluno entra. Parte do exemplo da Nordic (estados de transporte) e troca, por uma linha, para o modelo do curso (velocidade de um ventilador por vibracao, 4 classes, FFT) | nRF54L15-TAG | ✅ validado no ventilador |
| [`05_data_forwarder/`](05_data_forwarder/) | **Loop 2, caminho oficial:** coleta pelo `data_forwarder` da Nordic (CBOR/COBS por NUS, 9 canais) + GUI do Data Forwarder Host + `fwd_to_lab.py` + dataset de referencia do ventilador. LED de estado. Contorno de um bug do zcbor no Windows | nRF54L15-TAG (+ Bluetooth do PC) | ✅ roteiro dos 7 passos validado |
| [`06_mic_check/`](06_mic_check/) | Prova de bancada do microfone PDM (Adafruit 3492): mesma configuracao de PDM do `07_ww_kws`, barra de VU na serial. Valida a fiacao antes do modelo | nRF54LM20-DK + Adafruit 3492 | ✅ validado com o mic na DK |
| [`07_ww_kws/`](07_ww_kws/) | **Axon:** wake word "Okay Nordic" + 10 comandos de voz via microfone PDM, dois modelos TFLite na NPU | nRF54LM20-DK + Adafruit 3492 | ✅ validado na bancada (wake word + comandos) |
| [`08_cough_detection/`](08_cough_detection/) | Um zip do Edge AI Lab na NPU, do jeito mais curto: modelo pronto de tosse + as 4 chamadas da API. Exemplo-molde para qualquer solucao do Lab | nRF54LM20-DK + Adafruit 3492 | ✅ tosse validada na bancada (no 10) |
| [`09_dog_bark_detection/`](09_dog_bark_detection/) | O mesmo molde com outro zip (latido): trocar o modelo nao muda o app; muda a calibracao — este e "gatilho facil" (limiar 0,90 vs 0,50 da tosse) | nRF54LM20-DK + Adafruit 3492 | ✅ latido validado na bancada (no 10) |
| [`10_sound_events/`](10_sound_events/) | Cinco detectores do Lab "ao mesmo tempo" na NPU: multiplexing do Axon, interlayer buffer compartilhado, calibracao por detector | nRF54LM20-DK + Adafruit 3492 | 🔬 parcial: latido/tosse ok; bebe/miado/ronco em investigacao |
| `11_benchmark_npu_vs_cpu/` | Medição comparativa de latência/energia por inferência: NPU vs. CPU | nRF54LM20-DK | ⏳ a montar |
| [`hex/`](hex/) | Um `.hex` pronto por passo dos labs 01-10, para gravar sem compilar (`nrfutil device program`). Regenerados por `hex/build_all.py` | TAG e LM20-DK | ✅ |

Cada pasta tem seu próprio `README.md` com os comandos de build e o que estudar.

### Ordem de ensino

Os números seguem a sequência da aula:

```
LOOP 1 — nos trilhos
  01  demo pronto (HID)                    "isto funciona"
  03  coletar com a ponte simples          "de onde vem o dado"
      -> treinar no Edge AI Lab            "como vira modelo"
  01  modelo proprio no app de gestos      fecha o loop 1

LOOP 2 — solto
  04  a engine sozinha, com o modelo       "o framework, sem o resto"
      de exemplo da Nordic
  05  coletar pelo caminho oficial         gestos escolhidos pelo aluno
      -> treinar
  04  modelo proprio na app minima         fecha o loop 2
```

O **04 vem antes do 05**: mostrar a engine isolada — quatro chamadas, LED acendendo — antes
de pedir que o aluno colete e treine de novo. E o 04 já funciona **sem treino nenhum**, com
o modelo de exemplo da Nordic, então serve de demonstração antes de virar exercício.

> **[`NOTAS_MATERIAL.md`](NOTAS_MATERIAL.md)** — armadilhas descobertas no hardware durante o
> preparo, com medições. Insumo para os slides: cada item é algo que falha em silêncio ou
> contradiz a intuição.

## Tópicos teóricos

- Introdução ao Edge AI: processamento local vs. nuvem; banda, energia e latência; casos de uso em IoT
- Modelos tinyML (Neuton) no Cortex-M33 sem NPU dedicada
- Pipeline NPU + TensorFlow Lite no Zephyr: modelo TFLite → compilador → alocação RAM/Flash → inferência acelerada (até 15x mais rápida/eficiente que via CPU)
