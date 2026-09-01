# Modelos da nRF54L15-TAG

Dois modelos convivem aqui, um por subpasta. O `CMakeLists.txt` compila **um**,
escolhido pela variável `CURSO_MODELO` no topo dele.

| Subpasta | Solution id | Janela | Classes | Origem |
|---|---|---|---|---|
| [`fabrica/`](fabrica/) | **91278** | 99 | 8 (idle, unknown, 6 gestos) | Edge AI Add-on v2.3.0, treinado pela Nordic |
| [`manaus_4gestos/`](manaus_4gestos/) | **95867** | 100 | 4 (idle, unknown, swipe_right, swipe_left) | Treinado no curso em 2026-09-01 |

> Estrutura divergente do upstream, que tem um modelo solto por board. A convenção de
> subpasta é a mesma que o upstream já usa na `nrf54lm20dk` (`Axon/`, `Neuton/`).

## Como trocar

No [`CMakeLists.txt`](../../../CMakeLists.txt), comente uma linha e descomente a outra:

```cmake
set(CURSO_MODELO "fabrica")
# set(CURSO_MODELO "manaus_4gestos")
```

O default é `fabrica`: quem clona o repo pega o comportamento original do add-on, e
usar o modelo do curso é um ato explícito.

**Recompile com `-p`.** Sem build pristine o CMake não relê o arquivo e você grava o
modelo antigo achando que trocou.

⚠️ **Editar aqui é a única forma de trocar.** Não existe override por linha de comando:
com `--sysbuild`, o `-D` vai para o CMake do sysbuild e não chega nesta aplicação.
Testado em 2026-09-01, inclusive com o prefixo de imagem
(`-D01_gesture_recognition_CURSO_MODELO=...`) — nos dois casos o build **passa em
silêncio** com o valor do arquivo, e você grava o modelo errado num binário que parece
correto.

## Como confirmar qual subiu na TAG

O boot loga o id, sem precisar inspecionar arquivo (`src/main.c:145`):

```
<inf> main: nRF Edge AI Lab Solution id: 95867
```

`95867` = o do curso. `91278` = o de fábrica.

⚠️ Essa linha **só aparece com os buffers de log aumentados**. Compile com o fragmento
[`rtt_log.conf`](../../../configuration/nrf54l15tag_nrf54l15_cpuapp/rtt_log.conf), que
já traz `CONFIG_LOG_BUFFER_SIZE=4096` e `CONFIG_SEGGER_RTT_BUFFER_SIZE_UP=4096`. Sem
ele, a rajada de boot estoura os buffers e engole justamente as linhas do `main()`.

Sem o log, a verificação é no binário: procure a string do id dentro do `zephyr.elf`.

## Sobre o `manaus_4gestos`

Treinado no Edge AI Lab a partir de
[`03_central_uart/dataset_referencia/dataset_centrado.csv`](../../../../03_central_uart/dataset_referencia/).
Balanced accuracy de validação **0,994898**; footprint reportado pelo Lab: NVM 4,0 kB
(modelo 0,400 kB, 95 coeficientes) e SRAM 1,5 kB.

Os rótulos 0-3 são os quatro primeiros do `enum class_label_t`
(`src/inference_postprocessing.h`), então ele **cai no firmware sem editar C** — as
outras quatro classes simplesmente nunca disparam.

⚠️ A acurácia é otimista: treino e validação vieram da mesma gravação contínua, de uma
pessoa só, e ambos carregam a mesma dilatação de taxa (76-94 Hz na coleta contra 100 Hz
na inferência). O veredito é o tag na mão. Ver as limitações no
[README do dataset](../../../../03_central_uart/dataset_referencia/README.md).

## O `prj_example.conf` do `manaus_4gestos/`

Veio no zip do Lab e é **inerte aqui** — o `APPLICATION_CONFIG_DIR` aponta para
`configuration/<board>`, não para `src/`. Ele sugere `CONFIG_NRF_EDGEAI=y`,
`CONFIG_FPU=y` e `CONFIG_NEWLIB_LIBC=y`. Os dois primeiros o `prj.conf` da app já tem.
**Não aplique o `NEWLIB_LIBC`**: a app roda com picolibc e funciona; trocar de libc
mexeria no footprint sem necessidade.
