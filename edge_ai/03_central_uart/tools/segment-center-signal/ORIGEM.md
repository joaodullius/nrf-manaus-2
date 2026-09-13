# Origem e uso — `segment-center-signal`

Cópia do repositório da Nordic que centraliza gestos discretos na janela de treino.

| | |
|---|---|
| Upstream | https://github.com/nordicsemi-neuton/segment-center-signal |
| Branch / commit | `master` · `5af1abe46f9500a5b21240ec4d57dc0c90caee55` (2025-12-02) |
| Copiado em | 2026-09-01 |
| Alteração local | Em `segment_data_around_peaks.py`: o cabeçalho e o **bloco de execução do fim**. As sete funções do algoritmo estão intocadas. |

> ⚠️ **Licença.** O repositório de origem **não declara licença** — não há arquivo
> `LICENSE` nem metadado de licença no GitHub (`"license": null`). Isso o diferencia
> de todas as outras cópias deste repo, que preservam a LicenseRef-Nordic-5-Clause
> da Nordic. A cópia foi mantida por decisão do curso, para o aluno não depender de
> clone externo em sala. Se o material for redistribuído fora do treinamento,
> reveja este ponto.

Referenciado pela documentação oficial do Edge AI Lab em
*Getting started → Preparing raw dataset → Data segmentation*.

## Para que serve

Gestos **contínuos** (rotação, corrida) podem ser fatiados em qualquer ponto. Gestos
**discretos** (swipe, knock, tap) têm começo e fim: se a janela de 1 s cortar o gesto
ao meio, o treino recebe meio evento. Este script detecta cada evento e recorta uma
janela **centrada no pico**, produzindo segmentos perfeitos.

No nosso dataset isso vale para `swipe_right` e `swipe_left`. `idle` e `unknown` são
contínuos — centralizar não faz sentido.

## Como funciona

1. Toma o eixo escolhido (`work_axis`) e remove o offset DC.
2. Calcula um envelope de amplitude por janela deslizante — `sqrt(min² + max²)`.
3. Detecta onde o envelope cruza `threshold_coef × média` (início e fim de cada evento).
4. Recorta `total_wind_size` linhas centradas no meio de cada evento.

A saída é a concatenação dos segmentos: um CSV que é uma sequência de janelas perfeitas.

## Como rodar

**Não tem CLI.** Você edita o bloco `AJUSTE AQUI` no fim do `.py` e roda. Uma vez
por gesto discreto.

```bash
pip install -r requirements.txt      # numpy, pandas, matplotlib
python segment_data_around_peaks.py
```

O bloco a editar:

```python
gesture   = 'swipe_right'
ARQUIVO   = r'dataset\swipe_right_2026-09-01_10-36-13.csv'

WORK_AXIS      = 'gY'    # so detecta os gestos; nao chega no modelo
THRESHOLD_COEF = 0.95    # calibrado; o 0.5 do upstream nao serve para este dado
nrows_to_remove = 400    # ~5 s de cada ponta

TRAINING_WINDOW_SIZE = 100   # PAR, e igual ao "Window size" do Lab

MOSTRAR_GRAFICOS = True
```

Entrada e saída são resolvidas a partir da pasta do script, então não importa de
onde você chama. O resultado vai para `03_central_uart/dataset_centered/<gesture>.csv`,
já com o header do Lab; os brutos em `dataset/` não são tocados.

Para rodar sem janelas (depois de calibrado), `MOSTRAR_GRAFICOS = False`, ou
`MPLBACKEND=Agg` no ambiente.

### Escolha do eixo — medida, não chute

Medido nas gravações de 2026-09-01 (`03_central_uart/dataset/`):

| Canal | `idle` parado | desvio `swipe_right` | desvio `swipe_left` |
|---|---|---|---|
| `acc_z` | **10012** (gravidade) | 8251 | 6831 |
| `acc_x` | 30 | 5541 | 5638 |
| `gyro_y` (`gY`) | ~0 (desvio 1) | 3039 | 3022 |
| `gyro_z` (`gZ`) | ~0 (desvio 1) | 2534 | 4611 |

Use um **giroscópio**. O detector remove o DC subtraindo a média do arquivo inteiro;
nos acelerômetros a gravidade fica parada em `acc_z ≈ 10012`, e depois da subtração
as **pausas** entre gestos ficam num degrau de ~5600 em vez de zero — o envelope
nunca desce e a detecção degrada. Os giros repousam em zero, então a pausa dá
envelope quase nulo, que é o que o limiar precisa.

`gY` é o mais consistente entre os dois gestos e quase não satura (0,02% e 0,43%
das amostras no trilho de ±1000 dps). `gZ` é o plano B: maior no `swipe_left`
(desvio 4611), mas com **2,06%** das amostras no trilho.

## Quatro armadilhas (verificadas no fonte)

**1. Janela ímpar perde uma linha.** O recorte em `create_segmented_df()` é
`range(centro - int(w/2), centro + int(w/2))` — com `w=99` saem **98** linhas por
segmento, não 99. Aí os segmentos deixam de casar com a janela do Lab e o alinhamento
escorrega 1 linha por gesto. **Use um valor par.** Com 100, o Lab fica com
window 100 / training shift 100, e o firmware acompanha: `INPUT_WINDOW_SIZE` vem do
modelo gerado (`nrf_edgeai_user_model.c:27`), não está cravado na app.

**2. Ele renomeia as colunas.** O `df.columns = ['aX',...,'target']` do bloco de
exemplo sobrescreve o header. Sem o rename de volta, o `prep_dataset.py merge` recusa
o arquivo com "header inesperado" — e o Lab também não aceitaria. O rename está só no
bloco de exemplo, não nas funções: chamando `main()` direto com o nosso header,
`work_axis='acc_x'` funciona e nada precisa ser renomeado.

**3. Cada arquivo precisa ter um múltiplo da janela.** O Lab faz windowing estático
sequencial sobre o CSV inteiro. Se um arquivo contínuo (ex.: `idle`, 32.381 linhas)
vier antes do gesto centralizado no `dataset.csv`, as janelas do Lab começam
desalinhadas dos segmentos e a centralização é jogada fora. Os arquivos processados já
saem múltiplos por construção; apare os contínuos antes do merge:

```python
import pandas as pd, glob
for f in glob.glob('dataset/idle*.csv') + glob.glob('dataset/unknown*.csv'):
    d = pd.read_csv(f)
    d.iloc[:len(d) - len(d) % 100].to_csv(f, index=False)
```

**4. `work_axis` e `threshold_coef` são chutes — e o default não transporta.** Os
valores do exemplo (`aY`, `0.5`) são calibrados para a gravação da Nordic. Medido no
nosso `swipe_right`, o `0.5` deixa o pico na mediana **34** (centro ideal = 50), com só
12% dos gestos na faixa central e 15% de detecções ruins nas pontas. O `0.95` leva a
mediana para 47, o desvio de 18,9 para 8,8 e as pontas para 0,7%.

A faixa útil é estreita — ~0,90 a 1,05. Acima disso o limiar passa do envelope dos
gestos mais fracos e eles **somem em silêncio**: 135 → 44 → 1 → nenhum, sem erro
nenhum aparecer. Abaixo, os gestos se fundem e o recorte sai deslocado. Recalibre a
cada gravação: a intensidade do gesto muda o envelope, e portanto a média que serve
de referência ao limiar.

Como calibrar sem depender do olho: rode e meça onde o pico do canal de trabalho cai
dentro de cada segmento de `TRAINING_WINDOW_SIZE` linhas — se a mediana estiver longe
do meio, o limiar está errado. Os gráficos servem de confirmação, não de critério. E
para vê-los é preciso acrescentar `plt.show()`: o upstream chama `plot_segments()`
duas vezes e nunca mostra as figuras.

Sobra um deslocamento sistemático de ~3 amostras (mediana 47, não 50) que **não** sai
com calibração — ele é estável em toda a faixa útil. É do algoritmo: ele centraliza o
intervalo entre os cruzamentos do limiar, não o pico. Num swipe, com início rápido e
cauda longa, o pico cai um pouco antes do meio do intervalo. Inofensivo, desde que
seja consistente entre os gestos — e é.

**5. `iloc` negativo não dá erro — costura o fim da gravação no segmento.**
`create_segmented_df()` faz `df.iloc[i]` sem checar limites, para
`i` em `range(centro - w/2, centro + w/2)`. Um gesto detectado perto do começo
do arquivo dá `i` negativo, e no pandas isso **conta do fim**: o segmento sai
com linhas do final da gravação enxertadas no meio, sem erro nenhum. No fim do
arquivo o índice estoura e aí sim levanta `IndexError` — falha alto de um lado,
em silêncio do outro. O `../center_gestures.py` descarta esses segmentos antes
de chamar a função e reporta quantos foram.

## Automação: `../center_gestures.py`

Rodar o script à mão exige editar constantes e calibrar no olho. O
[`center_gestures.py`](../center_gestures.py) da pasta acima faz isso sozinho:
carrega as funções daqui (sem copiar), varre eixo × `threshold_coef`, pontua
cada combinação pelo **número absoluto de gestos bem centrados** e imprime a
tabela com a escolhida marcada. Também cobre as armadilhas 2, 3 e 5, e tem um
modo `--continuo` para `idle`/`unknown`.

```bash
python tools/center_gestures.py "dataset/swipe_right_*.csv"
python tools/center_gestures.py "dataset/idle_*.csv" "dataset/unknown_*.csv" --continuo
```

Use este arquivo diretamente quando quiser ver os gráficos ou entender o
algoritmo; use o `center_gestures.py` para produzir dataset.

## Custo

`create_segmented_df()` faz `df_segmented.loc[i] = row` em laço, que realoca o
DataFrame a cada linha. Para 5 min de gravação são milhares de linhas uma a uma —
leva minutos. É lento por construção, não por erro de uso.
