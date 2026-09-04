# 07 · Wake word e comandos de voz na NPU (Axon)

Primeiro exemplo do módulo que **não roda na CPU**: um microfone PDM alimenta dois modelos
TensorFlow Lite compilados para o **Axon**, a NPU do nRF54LM20B. O primeiro escuta a
frase de ativação **"Okay Nordic"**; quando ela é detectada, o segundo passa a reconhecer
dez comandos (**Go, Stop, Up, Down, Yes, No, On, Off, Right, Left**) por alguns segundos
e depois volta a esperar a frase.

> **Origem:** cópia literal de `applications/ww_kws` do
> **Edge AI Add-on for nRF Connect SDK v2.3.0** (tag `v2.3.0`, commit `1c24f3a`),
> copiada em 2026-09-04. Os arquivos principais carregam o caminho upstream no cabeçalho;
> licença Nordic preservada em [LICENSE](LICENSE).

## O que ele demonstra

- **Áudio 16 kHz mono** vindo do periférico **PDM20** em blocos de 10 ms (`src/dmic.c`),
  canal esquerdo.
- **Dois modelos na mesma app**, cada um com seu `nrf_edgeai_generated/`
  (`src/ww/` e `src/kws/`), os dois com a variante `_axon.h`: o descritor que a engine
  entrega para a NPU em vez de executar na CPU.
- **Pós-processamento é do aplicativo, não do modelo:** histórico deslizante para a
  wake word, média móvel exponencial para os comandos — detalhado em
  [Como os dois se relacionam no código](#como-os-dois-se-relacionam-no-código).
- **Duas seriais:** os logs do Zephyr saem no console de sempre (`uart20`, **VCOM1**) e as
  mensagens de estado do app (`Waiting for wakeword`, `Keyword spotted: Yes`…) saem na
  `uart30` (**VCOM0**), escolhida pelo `chosen ncs,control-output-uart` no overlay.
- **Buffers do Axon** dimensionados para os modelos embarcados no `prj.conf`
  (`CONFIG_NRF_AXON_INTERLAYER_BUFFER_SIZE=6656`): trocar de modelo pode exigir trocar
  esse número.

## Os dois modelos

Os dois vêm do **Edge AI Lab** (gerados a partir de texto, sem gravar áudio) e foram
compilados para o Axon: o arquivo `_axon.h` de cada um é o *command buffer* + pesos que
a engine entrega prontos para a NPU executar.

| | Wake word — [`src/ww/`](src/ww/) | Comandos — [`src/kws/`](src/kws/) |
|---|---|---|
| Solution id (Lab) | **36711** | **36712** |
| Getter no código | `nrf_edgeai_user_model_36711()` | `nrf_edgeai_user_model_36712()` |
| Classes | **1**: `okay nordic` — a saída é uma probabilidade só: "esta janela contém a frase?" | **12**: `OTHER`, `SILENCE` + os 10 comandos **down, go, left, no, off, on, right, stop, up, yes** |
| Flash (pesos + programa da NPU) | **~35 kB** (25,0k const + 9,7k cmd) | **~359 kB** (295,9k const + 62,9k cmd) |
| Papel | porteiro **sempre ligado** | vocabulário grande, roda **só por 3 s** |

Os rótulos estão em `nrf_edgeai_generated/nrf_edgeai_user_model_labels.h` de cada pasta;
os tamanhos saem de `arm-zephyr-eabi-nm --size-sort` no `zephyr.elf`
(símbolos `axon_model_const_…` e `cmd_buffer_…`).

**Por que dois modelos?** É a arquitetura clássica de *cascata*: o modelo de comandos é
**10× maior** que o da wake word. Deixá-lo escutando o tempo todo custaria energia e
geraria falsos positivos com 10 palavras abertas; o porteiro de 35 kB decide *quando*
vale a pena acordar o modelo caro. O mesmo padrão de "Hey Siri"/"Alexa".

A entrada é idêntica para os dois: PCM **16 kHz, int16**, em blocos de **160 amostras
(10 ms)** direto do DMIC (`INPUT_WINDOW_SIZE 160` no `nrf_edgeai_user_model.c`). O
front-end de DSP (extração de features de áudio) está **dentro do modelo**
(`MODEL_USES_AS_INPUT_DSP_FEATURES`) — o app entrega áudio cru e sai probabilidade.
Cada modelo produz uma predição a cada **30 ms** (3 blocos).

## Como os dois se relacionam no código

O [`main.c`](src/main.c) é uma máquina de dois estados que alterna dois loops — **nunca
rodam ao mesmo tempo**, e o mesmo stream do DMIC alimenta quem estiver de posse da vez:

```
            ww_loop()                                kws_loop()
  ┌──────────────────────────┐   detectou    ┌──────────────────────────────┐
  │ dmic_read → ww_process() │ ────────────► │ dmic_read → kws_process()    │
  │ (modelo 36711, sempre)   │    LED0 on    │ (modelo 36712, janela de 3s) │
  └──────────────────────────┘               └──────────────────────────────┘
              ▲                   LED0 off        │ cada comando aceito renova
              └───────────────────────────────────┘ os 3 s (CONFIG_KWS_PERIOD_MS)
                       timeout sem comando
```

Na troca de estado, `ww_reset()`/`kws_reset()` chamam
`nrf_edgeai_model_axon_init_persistent_vars()` para zerar a memória interna do modelo
que assume a vez — sem isso, o contexto de áudio velho vazaria de um estágio para o outro.

O **pós-processamento é do aplicativo, não do modelo** — os dois estágios usam
estratégias diferentes, e é aqui que os limiares do [`Kconfig`](Kconfig) entram:

- **Wake word** (`ww_postprocess()`, [`src/ww/wakeword.c`](src/ww/wakeword.c)): janela
  deslizante das últimas **20** predições (um bitmask, `WW_HISTORY_SIZE`); conta quantas
  passaram de **0,99** (`WW_PROBABILITY_THRESHOLD` 990) e aceita com **15 de 20**
  (`WW_COUNT_THRESHOLD`) — ou seja, ~450 ms de evidência dentro de 600 ms de história.
  No log de debug dá para ver a prob. cravar em 0.996 e o `count` subir até disparar.
- **Comandos** (`kws_postprocess()`, [`src/kws/kws.c`](src/kws/kws.c)): `OTHER` e
  `SILENCE` zeram tudo; um comando precisa vencer **10 inferências seguidas** (300 ms)
  com a **média móvel exponencial** da probabilidade (`KWS_EMA_ALPHA` 120 → α=0,12)
  acima de **0,8**. Depois de aceitar, pula 10 detecções (`SKIP_DETECTIONS_COUNT`)
  para o mesmo comando não contar duas vezes.

Saídas: os **estados** (`Waiting for wakeword`, `Keyword spotted: …`) vão para a
`uart30`/**VCOM0** via [`src/control_output.c`](src/control_output.c); os **logs** do
Zephyr ficam na `uart20`/**VCOM1**. **LED0** aceso = janela de comandos aberta;
**LED1** pisca = comando aceito.

## Hardware

nRF54LM20-DK (variante **B**) + microfone PDM MEMS **Adafruit 3492** (SPH0641), ligado
como no [`06_mic_check/`](../06_mic_check/) — figura, tabela de fios e as pegadinhas do
header P2 estão lá. **Valide a fiação no `06_mic_check` antes de gravar este app**: um
modelo mudo não diz se o problema é fio, canal, alimentação ou o modelo.

Os pinos vêm do overlay [`boards/nrf54lm20dk_nrf54lm20b_cpuapp.overlay`](boards/nrf54lm20dk_nrf54lm20b_cpuapp.overlay)
(o mesmo par CLK/DAT do `06_mic_check`); para outro microfone, os limites de clock e
ciclo de trabalho ficam em `src/dmic.c`.

## Build e gravação

O app precisa do **Edge AI Add-on**, que não vem no SDK `C:\ncs\v3.4.0` — ele entra como
módulo extra pelo `-DEXTRA_ZEPHYR_MODULES`, como nos exemplos Neuton. Entre no ambiente
do toolchain primeiro:

```
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 --terminal
```

Depois, de dentro de `C:\ncs\v3.4.0`:

```
west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild ^
     -d C:\work\nrf-manaus-2\edge_ai\07_ww_kws\build_lm20 ^
     C:\work\nrf-manaus-2\edge_ai\07_ww_kws ^
     -- -DEXTRA_ZEPHYR_MODULES=C:/ncs/sdk-edge-ai/edge-ai
nrfutil device program --firmware edge_ai\07_ww_kws\build_lm20\07_ww_kws\zephyr\zephyr.hex --serial-number <serial>
nrfutil device reset --serial-number <serial>
```

No VS Code (extensão nRF Connect): board `nrf54lm20dk/nrf54lm20b/cpuapp`, SDK v3.4.0,
*Extra CMake arguments* = `-DEXTRA_ZEPHYR_MODULES=C:/ncs/sdk-edge-ai/edge-ai`.

Dois terminais, os dois a 115200:

| COM | UART | O que sai |
|---|---|---|
| **VCOM0** (primeira COM da DK) | `uart30` | estados do app: `Waiting for wakeword`, `Wakeword detected`, `Waiting for keywords`, `Keyword spotted: <nome>`, `Keyword spotting window timeout` |
| **VCOM1** (segunda COM) | `uart20` | logs do Zephyr (`Initialization completed`, erros) |

Roteiro de teste:

1. Diga **"Okay Nordic"** a ~30 cm do mic. **LED0** acende: a app entrou no estágio de
   comandos.
2. Diga um comando (**"Yes"**, **"Stop"**…). **LED1** pisca por 1 s e a VCOM0 mostra
   `Keyword spotted: Yes`.
3. Fique em silêncio 3 s (`CONFIG_KWS_PERIOD_MS`): `Keyword spotting window timeout`,
   LED0 apaga, volta a esperar a wake word.

A pronúncia dos modelos é de inglês americano. Se a frase não pega, baixar
`CONFIG_WW_PROBABILITY_THRESHOLD` (padrão 990 = 99 %) ou `CONFIG_WW_COUNT_THRESHOLD`
(padrão 15 de 20) num `.conf` extra é o primeiro ajuste; o segundo é conferir no
[`06_mic_check`](../06_mic_check/) se o nível ao falar chega perto de -20 dBFS.

### Modos

`choice APP_MODE` no Kconfig:

| Opção | Comportamento |
|---|---|
| `CONFIG_APP_MODE_WW_GATED_KWS` (padrão) | wake word → janela de comandos → volta |
| `CONFIG_APP_MODE_WW_ONLY` | só a wake word; LED0 pisca a cada detecção. Bom para demonstrar a NPU com um modelo só |
| `CONFIG_APP_MODE_KWS_ONLY` | só comandos, o tempo todo |

`prj_release.conf` (`-DFILE_SUFFIX=release`) tira logs e asserts; `observability.conf`
liga o BLE + Memfault para métricas do modelo (não faz parte do roteiro do curso).

## Trocar os modelos

Os dois modelos vêm do **Edge AI Lab**, que gera wake word e comandos **a partir de texto**
(sem gravar áudio). Substituir é trocar os arquivos de `src/ww/nrf_edgeai_generated/` ou
`src/kws/nrf_edgeai_generated/` pelos baixados do Lab, apontar `ww_model`/`kws_model` para
o getter novo em `wakeword.c`/`kws.c`, e, no KWS, refazer a tabela
`keyword_detection_ctxs` com os rótulos de `nrf_edgeai_user_model_labels.h`. O
`README.rst` da Nordic (nesta pasta) detalha os passos.

## Referências

- Edge AI Add-on · *Wakeword and Keyword Spotting*:
  <https://nrfconnectdocs.nordicsemi.com/addons/addon-edge-ai/latest/applications/ww_kws/README.html>
- nRF54LM20 DK · *GPIO interface* (mapa de pinos dos headers) e *Power supply* (VDD:IO):
  <https://docs.nordicsemi.com/r/bundle/ug_nrf54lm20_dk/page/ug/nrf54lm20_dk/hw_desription/connector_if.html>
- Edge AI Lab · *Keyword spotting* / *Wake word detection*:
  <https://docs.nordicsemi.com/r/bundle/edge-ai-lab/page/keyword_spotting.html/overview>
