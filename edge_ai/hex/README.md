# Hex de referência — um por passo do módulo Edge AI

Binários prontos de cada passo do curso, para gravar **sem compilar**: repetir um lab,
recuperar uma placa, ou seguir a aula quando o build de alguém falhar. Cada hex
corresponde ao fonte deste repo no commit em que foi gerado; regenerar tudo é um comando
(abaixo).

## Os arquivos

| Arquivo | Passo | Placa | O que tem | Flash / RAM (B) |
|---|---|---|---|---|
| `01_gesture_fabrica_tag.hex` | bloco 03 · demo de gestos | TAG | `01_gesture_recognition`, modelo de fábrica (solution 91278), teclado BLE HID | 320.476 / 65.456 |
| `01_gesture_coleta_tag.hex` | loop 1 · coletar | TAG | o mesmo, com `data_collection.conf`: sem inferência, IMU por NUS | 302.048 / 63.632 |
| `01_gesture_manaus_4gestos_tag.hex` | loop 1 · substituir | TAG | `CURSO_MODELO manaus_4gestos` (solution 95867, 4 classes) | 317.544 / 65.184 |
| `02_anomaly_lm20dk.hex` | anomalia | LM20-DK (B) | `02_anomaly`, vetores embarcados | 62.812 / 8.960 |
| `03_central_uart_texto_lm20dk.hex` | loop 1 · ponte | LM20-DK (B) | `03_central_uart`, ponte de texto; pede o endereço da TAG na serial no boot | 235.616 / 45.404 |
| `04_classify_led_neuton_tag.hex` | loop 2 · modelo original | TAG | `04_classify_led` com o exemplo da Nordic (solution 90449, 50/1/7) | 87.608 / 19.488 |
| `04_classify_led_ventilador_tag.hex` | loop 2 · modelo do curso | TAG | `CURSO_MODELO ventilador_95922` (128/6/4), blocos do ventilador | 89.600 / 24.016 |
| `05_data_forwarder_tag.hex` | loop 2 · coletar | TAG | `05_data_forwarder` do repo: ±4 g / ±1000 dps, 9 canais, LED de estado — o da coleta do dataset de referência | 202.380 / 47.304 |
| `06_mic_check_lm20dk.hex` | Axon · provar o mic | LM20-DK (B) | `06_mic_check`, barra de VU do microfone PDM na VCOM1 | 52.772 / 9.896 |
| `07_ww_kws_lm20dk.hex` | Axon · wake word + comandos | LM20-DK (B) | `07_ww_kws`, "Okay Nordic" + 10 comandos na NPU; estados na VCOM0 | 511.648 / 54.216 |
| `08_cough_detection_lm20dk.hex` | Axon · um zip do Lab | LM20-DK (B) | `08_cough_detection`, detector de tosse; painel na VCOM1 | 143.304 / 25.512 |
| `09_dog_bark_detection_lm20dk.hex` | Axon · outro zip, mesmo molde | LM20-DK (B) | `09_dog_bark_detection`, detector de latido | 143.336 / 25.512 |
| `10_sound_events_lm20dk.hex` | Axon · cinco detectores | LM20-DK (B) | `10_sound_events`, 5 modelos intercalados na NPU, painel com rms e traço bruto | 285.396 / 46.896 |
| `11_benchmark_axon_lm20dk.hex` | benchmark · NPU | LM20-DK (B) | `11_benchmark_npu_vs_cpu` variante Axon: 700 inferências/rajada, latência na VCOM1 | 95.112 / 13.080 |
| `11_benchmark_neuton_lm20dk.hex` | benchmark · CPU | LM20-DK (B) | o mesmo com o modelo Neuton na CPU | 75.056 / 11.528 |

O hex do 03 serve para qualquer aluno: o central **pede o endereço da TAG no
terminal serial a cada boot** (115200 8N1) e só começa a varrer depois de um endereço
válido — um central com o endereço errado nunca conecta.

As placas LM20-DK do curso são a variante **B** (`nrf54lm20dk/nrf54lm20b/cpuapp`); os
hex da DK não servem na variante A.

## Gravar

Só precisa do `nrfutil` com o comando `device`. A TAG grava pelo `DEBUG OUT` da DK
(encaixada e alimentada, o debugger da DK aponta para ela); a DK grava com a TAG **fora**.

```
nrfutil device list                                           # serial da DK
nrfutil device program --firmware edge_ai\hex\<arquivo>.hex --serial-number <serial>
nrfutil device reset --serial-number <serial>
```

Se a placa recusar (`FPROTECT`, ou firmware antigo travando o debugger):

```
nrfutil device recover --serial-number <serial>
```

Log de qualquer um deles por RTT:

```
JLinkRTTLogger -Device NRF54L15_M33 -If SWD -Speed 4000 -USB <serial> -RTTChannel 0 rtt.log     # TAG
JLinkRTTLogger -Device CORTEX-M33 -RTTSearchRanges "0x20000000 0x80000" -USB <serial> -RTTChannel 0 rtt.log   # LM20-DK
```

## Regenerar

```
python edge_ai\hex\build_all.py            # todas
python edge_ai\hex\build_all.py 04 05      # so as que comecam com 04 ou 05
```

O script compila cada variante **pristine** em `build/hex/<nome>/`, aplica as edições
temporárias que o passo exige (blocos do 04) e as
**desfaz** em seguida — o fonte do repo não muda, mesmo se um build falhar. Os hex vêm
do `merged*.hex` do sysbuild quando existe (o 04 precisa de `sysbuild.conf` com
`SB_CONFIG_MERGED_HEX_FILES=y` para gerá-lo), senão do `zephyr.hex` da app.

Depois de regenerar, commite os hex junto com o fonte que os gerou.
