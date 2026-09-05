# Channel Sounding · Lab 2 — Initiator no nRF54LM20-DK: RTT e PBR lado a lado

Fecha o par com o TAG do lab 1 e imprime distância no terminal. É **aqui** que os dois
princípios físicos do Channel Sounding aparecem na prática — a cada procedure, o sample
imprime **três estimativas da mesma distância**:

```
Latest distance estimates on antenna path 0: ifft: 2.31, phase_slope: 2.44, rtt: 2.70 meters
```

| Coluna | Princípio | Como estima (`include/bluetooth/cs_de.h`) |
|---|---|---|
| `ifft` | **PBR** — fase | transformada inversa de Fourier sobre a fase por canal; o pico é o caminho mais curto |
| `phase_slope` | **PBR** — fase | inclinação média da fase em função da frequência |
| `rtt` | **RTT** — tempo | tempo de ida e volta médio dos steps de mode 1 |

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ras_initiator` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE). As duas
> divergências do curso estão marcadas no cabeçalho de `src/main.c`.

> **Precisão.** A própria Nordic classifica o algoritmo deste sample (`cs_de`, marcado
> `[EXPERIMENTAL]`) como referência: "*the accuracy is not representative for Channel
> Sounding and should be replaced if accuracy is important*". Os números que você vai
> ver são o que **um algoritmo simples** tira dos dados — não o teto da tecnologia. O
> lab 5 mostra o que muda com um algoritmo melhor.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54L15-TAG** | reflector do lab 1, **na bateria, fora do `DEBUG OUT`** |
| **nRF54LM20-DK** | roda este firmware; initiator, calcula e imprime |

## Passo 1 — o endereço do seu TAG

É o **mesmo do Edge AI**. O endereço BLE estático vem do próprio chip e não muda com
o firmware, então o `meu_tag.conf` que você preencheu no `edge_ai/03_central_uart`
serve aqui sem alteração:

```
copy ..\..\edge_ai\03_central_uart\meu_tag.conf meu_tag.conf
```

Se precisar reler: é a linha `Identity:` do boot do TAG, no RTT (lab 1).

## Passo 2 — compilar e gravar a DK

TAG **fora** do `DEBUG OUT` (senão o debugger grava o TAG). Confira com
`nrfutil device device-info`: tem que aparecer nRF54LM20.

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/channel_sounding_initiator/build_lm20 C:/work/nrf-manaus-2/comms/channel_sounding_initiator -- -DEXTRA_CONF_FILE=meu_tag.conf
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/channel_sounding_initiator/build_lm20
```

No VS Code: board target `nrf54lm20dk/nrf54lm20b/cpuapp` com `meu_tag.conf` em
*Kconfig fragments*.

Deixar o endereço vazio **falha o build de propósito** (`CMakeLists.txt`). Um initiator
sem filtro conectaria no TAG do colega: os seis TAGs da sala anunciam o mesmo UUID.

## Passo 3 — ler

Serial USB da DK, **115200 8N1**. A DK enumera duas portas COM; o log sai numa delas
(na bancada, a segunda). Sequência esperada:

```
I: Filtrando pelo tag EC:EF:40:2D:5E:46 (random)
I: Connected ...
I: CS capability exchange completed.
I: CS config creation complete. ID: 0
I: CS security enabled.
I: CS procedures enabled.
I: Latest distance estimates on antenna path 0: ifft: 1.02, phase_slope: 1.11, rtt: 1.35 meters
I: Latest distance estimates on antenna path 0: ifft: 0.98, phase_slope: 1.09, rtt: 0.90 meters
```

## Passo 4 — o experimento: RTT × PBR

Sem recompilar nada. Trena na mão.

**A. Distâncias conhecidas.** TAG a 1 m, 3 m e 5 m da DK, linha de visada. Para cada
uma, anote dez linhas. Perguntas:

- Qual coluna acompanha a trena? Qual tem o menor espalhamento?
- `ifft` e `phase_slope` medem a **mesma fase** por métodos diferentes — quanto
  divergem entre si?
- `rtt` mede **tempo**. Um erro de 1 ns em tempo de voo são 30 cm. Qual a resolução
  que você vê nele?

**B. Obstrução e multipath.** TAG a 3 m: (1) corpo entre TAG e DK; (2) TAG encostado
numa superfície metálica. O que a física prevê: os estimadores de **fase** reagem ao
multipath (o sinal refletido soma-se ao direto e distorce a fase), o de **tempo** é
mais grosseiro mas não "salta". Confira se é isso que aparece — e anote onde não é.

**C. Registre.** Média e desvio das três colunas por condição. É o dado que o lab 5
vai revisitar com outro algoritmo.

## Variações (opcional)

O sample tem um `choice` de Kconfig para o step mode. Dois fragmentos deixam isolar
um princípio de cada vez — rebuild **só da DK**, o TAG não muda:

```
-- -DEXTRA_CONF_FILE="meu_tag.conf;pbr_only.conf"   # so mode 2: ifft e phase_slope
-- -DEXTRA_CONF_FILE="meu_tag.conf;rtt_only.conf"   # so mode 1: rtt
```

## Várias bancadas na mesma sala

Seis pares medindo ao mesmo tempo não é condição documentada pela Nordic. Se as medidas
degradarem, escalone o intervalo de procedure por estação:

```
-- -DEXTRA_CONF_FILE=meu_tag.conf -DCONFIG_LAB_PROCEDURE_INTERVAL=<50 + n*12>
```

com `n` = número da estação (0 a 5). O valor está em intervalos de conexão de 20 ms:
50 = 1 s. Zero (default) mantém a escolha do sample (100–200 ms).

## As duas divergências do curso

1. **`src/main.c` — filtro por endereço.** O upstream filtra só pelo UUID do Ranging
   Service em modo OR. Aqui `add_tag_address_filter()` acrescenta o endereço de
   `CONFIG_LAB_TAG_ADDR_VALUE` e `bt_scan_filter_enable()` passa a `match_all = true`.
   Mesmo código do `edge_ai/03_central_uart`.
2. **`src/main.c` — intervalo de procedure.** `CONFIG_LAB_PROCEDURE_INTERVAL`, quando
   diferente de 0, sobrescreve o intervalo escolhido pelo sample.

E `prj.conf` ganha `CONFIG_BT_SCAN_ADDRESS_CNT=1`, o slot do filtro.

## Pegadinhas

- **Gravou o TAG achando que era a DK.** Com o TAG no `DEBUG OUT`, o `west flash` vai
  para o TAG. Tire-o antes.
- **Não conecta.** O endereço em `meu_tag.conf` é o do **seu** TAG? A linha
  `Filtrando pelo tag ...` mostra o que o firmware está usando. Se o TAG estava
  conectado quando você regravou a DK, ele pode ter parado de anunciar: reset no
  TAG (ver pegadinhas do lab 1).
- **Conectou e não mede.** Um segundo initiator (outra DK, um telefone) já pegou o
  TAG — ele só aceita uma conexão. Desligue o outro; `nrfutil device recover` numa DK
  esquecida com firmware antigo.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ras_initiator` e
  `subsys/bluetooth/cs_de/cs_de.c` (os três estimadores, em fonte)
- Nordic, *Bluetooth Channel Sounding Distance Estimation* (doc da biblioteca `cs_de`)
- Nordic, release notes do nRF Connect SDK v2.9.0 — a nota sobre a precisão do sample
- Nordic, webinar *Bluetooth Channel Sounding: From theory to practice on the nRF54L Series and Android*
