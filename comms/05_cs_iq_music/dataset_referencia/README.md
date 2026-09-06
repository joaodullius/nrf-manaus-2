# Dataset de referência — IQ de Channel Sounding capturado no preparo do curso

Oito capturas reais do par nRF54LM20-DK (initiator, lab 5) ↔ nRF54L15-TAG (reflector,
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
| [`ref_1m_tag_na_dk_1ap.csv`](ref_1m_tag_na_dk_1ap.csv) | 1,00 m | 99 | TAG na nRF54L15-DK, **um** caminho de antena (A1-B1) |
| [`ref_1m_tag_na_dk_2ap.csv`](ref_1m_tag_na_dk_2ap.csv) | 1,00 m | 99 × 2 ap | mesma posição, **dois** caminhos de antena (A1-B2) |
| [`ref_3m_1ap.csv`](ref_3m_1ap.csv) | 3,00 m | 99 | TAG na bateria, **um** caminho de antena |
| [`ref_3m_2ap.csv`](ref_3m_2ap.csv) | 3,00 m | 99 × 2 ap | mesma posição, **dois** caminhos de antena |

Distâncias medidas com trena, da antena do LM20-DK ao TAG.

As quatro últimas são o **experimento de antenas**, em duas distâncias: cada par foi
medido na mesma posição, um logo após o outro, trocando só `CONFIG_LAB_ANTENNA_PATHS`
no initiator. A conclusão está na seção "Duas antenas" do
[README do lab](../README.md). Em cada distância o achado foi confirmado em três
rodadas alternadas (1 → 2 → 1 → 2 → 1 → 2 caminhos, ~100 procedures cada); o repo
versiona uma rodada de cada, por tamanho.

Cuidado ao comparar 1,00 m com 3,00 m: mudou a distância **e** a montagem do TAG
(sobre uma DK contra na bateria). Dentro de cada distância a comparação é limpa;
entre distâncias, não.

## Como foi capturado

- **Data:** 2026-09-05 · uma sala, um par, mesma orientação do TAG nos três pontos
- **Firmware no DK:** `05_cs_iq_music` (`CONFIG_LAB_PROCEDURE_INTERVAL=50`,
  ~1 procedure/s) nos três de 1/3/5 m e nos dois de 1,00 m; o de 0,78 m foi capturado
  com o intervalo default do sample (~3,5 procedures/s)
- **Firmware no TAG:** `01_cs_reflector` (RAS, uma antena em uso)
- **Captura:** `python cs_capture.py --seconds 30 --out ...` (30 s por distância; 100 s nas duas de 1,00 m)
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
| 3,0 m | 4,46 ± 0,48 | 5,84 ± 0,72 | 4,42 ± 0,96 | 4,99 ± 0,96 |
| 5,0 m | 5,86 ± 0,84 | 6,75 ± 0,38 | 6,14 ± 1,02 | 6,21 ± 0,29 |
| 0,78 m | 1,92 ± 0,09 | 2,16 ± 0,16 | 1,39 ± 0,70 | 1,94 ± 0,07 |
| 1,00 m (1 caminho) | 2,44 ± 0,07 | 2,64 ± 0,06 | 1,49 ± 0,63 | 2,58 ± 0,03 |
| 1,00 m (2 caminhos, ap 0) | 2,39 ± 0,12 | 2,60 ± 0,32 | 1,64 ± 0,66 | 2,60 ± 0,06 |
| 3,00 m (1 caminho) | 3,98 ± 0,51 | 4,68 ± 0,14 | 3,41 ± 0,76 | 3,97 ± 0,57 |
| 3,00 m (2 caminhos, ap 0) | 3,90 ± 0,66 | 4,69 ± 0,50 | 3,72 ± 0,57 | 4,02 ± 0,42 |

Repare que `ref_3m.csv` e `ref_3m_1ap.csv` são as duas a 3,0 m e leem diferente
(4,46 contra 3,98 no `ifft`): foram sessões e pontos diferentes da sala. O viés não é
função só da distância — é da distância **e** do que há em volta. É exatamente por
isso que o lab pede para o aluno medir a sala dele.

`d_ifft` (NumPy − firmware) deve sair ≈ 0,000 em todos: o port reproduz o chip.

## Limitações

- **Uma sala, uma orientação, um par.** O viés de +0,9 a +1,5 m é desta bancada; noutra
  sala será outro. É por isso que o lab pede para o aluno medir a sua.
- **Antena única nas quatro primeiras.** O TAG tem duas antenas e o reflector as
  configura, mas o initiator usa um caminho por default. As capturas de 1,00 m e de
  3,00 m existem justamente para medir o que muda com dois — e a resposta, nas duas
  distâncias e em linha de visada, é: custa dispersão e não melhora a exatidão. Veja
  a seção "Duas antenas" do README do lab.
- **Sem obstrução.** Não há captura com corpo ou metal no caminho — o experimento B do
  lab 2 fica para a sala.
