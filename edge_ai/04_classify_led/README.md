# 04 · App mínima: IMU → inferência → LED

Onde o **modelo próprio do aluno** entra. O `01_gesture_recognition` tem HID, MCUboot,
mcumgr, UX state manager e pareamento MITM — o Edge AI é uma fração dele. Aqui sobra só a
engine, em quatro chamadas:

```c
nrf_edgeai_user_model()     /* pega o modelo gerado */
nrf_edgeai_init()
nrf_edgeai_feed_inputs()    /* UMA amostra por vez; o runtime acumula */
nrf_edgeai_run_inference()  /* roda quando a janela fecha */
```

> **Origem:** derivado de `samples/nrf_edgeai/classification` do Edge AI Add-on v2.3.0.
> O sample alimenta o modelo com **vetores embarcados**; aqui a entrada vem do IMU e a
> saída pinta o LED RGB. Licença Nordic preservada em [LICENSE](LICENSE).

## Dois modelos no repo, uma linha para trocar

Os modelos ficam em subpastas de `src/nrf_edgeai_generated/`, e o `CMakeLists.txt` escolhe
por `CURSO_MODELO` — como o `01_gesture_recognition` faz com `fabrica` e `manaus_4gestos`:

| Pasta | Modelo | Contrato (janela / entradas / classes) |
|---|---|---|
| `Neuton/` | **exemplo da Nordic** (ligado por padrão): estados de transporte de uma encomenda, a partir da magnitude da aceleração | 50 / 1 / 7 |
| `ventilador_95922/` | **o do curso**: velocidade de um ventilador pela vibração, treinado no Lab com o [dataset de referência do 05](../05_data_forwarder/dataset_referencia/) | 128 / 6 / 4 |
| `Axon/` | o exemplo compilado para a NPU (só nRF54LM20) | — |

**Ponto de partida: o exemplo da Nordic.** Funciona sem treinar nada — é a fiação
inteira de ponta a ponta antes de existir modelo próprio. Uma entrada, a magnitude da
aceleração em mili-g. No boot:

```
<inf> main: nRF Edge AI Lab Solution id: 90449
<inf> main: janela 50 · entradas 1 · classes 7 · 100 Hz
<inf> main: classe 0 — Idle (98%)
```

| `class` | LED | Estado |
|---:|---|---|
| 0 | apagado | Idle |
| 1 | vermelho | Shaking |
| 2 | amarelo | Impact |
| 3 | magenta | Free Fall |
| 4 | verde | Carrying |
| 5 | azul | in Car |
| 6 | ciano | Placed |

**O modelo do curso: o ventilador.** Seis entradas por amostra — os seis eixos do BMI270
em **micro-unidades SI**, como o Data Forwarder grava —, janela de 128 amostras a 100 Hz,
features de frequência. Trocar é uma linha no `CMakeLists.txt` e dois blocos no
`main.c`, que já estão lá comentados (constantes `USER_*` e `CLASS_COLORS`). No boot:

```
<inf> main: nRF Edge AI Lab Solution id: 95922
<inf> main: janela 128 · entradas 6 · classes 4 · 100 Hz
<inf> main: janela em 1282 ms (esperado 1280)
<inf> main: classe 0 — idle (99%)
```

| `class` | LED | Significa |
|---:|---|---|
| 0 | azul | `idle` — parada |
| 1 | verde | `vel1` |
| 2 | amarelo | `vel2` |
| 3 | vermelho | `vel3` |

A primeira inferência sai uma janela depois do boot e depois a cada janela
(`INPUT_WINDOW_SHIFT` no modelo gerado: 50 no exemplo, 128 no ventilador). O LED só muda
quando a classe muda.

## Build

```
west build -p -b nrf54l15tag/nrf54l15/cpuapp ^
  -d C:\work\nrf-manaus-2\edge_ai\04_classify_led\build_tag ^
  C:\work\nrf-manaus-2\edge_ai\04_classify_led
```

O LED RGB muda de cor a cada mudança de classe; o RTT diz qual e com que confiança.

## ⚠️ A escala da entrada — a armadilha central

O modelo espera os números **na escala do dataset em que foi treinado**, e errar isso é
silencioso. Dois modelos, duas escalas, no mesmo `main.c`:

- **ventilador_95922:** micro-unidades SI, `sensor_value_to_micro()`, sem fator — é o que
  está no CSV do Data Forwarder Host. Os limites no `.c` gerado confirmam:
  `INPUT_FEATURES_SCALE_MIN/MAX` do eixo `az` vão de 9.620.195 a 10.377.983, a gravidade
  em m/s² × 10⁶.
- **Neuton (exemplo da Nordic):** UMA entrada, a magnitude em **mili-g** (1 g ≈ 1000),
  não em m/s² (1 g ≈ 9,81). Isso **não está escrito na doc do sample**: foi preciso ler
  os vetores embarcados dele. O vetor da classe IDLE — TAG parada, só gravidade — tem
  valores **~1017**:

```c
CLASS_0_PARCEL_IDLE_ACCEL_DATA[] = {1019.23, 1018.65, 1016.69, ...};
```

Alimentar em m/s² **não dá erro nenhum**. Compila, roda, e classifica errado: 9,8 cai no
fundo da faixa que o modelo conhece (`INPUT_FEATURES_SCALE_MIN = 6.26`), e o fundo da faixa
é justamente queda livre.

**Verificado no hardware:** com m/s², a TAG parada na mesa reportava `Free Fall (65%)`. Com
mili-g, reporta `Idle (98%)`.

Essa é a lição central do loop 2, e vale gastar tempo dela em aula: **o modelo espera a
escala do dataset, e errar isso é silencioso.** No `main.c`, o leitor do IMU é escolhido
por `USER_UNIQ_INPUTS_NUM`: 6 → seis eixos em micro; 1 → magnitude em mili-g. Outro valor
não compila.

## Que features o modelo usa? Está no `.c`

Não precisa voltar ao Lab: o `nrf_edgeai_user_model.c` gerado descreve o extrator em dois
pipelines, um por domínio. No modelo do ventilador:

```c
static const nrf_edgeai_features_pipeline_func_f32_t timedomain_features_[] = {
    nrf_edgeai_feature_utility_tss_sum_f32,     /* utilitário: soma dos quadrados */
    nrf_edgeai_feature_std_f32,                 /* Standard deviation */
    nrf_edgeai_feature_rms_f32,                 /* Root mean square */
    nrf_edgeai_feature_mcr_f32                  /* Mean-crossing rate */
};
static const nrf_edgeai_features_pipeline_func_f32_t freqdomain_features_[] = {
    nrf_edgeai_feature_utility_rfft_128_f32,    /* a FFT de 128 pontos */
    nrf_edgeai_feature_dom_freqs_features_f32,  /* Dominant frequencies */
    nrf_edgeai_feature_freqs_energy_ratios_f32, /* razão de energia entre bandas */
    nrf_edgeai_feature_spectrum_bins_f32        /* Amplitude spectrum, 64 bins */
};
```

Isso é o que o firmware **calcula**. O que o modelo **consome** vem de
`FEATURES_EXTRACTION_MASK[]`: um `uint64` por canal, um bit por feature. No ventilador são
**45** bits ligados de `EXTRACTED_FEATURES_NUM` = 495 candidatas — o *Feature selection*
do Lab escolheu 45, e `ax` ficou com mais bits que os outros canais, coerente com o
`ax_amplitude_spectrum` no topo da Feature Importance. Feature marcado no Lab que não
sobreviveu à seleção nem entra no pipeline: o `.c` é a verdade do que roda na TAG.

## ⚠️ A taxa de amostragem — a segunda armadilha, silenciosa como a primeira

O modelo também espera **o ritmo do dataset**. Com features de frequência, o espectro que
o modelo vê depende diretamente da taxa em que a app entrega amostras: amostrar 3% mais
devagar desloca todos os picos 3% para cima, e com bins de FFT de 0,78 Hz (100 Hz / 128)
isso é mais de um bin em 30 Hz.

**Não use `k_msleep(10)` no laço.** O tempo da leitura do BMI270 pelo SPI (~0,3 ms)
soma ao sleep, cada amostra leva ~10,3 ms e o laço cai para **96,9 Hz**. Medido na TAG:
a janela de 128 amostras fechava em **1321 ms** em vez de 1280 — e a classe saía uma
velocidade acima da real. Nenhum erro, nenhum aviso — só a resposta errada, com 99% de
confiança.

O `main.c` amostra por **k_timer periódico + semáforo**, igual ao
`05_data_forwarder/src/sensor/bmi270.c`, e a janela fecha em 1282 ms (0,2%). O boot
imprime o ritmo das três primeiras janelas, e qualquer janela fora de 2% vira `<wrn>`:

```
<inf> main: janela em 1282 ms (esperado 1280)
```

Se aparecer `janela em ... taxa fora da da coleta`, o modelo está vendo outro espectro.

## Trocar pelo seu modelo (loop 2)

**1. Os arquivos gerados** — copie a pasta `nrf_edgeai_generated/` do zip do Lab para uma
subpasta nova de `src/nrf_edgeai_generated/` (por exemplo `meu_modelo/`). São **três**
arquivos que importam, e o `nrf_edgeai_user_types.h` vai junto: ele carrega os typedefs
do modelo, e manter o de outro modelo compila e infere errado.

```
nrf_edgeai_user_model.c
nrf_edgeai_user_model.h
nrf_edgeai_user_types.h
```

**2. `CURSO_MODELO`** no [`CMakeLists.txt`](CMakeLists.txt) apontando para a pasta.

**3. As três constantes** no topo do [`src/main.c`](src/main.c). Para o ventilador é só
trocar qual bloco está comentado:

```c
/* Neuton (exemplo da Nordic): 50 / 1 / 7 */
// #define USER_WINDOW_SIZE      50U
// #define USER_UNIQ_INPUTS_NUM  1U
// #define USER_MODELS_CLASS_NUM 7U

/* ventilador_95922 (modelo do curso): 128 / 6 / 4 */
#define USER_WINDOW_SIZE      128U
#define USER_UNIQ_INPUTS_NUM  6U
#define USER_MODELS_CLASS_NUM 4U
```

Elas **não são decorativas** — o `main()` confere cada uma contra o modelo carregado com
`__ASSERT_NO_MSG()`. Errar uma trava o boot. Intencional: o modelo tem **contrato**. Os
valores reais estão no `.c` gerado, como `INPUT_WINDOW_SIZE`, `INPUT_UNIQ_FEATURES_NUM` e
`MODEL_OUTPUTS_NUM`.

**4. A tabela `CLASS_COLORS`** — uma linha por classe, **na ordem do dicionário** que o
`fwd_to_lab.py merge` imprimiu. A do ventilador também está lá, comentada.

**5. A escala e o fundo de escala** — coletou com o `05_data_forwarder`? A leitura de 6
eixos em micro já está certa. Confira só `IMU_ACCEL_FS_G` / `IMU_GYRO_FS_DPS`: têm de
ser os mesmos que você deixou no `bmi270.c` do forwarder antes de coletar.

**6. `west build -p`.** Sem o `-p` o CMake não relê o `CURSO_MODELO` e você grava o
modelo antigo. Confira no RTT a linha `Solution id` — é o número do zip — e as três
linhas `janela em ... ms` logo depois: têm de bater com o esperado.

### Mudar o número de classes

| | O que acontece |
|---|---|
| **Menos** classes que entradas em `CLASS_COLORS` | erro de compilação — *excess elements in array initializer* |
| **Mais** classes que entradas em `CLASS_COLORS` | **compilava em silêncio**: o C preenche com zero, as classes novas ficam com LED apagado (igual a "Idle") e `nome = NULL` indo para o `%s` do `LOG_INF` |

O caso "mais" era o perigoso — build limpo, boot limpo, comportamento errado só quando o
modelo prevê uma classe nova. Blindado com:

```c
BUILD_ASSERT(ARRAY_SIZE(CLASS_COLORS) == USER_MODELS_CLASS_NUM,
	     "CLASS_COLORS precisa ter exatamente USER_MODELS_CLASS_NUM entradas");
```

Agora falha no build nos dois sentidos.

### Limite: 8 classes

O RGB da TAG é **GPIO liga/desliga por canal** — 3 bits, **8 combinações**, uma delas
apagada. Acima de 8 classes as cores se repetem e o LED deixa de identificar a classe.

Se precisar de mais:

- **PWM** — o board expõe `rgb_led_1` como `leds-group-multicolor`
  (`nrf54l15tag_common.dtsi:52`), então dá para variar intensidade. É o que o
  `01_gesture_recognition` usa para pulsar o LED.
- **Piscadas** — número de piscadas = índice da classe. Feio, mas lê bem em sala.

Na prática, oriente **3 a 5 classes** no loop 2: menos dado para coletar, cores bem
distintas, e cabe no tempo de aula.

## ⚠️ `NCS_SAMPLES_DEFAULTS` mata o log

O `prj.conf` do sample traz `CONFIG_NCS_SAMPLES_DEFAULTS=y`, que puxa
`CONFIG_LOG_MODE_MINIMAL=y`. Em modo mínimo o log **não tem backends** — ele vai para o
console, e a TAG não tem console (`CONFIG_CONSOLE is not set`).

Resultado: **silêncio absoluto no RTT com o firmware rodando normalmente**. Verificado no
hardware: nem o banner de boot aparecia, e a CPU estava executando. Foi preciso forçar
`CONFIG_LOG_MODE_DEFERRED=y`.

É o tipo de coisa que não aparece no build e custa uma hora de depuração em sala.

## Consumo

| | Flash (text+data) | RAM (data+bss) |
|---|---:|---:|
| `04_classify_led` (modelo do ventilador, FFT) | **89.384 B** | **24.016 B** |
| `04_classify_led` (modelo de exemplo da Nordic, padrão) | 87.608 B | 19.488 B |
| `01_gesture_recognition` (modo coleta) | 267.264 B | 58.496 B |

**Um terço do flash e um terço da RAM** do lab 01 — por não ter BLE, MCUboot nem mcumgr.
É o ponto do lab: o que sobra é a engine.
