# 03 · Coleta de dados — ponte NUS → serial

Segundo ato da sessão de Neuton AI: sair do demo pronto e **capturar dados do IMU** para
treinar um modelo próprio. A TAG entra em modo de coleta e transmite as amostras por
Bluetooth LE; esta DK recebe e joga na serial do PC.

> **Origem:** cópia de `nrf/samples/bluetooth/central_uart` do **nRF Connect SDK v3.4.0**,
> copiada em 2026-08-30. Licença Nordic preservada em [LICENSE](LICENSE).
> As duas divergências do curso estão marcadas no cabeçalho de `src/main.c` e `prj.conf`.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54L15-TAG** | roda o `01_gesture_recognition` em modo de coleta; lê o IMU e manda por NUS |
| **nRF54LM20-DK** | primeiro **grava a TAG** (ela encaixa no `DEBUG OUT`); depois, com a TAG fora, roda **este** firmware: recebe por NUS e escreve na serial USB |

São só dois kits por aluno, e a DK faz os dois papéis **em sequência**:

1. TAG no `DEBUG OUT` → grava o 01 em modo de coleta e lê o endereço BLE no RTT (Passos 1 e 2)
2. tira a TAG do `DEBUG OUT` — ela segue na bateria CR2032, anunciando
3. grava **este** central no próprio SoC da DK, com o endereço lido (Passo 3)

A ordem importa: enquanto a TAG está encaixada e alimentada, o debugger da DK aponta para
ela, não para o SoC da DK — gravar o central nessa hora gravaria a TAG.

Cada aluno tem o seu par TAG + DK. Como todos os tags anunciam com o mesmo nome, este
central **filtra pelo endereço BLE** do tag do aluno — sem isso ele conectaria no tag
do colega.

## Fluxo

```
TAG (BMI270 @100 Hz)                       nRF54LM20-DK                   PC
  amostra IMU                                                          
  int16 mili-unidades                                                  
        │                                                              
        ▼                                                              
  ble_nus_send()  ──BLE NUS──►  filtro por endereco ──► UART/USB ──► terminal
  "<id> ax,ay,az,gx,gy,gz\r\n"      (so o SEU tag)      serial USB
```

## Sem tempo de coletar? Use o dataset de referência

[`dataset_referencia/`](dataset_referencia/) traz uma coleta pronta do preparo do curso:
`dataset_centrado.csv` sobe direto no Edge AI Lab, e `bruto/` tem os CSVs por classe
para quem quiser rodar o pipeline inteiro sem gravar. Quatro classes (`idle`,
`unknown`, `swipe_right`, `swipe_left`), que são os rótulos 0-3 do enum — modelo
treinado com ele cai no firmware sem editar C.

Leia o [README de lá](dataset_referencia/README.md) antes: tem as limitações medidas,
inclusive a taxa de amostragem dilatada (76-94 Hz em vez de 100).

Ele **não** serve para o `05_data_forwarder`: unidades e fundo de escala são outros.

## Passo 1 — TAG em modo de coleta

Não existe cópia do gesture aqui: usa-se o **próprio `01_gesture_recognition`** com um
fragmento de Kconfig e um build dir separado, para o demo HID continuar intacto. A TAG
fica encaixada no `DEBUG OUT` da DK neste passo e no próximo. No VS Code: build
configuration da TAG com `data_collection.conf` em *Kconfig fragments*.

```
west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild ^
  -d C:\work\nrf-manaus-2\edge_ai\01_gesture_recognition\build_tag_collect ^
  C:\work\nrf-manaus-2\edge_ai\01_gesture_recognition ^
  -- -DEXTRA_CONF_FILE=data_collection.conf
```

O que o [`data_collection.conf`](../01_gesture_recognition/configuration/nrf54l15tag_nrf54l15_cpuapp/data_collection.conf)
liga: `CONFIG_DATA_COLLECTION_MODE=y` (o `main` deixa de rodar inferência) e
`CONFIG_BLE_MODE_NUS=y` (a saída vai por NUS).

## Passo 2 — descobrir o endereço do seu tag

Grave a TAG, abra o RTT e leia a linha **`Identity:`** do boot. Ela vem do
`bt_dev_show_info()` do próprio Zephyr, não é código do curso:

```
[00:00:00.961,829] <inf> bt_hci_core: Identity: EC:EF:40:2D:5E:46 (random)
                                                ^^^^^^^^^^^^^^^^^  ^^^^^^
                                                VALUE              TYPE
```

Essa linha só cabe no log com os buffers aumentados — o `prj.conf` da TAG já traz
`CONFIG_LOG_BUFFER_SIZE` e `CONFIG_SEGGER_RTT_BUFFER_SIZE_UP` em 4096 (ver
[Buffers de log](#por-que-dois-buffers) abaixo). Com os 1024 do Add-on o log corta no
meio de `HW Platform: Nordi` e o `Identity:` some.

Anote VALUE e TYPE. Agora **tire a TAG do `DEBUG OUT`** e deixe-a na bateria: o próximo
passo grava o próprio SoC da DK.

## Passo 3 — central com o seu endereço

Preencha [`meu_tag.conf`](meu_tag.conf) com o que você leu:

```conf
CONFIG_LAB_TAG_ADDR_VALUE="EC:EF:40:2D:5E:46"
CONFIG_LAB_TAG_ADDR_TYPE="random"
```

```
west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp ^
  -d C:\work\nrf-manaus-2\edge_ai\03_central_uart\build_lm20 ^
  C:\work\nrf-manaus-2\edge_ai\03_central_uart ^
  -- -DEXTRA_CONF_FILE=meu_tag.conf
```

No VS Code: build configuration da DK (`nrf54lm20dk/nrf54lm20b/cpuapp`) com
`meu_tag.conf` em *Kconfig fragments*. As DKs do curso são a variante **B**
(nRF54LM20B); a A também compila, com `nrf54lm20a`.

Deixar o endereço vazio **falha o build de propósito** (`CMakeLists.txt`), com a mensagem
explicando onde achar o endereço. Um central sem filtro conectaria no tag errado.

## Passo 4 — ler os dados

O CSV sai na serial USB da nRF54LM20-DK, **115200 8N1**. A DK enumera duas portas COM e
o dado vem em uma delas — na validação foi a **vcom1**, com a vcom0 muda. Se a primeira
não mostrar nada, tente a outra.

O que sai por onde:

| | Canal | Para quê |
|---|---|---|
| CSV do IMU | **serial USB** (uart20) | é o dado a capturar |
| Log do central | **RTT** | conferir `Filtrando pelo tag ...` e `Connected:` quando algo falhar |

Isso é escolha do sample, e é a escolha certa aqui: o `chosen` do `nrf54lm20dk` é
`zephyr,console = &uart20` / `zephyr,shell-uart = &uart20` e **não há** `nordic,nus-uart`,
então os dados da NUS caem no mesmo uart20 do console. Ligar `CONFIG_LOG_BACKEND_UART`
intercalaria linhas de log no meio do CSV e sujaria a captura — por isso o sample manda o
log para RTT e ainda usa `CONFIG_LOG_PRINTK=n`. Só o banner de boot do Zephyr escapa para
a serial.

```
87799 67,9602,535,1,-3,0
87800 62,9608,527,1,-4,0
87801 73,9610,524,0,-5,0
  │    │   │    │  │  │ └─ gz
  │    │   │    │  │  └─── gy
  │    │   │    │  └────── gx
  │    │   │    └───────── az
  │    │   └────────────── ay  (~9600 = 9,6 m/s2 = gravidade, tag deitado)
  │    └────────────────── ax
  └─────────────────────── id sequencial (detecta amostra perdida)
```

Unidades: `int16` em **mili-unidades** (`sensor_value_to_double() * 1000`), 100 Hz,
fundo de escala ±4 g / ±1000 dps. **Não** é o valor bruto do ADC.

## Passo 5 — formatar o dataset (`tools/prep_dataset.py`)

O Lab não aceita o que a serial cospe: ele quer header, colunas com nome canônico,
uma coluna de rótulo numérica e **um arquivo único** com todas as classes.

```
serial:  87801 73,9610,524,0,-5,0          <- id + 6 valores, sem header, sem rotulo
Lab:     acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z,class
         73,9610,524,0,-5,0,2
```

O script (stdlib + `pyserial`, que já vem no toolchain do nRF Connect) faz a ponte:

```bash
# 1. um comando por gesto — grava direto da serial, ja no formato do Lab
python tools/prep_dataset.py record swipe_right --seconds 300
python tools/prep_dataset.py record idle        --seconds 300
#    ... repita para as 8 classes

# 2. junta tudo e valida contra as regras do Lab
python tools/prep_dataset.py merge "dataset/*.csv" --out dataset.csv
```

`record` acha a porta sozinho (procura qual está enviando linhas no formato esperado),
mostra taxa em tempo real e **conta amostras perdidas** pelos buracos na sequência de id.
`merge` recusa subir dataset inválido: menos de 2 classes, menos de 20 amostras numa
classe, ausência da classe 0, valor vazio ou não-inteiro — e sai com código 1.

Quem preferir gravar com o **Serial Terminal** do nRF Connect for Desktop, como a doc da
Nordic descreve, usa `convert` no arquivo salvo em vez de `record`:

```bash
python tools/prep_dataset.py convert swipe_right captura.txt
```

### Unidades: não converter

O Lab aceita **INT16**, e é isso que a serial entrega (mili-unidades). A app alimenta
`nrf_edgeai_feed_inputs()` com `imu_data.raw`, que é a **mesma escala** — treinar em
mili-unidades é auto-consistente com a inferência no device. O exemplo da doc do Lab
mostra float físico (`9.8`), mas é exemplo, não requisito.

### O que o script não faz

**Centralizar gestos discretos.** `swipe`, `knock` e `tap` têm começo e fim, e o pico do
sinal precisa cair no meio da janela de 1 s — senão o treino recebe meio gesto. A Nordic
mantém script próprio para isso, e é melhor usar o dela do que manter uma segunda versão.
A cópia está aqui, em [`tools/segment-center-signal/`](tools/segment-center-signal/) —
leia o [`ORIGEM.md`](tools/segment-center-signal/ORIGEM.md) da pasta antes de rodar: ele
tem o bloco a editar e as quatro armadilhas do script (janela ímpar perde uma linha, ele
renomeia suas colunas, cada arquivo precisa ser múltiplo da janela, e os dois parâmetros
de detecção são chutes que precisam de calibração). Rotações são contínuas e não precisam.

**Enviar para o Lab.** Não há API documentada — o upload é drag-and-drop em
`ai.lab.nordicsemi.com`.

## Passo 6 — treinar e voltar para a TAG

No Lab: *classification*, target = coluna `class`, e em signal processing **window 99**
com **sliding shift 33** para inferência. Não é coincidência: são os mesmos
`INPUT_WINDOW_SIZE` e `INPUT_WINDOW_SHIFT` que o `01_gesture_recognition` já usa.

O treino devolve um zip. Copie **toda** a pasta `nrf_edgeai_generated/` dele para uma
subpasta nova em `01_gesture_recognition/src/nrf_edgeai_generated/nrf54l15tag/`,
aponte o `CURSO_MODELO` do `CMakeLists.txt` para ela e recompile o 01 **com `-p`** e
**sem** o `data_collection.conf`.

⚠️ São **cinco** arquivos, não dois. O `nrf_edgeai_user_types.h` carrega os typedefs do
modelo (`nrf_user_input_t`, `nrf_user_output_t`): mantê-lo do modelo anterior **compila
e infere errado**, sem aviso. E o `-p` não é opcional — o CMake só relê o
`CMakeLists.txt` num build pristine, então sem ele você grava o modelo antigo achando
que trocou.

Confira na TAG pelo log de boot, que já existe no sample (`src/main.c:145`):

```
<inf> main: nRF Edge AI Lab Solution id: 95867
```

O procedimento completo, com as quatro armadilhas, está em
[`src/nrf_edgeai_generated/nrf54l15tag/README.md`](../01_gesture_recognition/src/nrf_edgeai_generated/nrf54l15tag/)
e nas [notas do módulo](../NOTAS_MATERIAL.md).

### Classes (de `inference_postprocessing.h`)

| # | Classe | Nome no script |
|---|---|---|
| 0 | IDLE | `idle` |
| 1 | UNKNOWN | `unknown` |
| 2 | SWIPE_RIGHT | `swipe_right` |
| 3 | SWIPE_LEFT | `swipe_left` |
| 4 | DOUBLE_SHAKE | `double_shake` |
| 5 | DOUBLE_THUMB | `double_thumb` |
| 6 | ROTATION_RIGHT | `rotation_right` |
| 7 | ROTATION_LEFT | `rotation_left` |

O Lab exige alvo começando em 0, e a ordem do enum do lab 01 já satisfaz isso.

## As duas divergências do curso

**1. `src/main.c` — filtro por endereço.** O upstream filtra por UUID da NUS em modo OR e
alimenta o filtro de endereço a partir dos *bonds*, ou seja, conecta em qualquer coisa que
anuncie NUS. Aqui o endereço vem de `CONFIG_LAB_TAG_ADDR_VALUE`, o filtro de UUID sai, e
`bt_scan_filter_enable()` passa a `match_all = true`.

**2. `prj.conf` — buffers de log.** Ver abaixo.

### Por que dois buffers

Os dois vêm em 1024 bytes e a rajada de boot estoura **os dois**. Verificado no hardware:
o log do central cortava em `<inf> bt_hci_core: HCI transport: SDC` e sumiam as linhas
seguintes — inclusive o `Filtrando pelo tag ...`, que é justamente o que confirma em qual
tag este central vai conectar.

Não adianta mexer só no buffer do RTT: com `CONFIG_LOG_MODE_DEFERRED` (o padrão aqui) a
mensagem morre antes, no ring buffer do próprio subsistema de log.

```conf
CONFIG_LOG_BUFFER_SIZE=4096
CONFIG_SEGGER_RTT_BUFFER_SIZE_UP=4096
```

Modo bloqueante (`SEGGER_RTT_MODE_BLOCK_IF_FIFO_FULL`) resolveria também, mas travaria o
tag rodando na bateria sem debugger — que é exatamente o caso de uso da coleta.

## Validado no hardware

**2026-09-02 — setup do curso: TAG + nRF54LM20-DK (variante B).** TAG gravada pelo
`DEBUG OUT` da DK e lida pelo mesmo J-Link com o `prj.conf` novo: boot inteiro no RTT,
prompt `tag:~$`, `Identity: EC:EF:40:2D:5E:46 (random)` e `Solution id`. Depois, TAG na
bateria e o central gravado no SoC da DK (`nrf54lm20dk/nrf54lm20b/cpuapp`):

```
<inf> central_uart: Filtrando pelo tag EC:EF:40:2D:5E:46 (random)
<inf> central_uart: Scan started
<inf> central_uart: Filters matched. Address: EC:EF:40:2D:5E:46 (random) connectable: 1
<inf> central_uart: Connected: EC:EF:40:2D:5E:46 (random)
<inf> central_uart: MTU exchange done
<inf> central_uart: Security changed: EC:EF:40:2D:5E:46 (random) level 2
<inf> central_uart: Service discovery completed
```

CSV na **vcom1** da LM20-DK (a vcom0 muda), ids contíguos. `tools/prep_dataset.py record`
apontado para essa porta: **589 amostras em 6,1 s (96,9 Hz), zero perdidas**.

Consumo: central na LM20B **235.180 B** flash / **45.396 B** RAM · tag em coleta
**302.048 B** flash / **63.632 B** RAM (já com console/shell RTT e buffers de 4096 no
`prj.conf`).

Um detalhe de bancada que vale a lição do [Hardware](#hardware): enquanto uma DK antiga
ainda rodava um central com o mesmo filtro, a LM20 casava o filtro e falhava em
`Failed to connect ..., 0x02` — a TAG aceita um central por vez, e ganha quem varre
primeiro. Apagar o outro central (`nrfutil device recover`) resolveu na hora.

**2026-08-30 — setup de preparo: TAG + nRF54L15-DK como central.** Mesmo fluxo, 549
linhas em 4 s, ~99 Hz; `record` com 598 amostras a 99,6 Hz e zero perdidas; `merge` e
`convert` exercitados, inclusive nos casos de erro (uma classe só recusada com saída 1;
buraco de id detectado num log com o banner de boot no meio).

## Pontos em aberto

**Aviso de pareamento.** Na nRF54L15-DK toda conexão registrava:

```
<err> bt_smp: pairing failed (peer reason 0x3)
<wrn> central_uart: Security failed: ... level 1 err 4
```

O `central_uart` pede segurança porque o sample habilita bonding; o tag em modo de coleta
não exige criptografia na NUS. Na LM20B (2026-09-02) a segurança subiu para *level 2* sem
erro. Num caso ou no outro, **o dado flui normalmente** — a descoberta de serviço
completa e as notificações chegam. É ruído, não falha. Deixado como está para não
divergir mais do sample; se incomodar em aula, dá para parar de pedir segurança no
central.

**Nada mais em aberto no caminho de dados.** As duas dúvidas que ficaram da rodada
anterior foram fechadas contra a doc do Edge AI Lab:

- *escala das unidades* — o Lab aceita INT16, e mili-unidades casam com o que a app
  alimenta na inferência. Não converter. Ver [Unidades](#unidades-não-converter).
- *rotulagem* — resolvida pelo `record`, um arquivo por classe, e pelo `merge`.

O que continua fora do escopo por decisão: a centralização de gestos discretos (script da
Nordic) e o upload (sem API, é drag-and-drop).
