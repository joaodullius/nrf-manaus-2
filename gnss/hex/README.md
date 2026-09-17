# Hex de referência — as cinco configurações do módulo de GNSS

Binários prontos, para gravar **sem compilar**: repetir um lab, recuperar uma placa, ou
seguir a aula quando o build de alguém falhar. Todos saem do **mesmo código-fonte**
(`gnss/01_nrf9151_basic`) em cinco configurações de Kconfig, que é o desenho dos labs 2 e 3.
Cada hex corresponde ao fonte deste repo no commit em que foi gerado.

**Todos são públicos.** Nenhum carrega credencial: a coordenada de referência
(`GNSS_SAMPLE_REFERENCE_LATITUDE/LONGITUDE`) fica vazia no repositório, e a variante de
nuvem só liga a biblioteca cliente da nRF Cloud — o certificado e o provisionamento do
dispositivo são pré-requisito para **rodar**, não para compilar.

## Os arquivos

| Arquivo | Lab | O que tem | Exige para rodar | Flash / RAM (B) |
|---|---|---|---|---|
| `01_nrf9151_basic.hex` | 1 | rastreio contínuo, sem assistência, console com PVT, log e AT host | antena + céu; não usa LTE | 83.052 / 33.044 |
| `02_nrf9151_ttff_sem.hex` | 2 | modo de teste de TTFF, partida a frio forçada, sem assistência | antena + céu; não usa LTE | 83.528 / 35.708 |
| `02_nrf9151_ttff_minima.hex` | 2 | idem, assistência mínima (almanaque de fábrica + hora da rede + MCC) | antena + SIM com cobertura LTE-M | 107.092 / 36.188 |
| `02_nrf9151_ttff_nuvem.hex` | 2 | idem, A-GNSS pela nRF Cloud por CoAP | antena + SIM LTE-M + **DK provisionada na nRF Cloud** | 128.108 / 48.764 |
| `03_nrf9151_nmea.hex` | 3 e demo | só NMEA na porta: `NMEA_ONLY=y`, `LOG=n`, `AT_HOST_LIBRARY=n` | antena + céu; não usa LTE; u-center 2 ou `nmea_captura.py` no PC | 68.352 / 27.308 |

Os tamanhos são da **imagem de aplicação**. O alvo `/ns` traz TF-M, e o hex publicado é o
`merged_nrf9151dk_nrf9151_ns.hex` do sysbuild (`SB_CONFIG_MERGED_HEX_FILES=y` no
`sysbuild.conf` do lab): a imagem segura e a não segura já fundidas, o mesmo conteúdo do
`tfm_merged.hex` que o `west flash` grava. O `zephyr.hex` sozinho não roda. A placa é a **nRF9151 SMA-DK** (PCA10201), alvo `nrf9151dk/nrf9151/ns`, com
`CONFIG_MODEM_ANTENNA_GNSS_EXTERNAL=y` em todos: sem antena ativa no J2 nada funciona, e numa
nRF9151 DK comum essa opção desliga o LNA de bordo.

A variante periódica do lab 2 (`build_periodico`) não tem hex aqui: é a receita do README do lab,
para o aluno compilar.

## Gravar

Só precisa do `nrfutil` com o comando `device`:

```
nrfutil device list                                                    # serial da DK
nrfutil device program --firmware gnss\hex\<arquivo>.hex --options chip_erase_mode=ERASE_ALL --serial-number <serial>
nrfutil device reset --serial-number <serial>
```

Se a placa recusar (`FPROTECT`, ou firmware antigo travando o debugger):

```
nrfutil device recover --serial-number <serial>
```

O `nrfutil device fw-info` não lê a versão do firmware do modem em nRF91; ela sai por
`AT+CGMR` no console do hex do lab 1 (`mfw_nrf91x1_2.0.4` nas placas do curso).

## Regenerar

```
python gnss\hex\build_all.py --list      # as cinco variantes
python gnss\hex\build_all.py             # todas
python gnss\hex\build_all.py 02 03       # so as que comecam com 02 ou 03
```

Cada variante é compilada **pristine** em `build/hex_gnss/<nome>/`, com `--sysbuild` e os
`-D01_nrf9151_basic_CONFIG_*` prefixados pelo nome da imagem, e o script confere o `.config`
gerado antes de copiar o `merged_<board>.hex` (a mesma asserção dos `verifica_*.sh` dos
labs). A sequência de testes do módulo, com o que cada build exige para rodar, está no
[`README.md`](../README.md) de `gnss/`.

Requisitos: NCS v3.4.0 em `C:/ncs/v3.4.0` — ver [`PREREQUISITOS.md`](../../PREREQUISITOS.md).

Depois de regenerar, commite os hex junto com o fonte que os gerou.
