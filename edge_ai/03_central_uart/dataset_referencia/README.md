# Dataset de referência — gestos capturados no preparo do curso

Rede de segurança para a aula: se não houver tempo de coletar, ou se a coleta de
alguém falhar, este dataset já está pronto para subir no Edge AI Lab.

> **Só serve para o loop 1** (`01_gesture_recognition` + `03_central_uart`).
> Ver [Por que não serve para o loop 2](#por-que-não-serve-para-o-loop-2).

## O que tem aqui

| Arquivo | Linhas | Para quê |
|---|---|---|
| [`dataset_centrado.csv`](dataset_centrado.csv) | 81.500 | **Sobe direto no Lab.** Gestos centralizados, todas as classes múltiplas de 100 |
| [`bruto/`](bruto/) | — | Os 5 CSVs por classe, como saíram da serial. Ponto de partida para o aluno rodar o pipeline inteiro |

O merge bruto não está aqui de propósito: é regenerável em segundos a partir de
`bruto/`, e ter os dois convida a subir o errado.

## Como foi capturado

- **Data:** 2026-09-01 · **uma** pessoa, **um** tag
- **Firmware na TAG:** `01_gesture_recognition` com `data_collection.conf`
  (`CONFIG_DATA_COLLECTION_MODE=y`, `CONFIG_BLE_MODE_NUS=y`)
- **Ponte:** `03_central_uart` na nRF54L15-DK, filtrando pelo endereço do tag
- **Dado:** 6 canais, `int16` em **mili-unidades**, fundo de escala **±4 g / ±1000 dps**
- **Protocolo de gravação** (o que a doc do Lab recomenda): 3-5 s parado no começo,
  gesto de 1-2 s, ~1 s de pausa entre eles, variando velocidade e intensidade

Classes gravadas — **4 das 8** do `enum class_label_t`:

| # | Classe | Duração | Taxa medida |
|---|---|---|---|
| 0 | `idle` | 45 s + 5 min | 90,9 e 94,3 Hz |
| 1 | `unknown` | 5 min | 81,8 Hz (46 amostras perdidas, 0,19%) |
| 2 | `swipe_right` | 5 min | 76,4 Hz |
| 3 | `swipe_left` | 5 min | 84,5 Hz |

Os rótulos 0-3 são exatamente os quatro primeiros do enum, então um modelo treinado
com este dataset **cai no firmware sem editar uma linha de C**. As outras quatro
classes (`double_shake`, `double_thumb`, `rotation_right`, `rotation_left`)
simplesmente nunca disparam.

## Como reproduzir o `dataset_centrado.csv` a partir do `bruto/`

```bash
cd edge_ai/03_central_uart
python tools/center_gestures.py "dataset_referencia/bruto/swipe_*.csv"
python tools/center_gestures.py "dataset_referencia/bruto/idle_*.csv" \
                                "dataset_referencia/bruto/unknown_*.csv" --continuo
python tools/prep_dataset.py merge "dataset_centered/*.csv" --out dataset_centrado.csv
```

A calibração automática deve reencontrar `gyro_y` / 0,95 para o `swipe_right` e
`gyro_z` / 1,25 para o `swipe_left`.

## Configuração no Edge AI Lab

| Campo | `dataset_centrado.csv` | merge do `bruto/` (sem centralizar) |
|---|---|---|
| Task type | Multi Classification | Multi Classification |
| Target | `class` | `class` |
| Data Type | 16-bit Integer | 16-bit Integer |
| Normalization | Unique scale | Unique scale |
| Evaluation metric | **Balanced Accuracy** | **Balanced Accuracy** |
| Window size | **100** | **99** |
| Sliding shift — training | **100** | **33** |
| Sliding shift — inference | 33 | 33 |
| Sub-windowing | 4, com full-window features | 4, com full-window features |
| Weights & Coefficients | Quantization-Aware 16-bit Integer | idem |
| Output format | Floating-point 32-bit (travado) | idem |
| Target hardware | Cortex-M33 | Cortex-M33 |

Shift de treino = janela no centralizado: sobreposição geraria janelas fora de fase
e desfaria o alinhamento. No bruto é o contrário — o 33 ajuda, porque lá o gesto cai
em fase aleatória de qualquer jeito.

## Limitações — leia antes de tirar conclusão

**1. Taxa de amostragem dilatada.** A coleta saiu a 76-94 Hz, não a 100 Hz, e a taxa
varia **por classe**. Na inferência não há NUS e o `k_timer` roda solto a 100 Hz, então
o mesmo gesto ocupa ~76 linhas no treino e ~100 na inferência — esticado. A causa está
no `main.c` do sample: o semáforo `imu_data_ready_sem` tem limite 1 (`main.c:332`) e a
mesma thread amostra e envia, então tick que chega durante o envio é descartado. E o
`id` do `ble_nus.c:143` incrementa **por envio**, não por tick, então essa perda não
gera buraco de id — é invisível para o detector. Ver a nota correspondente no
[`NOTAS_MATERIAL.md`](../../NOTAS_MATERIAL.md).

**2. Uma pessoa só.** A doc do Lab recomenda 1-5 indivíduos para um PoC. O modelo vai
generalizar mal para quem gesticula diferente — o que, em sala, é uma demonstração
melhor que um modelo perfeito.

**3. Desbalanceado.** Depois da centralização são 568 janelas de fundo
(`idle` + `unknown`) contra 247 de gesto, 2,3:1. Daí a Balanced Accuracy na tabela
acima. Se o modelo vier mudo na TAG, aparar `idle` e `unknown` para ~150 janelas cada
é o primeiro ajuste — e não exige recoletar.

**4. Metade das linhas de swipe no `bruto/` são pausa.** A centralização descarta
41% do `swipe_right` e 56% do `swipe_left`: são os intervalos entre gestos, que no
arquivo bruto estão **rotulados como swipe**. Treinar direto do `bruto/` treina esse
rótulo errado. É o argumento concreto de por que a centralização existe.

## Por que não serve para o loop 2

O `05_data_forwarder` produz dado de outra natureza:

| | `03_central_uart` (este dataset) | `05_data_forwarder` |
|---|---|---|
| Canais | 6 | 9, ou 6 com `gesture_compat.conf` |
| Unidades | **mili** | **micro** (`INT32_VALUES=y`) |
| Fundo de escala | ±4 g / ±1000 dps | ±2 g / ±500 dps (`src/sensor/bmi270.c:85` e `:102`) |

Escala e unidade diferentes: um modelo treinado aqui não infere corretamente com dado
de lá, e vice-versa. O loop 2 precisa do próprio dataset de referência, capturado pelo
caminho do 05.
