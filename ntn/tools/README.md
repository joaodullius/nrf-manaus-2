# ntn/tools

Ferramentas de referência em Python usadas para capturar, converter e
analisar os traces do modem NTN (Nordic nRF91 + SatelIoT). São as mesmas
ferramentas usadas para montar o material do módulo — não geram nenhum slide
nem `.pptx`, só dados e gráficos a partir dos traces.

## Instalação

```bash
pip install -r requirements.txt
```

## `nrfutil install trace`

`nrf_trace.py` decodifica os `.bin` binários chamando `nrfutil trace lte` por
baixo. Isso só é necessário para reconverter um `.bin` novo — os `.txt` já
convertidos (em `traces-txt/`) não precisam do `nrfutil`. Se for reconverter:

```bash
nrfutil install trace     # precisa da versao 5.4.0 ou maior
nrfutil trace --version   # confirma
```

## Scripts

| script | o que faz | exemplo de uso |
| --- | --- | --- |
| `nrf_trace.py` | Converte um dump binário de trace do modem (`.bin`) em registros com timestamps absolutos, ancorando no GNSS, no `+CCLK` ou no mtime do arquivo — nunca no timestamp de uptime que o `nrfutil` soma errado. Usado como biblioteca (`convert`, `parse_text`, `write_txt`) por `plot_snr.py` e `sync_traces.py`. | `from tools import nrf_trace; nrf_trace.convert(bin_path, db_path)` |
| `plot_snr.py` | Lê um `.txt` de trace já convertido e gera o combinado SNR/RSRP × tempo, eventos do procedimento (MIB, SIB, RAR, NAS, `+CSCON`, UDP, T310), elevação e carta polar da passada. `--tle-file` usa um TLE local em vez de baixar do CelesTrak; `--out-dir` escolhe a pasta do PNG (padrão `plots/`); `--duration` corta os primeiros N s a partir da primeira medida. | `python plot_snr.py trace.txt -s SATELIOT_1 --tle-file x.tle --no-open` |
| `tle_fetcher.py` | Biblioteca que busca o TLE de um satélite por NORAD ID, tentando CelesTrak, depois N2YO (se houver chave), depois SatNOGS. Usada por `LEO_next_passes.py`, `get_trace.py`, `get_tle.py`, `plot_snr.py` e `plot_ab_antennas.py`. | `from tools.tle_fetcher import fetch_tle; fetch_tle(60550)` |
| `LEO_next_passes.py` | Calcula as próximas passagens de um ou mais satélites LEO sobre um observador, com elevação, azimute e horário; opcionalmente plota ou gera um mapa da passagem. Observador padrão: Porto Alegre (`--lat`/`--lon` sobrepõem). | `python LEO_next_passes.py -s SATELIOT_1 -e 45 --lat -30.03 --lon -51.23` |
| `serial_modem_test.py` | Envia a sequência de comandos AT de setup para um modem nRF9160/nRF9151 numa porta serial, para os RATs NTN, NB-IoT e LTE-M, com shell interativo depois. Observador padrão: Porto Alegre (`--lat`/`--lon`/`--alt` sobrepõem). | `python serial_modem_test.py --port COM26 --rat NTN --lat -30.033 --lon -51.229` |
| `ntn_search.py` | Versão mínima do setup NTN: configura o modem para busca contínua da SatelIoT (PLMN 90197) e mostra as URCs decodificadas. Observador padrão: Porto Alegre (`--lat`/`--lon`/`--alt` sobrepõem). | `python ntn_search.py --port COM3 --lat -30.033 --lon -51.229` |
| `analyze_elevation_signal.py` | Agrega elevação x RSRP/SNR de todos os `.txt` de uma pasta, interpolando a elevação pelo TLE em cada timestamp, e produz um scatter com média/desvio por faixa de 5°. | `python analyze_elevation_signal.py --dir traces-txt` |
| `plot_ab_antennas.py` | Compara duas (ou mais) capturas do mesmo pass com antenas diferentes: um painel de elevação (geometria única) e um painel cada de RSRP e SNR, uma série por antena. | `python plot_ab_antennas.py a.txt b.txt --out ab.png` |
| `sync_traces.py` | Copia `.bin` novos de uma máquina remota via SSH/SFTP incremental (por nome + tamanho), preserva o mtime remoto e converte cada `.bin` baixado para `.txt` com `nrf_trace`. | `python sync_traces.py --host user@192.168.1.9 --dry-run` |
| `get_trace.py` | Roda `nrfutil trace lte` automaticamente alinhado às passagens de satélite: inicia antes da subida (`--pre`) e para depois do pico (`--post`), em loop. | `python get_trace.py --port COM26 -s SATELIOT_1 -e 50` |
| `get_tle.py` | Script de linha única: imprime o TLE atual de cada satélite SatelIoT conhecido. | `python get_tle.py` |

## Testes

```bash
cd ntn/tools
python -m unittest test_plot_snr_formats test_plot_ab_antennas -v
python -m unittest test_nrf_trace test_sync_traces -v
```

Os testes de integração (que decodificam um `.bin` real ou leem o
`trace_db_external_*.tar.gz`) aparecem como `skipped` neste repositório: os
`.bin` (~500 KB cada) e o trace database (~61 KB) não entram no repositório.
Rodam completos em `nrf-ntn-priv`, onde esses arquivos existem.
