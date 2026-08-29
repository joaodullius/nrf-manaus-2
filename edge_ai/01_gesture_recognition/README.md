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

### O build padrão já é o que queremos

Sem `FILE_SUFFIX`, vale o `prj.conf` — e ele já traz as três escolhas do curso:

| Kconfig | Valor | Por quê já vem assim |
|---|---|---|
| `CONFIG_NRF_EDGEAI_GESTURE_RECOGNITION_MODEL_NEUTON` | `y` | Axon depende de `SOC_NRF54LM20B`; na nRF54L15 só há Neuton |
| `CONFIG_BLE_MODE_HID` | `y` | padrão fora do modo de coleta |
| `CONFIG_BLE_MITM_AUTH` | `y` | `default y` no Kconfig e explícito no `prj.conf` |

⚠️ Não use `prj_release.conf` nesta aula: ele **desliga** o `CONFIG_BLE_MITM_AUTH`.

Consumo do build de referência: **FLASH 285.052 B (40,0%)** · **RAM 54.152 B (20,7%)**.

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

## Próximos passos do módulo

Este mesmo código atende os três atos da sessão de Neuton AI — muda só o Kconfig:

1. **Demo pronto** (este build) — entender o mecanismo.
2. **Modo de coleta** — `CONFIG_DATA_COLLECTION_MODE=y` + `CONFIG_BLE_MODE_NONE=y`.
   Sai `acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z` na serial a 100 Hz, sem inferência.
3. **Modelo próprio** — treinar no [Nordic Edge AI Lab](https://ai.lab.nordicsemi.com/),
   baixar o `nrf_edgeai_user_model.c` e substituir em
   `src/nrf_edgeai_generated/nrf54l15tag/`, recompilar e comparar.
