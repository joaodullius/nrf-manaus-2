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
| `03_central_uart_texto_lm20dk.hex` | loop 1 · ponte | LM20-DK (B) | `03_central_uart` filtrando pela TAG de referência, ponte de texto | 235.264 / 45.396 |
| `03_central_uart_binario_lm20dk.hex` | loop 2 · plano B | LM20-DK (B) | o mesmo com `binary_bridge.conf` (bytes intactos, MTU 247) | 235.248 / 49.768 |
| `04_classify_led_neuton_tag.hex` | loop 2 · modelo original | TAG | `04_classify_led` com o exemplo da Nordic (solution 90449, 50/1/7) | 87.608 / 19.488 |
| `04_classify_led_ventilador_tag.hex` | loop 2 · modelo do curso | TAG | `CURSO_MODELO ventilador_95922` (128/6/4), blocos do ventilador | 89.600 / 24.016 |
| `05_data_forwarder_sample_tag.hex` | loop 2 · coletar | TAG | `05_data_forwarder` como o sample: ±2 g / ±500 dps, 9 canais, LED de estado | 202.380 / 47.304 |
| `05_data_forwarder_4g_tag.hex` | loop 2 · coletar (curso) | TAG | o mesmo com o fundo de escala editado: **±4 g / ±1000 dps** — o da coleta do dataset de referência | 202.380 / 47.304 |

⚠️ **Os dois hex do 03 filtram pelo endereço da TAG de referência** (`EC:EF:40:2D:5E:46`,
`random`). Servem na bancada do instrutor e como referência. O aluno **tem de compilar o
dele** com o endereço da própria TAG em `meu_tag.conf` — um central com o endereço errado
nunca conecta.

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
temporárias que o passo exige (fundo de escala do 05, blocos do 04, endereço do 03) e as
**desfaz** em seguida — o fonte do repo não muda, mesmo se um build falhar. Os hex vêm
do `merged.hex` do sysbuild quando existe, senão do `zephyr.hex` da app.

Depois de regenerar, commite os hex junto com o fonte que os gerou.
