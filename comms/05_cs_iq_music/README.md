# Channel Sounding · Lab 5 — O IQ no PC: reproduzir o chip e tentar um algoritmo melhor

A Nordic diz, com todas as letras, que o algoritmo do `ras_initiator` é referência:
*"provided just as reference algorithms — we recommend you to work with a third party
algorithm partner if you require more sophisticated algorithms."* O que ela **não** diz é
que o algoritmo vem em fonte — `subsys/bluetooth/cs_de/cs_de.c`, 328 linhas — e que o
IQ cru está numa estrutura que o próprio sample monta. Este lab tira o IQ do chip e
faz duas coisas com ele no PC:

1. **Reproduz o número do firmware** com o mesmo algoritmo, em NumPy. *Entendi o que o
   chip faz?*
2. **Roda um algoritmo de super-resolução** (MUSIC) sobre o mesmo IQ. *O que muda?*

O ganho é **medido, não prometido**. Veja a tabela no fim.

> **Origem.** Firmware: cópia do `ras_initiator` do **nRF Connect SDK v3.4.0** via o
> lab 2, com uma divergência a mais (`csv_dump_report()`), marcada em `src/main.c`.
> Python: `tools/cs_de_numpy.py` é reimplementação do `cs_de.c` da Nordic (código do
> curso); `tools/music/` é cópia do projeto **skig/waves** (MIT) — ver
> [`tools/music/ORIGEM.md`](tools/music/ORIGEM.md).

## Hardware

| Peça | Papel |
|---|---|
| **nRF54L15-TAG** | reflector RAS do lab 1, na bateria |
| **nRF54LM20-DK** | initiator que, além de medir, despeja o IQ na serial USB |
| **PC** | Python 3.11 com `numpy`, `pyserial`, `pytest` |

## Passo 1 — o firmware

O mesmo `meu_tag.conf` dos labs 2 e 3. TAG fora do `DEBUG OUT`.

```
copy ..\02_cs_initiator\meu_tag.conf meu_tag.conf
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/05_cs_iq_music/build_lm20 C:/work/nrf-manaus-2/comms/05_cs_iq_music -- -DEXTRA_CONF_FILE=meu_tag.conf
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/05_cs_iq_music/build_lm20
```

O que sai na serial (115200 8N1), por procedure — 75 linhas `IQ` e uma `CS`:

```
IQ,42,0,2,-812.0,455.0,301.0,-903.0
IQ,42,0,3,-799.0,480.0,318.0,-897.0
...
CS,42,0,1,1.023,1.087,1.349,12,180
   │  │ │   │     │     │    │  └─ rtt acumulado (meias-ns), como o cs_de recebe
   │  │ │   │     │     │    └──── quantos steps de RTT entraram
   │  │ │   │     │     └───────── rtt (m)          ┐
   │  │ │   │     └─────────────── phase_slope (m)  ├ o que o FIRMWARE calculou
   │  │ │   └───────────────────── ifft (m)         ┘
   │  │ └───────────────────────── tone quality (1 = OK)
   │  └─────────────────────────── antenna path
   └────────────────────────────── ranging counter
```

O firmware roda a **1 procedure/s de propósito**: cada procedure é ~2,7 kB de CSV, e
a 115200 8N1 (~11,5 kB/s úteis) o teto é ~4 procedures/s — menos que o default do
sample. O botão é `CONFIG_LAB_PROCEDURE_INTERVAL` (`prj.conf` já traz `=50`, 1 s).

O log do sample (`Filtrando pelo tag`, `CS procedures enabled`, ...) vai para o
**RTT**, não para a serial — senão intercalaria com o CSV. Se precisar dele,
`JLinkRTTLogger -Device CORTEX-M33 -RTTSearchRanges "0x20000000 0x80000" -USB <serial da DK>`.

## Passo 2 — o ambiente Python

```
cd tools
python -m pip install -r requirements.txt
python -m pytest -q          # 20 passed: o port e o adaptador batem com IQ sintetico
```

## Passo 3 — capturar

```
python cs_capture.py --seconds 30 --out ../capturas/1m.csv
```

Acha a porta sozinho, mostra a taxa e a última estimativa, e guarda só as linhas
válidas. Repita para 3 m e 5 m, com trena. `capturas/` não é versionada.

O `cs_capture.py` ativa o DTR ao abrir a porta: a serial USB da LM20-DK só fala com
o VCOM se o DTR estiver ligado. Se você abrir a mesma COM num terminal próprio
(PuTTY, `screen`, etc.) e não ver nada, é essa a causa — ative o DTR do lado do
terminal.

## Passo 4 — comparar

```
python cs_compare.py ../capturas/1m.csv
```

```
counter tq  ifft_fw  ifft_np   d_ifft    ps_fw    ps_np   rtt_fw   rtt_np    music
     42  1    1.023    1.021   -0.002    1.087    1.087    1.349    1.349     0.98
...
 estimador    media   desvio    n
   ifft_fw    x.xxx    x.xxx   nn
     ps_fw    x.xxx    x.xxx   nn
    rtt_fw    x.xxx    x.xxx   nn
     music    x.xxx    x.xxx   nn
```

Três colunas para olhar primeiro:

- **`d_ifft`** — NumPy menos firmware. Tem que ser ~0 (o chip calcula em float32).
  Se não for, o port não reproduz o chip, e nada do resto vale.
- **`rtt_np` = `rtt_fw`** a três casas: é uma média, não há o que divergir.
- **`music`** — o mesmo IQ, outro algoritmo. Compare média **e desvio** com `ifft_fw`.

## Sem hardware? Use o dataset de referência

[`dataset_referencia/`](dataset_referencia/) traz as quatro capturas reais que geraram a
tabela no fim deste README (1, 3 e 5 m com trena, mais a montagem de bancada a 0,78 m).
O `cs_compare.py` roda nelas do mesmo jeito:

```
python cs_compare.py ../dataset_referencia/ref_3m.csv
```

## Passo 5 — ler o algoritmo

Abra `tools/cs_de_numpy.py` e `C:\ncs\v3.4.0\nrf\subsys\bluetooth\cs_de\cs_de.c`
lado a lado. Cada função do Python tem no docstring o nome da função C que reproduz:

| C (`cs_de.c`) | Python | O que faz |
|---|---|---|
| `cs_de_combined_iq_calculate` | `combine` | produto complexo local × remoto: soma as fases da ida e da volta |
| `cs_de_rtt` | `rtt_m` | média das meias-ns, metade é o voo, × c |
| `cs_de_phase_slope` | `phase_slope_m` | fase entre canais adjacentes → inclinação → distância |
| `calculate_ifft_mag` | `ifft_mag` | IFFT via FFT do conjugado |
| `find_ifft_peak_index` | `_find_peak_index` | maior pico; depois procura um **mais curto** que seja ≥ 40 % dele |
| `calculate_left_null_compensation_of_peak` | `_left_null_compensation` | se o nulo à esquerda está longe demais, o pico foi alargado por multipath — recua |
| `calculate_ifft_peak_index_to_distance` | `_peak_to_distance` | interpolação parabólica do pico |

Duas perguntas para discutir: por que a busca por um pico "mais curto" (o que
acontece numa reflexão forte)? E por que a compensação pelo nulo (o que o multipath
faz com a largura do pico)?

O MUSIC vendido em `tools/music/` (ver `ORIGEM.md`) expõe duas funções encadeadas —
`compute_music_spectrum` monta o pseudo-espectro a partir de fase e amplitude por
canal, `calculate_distance_from_music` acha o pico nele — e constrói o vetor de
apontamento pela **posição** do canal na lista, não pelo seu número. Por isso
`music_adapter.py` preenche os três canais reservados (23–25) interpolando fase
desenrolada e amplitude entre os vizinhos válidos antes de chamar o MUSIC: sem isso,
o buraco de 3 canais viraria um salto de fase e deslocaria o pico. Essa interpolação
é exata para um caminho único e uma aproximação sob multipath, válida até ~18 m de
distância (≈ 37 m de caminho de ida-e-volta, a partir de 4·Δφ < π).

### A grade do MUSIC — e por que o pico é interpolado

`calculate_distance_from_music` devolve o **argmax cru** do pseudo-espectro, numa
grade de 512 atrasos entre 0 e 500 ns. Isso é 0,98 ns por bin — **14,7 cm** de
distância, já com o `/2` de ida e volta. A estimativa sai quantizada nesse passo, e
na bancada dá para ver a olho nu: 100 procedures com o TAG parado a 1 m caíram em
**apenas 4 valores distintos**, espaçados exatamente 0,1467 m.

O `cs_de` resolve o mesmo problema na IFFT com interpolação parabólica do pico
(`calculate_ifft_peak_index_to_distance`, a última linha da tabela acima).
`music_adapter._peak_distance` faz o equivalente sobre o log do pseudo-espectro. É
o default; `cs_compare.py --music-grid` desliga, para comparar:

```bash
python cs_compare.py ../dataset_referencia/ref_5m.csv --music-grid
```

O efeito depende de quanto o dado já espalha por conta própria:

| | grade crua (waves) | pico interpolado |
|---|---|---|
| `ref_5m.csv` (TAG na bateria, 5 m) | 6,204 ± 0,296 · 7 valores distintos | 6,215 ± 0,291 · 30 |
| `ref_1m_tag_na_dk_1ap.csv` (TAG parado, 1 m) | 2,579 ± 0,072 · 4 valores distintos | 2,575 ± 0,028 · 99 |

Nos datasets de 1/3/5 m com o TAG na bateria, o espalhamento físico já era bem
maior que o passo da grade e a interpolação **quase não muda nada** — é higiene, não
ganho. Na captura mais estável (TAG parado sobre a DK, um caminho de antena) era a
grade que dominava: o desvio cai de 0,072 para **0,028 m**, 2,5×. A lição vale para
qualquer estimador: antes de comparar desvios, veja se um deles não está preso na
resolução da própria grade.

## Medição de referência da bancada

Medido em 2026-09-05 na bancada do curso: trena da antena do LM20-DK ao TAG, linha de
visada, TAG na bateria, 30 s por distância (`CONFIG_LAB_PROCEDURE_INTERVAL=50`, ~1
procedure/s). Média ± desvio em metros:

| Trena | `ifft_fw` | `phase_slope` | `rtt` | `music` | n |
|---|---|---|---|---|---|
| 1,0 m | 2,05 ± 0,23 | 2,70 ± 0,16 | 1,89 ± 0,61 | 2,17 ± 0,16 | 30 |
| 3,0 m | 4,46 ± 0,48 | 5,84 ± 0,72 | 4,42 ± 0,96 | 4,99 ± 0,96 | 30 |
| 5,0 m | 5,86 ± 0,84 | 6,75 ± 0,38 | 6,14 ± 1,02 | 6,21 ± 0,29 | 30 |

E, na mesma data, com o TAG **montado sobre uma nRF54L15-DK** ao lado de cabos USB
(a montagem de bancada, não a de campo), a 0,78 m:

| Trena | `ifft_fw` | `phase_slope` | `rtt` | `music` | n |
|---|---|---|---|---|---|
| 0,78 m | 1,92 ± 0,09 | 2,16 ± 0,16 | 1,39 ± 0,70 | 1,94 ± 0,07 | 69 |

![Quatro estimadores contra a trena — média ± desvio por ponto, com a reta ideal](cs_vies.png)

Três coisas que os números dizem, sem precisar de mais teoria:

- **Todos os estimadores leem longe demais**, de +0,9 a +1,5 m no `ifft` — e o viés
  **não é constante**, então não é um simples offset de calibração para subtrair.
  Causas plausíveis, sem afirmar qual pesa mais: multipath da sala, antena única,
  algoritmo de referência sem calibração de atraso de grupo.
- **O espalhamento cresce com a distância** no `ifft` (0,23 → 0,48 → 0,84 m) e no
  `rtt` (sempre o mais ruidoso, ~1 m).
- **O MUSIC reduz o espalhamento, não o viés**: a 5 m, 0,29 m contra 0,84 m do `ifft`,
  com a média igualmente deslocada. É o ganho realista de um algoritmo melhor sobre os
  mesmos dados — repetibilidade — e o limite do que um algoritmo sozinho consegue.

O que ler nela: o **desvio** de cada estimador é a sua repetibilidade; a diferença da
média para a trena é o **viés**. O `rtt` é o mais grosseiro; o `phase_slope` é o mais
simples; o `ifft` é o que a Nordic escolhe como `best`; o `music` é o que este lab
acrescenta. Nenhum deles é "o teto da tecnologia" — são quatro algoritmos sobre um
caminho de antena, sem calibração.

## Duas antenas — o experimento, e o que ele respondeu

O nRF54L15-TAG tem **duas antenas** e o reflector do lab 1 já as configura; a
LM20-DK tem uma. O par 1 × 2 dá **dois caminhos de antena** (A1-B1 e A1-B2), e é o
*initiator* quem decide usar um ou dois — o TAG não muda, e não precisa ser
regravado para alternar:

```
west build ... -- -DEXTRA_CONF_FILE=meu_tag.conf -DCONFIG_LAB_ANTENNA_PATHS=2
```

Com 2, cada procedure aparece **duas vezes** no CSV, `ap 0` e `ap 1` do mesmo
ranging counter, e o `cs_compare.py` ganha quatro colunas: `ifft_ap1`, `music_ap1`,
`music_2ap` (soma dos pseudo-espectros dos dois caminhos) e `music_cov` (média das
covariâncias antes da autodecomposição — a forma canônica de dar diversidade ao
MUSIC; ver `tools/music/ORIGEM.md`). O `rtt` vem `nan` nas linhas de `ap 1`: os
tempos acumulados são os mesmos nos dois caminhos, e o `cs_de` só preenche a
estimativa de RTT no primeiro.

### O que foi medido

Duas distâncias, quatro capturas versionadas. Em cada distância, as duas
configurações foram medidas **na mesma posição, uma logo após a outra**, trocando só
o firmware do initiator. Cada linha é a mediana de ~100 procedures; a dispersão é a
**MAD** (desvio absoluto mediano, escalado para comparar com o desvio padrão), que
não se deixa inflar por meia dúzia de procedures ruins.

**1,00 m — TAG apoiado sobre uma nRF54L15-DK**

| | ifft | phase_slope | MUSIC |
|---|---|---|---|
| **1 caminho** | +1,45 · MAD **0,039** | +1,64 · MAD **0,040** | +1,58 · MAD **0,033** |
| 2 caminhos · `ap 0` | +1,44 · MAD 0,076 | +1,65 · MAD 0,156 | +1,60 · MAD 0,049 |
| 2 caminhos · `ap 1` | +1,38 · MAD 0,052 | — | +1,57 · MAD 0,048 |
| 2 caminhos · combinados | — | — | +1,59 · MAD 0,047 |

**3,00 m — TAG na bateria, linha de visada**

| | ifft | phase_slope | MUSIC |
|---|---|---|---|
| **1 caminho** | +1,11 · MAD **0,037** | +1,66 · MAD **0,119** | +1,07 · MAD **0,035** |
| 2 caminhos · `ap 0` | +1,08 · MAD 0,047 | +1,61 · MAD 0,259 | +1,06 · MAD 0,049 |
| 2 caminhos · `ap 1` | **+2,01** · MAD 0,043 | — | **+2,10** · MAD 0,051 |
| 2 caminhos · combinados | — | — | +1,56 · MAD 0,043 |

Os números são o **viés** (mediana do lido menos a trena). Confirmado em três rodadas
alternadas por distância (1 → 2 → 1 → 2 → 1 → 2 caminhos, ~100 procedures cada); o
repo versiona uma rodada de cada.

![Um caminho de antena contra dois, em duas distâncias](cs_antenas.png)

### Três leituras

- **Ligar o segundo caminho custa dispersão no primeiro.** É grande e reprodutível
  no `phase_slope`: MAD 0,040 → 0,156 a 1 m, e 0,119 → 0,259 a 3 m. No `ifft` e no
  MUSIC é claro a 1 m (0,039 → 0,076 e 0,033 → 0,049) e pequeno a 3 m (0,037 →
  0,047 e 0,035 → 0,049), da mesma ordem da variação entre rodadas. A explicação
  provável — hipótese nossa, não algo que a doc do SDC confirme — é que o subevent
  tem orçamento de tempo fixo e, com dois caminhos, ele é dividido. O que o dado
  sustenta: os steps de RTT por procedure não mudam (19,2 contra 18,8), então
  encolheu a medida de **tom**, não a de tempo.
- **O segundo caminho nunca é melhor, e pode ser muito pior.** A 1 m ele empata com
  o primeiro (diferença de −0,03 m). A 3 m ele lê **1,07 m mais longe** — e com a
  mesma repetibilidade do primeiro (MAD 0,043 contra 0,047). É um erro *estável*,
  não ruído: a segunda antena se fixa num caminho mais longo.
- **Nenhuma combinação recupera.** A 1 m as duas combinações empatam com o pior dos
  caminhos (MAD 0,047–0,048 contra 0,033 de um caminho só). A 3 m elas pioram a
  **exatidão**: o erro mediano do MUSIC sai de 1,06 m (`ap 0`) para 1,56 m com a
  média das covariâncias e 2,03 m com a soma dos espectros, porque as duas puxam a
  estimativa para o caminho errado.

### O que muda com a distância

A relação entre os dois caminhos **não é uma constante do hardware**. A correlação
entre a estimativa do `ap 0` e a do `ap 1`, procedure a procedure, é **+0,94 a 1 m**
e **+0,10 a 3 m**. São dois regimes opostos, e nenhum ajuda:

- **A 1 m os caminhos são redundantes.** As duas antenas veem praticamente o mesmo
  canal, então combinar não acrescenta informação — só ruído.
- **A 3 m os caminhos são independentes** (é a diversidade que se procurava!), mas
  um deles está 1 m errado. Diversidade só paga quando os caminhos são independentes
  **e** comparavelmente bons; aqui, misturar um caminho bom com um ruim dá um
  resultado no meio.

Isso também desmente a leitura fácil de que o desvio do `ap 1` seria um offset fixo
da segunda antena: ele muda de −0,03 m para +1,07 m entre as duas medidas. Não é
comprimento elétrico — é geometria, orientação e o que cada antena enxerga.

Por isso `CONFIG_LAB_ANTENNA_PATHS` tem **default 1**: nas duas distâncias, dois
caminhos custam dispersão e não devolvem exatidão.

**O que este experimento não diz.** As duas distâncias diferem também na
**montagem** (1 m com o TAG apoiado numa DK, 3 m com o TAG na bateria), então não dá
para atribuir a diferença à distância sozinha. E as duas são linha de visada, numa
sala só. Diversidade de antena existe justamente para o caso oposto — multipath
forte, obstrução, o caminho direto atenuado num dos lados. O experimento que falta é
repetir a tabela com o corpo de alguém entre o TAG e a DK, ou com o TAG encostado em
metal (o experimento B do lab 2). O código já está pronto: é só capturar com
`CONFIG_LAB_ANTENNA_PATHS=2` e rodar o `cs_compare.py`.

## Onde ir a partir daqui

- `--nfft 1024` no `cs_compare.py` **não** melhora a resolução — só a interpolação
  (zero-padding). Confira.
- `music/cs_music.py` assume **um** caminho (`_N_SIGNALS = 1`). Com dois, o que muda
  na obstrução do lab 2?
- **Com obstrução**, refaça a tabela da seção "Duas antenas": é a condição em que a
  diversidade de antena deveria finalmente pagar. Em linha de visada, não pagou.
- `NORMALIZE_COV = False` no `music_adapter.py` faz a média das covariâncias pesar
  cada caminho pela potência dele. Muda alguma coisa quando as antenas têm ganhos
  diferentes?
- Parceiros de algoritmo da Nordic (Metirionic e outros) é o caminho de produto.

## A divergência a mais deste lab

**`src/main.c` — `csv_dump_report()`**, chamada em `ranging_data_cb()` logo após
`cs_de_calc()`. Despeja `m_cs_de_report` — a estrutura que o próprio sample monta — em
CSV por `printk`. `prj.conf` manda o log para o RTT (`CONFIG_LOG_BACKEND_UART=n`,
`CONFIG_LOG_PRINTK=n`) para a serial ficar só com o CSV.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/subsys/bluetooth/cs_de/cs_de.c`, `nrf/include/bluetooth/cs_de.h`
- Nordic, *Bluetooth Channel Sounding Distance Estimation* (doc da biblioteca `cs_de`)
- Nordic, webinar *Bluetooth Channel Sounding: From theory to practice on the nRF54L Series and Android* (a posição sobre algoritmos de referência e parceiros)
- Nordic DevZone #128575, *Channel Sounding ranging algorithm* — `cs_de` é experimental
- skig/waves — https://github.com/skig/waves (MIT): `toolset/processing/cs_music.py`
- Bluetooth SIG, *Bluetooth Channel Sounding: A step towards 10-cm ranging accuracy...* — super-resolução vs IFFT (não verificado por nós; é o que a tabela acima mede)
