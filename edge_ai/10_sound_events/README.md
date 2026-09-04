# 09 · Cinco detectores de som "ao mesmo tempo" na NPU (Axon)

O `07_ww_kws` alterna dois modelos; este exemplo — **código do curso** — pendura
**cinco engines independentes no mesmo microfone** e roda todas a cada janela de
áudio: choro de bebê, latido, ronco, tosse e miado. É a demonstração de que a NPU é
um **recurso multiplexável**, como qualquer periférico.

> **Origem dos modelos:** soluções prontas *sound event detection* do
> **[Nordic Edge AI Lab](https://www.nordicsemi.com/Products/Technologies/Edge-AI/Get-Started)**,
> baixadas como zip e copiadas para [`src/models/`](src/models/) — cada uma com sua
> `nrf_edgeai_generated/` e licença. O app em volta (`src/main.c`) é do curso.

## Os cinco modelos — e por que "é padrão"

Todo zip do Edge AI Lab tem o mesmo contrato: uma pasta `nrf_edgeai_generated/` com o
modelo compilado e a mesma API de 4 chamadas (`nrf_edgeai_user_model*()` →
`nrf_edgeai_init()` → `nrf_edgeai_feed_inputs()` → `nrf_edgeai_run_inference()`).
Os cinco daqui são **gêmeos estruturais do modelo de wake word do 07**:

| Propriedade | Valor (idêntico nos cinco) |
|---|---|
| Tarefa | detector de **1 classe** (sigmoide: "o evento está presente?") |
| Entrada | PCM int16 @ 16 kHz, janela de 160 amostras (blocos de 10 ms) |
| Execução | `…axon_audiomels`: mel-espectrograma + rede na NPU |
| Interlayer buffer | **6.048 B** — os cinco declaram a mesma necessidade |
| Getter | `nrf_edgeai_user_model_sound_event_<nome>()` |

A única coisa que muda de um zip para outro é o **nome** nos símbolos e o rótulo em
`nrf_edgeai_user_model_labels.h`. Trocar/adicionar um detector é copiar a pasta e
acrescentar uma linha na tabela `detectors[]` do [`src/main.c`](src/main.c) e uma no
[`CMakeLists.txt`](CMakeLists.txt) — o exemplo inteiro é essa tabela.

## "Ao mesmo tempo" — o que isso significa de verdade

A NPU executa **um job por vez** (o driver serializa com um mutex). "Cinco ao mesmo
tempo" significa: o mesmo bloco de áudio alimenta as cinco engines e, quando a janela
fecha (a cada 30 ms), as cinco inferências rodam **em sequência** — cada uma dura uma
fração disso, sobra NPU de folga. O custo de RAM também não soma: o **interlayer
buffer é compartilhado** (dono é quem estiver executando), e como os cinco pedem os
mesmos 6.048 B, cinco modelos custam o mesmo buffer que um.

Um cuidado de código que o `main.c` demonstra (e que muda em relação ao 07): com
vários consumidores, o bloco do DMIC só volta para o driver **depois** de alimentar
todas as engines — cada `feed_inputs()` copia as amostras para a janela interna do
modelo, e só então vem o `k_mem_slab_free()`.

## Pós-processamento — por que contagem de quadros, e por detector

Como no 07, é do app, não do modelo — e a bancada ensinou duas lições que estão
cristalizadas no código:

1. **Média móvel não serve para evento curto.** A primeira versão usava EMA da
   probabilidade: o choro de bebê dava picos brutos de 94 % em 1–3 quadros e a EMA
   ficava em 0 % — o evento acabava antes de a média subir. A versão final usa o
   **mesmo padrão da wake word do 07**: janela deslizante de 15 quadros (~450 ms)
   contando quantos passaram do limiar **bruto**.
2. **Cada modelo tem um temperamento.** O de latido dispara em qualquer som impulsivo
   (tosse, miado, ronco — picos de 92–99 %); os de tosse/ronco são tímidos. Por isso
   o limiar e o número de quadros são **por detector**, na própria tabela
   `detectors[]` — a mesma solução da tabela `keyword_detection_ctxs[]` do KWS da
   Nordic:

| Detector | limiar bruto | quadros | racional |
|---|---|---|---|
| latido | 0,90 | 5 de 15 | gatilho fácil: exige evidência sustentada |
| bebê, miado | 0,70 | 2 de 15 | eventos curtos, picos altos |
| tosse, ronco | 0,50 | 2–3 de 15 | modelos tímidos: limiar baixo |

Depois de cada detecção há um *cooldown* de ~2 s. **Calibrar essa tabela ao vivo é o
exercício da aula** — o painel imprime `EMA/pico` por segundo justamente para isso: o
pico mostra o que o modelo viu de verdade; a EMA, o que uma média faria com ele.

## Hardware

O mesmo do módulo: nRF54LM20-DK (variante B) + Adafruit 3492, ligado como no
[`06_mic_check/`](../06_mic_check/) (figura e tabela de fios lá). Valide o mic no
`06_mic_check` antes.

## Build e gravação

Como no `07_ww_kws`: SDK padrão + add-on como módulo extra.

```
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 --terminal
```

De dentro de `C:\ncs\v3.4.0`:

```
west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild ^
     -d C:\work\nrf-manaus-2\edge_ai\10_sound_events\build_lm20 ^
     C:\work\nrf-manaus-2\edge_ai\10_sound_events ^
     -- -DEXTRA_ZEPHYR_MODULES=C:/ncs/sdk-edge-ai/edge-ai
nrfutil device program --firmware edge_ai\10_sound_events\build_lm20\10_sound_events\zephyr\zephyr.hex --serial-number <serial>
nrfutil device reset --serial-number <serial>
```

## O que se vê

Terminal na **VCOM1** (segunda COM da DK), 115200:

```
=== 10_sound_events: 5 detectores na NPU Axon (PDM CLK=P1.04 DAT=P1.05) ===
  modelo 'bebe' pronto (solution sound_event_baby_cry)
  ...
Escutando. Painel a cada 1 s; deteccoes com '>>>'.

[painel] rms:   45 bebe:  0/  0% latido:  3/ 12% ronco:  0/  0% tosse:  0/  2% miado:  0/  0%
~ bebe:  2 latido: 97 ronco:  4 tosse:  1 miado:  0
>>> tosse (pico 95%, 2 quadros > 50%) — evento 1
```

Cada detector mostra `EMA/pico` do último segundo; `rms` é o nível de áudio que
chegou (compare com o `06_mic_check`). **Olhe o pico**: evento curto some da EMA mas
não do pico. As linhas `~` são o traço bruto — as cinco probabilidades daquela
inferência, impressas sempre que alguma passa de 25 %.

## Resultados na bancada (2026-09-04) — investigação em aberto

Testado som a som (tosse real; latido, miado, ronco e choro por vídeo no celular
colado no mic), com o pós-processamento final:

| Som | Pico no detector certo | Disparou? | Observações |
|---|---|---|---|
| latido | 99 % | ✅ em rajada | e parou de disparar nos outros sons após o freio de 5 quadros |
| tosse | 87–99 % | ✅ 4× | o miado deu 2 falsos positivos junto (os dois modelos se confundem) |
| miado | 0–13 % | ❌ | **intrigante:** numa rodada anterior o mesmo vídeo deu pico de 87–98 % e disparou; reset da placa não mudou nada |
| ronco | 35 % | ❌ | ronco teatral e vídeo não convenceram o modelo |
| bebê | 0–1 % | ❌ | o modelo não reagiu ao vídeo testado — o áudio chegava (latido viu 92 % no mesmo som); também teve uma rodada anterior com pico de 94 % |

Duas lições e um mistério:

- **Modelos prontos generalizam de forma desigual** — dependem do quanto o som da
  bancada se parece com o dataset do Lab. Testar com fontes variadas (e, se preciso,
  retreinar no Lab) faz parte do fluxo real de Edge AI.
- **Sem ver a probabilidade bruta, não se diagnostica nada** — por isso o painel
  ganhou o `rms` (nível de áudio que chegou) e o traço `~ bebe: 2 latido: 97 …`,
  impresso a cada inferência em que algum detector passa de 25 %.
- **O mistério em aberto:** bebê e miado viram o próprio som numa rodada e ficaram
  cegos nas seguintes, com o mesmo vídeo e os demais detectores reagindo — descartada
  deriva de estado (reset não resolve). Hipóteses vivas: trecho/volume do vídeo e
  interação entre os modelos na sequência de inferências. A instrumentação acima
  existe para fechar essa questão na próxima sessão de bancada.
