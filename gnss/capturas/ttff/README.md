# Tempo até o primeiro fix — as três variantes de assistência

Logs da serial do `build_02_*` (modo de teste de TTFF, partida a frio forçada a
cada ciclo, 120 s de sono entre ciclos), colhidos em 09/09/2026 na bancada de
Porto Alegre, antena ANN-MB2 no J2 sobre plano de terra, janela entre dois
prédios. SIM Claro, LTE-M forçado (`CONFIG_LTE_NETWORK_MODE_LTE_M_GPS=y`).

| arquivo | variante | bloco |
|---|---|---|
| `r1_sem.log`, `r2_sem.log` | sem assistência (`build_02_sem`) | 20 min cada |
| `r1_min.log`, `r2_min.log` | assistência mínima (`build_02_min`) | 20 min cada |
| `r1_nuvem.log`, `r2_nuvem.log` | A-GNSS pela nRF Cloud (`build_02_nuvem`) | 20 min cada |
| `noite_min.log` | assistência mínima, sessão da madrugada | 25 min |

As duas rodadas têm a **ordem invertida** (`sem → min → nuvem`, depois
`nuvem → min → sem`), para que uma deriva lenta do céu não vire diferença entre
variantes.

O que se extrai de cada log:

```
grep -oE "Time to fix: [0-9.]+ s" <log>
grep -oE "blocked by LTE: [0-9]+ s" <log>      # so a variante de nuvem reporta
```

A variante mínima rende poucas amostras porque o firmware trava depois do
primeiro `Sleeping for 120 s` — o ciclo seguinte às vezes não começa. Não é a
instrumentação: as outras duas, no mesmo script e na mesma porta, produzem
normalmente.

Figura e tabela do material: `doc/_template/fig_m2_07_ttff_degraus.py` lê estes
logs e escreve `doc/gnss/data/ttff_degraus.json`.
