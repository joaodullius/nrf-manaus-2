# Hex de referência — um por passo do módulo de Comunicação

Binários prontos de cada passo, para gravar **sem compilar**: repetir um lab, recuperar
uma placa, ou seguir a aula quando o build de alguém falhar. Cada hex corresponde ao
fonte deste repo no commit em que foi gerado; regenerar tudo é um comando (abaixo).

Nenhum hex embute credencial. Nos labs de Wi-Fi que precisam da rede da sala (7, 9, 10,
11, 12, 13), o firmware pede SSID e senha — e, onde há servidor no PC, IP e porta — no
terminal serial no primeiro boot e grava em settings (`src/lab_rede.c` de cada lab).
Nos boots seguintes mostra o que tem gravado e dá 5 s para trocar.

## Os arquivos

| Arquivo | Lab | Placa | O que tem | Flash / RAM (B) |
|---|---|---|---|---|
| `01_cs_reflector_tag.hex` | CS 1 | TAG | reflector RAS, o default do lab | 247.796 / 62.590 |
| `01_cs_reflector_demo_tag.hex` | CS 1 · demo | TAG | o mesmo com `android_ranging.conf;demo.conf;s26.conf` — o da demo com smartphone | 263.216 / 59.878 |
| `02_cs_initiator_lm20.hex` | CS 2 | LM20-DK (B) | initiator RAS com `ifft`, `phase_slope` e `rtt` | 288.256 / 67.536 |
| `02_cs_initiator_pbr_lm20.hex` | CS 2 · só PBR | LM20-DK (B) | o mesmo com `pbr_only.conf` (modo 2: sem a coluna `rtt`) | 288.228 / 67.536 |
| `03_cs_ipt_reflector_tag.hex` | CS 3 | TAG | reflector IPT | 240.876 / 52.888 |
| `03_cs_ipt_initiator_lm20.hex` | CS 3 | LM20-DK (B) | initiator IPT | 274.720 / 54.856 |
| `05_cs_iq_music_lm20.hex` | CS 5 | LM20-DK (B) | IQ para o PC, 1 procedure/s | 299.036 / 83.624 |
| `05_cs_iq_music_demo_lm20.hex` | CS 5 · demo | LM20-DK (B) | o mesmo a ~2/s (`demo.conf`), para o painel ao vivo | 299.036 / 83.624 |
| `06_wifi_shell_lm20.hex` | Lab 6 | LM20-DK (B) + EB II | shell de Wi-Fi da Nordic. **É também o firmware da Parte A do lab 11** | 746.740 / 353.824 |
| `07_wifi_sta_lm20.hex` | Lab 7 | LM20-DK (B) + EB II | associação programática; pede SSID/senha no boot | 565.940 / 188.920 |
| `08a_wifi_provisioning_lm20.hex` | Lab 8a | LM20-DK (B) + EB II | provisionamento por SoftAP, SSID `nrf-wifiprov` | 728.140 / 271.813 |
| `08b_wifi_provisioning_ble_lm20.hex` | Lab 8b | LM20-DK (B) + EB II | provisionamento por Bluetooth LE | 678.024 / 320.304 |
| `09_wifi_tcp_lm20.hex` | Lab 9 | LM20-DK (B) + EB II | telemetria por TCP puro; pede rede e servidor (porta padrão 9000) | 566.772 / 192.200 |
| `10_wifi_http_lm20.hex` | Lab 10 | LM20-DK (B) + EB II | o firmware do 9 com transporte HTTP (porta padrão 8000) | 578.268 / 192.448 |
| `10_wifi_mqtt_lm20.hex` | Lab 10 | LM20-DK (B) + EB II | o firmware do 9 com transporte MQTT (porta padrão 1883) | 572.084 / 193.640 |
| `11_wifi_twt_lm20.hex` | Lab 11 · Parte B | LM20-DK (B) + EB II | negocia TWT sozinho no boot; pede SSID/senha | 569.372 / 266.296 |
| `12_wifi_coex_on_lm20.hex` | Lab 12 | LM20-DK (B) + EB II | coexistência BLE × Wi-Fi com o árbitro ligado (`MPSL_CX=y`, antenas separadas); pede rede e servidor (porta padrão 5001) | 754.376 / 374.508 |
| `12_wifi_coex_off_lm20.hex` | Lab 12 | LM20-DK (B) + EB II | o mesmo com o árbitro desligado (`MPSL_CX=n`) | 753.820 / 374.492 |
| `13_wifi_location_lm20.hex` | Lab 13 | LM20-DK (B) + EB II | varredura de APs enviada ao PC; pede rede e servidor (porta padrão 9000) | 564.656 / 187.512 |

Os dois hex do **05** têm tamanho idêntico porque a única diferença é uma constante
(`LAB_PROCEDURE_INTERVAL`); os binários **são** diferentes.

Os hex de initiator servem para qualquer aluno: o firmware **pede o endereço do TAG na
serial a cada boot** (115200 8N1) e só começa a varrer depois de um válido — um
initiator com o endereço errado nunca conecta. Os hex de Wi-Fi dos labs 7, 9, 10, 11,
12 e 13 seguem o mesmo princípio com a rede: pedem no primeiro boot, gravam em settings
e reaproveitam nos seguintes. Uma regravação normal (`west flash`, `nrfutil device
program`) não apaga a `storage_partition`; `nrfutil device recover` apaga, e o prompt
volta.

As placas LM20-DK do curso são a variante **B** (`nrf54lm20dk/nrf54lm20b/cpuapp`); os hex
da DK não servem na variante A. Os hex de Wi-Fi só funcionam com a **nRF7002-EB II
encaixada** — o shield entra na configuração do build, não é detectado em tempo de
execução.

## Os que não estão aqui

| Lab | Por quê |
|---|---|
| CS 4 | é roteiro, não tem firmware |
| 11 (Parte A) | roda o firmware do **lab 6**: use `06_wifi_shell_lm20.hex` |

## Gravar

Só precisa do `nrfutil` com o comando `device`. O TAG grava pelo `DEBUG OUT` da DK
(encaixado e alimentado, o debugger da DK aponta para ele); a DK grava com o TAG **fora**.

```
nrfutil device list                                           # serial da DK
nrfutil device program --firmware comms\hex\<arquivo>.hex --serial-number <serial>
nrfutil device reset --serial-number <serial>
```

Se a placa recusar (`FPROTECT`, ou firmware antigo travando o debugger):

```
nrfutil device recover --serial-number <serial>
```

> **Com a EB II encaixada, o console troca de VCOM.** O shield move o `zephyr,console` da
> `uart20` para a `uart30`, e isso troca a porta serial do PC: **sem** shield o log sai na
> segunda VCOM, **com** shield sai na primeira. Medido no lab 6. É nessa porta que o
> prompt de SSID/senha aparece.

## Regenerar

```
python comms\hex\build_all.py --list          # as variantes
python comms\hex\build_all.py                 # todas
python comms\hex\build_all.py 02 05           # so as que comecam com 02 ou 05
```

Cada variante é compilada **pristine** em `build/hex/<nome>/`, com `--sysbuild` e, nos
labs de Wi-Fi, com os `-D<imagem>_SHIELD` / `_SNIPPET` prefixados pelo nome da imagem —
a regra do sysbuild que vale para toda a frente. O hex copiado é o `merged_<board>.hex`
do sysbuild (`SB_CONFIG_MERGED_HEX_FILES=y` em todos os `sysbuild.conf`).

Requisitos: NCS v3.4.0 em `C:/ncs/v3.4.0` e os blobs do nRF70
(`west blobs fetch nrf_wifi`) — ver [`PREREQUISITOS.md`](../../PREREQUISITOS.md).

Depois de regenerar, commite os hex junto com o fonte que os gerou.
