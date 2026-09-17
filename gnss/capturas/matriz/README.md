# Matriz de dispersão — nRF9151 e ZED-X20P medidos ao mesmo tempo

Campanha de 09/09/2026, 13:06–14:35, na janela entre os dois prédios (visada
parcial). Os dois receptores gravaram **simultaneamente**, cada um com sua
ANN-MB2 sobre plano de terra, lado a lado.

## O desenho

Quatro condições no X20P, em blocos de **300 s cada — todos com a mesma
duração**, e o nRF9151 gravando contínuo em paralelo:

| | sem correção | com PointPerfect (NTRIP) |
|---|---|---|
| **sem GLONASS** | A | C |
| **com GLONASS** | B | D |

Três rodadas com a ordem girada (`ABCD` → `DCBA` → `BDAC`). SBAS desligado do
começo ao fim. A correção das condições C e D é o **PointPerfect via Nordian**
(PPP-RTK por NTRIP, `services.nordian.com`, mountpoint `NEAR-RTCM-VRS`): base
virtual gerada na posição do GGA do rover, baseline efetiva ~0.

Cada decisão acima existe para tapar um buraco que já produziu conclusão errada
nesta bancada:

- **Duração igual em todos os blocos.** O CEP cresce com a janela: a mesma
  captura deu 1,129 m inteira (15 min) e 0,338 m em janelas de 5 min. Comparar
  durações diferentes mede a duração, não a condição.
- **Ordem girada.** O ambiente deriva o bastante para engolir os efeitos — o
  nRF9151, sem nada mudar nele, variou de 1,80 a 4,75 m de CEP50 ao longo da
  campanha. Blocos enfileirados comparariam horas, não condições.
- **SBAS desligado.** Ele entrando e saindo em proporções diferentes por bloco
  já fabricou um "ganho de 2,6× do GLONASS" inexistente.
- **Um CEP por bloco, nunca concatenado.** Entre blocos a deriva entra como
  dispersão.

## Os arquivos

- `rN_X.nmea` / `rN_X.uc2` — X20P (COM17), 300 s. `N` é a rodada, `X` a condição.
- `9151_rN_X.nmea` / `.uc2` — nRF9151 (COM23) **na mesma janela de tempo**.
- `_janelas.json` — início e fim de cada bloco, em tempo unix.
- `_diario.txt` — o log da campanha.
- `degrau.png` — a figura.

Os `.uc2` abrem no u-center 2 para reproduzir a captura e conferir o mapa de
desvio contra o nosso.

Faltam `r3_A` e `r3_C`: a campanha foi encerrada antes deles para liberar a
bancada. As duas condições usadas na figura (B e D) têm as três rodadas.

## O que saiu

Todas as constelações ligadas, mediana dos blocos:

| | CEP50 | CEP95 | satélites usados |
|---|---|---|---|
| nRF9151 (GPS L1) | 2,49 m | 5,54 m | 8,5 |
| X20P autônomo | 0,24 m | 0,55 m | 27,1 |
| X20P + PointPerfect (PPP-RTK por NTRIP), bloco inteiro | 0,24 m | 0,48 m | 27,1 |
| X20P + PointPerfect, **só épocas em RTK fixo** | **0,06 m** | **0,10 m** | 27,1 |

**O degrau entre receptores é de ~10×**, com as faixas bem separadas: o pior
bloco do X20P (0,32 m) está seis vezes abaixo do melhor bloco do nRF9151
(1,80 m). Como mediram o mesmo céu nos mesmos minutos, não há como atribuir
isso a condição de propagação.

### Duas armadilhas que esta campanha revelou

**O CEP de um bloco misto não mede ruído, mede o degrau entre soluções.** Um
bloco que passa parte do tempo em RTK fixo e parte em flutuante tem as duas
nuvens deslocadas uma da outra, e essa distância entra inteira na conta. Em
`r2_D` o bloco inteiro dá 0,479 m e o recorte das épocas fixas dá 0,069 m — 7×
de diferença produzida pela transição, não por dispersão. Por isso a tabela
separa as duas linhas.

**O GLONASS não muda a dispersão, muda a capacidade de fixar ambiguidade.**

| | épocas em RTK fixo |
|---|---|
| com GLONASS (blocos D) | 306 de 901 |
| sem GLONASS (blocos C) | **0 de 600** |

É um efeito categórico, invisível no CEP. Quando o RTK fixou, levou 107 s e
187 s **dentro do bloco** — depois dos 240 s de convergência que o roteiro já
concedia. Nesta visada, o tempo até o RTK fixo passa de 5 minutos.

### O `numSV` da GGA não serve para contar satélites

O NMEA 0183 limita esse campo a 12, e com multiconstelação ele fica cravado em
12 com ou sem GLONASS. Os números da tabela vêm dos GSA, que listam os PRN
efetivamente usados. Um gráfico de "satélites usados" feito da GGA mostraria uma
linha reta e esconderia exatamente o que se quer demonstrar.
