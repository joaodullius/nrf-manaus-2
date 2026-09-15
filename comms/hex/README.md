# Hex de referência — um por passo do módulo de Comunicação

Binários prontos de cada passo, para gravar **sem compilar**: repetir um lab, recuperar
uma placa, ou seguir a aula quando o build de alguém falhar. Cada hex corresponde ao
fonte deste repo no commit em que foi gerado; regenerar tudo é um comando (abaixo).

> **Falta metade dos labs de Wi-Fi aqui, e é de propósito.** Os labs 7, 9, 10, 11, 12 e
> 13 embutem a **credencial da rede** no binário. Um hex com a senha dentro **é a senha
> em claro**, só que mais difícil de ver — então eles não são versionados. O
> `build_all.py` sabe gerá-los, e a saída vai para `build/hex/_local/`, fora do git. Ver
> "Os que não estão aqui".

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
| `08a_wifi_provisioning_lm20.hex` | Lab 8a | LM20-DK (B) + EB II | provisionamento por SoftAP, SSID `nrf-wifiprov` | 728.140 / 271.813 |
| `08b_wifi_provisioning_ble_lm20.hex` | Lab 8b | LM20-DK (B) + EB II | provisionamento por Bluetooth LE | 678.024 / 320.304 |

Os dois hex do **05** têm tamanho idêntico porque a única diferença é uma constante
(`LAB_PROCEDURE_INTERVAL`); os binários **são** diferentes.

Os hex de initiator servem para qualquer aluno: o firmware **pede o endereço do TAG na
serial a cada boot** (115200 8N1) e só começa a varrer depois de um válido — um
initiator com o endereço errado nunca conecta.

As placas LM20-DK do curso são a variante **B** (`nrf54lm20dk/nrf54lm20b/cpuapp`); os hex
da DK não servem na variante A. Os três hex de Wi-Fi só funcionam com a **nRF7002-EB II
encaixada** — o shield entra na configuração do build, não é detectado em tempo de
execução.

## Os que não estão aqui

| Lab | Por quê | Como gerar |
|---|---|---|
| 7, 9, 10, 11 (Parte B), 12, 13 | credencial da rede embutida | `build_all.py` com `COMMS_REDE_CONF` |
| CS 4 | é roteiro, não tem firmware | — |
| 11 (Parte A) | roda o firmware do **lab 6** | use `06_wifi_shell_lm20.hex` |

Para gerá-los na sala, com a rede da sala:

```
set COMMS_REDE_CONF=C:\rede\minha_rede.conf     # um minha_rede.conf JA preenchido
set COMMS_SERVIDOR_IP=192.168.15.15             # o IP do PC (labs 9, 10, 12, 13)
python comms\hex\build_all.py 07 09 10 11 12 13
```

A saída vai para `build/hex/_local/`, que o `.gitignore` cobre. **Não mova esses arquivos
para cá.**

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
> segunda VCOM, **com** shield sai na primeira. Medido no lab 6.

## Regenerar

```
python comms\hex\build_all.py --list          # o que existe, e o que precisa de credencial
python comms\hex\build_all.py --publicas      # so as versionaveis (as 11 daqui)
python comms\hex\build_all.py 02 05           # so as que comecam com 02 ou 05
```

Cada variante é compilada **pristine** em `build/hex/<nome>/`, com `--sysbuild` e, nos
labs de Wi-Fi, com os `-D<imagem>_SHIELD` / `_SNIPPET` prefixados pelo nome da imagem —
a regra do sysbuild que vale para toda a frente. A credencial de Wi-Fi entra por um
fragmento gerado **fora do repo**, então nenhum build altera um arquivo versionado.

Requisitos: NCS v3.4.0 em `C:/ncs/v3.4.0` e os blobs do nRF70
(`west blobs fetch nrf_wifi`) — ver [`PREREQUISITOS.md`](../../PREREQUISITOS.md).

Depois de regenerar, commite os hex junto com o fonte que os gerou.
