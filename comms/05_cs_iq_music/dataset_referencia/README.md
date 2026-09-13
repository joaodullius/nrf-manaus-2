# Dataset de referência — IQ de Channel Sounding capturado no preparo do curso

Dezesseis capturas reais do par nRF54LM20-DK (initiator, lab 5) ↔ nRF54L15-TAG (reflector,
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
| [`ref_3m_1ap.csv`](ref_3m_1ap.csv) | 3,00 m | 99 | TAG na bateria, **um** caminho de antena |
| [`ref_3m_2ap.csv`](ref_3m_2ap.csv) | 3,00 m | 99 × 2 ap | mesma posição, **dois** caminhos de antena |
| [`ref_3m_obstruido_1ap.csv`](ref_3m_obstruido_1ap.csv) | 3,00 m | 67 | mesma posição, **pessoa sentada** entre a DK e o TAG (~40 cm da DK), um caminho |
| [`ref_3m_obstruido_2ap.csv`](ref_3m_obstruido_2ap.csv) | 3,00 m | 69 × 2 ap | mesma obstrução, dois caminhos |
| [`ref_bat_1m_1ap.csv`](ref_bat_1m_1ap.csv) / [`_2ap`](ref_bat_1m_2ap.csv) | 1,00 m | ~70 cada | **varredura na bateria**, 1 e 2 caminhos, mesma posição |
| [`ref_bat_3m_1ap.csv`](ref_bat_3m_1ap.csv) / [`_2ap`](ref_bat_3m_2ap.csv) | 3,00 m | ~70 cada | idem |
| [`ref_bat_5m_1ap.csv`](ref_bat_5m_1ap.csv) / [`_2ap`](ref_bat_5m_2ap.csv) | 5,00 m | ~70 cada | idem |
| [`ref_bat_5m_girado_1ap.csv`](ref_bat_5m_girado_1ap.csv) / [`_2ap`](ref_bat_5m_girado_2ap.csv) | 5,00 m | ~70 cada | mesmo ponto, **TAG girado no lugar** |

Distâncias medidas com trena, da antena do LM20-DK ao TAG.

As oito `ref_bat_*` são a **varredura de antenas**: TAG na bateria, 1/3/5 m e 5 m com
o TAG girado no lugar. Em cada ponto, 1 e 2 caminhos de antena foram medidos na mesma
posição, um logo após o outro, trocando só `CONFIG_LAB_ANTENNA_PATHS` no initiator, em
duas rodadas alternadas (1 → 2 → 1 → 2); o repo versiona a primeira rodada de cada.
As `ref_3m_1ap/2ap` são o mesmo experimento numa sessão anterior, e servem de controle
livre para a obstrução. A leitura está na seção "Duas antenas" do
[README do lab](../README.md), com os números de **mediana e MAD** desses arquivos.

As duas obstruídas são o par livre/obstruído de 3,00 m: mesma posição, mesma sessão,
mudando só a pessoa no caminho. A captura obstruída foi emparedada por capturas livres
antes e depois, que batem entre si — é o que autoriza atribuir a diferença ao corpo. A
condição obstruída é bem menos estável que a livre (a pessoa respira e se mexe): das
três rodadas obstruídas, o repo guarda uma como exemplo, não como valor de referência.

Todas as capturas de antenas estão na mesma montagem (bateria), então a comparação
entre distâncias vale — mas repare que `ref_3m_1ap` e `ref_bat_3m_1ap` são sessões
diferentes no mesmo ponto e leem parecido no `ifft` (4,11 e 4,10) e diferente no
MUSIC (4,07 e 4,54): o `ifft` é o mais estável entre sessões também.

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
| 3,00 m (1 caminho) | 3,98 ± 0,51 | 4,68 ± 0,14 | 3,41 ± 0,76 | 3,97 ± 0,57 |
| 3,00 m (2 caminhos, ap 0) | 3,90 ± 0,66 | 4,69 ± 0,50 | 3,72 ± 0,57 | 4,02 ± 0,42 |
| 3,00 m obstruído (1 caminho) | 4,31 ± 1,26 | 8,18 ± 0,51 | 6,67 ± 1,62 | 7,58 ± 1,40 |

Repare que `ref_3m.csv` e `ref_3m_1ap.csv` são as duas a 3,0 m e leem diferente
(4,46 contra 3,98 no `ifft`): foram sessões e pontos diferentes da sala. O viés não é
função só da distância — é da distância **e** do que há em volta. É exatamente por
isso que o lab pede para o aluno medir a sala dele.

`d_ifft` (NumPy − firmware) deve sair ≈ 0,000 em todos: o port reproduz o chip. As
`ref_bat_*` e as obstruídas estão tabuladas em mediana e MAD no README do lab.

## Limitações

- **Uma sala, uma orientação, um par.** O viés de +0,9 a +1,5 m é desta bancada; noutra
  sala será outro. É por isso que o lab pede para o aluno medir a sua.
- **Antena única nas quatro primeiras.** Foram capturadas quando o initiator usava um
  caminho. Hoje o default é dois, e as `ref_bat_*` mostram por quê: qual caminho é o
  bom muda com a geometria, e escolher entre eles (`ifft_min`) cortou o pior caso de
  2,46 para 1,17 m. Veja a seção "Duas antenas" do README do lab.
- **Sem obstrução.** Não há captura com corpo ou metal no caminho — o experimento B do
  lab 2 fica para a sala.
