# Origem e uso — `music/`

Copia do estimador MUSIC do projeto **waves**, uma ferramenta open source de analise
de Channel Sounding para o nRF54L15 DK.

| | |
|---|---|
| Upstream | https://github.com/skig/waves |
| Arquivos | `toolset/processing/cs_music.py`, `toolset/constants.py`, `LICENSE` |
| Branch / commit | `main` · `1b8eb7ad27e478af1215f361cbef494b3095bb74` (2026-05-03) |
| Copiado em | 2026-09-05 |
| Licenca | MIT (arquivo `LICENSE` ao lado, do upstream) |
| Alteracao local | Em `cs_music.py`: so a linha de import (`toolset.constants` -> `.constants`), marcada. O algoritmo esta intocado. |

## Para que serve

`cs_de_numpy.py` reproduz o que o firmware da Nordic faz: IFFT sobre os tons, pico =
caminho mais curto. A resolucao bruta do IFFT sobre 75 MHz de banda e de ~2 m por
bin, e a interpolacao do pico e o que a leva a decimetros. **MUSIC** (MUltiple SIgnal
Classification) e o metodo classico de super-resolucao: em vez de procurar o pico da
transformada, decompoe a matriz de covariancia dos tons em subespaco de sinal e de
ruido e varre os atrasos possiveis procurando onde o vetor de direcao e ortogonal ao
ruido. Resolve caminhos mais proximos entre si do que o IFFT consegue.

## O que o arquivo faz (lido do fonte)

- Expoe duas funcoes, nao uma so — a assinatura lida diverge da premissa inicial da
  tarefa (que esperava `calculate_distance_from_music(phase_data, amplitude_data)`):
  - `compute_music_spectrum(phase_data, amplitude_data) -> (delays_ns, pseudo_spectrum)`,
    ambos `Optional[np.ndarray]` (`None, None` se houver menos de 4 canais em comum
    entre os dois dicionarios).
  - `calculate_distance_from_music(delays_ns, pseudo_spectrum) -> float`: recebe a
    saida da funcao acima (nao os dicionarios de fase/amplitude) e devolve a
    distancia (m) do pico do pseudo-espectro.
- Entrada de `compute_music_spectrum`: dois dicionarios indexados por canal — fase
  (rad) e amplitude (dB). Minimo de 4 canais em comum.
- Monta o vetor complexo `10**(amp/20) * exp(j*fase)` por canal.
- Covariancia por *spatial smoothing* (subarrays sobrepostos, tamanho `_SUBARRAY_LEN`
  ou `N // 2` se `None`, com piso `_N_SIGNALS + 1`).
- Autodecomposicao (`np.linalg.eigh`); subespaco de ruido = todos menos
  `_N_SIGNALS = 1` autovetores (os de maior autovalor).
- Pseudo-espectro `1 / |a(tau)^H E_n|^2` numa grade de `_N_DELAY_POINTS = 512`
  atrasos entre 0 e `_MAX_DELAY_NS = 500` ns.
- `calculate_distance_from_music` devolve `delays_ns[argmax(pseudo_spectrum)] *
  SPEED_OF_LIGHT / 1e9` — a distancia correspondente ao atraso do pico.
- O vetor de apontamento (`lags = np.arange(L)`) e construido pela POSICAO do
  canal na lista ordenada de canais comuns, assumindo 1 MHz entre vizinhos —
  nunca pelo numero real do canal (a chave do dicionario so serve para
  ordenar e indexar fase/amplitude). Canais nao contiguos (com buracos) violam
  essa premissa e deslocam o pico do pseudo-espectro (ver secao seguinte).

## O que o curso acrescenta em volta (`../music_adapter.py`)

O IQ que o nosso firmware entrega e o **produto** local x remoto — a fase acumulada
na **ida e na volta**. O `waves` foi escrito para outra fonte de dados (fase de um
unico trecho, nao ida-e-volta) e, alem disso, expoe duas funcoes encadeadas em vez
de uma so: o adaptador chama `compute_music_spectrum(phase, amp)` e passa o par
`(delays_ns, pseudo_spectrum)` resultante para `calculate_distance_from_music`.

Alem disso, como o `waves` monta o vetor de apontamento pela POSICAO do canal (nao
pelo numero real — ver secao anterior), os canais reservados zerados (23..25,
indices 21..23) nao podem ser simplesmente omitidos: isso criaria um buraco na
lista ordenada de canais comuns e um salto de fase equivalente a "pular" 4 MHz em
vez de 1 MHz naquele ponto, deslocando o pico do pseudo-espectro (deslocamento que
cresce com a distancia real). Por isso `music_adapter._fill_reserved_channels`
preenche os buracos INTERIORES (entre o primeiro e o ultimo canal valido) por
interpolacao linear de fase desenrolada (`np.unwrap`) e de amplitude entre os
canais validos vizinhos, antes de montar os dicionarios fase/amplitude. Essa
interpolacao e exata para um caminho unico (a fase e linear em frequencia) e uma
aproximacao sob multipath; e valida enquanto `4*dphi < pi` entre canais adjacentes
usados na interpolacao, ou seja, valida ate ~18 m de distancia (~37 m de caminho de
ida-e-volta, com 1 MHz de espacamento entre canais).

O adaptador tambem converte o IQ combinado em fase/amplitude por canal e ajusta a
convencao de ida-e-volta. O teste `tests/test_music_adapter.py` com IQ sintetico a
3 m e o que fixa essa convencao — os valores finais sao `ROUND_TRIP_DIVISOR = 2.0`
e `CONJUGATE = False` (o `waves` devolve a distancia de ida-e-volta para o nosso IQ
combinado, entao dividir por 2 recupera a distancia real; o sinal da fase ja bate
com a convencao do `waves`, sem precisar conjugar). Com o preenchimento dos canais
reservados, os tres pontos do teste (1 m, 3 m, 7.5 m) caem dentro da tolerancia de
0.2 m: 1.0 -> 1.027 m, 3.0 -> 2.933 m, 7.5 -> 7.480 m.

### Pico do pseudo-espectro: interpolacao parabolica (`INTERPOLATE_PEAK`)

`calculate_distance_from_music` do `waves` devolve o **argmax cru** da grade de
atrasos: 512 pontos entre 0 e 500 ns, ou 0,98 ns por bin — 14,7 cm de distancia,
ja com o `/2` de ida e volta. A estimativa sai quantizada nesse passo. Na bancada
do curso isso ficou visivel: 100 procedures com o TAG parado a 1 m cairam em
**apenas 4 valores distintos**, espacados exatamente 0,1467 m.

O `cs_de` da Nordic resolve o mesmo problema na IFFT com interpolacao parabolica
do pico (`calculate_ifft_peak_index_to_distance`). `music_adapter._peak_distance`
faz o equivalente aqui, sobre o **log** do pseudo-espectro (o pico do MUSIC e
estreito demais para a parabola casar na escala linear). E o default; o
`cs_compare.py --music-grid` desliga, para comparar.

Medido nos quatro datasets de `dataset_referencia/` (grade crua -> interpolado):
a quantizacao some (3 a 7 valores distintos por dataset -> todos distintos), mas
media e desvio **quase nao mudam** (por exemplo, a 5 m: 6,204 +- 0,296 ->
6,215 +- 0,291). Ou seja: a grade nao era o que limitava a precisao — o
espalhamento fisico ja era maior que o passo dela. E uma correcao de higiene, nao
um ganho.

### Varios caminhos de antena: `music_multi_m` e `music_cov_m`

Com `CONFIG_LAB_ANTENNA_PATHS=2` o firmware entrega o IQ de dois caminhos de
antena (A1-B1 e A1-B2) na mesma procedure. Duas formas de combinar:

- `music_multi_m`: soma os pseudo-espectros normalizados dos caminhos e pega o
  pico da soma (combinacao incoerente). Usa so as funcoes publicas do `waves`.
- `music_cov_m`: monta a covariancia de cada caminho e tira a **media delas antes
  da autodecomposicao** — a forma canonica de dar diversidade ao MUSIC. Isso nao
  da para fazer pelas duas funcoes que o `waves` expoe (elas vao do vetor de
  canais direto ao espectro, sem devolver a covariancia), entao
  `_smoothed_covariance` e `_spectrum_from_covariance` **repetem a construcao do
  `cs_music.py`**, com os mesmos parametros importados de la. O teste
  `test_cov_path_matches_waves` exige que, para um caminho so, o espectro daqui
  seja identico ao do arquivo vendorizado: se o upstream mudar, o teste quebra.
  `NORMALIZE_COV = True` divide cada covariancia pelo seu traco, para que a antena
  de maior ganho nao domine a media.

O resultado medido na bancada esta no README do lab (secao "Duas antenas"): a
1 m em linha de visada os dois caminhos sao correlacionados demais (+0,69) para
haver diversidade a explorar, e nenhuma das duas combinacoes bate o melhor
caminho sozinho.

## Limites conhecidos

- `_N_SIGNALS = 1`: assume um caminho dominante. Em multipath forte o pico pode
  cair no caminho refletido.
- Sem calibracao de fase entre initiator e reflector — o `cs_de` tambem nao faz.
- Antena unica por default no lab 2; no lab 5, `CONFIG_LAB_ANTENNA_PATHS`
  escolhe 1 ou 2 caminhos. Medido: dois caminhos nao melhoraram a estimativa
  a 1 m em linha de visada (ver README do lab).
- `_fill_reserved_channels` (no adaptador) e exata so para caminho unico; em
  multipath e uma aproximacao. Deixa de valer quando `4*dphi >= pi` entre canais
  adjacentes usados na interpolacao — na pratica, acima de ~18 m de distancia
  (~37 m de caminho de ida-e-volta, com 1 MHz de espacamento entre canais).
