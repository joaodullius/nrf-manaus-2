# 08 · Um zip do Edge AI Lab na NPU — detector de tosse

O jeito mais curto de sair de um **zip baixado do Edge AI Lab** para um firmware
rodando na NPU Axon: **um** modelo, **um** `main.c`, e as **4 chamadas** da API
`nrf_edgeai`. Este é o exemplo-molde — o [`09_dog_bark_detection/`](../09_dog_bark_detection/)
é o mesmo app com outro zip, e o [`10_sound_events/`](../10_sound_events/) pendura
cinco de uma vez.

> **Origem do modelo:** solução pronta *Cough Detection* (`sound-event-cough`) do
> [Nordic Edge AI Lab](https://www.nordicsemi.com/Products/Technologies/Edge-AI/Get-Started),
> baixada como zip; a pasta [`src/nrf_edgeai_generated/`](src/nrf_edgeai_generated/) é a
> cópia literal do que veio dentro, com a licença em [LICENSE.txt](LICENSE.txt). O
> guia genérico que o Lab põe no zip está preservado em
> [README_edgeai_lab.md](README_edgeai_lab.md). O app (`src/main.c`) é do curso.

## O que vem no zip — a anatomia padrão

Todo zip do Lab tem o mesmo contrato (vale para gestos, som, anomalia…):

| Arquivo | O que é |
|---|---|
| `nrf_edgeai_user_model.c/.h` | o modelo: descritores, pipeline de features e o getter `nrf_edgeai_user_model_<solution>()` |
| `nrf_edgeai_user_model_axon.h` | o modelo **compilado para a NPU**: *command buffer* + pesos int8 (só existe se a solução foi gerada para Axon) |
| `nrf_edgeai_user_model_labels.h` | rótulos (aqui, 1 classe: `cough`) |
| `nrf_edgeai_user_types.h` | tipos de entrada/saída |
| `prj_example.conf` | os Kconfig de engine que o app precisa (base do nosso [`prj.conf`](prj.conf)) |

Com **um** modelo só no binário, o alias genérico `nrf_edgeai_user_model()` já aponta
para ele — o `main.c` nem precisa saber o nome da solution.

## As 4 chamadas (o template do zip)

O [`src/main.c`](src/main.c) segue o fluxo do guia do Lab, comentado passo a passo:

```c
nrf_edgeai_t *p_model = nrf_edgeai_user_model();       /* 1. pegar o modelo   */
nrf_edgeai_init(p_model);                              /* 2. inicializar (1x) */
/* loop: */
nrf_edgeai_feed_inputs(p_model, buf, 160);             /* 3. alimentar        */
nrf_edgeai_run_inference(p_model);                     /* 4. inferir (na NPU) */
float prob = p_model->decoded_output.classif.probabilities.p_f32[0];
```

`feed_inputs` devolve `INPROGRESS` enquanto a janela interna não fecha — o app só
pula o resto do loop. A entrada são os blocos de 10 ms crus do PDM (16 kHz, int16);
o mel-espectrograma acontece dentro da execução no Axon (detalhes no
[`07_ww_kws`](../07_ww_kws/README.md#como-a-inferência-roda-no-axon)).

O pós-processamento é o padrão da wake word: **2 quadros** acima de **50 %** numa
janela de 15 (~450 ms), com *cooldown* de 2 s — valores calibrados na bancada (tosse
real dá picos de 87–99 % em 1–3 quadros; média móvel não funciona para evento tão
curto).

## Hardware

nRF54LM20-DK (variante B) + Adafruit 3492, ligado como no
[`06_mic_check/`](../06_mic_check/) — valide o mic lá antes.

## Build e gravação

```
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 --terminal
```

De dentro de `C:\ncs\v3.4.0`:

```
west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild ^
     -d C:\work\nrf-manaus-2\edge_ai\08_cough_detection\build_lm20 ^
     C:\work\nrf-manaus-2\edge_ai\08_cough_detection ^
     -- -DEXTRA_ZEPHYR_MODULES=C:/ncs/sdk-edge-ai/edge-ai
nrfutil device program --firmware edge_ai\08_cough_detection\build_lm20\08_cough_detection\zephyr\zephyr.hex --serial-number <serial>
nrfutil device reset --serial-number <serial>
```

## O que se vê

Terminal na **VCOM1** (segunda COM da DK), 115200. Tussa perto do mic:

```
=== 08_cough_detection: detector de tosse na NPU Axon ===
Modelo pronto: solution sound_event_cough, janela de 160 amostras
Escutando. Tussa perto do microfone.

[tosse] pico do ultimo segundo:   2%  (eventos: 0)
>>> TOSSE (pico 95%) — evento 1
```

## Trocar o modelo (o exercício)

Baixe **outro** zip de detector do Lab, substitua a pasta `src/nrf_edgeai_generated/`
e recompile com `-p` — nada mais muda, porque o alias `nrf_edgeai_user_model()` segue
o modelo embarcado. Ajuste `RAW_THRESHOLD`/`MIN_HITS` ao temperamento do modelo novo
(veja o contraste com o [`09_dog_bark_detection`](../09_dog_bark_detection/), que
precisa de limiar 0,90 e 5 quadros).
