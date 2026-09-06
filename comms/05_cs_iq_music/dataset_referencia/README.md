# Dataset de referência — IQ de Channel Sounding capturado no preparo do curso

Quatro capturas reais do par nRF54LM20-DK (initiator, lab 5) ↔ nRF54L15-TAG (reflector,
lab 1), no formato exato que o firmware despeja na serial (`IQ,...` / `CS,...`). Servem
para rodar o `cs_compare.py` **sem hardware**, para reproduzir a tabela do README do lab
e para as figuras do material.

## O que tem aqui

| Arquivo | Trena | Procedures | Montagem |
|---|---|---|---|
| [`ref_1m.csv`](ref_1m.csv) | 1,0 m | 30 | TAG na bateria, linha de visada |
| [`ref_3m.csv`](ref_3m.csv) | 3,0 m | 30 | TAG na bateria, linha de visada |
| [`ref_5m.csv`](ref_5m.csv) | 5,0 m | 30 | TAG na bateria, linha de visada |
| [`ref_0m78_tag_na_dk.csv`](ref_0m78_tag_na_dk.csv) | 0,78 m | 69 | TAG encaixado numa nRF54L15-DK, ao lado de cabos USB (montagem de bancada) |

Distâncias medidas com trena, da antena do LM20-DK ao TAG.

## Como foi capturado

- **Data:** 2026-09-05 · uma sala, um par, mesma orientação do TAG nos três pontos
- **Firmware no DK:** `05_cs_iq_music` (`CONFIG_LAB_PROCEDURE_INTERVAL=50`,
  ~1 procedure/s) nos três de 1/3/5 m; o de 0,78 m foi capturado com o intervalo default do
  sample (~3,5 procedures/s)
- **Firmware no TAG:** `01_cs_reflector` (RAS, uma antena em uso)
- **Captura:** `python cs_capture.py --seconds 30 --out ...` (30 s por distância)
- **Dado:** 75 linhas `IQ` por procedure (I/Q local e remoto por canal, canais 2–76;
  23–25 reservados saem zerados) e uma linha `CS` com as estimativas do próprio firmware
  (`ifft`, `phase_slope`, `rtt`)

## Como usar

```bash
cd ../tools
python cs_compare.py ../dataset_referencia/ref_3m.csv
```

Resultado esperado (média ± desvio, metros):

| Trena | `ifft_fw` | `phase_slope` | `rtt` | `music` |
|---|---|---|---|---|
| 1,0 m | 2,05 ± 0,23 | 2,70 ± 0,16 | 1,89 ± 0,61 | 2,17 ± 0,16 |
| 3,0 m | 4,46 ± 0,48 | 5,84 ± 0,72 | 4,42 ± 0,96 | 4,97 ± 0,96 |
| 5,0 m | 5,86 ± 0,84 | 6,75 ± 0,38 | 6,14 ± 1,02 | 6,20 ± 0,30 |
| 0,78 m | 1,92 ± 0,09 | 2,16 ± 0,16 | 1,39 ± 0,70 | 1,95 ± 0,08 |

`d_ifft` (NumPy − firmware) deve sair ≈ 0,000 em todos: o port reproduz o chip.

## Limitações

- **Uma sala, uma orientação, um par.** O viés de +0,9 a +1,5 m é desta bancada; noutra
  sala será outro. É por isso que o lab pede para o aluno medir a sua.
- **Antena única.** O TAG tem duas antenas e o reflector as configura, mas o initiator do
  lab usa um caminho (`CONFIG_BT_RAS_MAX_ANTENNA_PATHS=1`).
- **Sem obstrução.** Não há captura com corpo ou metal no caminho — o experimento B do
  lab 2 fica para a sala.
