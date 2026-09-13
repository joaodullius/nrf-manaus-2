# Redes Não Terrestres — NB-IoT NTN no nRF9151, GEO e LEO

Comparação GEO × LEO em NB-IoT NTN (3GPP R17), demo ao vivo com satélite GEO
(Skylo) e figuras de passadas LEO reais (SatelIoT), mais uma passada sintética
completa composta de trechos reais.

## Hardware

1 × nRF9151-SMA-DK com SIM Skylo (eminify) e antena NTN externa. Os demais
kits do treinamento (nRF54LM20-DK, nRF54L15-TAG, nRF7002-EBII, u-blox
EVK-X20P) não participam deste módulo.

## Formato

Demo do instrutor. Não há lab de aluno: nenhum kit de aluno tem SIM NTN, e
não há passada SatelIoT sobre Manaus na semana do curso. O que fica para o
aluno é o código de referência — os scripts de captura e análise em
[`tools/`](tools/) e os snapshots de firmware em [`firmware/`](firmware/).

## Conteúdo

| Pasta | O que é | Usada em |
|---|---|---|
| [`01_geo_live/`](01_geo_live/) | Roteiro e script da demo Skylo (GEO) por Serial Modem | Bloco de demo, 30 min |
| [`02_leo_passada/`](02_leo_passada/) | Traces LEO reais e a passada sintética completa; figuras pelo `plot_snr.py` | Parte B da teoria |
| [`tools/`](tools/) | Conversão de trace, plot, previsão de passada, testes de modem | Referência |
| [`firmware/geo/`](firmware/geo/), [`firmware/leo/`](firmware/leo/) | Snapshots dos apps do Asset Tracker Template | Referência |
| [`hex/`](hex/) | Serial Modem v1.0.0 (`.hex`, no repositório), passos de gravação e onde obter o firmware de modem NTN (licença Nordic, só link) | Demo |

## Ordem de ensino

Bloco de ~2 h no dia 4, sem folga:

| Bloco | Minutos |
|---|---|
| Parte A — comparação GEO × LEO por parâmetro | 30 |
| Parte B — procedimento de acesso, com as figuras da passada LEO | 40 |
| Demo GEO ao vivo (Skylo, Serial Modem) | 30 |
| Fecho: critérios de seleção e o que o NCS entrega | 10 |
| **Total** | **110** |

## O que o aluno precisa saber antes

O GNSS interno do nRF9151 e o NTN **não rodam ao mesmo tempo** — o modem
alterna entre um fluxo GNSS-only e um fluxo NTN-only, sem os dois ativos
juntos. O firmware de modem NTN (`mfw_nrf9151-ntn`) **substitui** o firmware
de modem usado no módulo de GNSS (`mfw_nrf91x1`); regravar o kit para voltar
ao GNSS com assistência.

## Bandas e canal

| Banda | Nome | UL (MHz) | DL (MHz) | N_Offs-DL | EARFCN DL |
|---|---|---|---|---|---|
| 255 | L-band NTN (global) | 1626,5–1660,5 | 1525–1559 | 228 736 | 228 736–229 075 |
| 256 | S-band NTN (Europa) | 1980–2010 | 2170–2200 | 229 076 | 229 076–229 375 |
| 23/252 | S-band NTN (EUA) | 2000–2020 | 2180–2200 | 7 500 | 7 500–7 699 |
| 249 | TDD | 1616–1626,5 | 1616–1626,5 | — | — |

F_DL = F_DL_low + 0,1 · (N_DL − N_Offs-DL). O canal usado nos traces de
referência, EARFCN **229232**, cai na banda 256: **2185,6 MHz DL / 1995,6 MHz
UL**.

## As figuras da passada LEO

Saem do `plot_snr.py` de [`tools/`](tools/), sobre os traces reais e sobre a passada
sintética composta pelo `compoe_passada.py`:

```bash
cd ntn/02_leo_passada
python compoe_passada.py
python ../tools/plot_snr.py passada_sintetica_SIOT1.txt -s SATELIOT_1 --tle-file tle/sateliot_1_20260913.tle --no-open --out-dir plots
```

O que é medido e o que é calculado ou composto:

- **RSRP/SNR e os eventos** (MIB, SIB1, SI, RAR, grants, NAS, `+CSCON`, UDP, T310) vêm
  direto dos traces reais.
- **Elevação e azimute** não estão no trace: são calculados por SGP4 a partir do TLE.
- **A passada sintética** cobre do nascer ao pôr; nenhum trace real cobre a passada
  inteira, porque o firmware liga o rádio só no pico. Os trechos reais mantêm seu timing
  interno; só a busca de célula entre o modem ligar e o MIB é gerada, e cada linha gerada
  leva `[sintetico]`. Detalhes em [`02_leo_passada/README.md`](02_leo_passada/README.md).

## Passadas SatelIoT na semana do curso

A SatelIoT informou que o SATELIOT_1 não está disponível em Manaus na semana do curso. O
mapa em [`02_leo_passada/semana/`](02_leo_passada/semana/) (SGP4, TLE do CelesTrak de 13/09)
mostra as 28 passadas do SATELIOT_1 sobre o SIDIA entre 13 e 20/09: só uma chega a 50°, no
sábado 12/09 à noite, antes do curso; as demais ficam entre 4° e 46°.
