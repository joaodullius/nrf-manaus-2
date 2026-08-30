# 01 · Reconhecimento de gestos (Neuton na CPU)

Primeiro exemplo do módulo Edge AI. O tag lê o IMU, roda um modelo Neuton **na CPU** do nRF54L15 e se apresenta ao PC como um **teclado Bluetooth LE (HID)** — cada gesto vira uma tecla.

> **Origem:** cópia literal de `applications/gesture_recognition` do
> **Edge AI Add-on for nRF Connect SDK v2.3.0** (tag `v2.3.0`, commit `1c24f3a`),
> copiada em 2026-08-29. O código está aqui para o aluno usar a base do repositório
> em vez de garimpar no SDK — não é código do curso.
> `src/main.c` e o `prj.conf` da TAG carregam o caminho upstream no cabeçalho.
> Licença original preservada em [LICENSE](LICENSE) (LicenseRef-Nordic-5-Clause).

**Não copiamos** a pasta `images/` do upstream: são 104 MB de GIFs (de um total de 105 MB).
Para ver as animações de cada gesto e da orientação inicial do tag, consulte o
[README.rst](README.rst) original renderizado na documentação do Add-on.

## Hardware

- **nRF54L15-TAG** (`nrf54l15tag/nrf54l15/cpuapp`) — IMU integrado
- PC com Bluetooth LE para receber o HID

## Como a inferência roda a partir da amostragem

```
k_timer 10 ms ──► sensor_sample_fetch/channel_get ──► phys x1000 -> int16[6]
 (nao ha IRQ)          (Sensor API do Zephyr, BMI270)              │
                                                                   ▼
                                              nrf_edgeai_feed_inputs()  (1 amostra)
                                                32 de 33 devolvem INPROGRESS
                                                                   │
                                                                   ▼
                                              nrf_edgeai_run_inference()  (Neuton, CPU)
                                                classe + probabilidades
                                                                   │
                                                                   ▼
        inference_postprocess()  ──►  should_act_on_prediction()  ──►  ble_hid_send_key()
         filtro 1: concordancia          filtro 2: debounce 800 ms        tabela modo/classe
```

### Leitura do sensor

Usa a **Sensor API padrão do Zephyr**, nada proprietário — o IMU é um **BMI270**
(`DEVICE_DT_GET_ONE(bosch_bmi270)`):

- `sensor_attr_set()` na inicialização: fundo de escala (±4 g, ±1000 dps),
  oversampling e frequência de amostragem.
- `sensor_sample_fetch()` + `sensor_channel_get()` a cada leitura.
- `sensor_value_to_double()` converte para grandeza física.

**Não há trigger de data-ready.** O módulo arma um `k_timer` com período
`1000 / data_rate_hz` = **10 ms**; o handler chama o callback, que faz `k_sem_give()`.
O `main` está bloqueado em `k_sem_take(K_FOREVER)`. Ou seja: **amostragem por timer de
software, com polling do sensor** — não sincronizada com o ODR interno do BMI270.
Vale saber disso antes de coletar dados para treinar modelo próprio.

### O que o modelo recebe

Atenção ao nome do campo: `imu_data_t.raw` **não é o valor bruto do ADC**. É
`sensor_value_to_double() * 1000` truncado para `int16_t` — ou seja, a grandeza física
em mili-unidades.

- **Neuton (CPU)** recebe `int16_t[6]` — o campo `.raw`.
- **Axon (NPU)** recebe `flt32_t[6]` — `.phys * 1000`, a **mesma escala** em ponto flutuante.
- **Não há pré-processamento na aplicação**: normalização e extração de atributos estão
  dentro do modelo, geradas pelo Edge AI Lab.

### A janela e os dois filtros

- A aplicação **não** monta a janela: entrega uma amostra por vez a
  `nrf_edgeai_feed_inputs()`, e o runtime acumula. `NRF_EDGEAI_ERR_INPROGRESS`
  em 32 de cada 33 chamadas é o comportamento normal, **não erro**.
- A janela tem `INPUT_WINDOW_SIZE = 99` amostras (≈ 1 s de movimento) e desloca de
  `INPUT_WINDOW_SHIFT = 33` em 33: **uma inferência a cada ~330 ms**, reaproveitando
  66 amostras da janela anterior. A primeira inferência só sai ≈ 1 s depois de ligar.
- **Filtro 1 — `inference_postprocess()`** (código do exemplo, não API): acumula até 3
  predições seguidas da mesma classe e exige `min_repeat_count` repetições com **média**
  das probabilidades acima do limiar. Reprovou, vira `UNKNOWN`.

  | Classe | Repetições mín. | Limiar |
  |---|---|---|
  | `SWIPE_LEFT` · `SWIPE_RIGHT` | 2 | 0,80 |
  | `DOUBLE_SHAKE` | 2 | 0,70 |
  | `DOUBLE_THUMB` (double tap) | 3 | 0,70 |
  | `ROTATION_RIGHT` · `ROTATION_LEFT` | 2 | 0,70 |
  | `IDLE` · `UNKNOWN` | 0 | — |

- **Filtro 2 — `should_act_on_prediction()`** (também código do exemplo): *debounce* de
  **800 ms** entre ações, do qual as rotações são isentas (volume precisa repetir).

### Funções da API Edge AI usadas

São só **sete** — todo o resto do arquivo é código da aplicação:

| Função | Papel |
|---|---|
| `nrf_edgeai_user_model()` | handle do modelo gerado (`nrf_edgeai_t *`) |
| `nrf_edgeai_is_runtime_compatible()` | confere modelo × versão do runtime |
| `nrf_edgeai_init()` | prepara buffers internos e a janela |
| `nrf_edgeai_runtime_version()` | versão do runtime (log) |
| `nrf_edgeai_solution_id_str()` | id da solução do Edge AI Lab (log) |
| `nrf_edgeai_feed_inputs()` | empurra **uma** amostra; devolve `INPROGRESS` |
| `nrf_edgeai_run_inference()` | roda a janela; resultado em `model->decoded_output` |

Arquivos para ler: [`src/main.c`](src/main.c) (laço, filtro 2 e ação),
[`src/inference_postprocessing.c`](src/inference_postprocessing.c) (filtro 1) e
[`src/hw_modules/sensor/imu/imu.c`](src/hw_modules/sensor/imu/imu.c) (Sensor API + timer).

## Tabela de gestos

Duas modalidades, alternadas pelo botão; o LED indica qual está ativa.

| Gesto | Controle de apresentação · LED azul | Controle de música · LED verde |
|---|---|---|
| Double shake | F5 | Play/pause |
| Double tap | Escape | Mute |
| Swipe right | Seta direita | Próxima |
| Swipe left | Seta esquerda | Anterior |
| Rotation clockwise | — | Volume + |
| Rotation counter-clockwise | — | Volume − |

O modelo reconhece **8 classes**: as 6 acima, mais `IDLE` (sem gesto) e `Unknown`.

> O modelo de fábrica foi treinado com um dataset limitado. Use os pulsos mais que o
> braço inteiro, e respeite a orientação inicial do tag — a taxa de acerto depende disso.

## Build

O exemplo compila a partir deste repositório, apontando o `west` do workspace do Add-on
para a pasta daqui. Entre no ambiente do toolchain primeiro:

```bash
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 --terminal
```

Depois, de dentro de `C:\ncs\sdk-edge-ai`:

```bash
west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d C:\work\nrf-manaus-2\build\01_gesture C:\work\nrf-manaus-2\edge_ai\01_gesture_recognition
```

```bash
west flash -d C:\work\nrf-manaus-2\build\01_gesture
```

### Build pelo VS Code (extensão nRF Connect)

Na build configuration (board `nrf54l15tag/nrf54l15/cpuapp`, SDK v3.4.0), preencha:

| Campo | Valor |
|---|---|
| *Extra CMake arguments* | `-DEXTRA_ZEPHYR_MODULES=C:/ncs/sdk-edge-ai/edge-ai` |
| *Kconfig fragments* / `CONF_FILE` | **deixar vazio** |

O módulo extra é obrigatório: o SDK `C:\ncs\v3.4.0` não traz o `edge-ai` — ele vive no
workspace separado `C:\ncs\sdk-edge-ai` e é quem define `CONFIG_NRF_EDGEAI`. O `CONF_FILE`
fica vazio porque o [`CMakeLists.txt`](CMakeLists.txt) já aponta o
`APPLICATION_CONFIG_DIR` para `configuration/<board>`, e o `prj.conf` certo é encontrado
sozinho.

Alternativa: em *Manage SDKs → Add existing*, registrar `C:\ncs\sdk-edge-ai` como SDK (mesmo
toolchain v3.4.0) e selecioná-lo na build configuration — aí o módulo já vem no workspace e
o argumento extra não é necessário.

### O build padrão já é o que queremos

Sem `FILE_SUFFIX`, vale o `prj.conf` — e ele já traz as três escolhas do curso:

| Kconfig | Valor | Por quê já vem assim |
|---|---|---|
| `CONFIG_NRF_EDGEAI_GESTURE_RECOGNITION_MODEL_NEUTON` | `y` | Axon depende de `SOC_NRF54LM20B`; na nRF54L15 só há Neuton |
| `CONFIG_BLE_MODE_HID` | `y` | padrão fora do modo de coleta |
| `CONFIG_BLE_MITM_AUTH` | `y` | `default y` no Kconfig e explícito no `prj.conf` |

⚠️ Não use `prj_release.conf` nesta aula: ele **desliga** o `CONFIG_BLE_MITM_AUTH`.

Consumo do build de referência: **FLASH 285.052 B (40,0%)** · **RAM 54.152 B (20,7%)**.
Com o fragmento `rtt_log.conf` (ver abaixo): **FLASH 320.460 B (45,0%)** ·
**RAM 59.313 B (22,6%)** — o shell custa ~35 kB de flash e ~5 kB de RAM.

## Console e terminal por RTT

A TAG **não tem UART de console**: o `nrf54l15tag_nrf54l15_cpuapp.dts` não declara
`zephyr,console` nem `zephyr,shell-uart`, e não há USB-serial na placa. Todo o texto sai
pelo **RTT** (buffer em RAM lido pelo debugger J-Link do DK em que a TAG está encaixada).

O `prj.conf` do upstream já liga `CONFIG_USE_SEGGER_RTT` + `CONFIG_LOG` — ou seja, os
`LOG_INF()` já saíam. O que faltava era o **console** (`printk`) e o **shell**.

Isso fica num **fragmento opcional**, não no `prj.conf`: assim o
[`prj.conf`](configuration/nrf54l15tag_nrf54l15_cpuapp/prj.conf) continua **byte a byte
igual ao do SDK** e o aluno vê exatamente o que o curso acrescenta.

[`configuration/nrf54l15tag_nrf54l15_cpuapp/rtt_log.conf`](configuration/nrf54l15tag_nrf54l15_cpuapp/rtt_log.conf):

```conf
CONFIG_RTT_CONSOLE=y
CONFIG_SHELL=y
CONFIG_SHELL_BACKEND_RTT=y
CONFIG_SHELL_BACKEND_SERIAL=n
CONFIG_SHELL_PROMPT_RTT="tag:~$ "
```

Como aplicar:

```bash
west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild ^
  -d C:\work\nrf-manaus-2\edge_ai\01_gesture_recognition\build_tag ^
  C:\work\nrf-manaus-2\edge_ai\01_gesture_recognition ^
  -- -DEXTRA_CONF_FILE=rtt_log.conf
```

No VS Code, campo *Kconfig fragments* da build configuration: `rtt_log.conf`.

O caminho **relativo** funciona porque o `CMakeLists.txt` aponta `APPLICATION_CONFIG_DIR`
para `configuration/<board>`, e o Zephyr resolve `EXTRA_CONF_FILE` relativo contra esse
diretório (`zephyr/cmake/modules/kconfig.cmake`, `merge_config_files`). Sem o
`-DEXTRA_CONF_FILE`, o build é o do SDK, sem alteração nenhuma.

| Kconfig | O que habilita |
|---|---|
| `CONFIG_RTT_CONSOLE` | `printk()` sai por RTT — é o que imprime o CSV do modo de coleta (`src/main.c:436`) e a passkey do pareamento |
| `CONFIG_SHELL` + `CONFIG_SHELL_BACKEND_RTT` | terminal interativo por RTT (`kernel version`, `kernel uptime`, `device list`, …) |
| `CONFIG_SHELL_BACKEND_SERIAL=n` | explícito porque não há UART de console no DTS |

### Um canal, um escritor

Ao ligar `CONFIG_SHELL`, o Zephyr ativa `CONFIG_SHELL_LOG_BACKEND=y` e o
`CONFIG_LOG_BACKEND_RTT` passa a `n` sozinho (seu `default y if !SHELL_LOG_BACKEND`).
Isso é o comportamento desejado: **o log passa a sair pelo shell**, e não há dois
escritores disputando o buffer RTT 0. Confirme no build:

```bash
grep -E "LOG_BACKEND_RTT|SHELL_LOG_BACKEND" build_tag/01_gesture_recognition/zephyr/.config
# CONFIG_LOG_BACKEND_RTT is not set
# CONFIG_SHELL_LOG_BACKEND=y
```

### Como abrir o terminal

A TAG é programada e depurada pelo debugger **do DK** em que ela está encaixada
(header P1 da TAG no header `DEBUG OUT` do nRF54L15 DK) — quando encaixada, ela vira o
alvo padrão do DK. Alimente a TAG por **bateria CR2032 OU** por `VDD SWD0` no DK,
**nunca os dois**.

| Ferramenta | Como |
|---|---|
| **VS Code (nRF Connect)** | painel *Connected Devices* → dispositivo → ícone **Start RTT terminal** |
| **west** | `west rtt -d C:\work\nrf-manaus-2\edge_ai\01_gesture_recognition\build_tag` (runner `jlink`; force com `-r jlink` se preciso) |
| **SEGGER** | `JLinkRTTViewer` (ou `JLinkRTTClient` após um `JLinkExe`), target `nRF54L15` |

Com o shell ativo, o prompt `tag:~$` aparece depois do boot, os logs continuam
rolando e o terminal aceita digitação ao mesmo tempo.

⚠️ O comando `log` **não existe** neste build (precisaria de `CONFIG_LOG_CMDS=y`), e o
comando de threads é `kernel thread list`, não `kernel threads`. O nível de log é o de
compilação (`CONFIG_LOG_DEFAULT_LEVEL=3`, INF) — mensagens `LOG_DBG` não são compiladas
e nenhum comando de shell as traz de volta.

### Testado na TAG

Gravado com `nrfutil` (MCUboot + `zephyr.signed.hex`, `verify=VERIFY_READ`) numa TAG
encaixada no `DEBUG OUT` de um nRF54LM20 DK, e lido pelo servidor RTT do J-Link:

```
*** Booting nRF Connect SDK v3.4.0-99553055607b ***      <- printk (RTT_CONSOLE)
*** Using Zephyr OS v4.4.0-bf801e4e3d19 ***
*** Using Edge AI Add-on v2.3.0-1c24f3a94ac9 ***
[00:00:00.767,529] <inf> ADXL367: ADXL367 passed self-test   <- LOG pelo shell
[00:00:00.952,959] <inf> fs_nvs: 8 Sectors of 4096 bytes

tag:~$ kernel version
Zephyr version 4.4.0
tag:~$ kernel uptime
Uptime: 22687 ms
tag:~$ device list
devices:
- adxl367@1d (READY)
- bme688@76 (READY)
- bmi270@0 (READY)      <- o IMU do exemplo, confirmando que o alvo e a TAG
```

O `device list` mostrando `bmi270` é a prova de que o debugger do DK está mesmo
redirecionado para a TAG, e não para o SoC do próprio DK.

### E por BLE, sem debugger? (log via NUS)

Pergunta natural: dá para largar o J-Link e ler o log pelo celular, via NUS? Existem três
caminhos, e **nenhum deles é o que o sample já faz hoje**:

| Caminho | Origem | O que manda | Estado neste sample |
|---|---|---|---|
| `CONFIG_BLE_MODE_NUS` | do próprio sample | **amostras do IMU** em CSV (`ble_nus_send()`), não log | existe, mas `depends on DATA_COLLECTION_MODE` — desliga a inferência |
| `CONFIG_LOG_BACKEND_BLE` | Zephyr (`subsys/logging/backends/log_backend_ble.c`) | **o log de verdade**, por notificação | não usado; `select EXPERIMENTAL` |
| `CONFIG_SHELL_BT_NUS` | NCS (`nrf/subsys/shell/shell_bt_nus.c`) | **o shell inteiro** por NUS | não usado; precisa de `shell_bt_nus_enable(conn)` no código |

**O que o sample tem hoje não é logging.** `CONFIG_BLE_MODE_NUS` só é selecionável com
`CONFIG_DATA_COLLECTION_MODE=y`, e nesse modo o `main` **não roda inferência** — ele
manda `"<id> ax,ay,az,gx,gy,gz
"` por NUS para você coletar dataset. É um canal de
dados, não de log.

**O caminho pronto para log é o do Zephyr**, `CONFIG_LOG_BACKEND_BLE=y`: ele registra
sozinho (`LOG_BACKEND_DEFINE(..., true)`) um serviço GATT com os **mesmos UUIDs do NUS**
(`6E400001/2/3`), então o nRF Connect / nRF Toolbox enxerga como um terminal NUS comum.
Requisitos que este build já satisfaz: `CONFIG_BT=y` e
`CONFIG_LOG_PROCESS_THREAD_STACK_SIZE>=2048`.

⚠️ **Colisão de UUID:** `CONFIG_BT_NUS` (o do sample) e `CONFIG_LOG_BACKEND_BLE` (o do
Zephyr) declaram serviços GATT distintos com os **mesmos UUIDs**. Ligar os dois juntos
faz o dispositivo anunciar dois NUS — escolha um. Na prática: log por BLE combina com o
modo HID (padrão), não com o modo de coleta.

⚠️ Nos dois casos o **boot inteiro se perde**: o BLE só existe depois que a pilha sobe e
alguém conecta e assina a notificação. Para ver `*** Booting nRF Connect SDK ***`,
init do Edge AI e falha de sensor, só RTT. Por isso o RTT continua sendo o canal de
depuração do lab, e NUS é complemento para uso sem fio.

Nada disso está habilitado — é o mapa do caminho, não configuração aplicada.

**Por que o curso ficou só no RTT.** Chegamos a avaliar um fragmento `ble_log.conf` com
`CONFIG_LOG_BACKEND_BLE` para depurar sem J-Link. Dois bloqueios no modo HID (o padrão)
mataram a ideia, e ambos estão no código do sample, não no backend:

- **O tag para de anunciar quando o PC conecta.** `ble_hid.c` chama `start_advertising()`
  no init e **só de novo no `disconnected()`** — o `connected()` não re-anuncia. Com o
  host HID conectado não há como o celular entrar, mesmo com `CONFIG_BT_MAX_CONN=2`.
  Ou seja: ou você usa o teclado BLE, ou você lê o log. Não os dois.
- **Qualquer central é forçado a `BT_SECURITY_L4`.** O `connected()` chama
  `bt_conn_set_security()` com L4 quando `CONFIG_BLE_MITM_AUTH=y` e **desconecta** quem
  falhar. O celular teria que parear com MITM (long press no botão) só para ler log.

Somado a isso, o log por BLE perde todo o boot — o backend só ativa quando alguém
assina a notificação (`log_notify_changed()` → `log_backend_enable()`). Para um lab de
40 minutos, RTT entrega mais com menos.

## Pareamento com MITM

Com `CONFIG_BLE_MITM_AUTH=y` a conexão sobe para **Security Level 4** e o pareamento
exige confirmação física no tag — é isso que faz cada dupla parear com o **seu** tag
numa sala com vários anunciando ao mesmo tempo.

O terminal imprime a passkey e as ações do botão:

```
Passkey for 9C:B6:D0:C0:CE:FC (public): 123456
===== Button Functionality (Pairing Confirmation Mode) =====
Short press (< 500 ms): Reject pairing
Long press  (> 2000 ms): Confirm pairing
```

- **Long press (> 2000 ms)** no botão do usuário → confirma
- **Short press (< 500 ms)** → rejeita

Depois de conectado, o LED muda de vermelho para verde ou azul, conforme a modalidade.

## O que a engine oferece além do que o demo usa

Validado contra a [doc oficial do runtime](https://nrfconnectdocs.nordicsemi.com/addons/addon-edge-ai/latest/libraries/nrf_edgeai/runtime.html):

- **Alimentação em lote**: `feed_inputs()` aceita qualquer quantidade de amostras.
  O streaming amostra-a-amostra deste demo é uma escolha; os samples oficiais do
  Add-on entregam a janela inteira de uma vez
  (`nrf_edgeai_uniq_inputs_num() × nrf_edgeai_input_window_size()` valores) e o
  `run_inference()` sai na primeira chamada. Exemplo real: no `ww_kws` (voz) a
  janela é 160 = shift 160, e cada bloco DMA de 10 ms do microfone é exatamente
  uma janela — o app até assevera `num_samples == nrf_edgeai_input_window_size()`.
- **API de introspecção** — é o que permite escrever o laço sem números mágicos
  (sem hardcodar 6, 99 ou int16): `nrf_edgeai_input_type()`,
  `nrf_edgeai_uniq_inputs_num()`, `nrf_edgeai_input_window_size()`,
  `nrf_edgeai_input_subwindows_num()`, `nrf_edgeai_model_task()`,
  `nrf_edgeai_model_outputs_num()`.
- **Três tarefas, três saídas** (`nrf_edgeai_model_task_t`): classificação
  (`decoded_output.classif`), regressão (`.regression.p_outputs[]`) e detecção de
  anomalia (`.anomaly.score` — o limiar é decisão da aplicação). O laço é o mesmo;
  muda só a união que você lê. Em modelos quantizados, as probabilidades vêm em
  `probabilities.q8`/`q16` em vez de `p_f32`.
- **Footprint oficial** (números para citar em aula): runtime ≈ 2 kB de flash +
  0,5–1 kB de RAM; modelo tipicamente 1–10 kB; solução completa em geral
  **5–10 kB de flash e 2–5 kB de RAM**. A biblioteca é C portátil, sem malloc,
  entregue como `.a` pré-compilada por arquitetura e ligada via `CONFIG_NRF_EDGEAI`.
- **Pipeline DSP dentro do modelo**: o pré-processamento que "não está na
  aplicação" vive no módulo DSP da biblioteca (FFT, RFHT, Mel-spectrogram,
  estatísticas) — só os blocos selecionados no Edge AI Lab entram no binário.
- **Observabilidade**: a `nrf_edgeai_obsv` coleta estatísticas das probabilidades
  em produção e sobe para o Memfault — fora do escopo do curso, mas bom saber
  que existe.

### Restrições do Edge AI Lab para o modelo próprio (Ato 3)

Antes de treinar, saiba que o Lab impõe:

- A janela deve capturar o **evento inteiro** — gesto cortado no meio não treina.
- **Features de frequência** exigem janela em potência de 2, entre **128 e 2048**
  amostras (o modelo de fábrica usa 99 — só features de tempo).
- O *data type* do dataset deve englobar o maior tipo presente (int8+float32 → float32).
- Saída quantizada (8/16 bits) muda o formato da probabilidade que o firmware lê.
- Target: **Arm Cortex-M33** para a nRF54L15.

## Próximos passos do módulo

Este mesmo código atende os três atos da sessão de Neuton AI — muda só o Kconfig:

1. **Demo pronto** (este build) — entender o mecanismo.
2. **Modo de coleta** — `CONFIG_DATA_COLLECTION_MODE=y` + `CONFIG_BLE_MODE_NONE=y`.
   Sai `acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z` na serial a 100 Hz, sem inferência.
3. **Modelo próprio** — treinar no [Nordic Edge AI Lab](https://ai.lab.nordicsemi.com/),
   baixar o `nrf_edgeai_user_model.c` e substituir em
   `src/nrf_edgeai_generated/nrf54l15tag/`, recompilar e comparar.
