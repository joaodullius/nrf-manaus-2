# 05 · App mínima: IMU → inferência → LED

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

## Funciona sem treinar nada

Vem com o **modelo de exemplo da Nordic** — estados de encomenda, com uma entrada: a
magnitude da aceleração. E ele **classifica de verdade** na TAG:

```
<inf> main: janela 50 · entradas 1 · classes 7 · 100 Hz
<inf> main: classe 4 — Carrying (91%)
<inf> main: classe 0 — Idle (98%)
```

Parada na mesa: `Idle` com 98%. Isso torna o lab utilizável **antes** de existir modelo
treinado — o aluno vê a engine funcionando, e só depois troca pelo modelo dele.

## Build

```
west build -p -b nrf54l15tag/nrf54l15/cpuapp ^
  -d C:\work\nrf-manaus-2\edge_ai\05_gesture_led\build_tag ^
  C:\work\nrf-manaus-2\edge_ai\05_gesture_led
```

O LED RGB muda de cor a cada mudança de classe; o RTT diz qual e com que confiança.

## ⚠️ A unidade da entrada — a armadilha central

O modelo espera a magnitude em **mili-g** (1 g ≈ 1000), não em m/s² (1 g ≈ 9,81). Isso
**não está escrito na doc do sample**: foi preciso ler os vetores embarcados dele. O vetor
da classe IDLE — TAG parada, só gravidade — tem valores **~1017**:

```c
CLASS_0_PARCEL_IDLE_ACCEL_DATA[] = {1019.23, 1018.65, 1016.69, ...};
```

Alimentar em m/s² **não dá erro nenhum**. Compila, roda, e classifica errado: 9,8 cai no
fundo da faixa que o modelo conhece (`INPUT_FEATURES_SCALE_MIN = 6.26`), e o fundo da faixa
é justamente queda livre.

**Verificado no hardware:** com m/s², a TAG parada na mesa reportava `Free Fall (65%)`. Com
mili-g, reporta `Idle (98%)`.

Essa é a lição central do loop 2, e vale gastar tempo dela em aula: **o modelo espera a
escala do dataset, e errar isso é silencioso.**

## Trocar pelo seu modelo (loop 2)

**1. Os arquivos gerados** — substitua em `src/nrf_edgeai_generated/Neuton/`:

```
nrf_edgeai_user_model.c
nrf_edgeai_user_model.h
nrf_edgeai_user_types.h
```

**2. As três constantes** no topo do [`src/main.c`](src/main.c):

```c
#define USER_WINDOW_SIZE      50U
#define USER_UNIQ_INPUTS_NUM   1U
#define USER_MODELS_CLASS_NUM  7U
```

Elas **não são decorativas** — o `main()` confere cada uma contra o modelo carregado com
`__ASSERT_NO_MSG()`. Errar uma trava o boot. Intencional: o modelo tem **contrato**. Os
valores reais estão no `.c` gerado, como `INPUT_WINDOW_SIZE`, `INPUT_UNIQ_FEATURES_NUM` e
`MODEL_OUTPUTS_NUM`.

**3. A tabela `CLASS_COLORS`** — uma linha por classe.

**4. A entrada** — hoje `imu_read_magnitude()` entrega um valor. Modelo com 6 canais
(accel + gyro)? Troque a função por uma que preencha um vetor de 6 e ajuste
`USER_UNIQ_INPUTS_NUM`. **Na mesma escala em que você capturou**: o
[`03_central_uart`](../03_central_uart/) entrega mili-unidades; o
[`04_data_forwarder`](../04_data_forwarder/) no padrão, micro.

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
| `05_gesture_led` (modelo de exemplo) | **87.108 B** | **19.413 B** |
| `01_gesture_recognition` (modo coleta) | 267.264 B | 58.496 B |

**Um terço do flash e um terço da RAM** do lab 01 — por não ter BLE, MCUboot nem mcumgr.
É o ponto do lab: o que sobra é a engine.
