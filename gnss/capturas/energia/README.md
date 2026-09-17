# Corrente do nRF9151 — modo periódico e ciclo de A-GNSS

Capturas de 09/09/2026 com o PPK2 em **amperímetro** no P22 da nRF9151 SMA-DK
(jumper fora, VOUT no pino 1, VIN no pino 2, GND no pino 4), medindo o trilho
`VDD_nRF` que alimenta o SiP. A placa alimenta; o PPK2 só mede. Mesma antena
(ANN-MB2 no J2) e mesma posição das demais capturas do módulo.

**O trilho está a ~5 V** (é o `VDD_5V` da USB que chega ao pino 1 pelo jumper de
fábrica). Os números da Product Specification são a 3,7 V. O SiP tem DC/DC
interno, então a potência é aproximadamente constante e a corrente **cai com a
tensão**: 35 mA medidos a 5 V correspondem a ~47 mA a 3,7 V. As figuras do
material dizem isso.

| arquivo | firmware | o que é |
|---|---|---|
| `periodico_console.csv` + `.log` | `build_periodico` (periódico 120 s, assistência mínima, LTE sob demanda) | 720 s em bins de 100 ms, com o console ligado |
| `periodico_mudo.csv` | o mesmo, com `CONFIG_LOG=n` e `AT_HOST_LIBRARY=n` | 720 s em bins de 20 ms, sem console |
| `nuvem_ciclos.csv` + `.log` | `build_nuvem` (TTFF a frio, A-GNSS pela nRF Cloud, LTE-M) | 25 min em bins de 1 s, seis ciclos de partida a frio |

Colunas dos CSV: `t_s, media_mA, min_mA, max_mA, n` — média, mínimo e máximo
dentro de cada bin, e o número de amostras do PPK2 que caíram nele.

## O que se lê deles

- **Rastreando, o GNSS custa um platô liso de ~35 mA** (a 5 V) nos três arquivos.
- **Piso de sono:** 0,429 mA com o console ligado, **2 µA** sem console. O
  `LOG_MODE_IMMEDIATE` do console nunca deixa o SoC dormir — é por isso que a
  metodologia manda desligar o console para medir energia.
- **Modo periódico a 120 s, em regime (depois da primeira partida):** média de
  1,40 mA com console e **0,31 mA** sem console. A Product Specification dá
  0,5 mA para fix a cada 2 min com A-GPS, incluindo o LTE.
- **Ciclo de A-GNSS:** a janela `+CSCON: 1` → `+CSCON: 0` dura ~30 s, o dado de
  assistência chega em menos de 1 s, e o GNSS só começa a rastrear quando a rede
  libera a conexão. Figura em `doc/gnss/img/rrc_release_agnss.png`, gerada por
  `doc-source/gnss/tools/rrc_corrente.py nuvem_ciclos.log nuvem_ciclos.csv <png>` (repo de docs).

Figuras do material: `doc/_template/fig_m2_07_periodico.py` e
`fig_m2_07_consumo.py` leem estes arquivos e escrevem `doc/gnss/data/energia_gnss.json`.
