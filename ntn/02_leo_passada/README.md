# Passada LEO — traces reais e a passada sintética completa

Material de figura para a Parte B da teoria (procedimento de acesso e transferência de
dados em NTN). Não há lab nem demo ao vivo de LEO: não há passada SatelIoT sobre Manaus na
semana do curso. As figuras saem do `plot_snr.py` de [`../tools/`](../tools/), o mesmo que
gera os combinados de sinal/eventos/elevação/polar dos traces de bancada.

## O que há aqui

| Arquivo | O que é |
|---|---|
| `data/*.txt` | Seis traces de modem reais, convertidos pelo `nrf_trace.py` (hora UTC absoluta por linha) |
| `tle/*.tle` | TLEs do CelesTrak de 2026-09-13 (SATELIOT_1, usado na geometria; SATELIOT_3) e o de 2026-08-22 do `overlay-guardiansat.conf` do firmware |
| `compoe_passada.py` | Compõe `passada_sintetica_SIOT1.txt`: uma passada do nascer ao pôr feita de trechos dos traces reais |
| `test_compoe_passada.py` | 5 testes: a composição é lida pelo `plot_snr.load_log` e contém a sequência inteira, na ordem |

## Por que uma passada sintética

Nenhum trace real cobre a passada inteira: o firmware liga o rádio no pico e a parte de
rádio dura 15–30 s. A passada sintética junta, na geometria real da passada de 07/09 sobre
Porto Alegre (nascer 02:22:37, pico 60,7° às 02:28:53, pôr 02:35:05 UTC), os trechos reais em
que cada passo aparece:

| Fase | Origem | Onde fica |
|---|---|---|
| Modem liga (`AT+CFUN=21`) e 8 s de busca | `20260907_0228_SIOT1_BRA_KY` | 20 s após o nascer |
| Busca de célula até o MIB | **gerada**: `RRC State: 1 (ERRC_CNTRL_RRC_NO_CELL)` a cada 2 s, cada linha com `[sintetico]` | entre os dois trechos |
| MIB, SIB1, SI, Attach Request, PRACH/RAR, `+CSCON: 1`, Attach Accept, `+CEREG: 5` | `20260907_0228_SIOT1_BRA_KY` | elevação 35° subindo |
| Envio UL e resposta DL do servidor | `20260909_0233_SIOT1_BRA_KY` | 3 s depois |
| Perda da célula: T310, `+CSCON: 0`, NO_CELL | `20260412_1349_SIOT3_BRA` | elevação 8° descendo |

Cada trecho mantém seus intervalos internos; só a posição do trecho na passada é escolhida
pela elevação (SGP4 sobre o TLE). Entre o DL e a perda da célula não há linhas: o UE fica
conectado sem tráfego e o gráfico de RSRP para onde param as medidas reais. A primeira linha
do arquivo gerado declara a origem dos trechos.

Ordem que o trace real impõe e a figura mostra: o Attach Request é registrado antes do RAR
(o PDU NAS é montado antes do Msg3) e o `+CSCON: 1` chega antes do Attach Accept.

## Como gerar as figuras

```bash
cd ntn/02_leo_passada
python compoe_passada.py
# passada inteira, do nascer ao por
python ../tools/plot_snr.py passada_sintetica_SIOT1.txt -s SATELIOT_1 --tle-file tle/sateliot_1_20260913.tle --no-open --out-dir plots
# so a sequencia de acesso (25 s a partir da primeira medida)
python ../tools/plot_snr.py passada_sintetica_SIOT1.txt -s SATELIOT_1 --tle-file tle/sateliot_1_20260913.tle --no-open --out-dir plots --duration 25
# um trace real, para comparar
python ../tools/plot_snr.py data/20260907_0228_SIOT1_BRA_KY.txt -s SATELIOT_1 --tle-file tle/sateliot_1_20260913.tle --no-open --out-dir plots
```

`--tle-file` e `--out-dir` são as duas opções acrescentadas ao `plot_snr.py` do curso; sem
`--tle-file` ele baixa o TLE do CelesTrak. Os PNG vão para `plots/` (não versionado). O
`--duration` corta a partir da primeira medida de RSRP, que é o MIB.

## Os traces

| Trace | O que mostra | Horas UTC |
|---|---|---|
| `20260907_0228_SIOT1_BRA_KY` | Attach completo até o primeiro pacote UL — referência principal | `%CHSELECT`/`%SIBCONFIG` 02:28:35 → MIB 02:28:43 → SIB1-NB 02:28:45,1 → SI-NB 02:28:45,4 e 45,5 → Attach Request 02:28:45,5 → RAR/PRACH 02:28:47,1 → `+CSCON: 1` 02:28:47,8 → Attach Accept/Complete 02:28:53,8 → `+CEREG: 5` 02:28:54,8 → primeiro UL 02:28:54,8 |
| `20260909_0233_SIOT1_BRA_KY` | Contexto já existente, Control Plane Service Request, DL do servidor | CP Service Request com PDU ESM 02:33:37 → Service Accept 02:33:40,2 → DL 02:33:40,45 e 40,59, cada um seguido de UL ICMP |
| `20260906_0226_SIOT1_BRA_YG` | Attach Reject, causa EMM #8 | Attach Request 02:26:22 → Attach Reject `07 44 08` 02:26:25 ("EPS services and non-EPS services not allowed"); a rede libera a conexão no mesmo instante |
| `20260907_0228_SIOT1_BRA_YG` | Célula encontrada 19 s depois do KY, PRACH sem RAR, volta à busca — gêmeo do KY, contraste de antena | `+CFUN=21` 02:28:32 → MIB 02:29:02 → PRACH CE2 02:29:05 e 02:29:18, sem RAR → `+CEREG: 4` 02:29:50 → `+CFUN=45` 02:31:34 |
| `20260902_0216_SIOT1_BRA` | Attach, envio, `+CSCON: 0` e re-acesso por Service Request no mesmo minuto; `%SIBREQ=32` termina com `%SIBREQ: 0,1` (status 1 = célula perdida) sem entregar dados | 02:16:12 → 02:16:58 |
| `20260412_1349_SIOT3_BRA` | Perda da célula em conexão: T310, `+CSCON: 0`, NO_CELL (SATELIOT_3, formato antigo sem data) | 14:53:59 |

Nos traces de setembro o modem liga com `AT+CFUN=21` e a busca de célula aparece como
`RRCSTATECHANGEEVENT RRC State` alternando 0/1 a cada 2 s, sem o nome `ERRC_CNTRL_RRC_NO_CELL`
que o `plot_snr` procura — por isso a busca só aparece nas figuras dos traces antigos e na
sintética, cujas linhas geradas levam o nome. Nenhum trace tem a URC `%SIBCONFIG: 32`.

## Passadas da semana em Manaus

A SatelIoT informou que o SATELIOT_1 não está disponível em Manaus na semana do curso.
`semana/passadas_semana_manaus.txt` é a saída do `tools/LEO_next_passes.py` (TLE do CelesTrak
de 13/09, SGP4) para o SATELIOT_1 sobre o SIDIA (−3,0930, −60,0207) entre 13 e 20/09/2026;
`semana/mapa_semana.py` desenha a tabela: elevação máxima de cada passada por hora local, com a
régua em 50°, e o pico de cada uma na carta polar. São 28 passadas, quatro por dia (~21:20 e
~22:55 subindo, a leste e a oeste-sudoeste; ~09:25 e ~10:55 descendo, a leste-sudeste e a
oeste). Só uma chega a 50°, no sábado 12/09 às 22:51 (antes do curso); as passadas de ~22:55
caem de 46° na segunda para 30° no sábado.

```bash
cd ntn/02_leo_passada/semana
PYTHONIOENCODING=utf-8 python ../../tools/LEO_next_passes.py --lat -3.0930 --lon -60.0207 --days 7 -e 0 --start "2026-09-13 00:00" -p --clean | sed 's/\x1b\[[0-9;]*m//g' > passadas_semana_manaus.txt
python mapa_semana.py            # plots/mapa_semana_manaus.png
```

## Limites

- **Geometria calculada, não medida.** Elevação e azimute vêm de SGP4 sobre o TLE de 13/09
  (CelesTrak), seis dias depois da passada de referência. O TLE de 22/08 do firmware, quinze
  dias antes, dá a mesma passada com 4–5 s de diferença no nascer, pico e pôr.
- **"Net ACK" é inferência** do `plot_snr`: o trace-db externo não decodifica RLC STATUS; a
  confirmação é o primeiro bloco DCI N1 após o envio que não é RAR, é confirmado por HARQ-ACK
  do UE (no NPUSCH formato 2 — NB-IoT não tem PUCCH; o rótulo `PUCCH_POWER_CONTROL` do trace é
  interno do modem) e não carrega PDU L3.
- O trace de abril é do SATELIOT_3; entra na sintética só pelo trecho de T310, com a
  geometria da passada de 07/09 do SATELIOT_1.

## Testes

```bash
cd ntn/02_leo_passada && python -W error::ResourceWarning -m unittest test_compoe_passada -v
```
