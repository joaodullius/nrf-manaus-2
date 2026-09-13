# Firmware LEO — Asset Tracker Template com predição de passada por SGP4

## Origem

Snapshot do repositório `Asset-Tracker-Template` (west workspace da Nordic),
branch `leo_ntn_status_leds_v2`, commit `2ec6cf80`. Extraído com:

```bash
git archive 2ec6cf80 app | tar -x -C ntn/firmware/leo
```

## O que este snapshot é

O diretório `app/` inteiro do branch, menos os overlays de Memfault e
GuardianSat (`overlay-memfault.conf`,
`overlay-upload-modem-traces-to-memfault.conf`, `overlay-guardiansat.conf`) —
todos ligados a serviços e credenciais de terceiros que não fazem parte deste
material. Nenhum outro arquivo foi alterado.

Este snapshot **não compila fora do west workspace do Asset Tracker
Template**: falta o manifesto west (`west.yml`), os módulos dos quais `app/`
depende (`app`, `zephyr`, drivers do nRF9151, etc.) e o restante da árvore
que o `west init`/`west update` do ATT normalmente traz.

**Foi este firmware que gerou os traces em `../02_leo_passada/data/`.**

## Como reconstruir

```bash
west init -m <url do Asset-Tracker-Template>
west update
# substituir o app/ do workspace pelo conteúdo desta pasta
west build --board nrf9151dk/nrf9151/ns -- "-DEXTRA_CONF_FILE=overlay-ntn-sateliot.conf"
```

Os comandos `west` acima rodam através do gerenciador de toolchain da Nordic,
que fixa a versão do NCS usada no curso (v3.4.0):

```bash
C:\ncs\toolchain\...\nrfutil toolchain-manager launch --ncs-version v3.4.0 -- west build ...
```

## Canal SatelIoT

`overlay-ntn-sateliot.conf` habilita `CONFIG_APP_NTN_CHANNEL_SELECT_ENABLE` e
fixa `CONFIG_APP_NTN_CHANNEL_SELECT=229232` (EARFCN do canal SatelIoT no
Brasil; o overlay traz, comentados, os EARFCN de Noruega, Finlândia/Barcelona
e Austrália para os outros territórios da constelação).

## TLE por Kconfig

O TLE (Two-Line Element) do satélite pode ser pré-provisionado em tempo de
build em vez de vir por SIB32 em tempo de execução:
`CONFIG_APP_NTN_TLE_FROM_KCONFIG=y` habilita
`CONFIG_APP_NTN_TLE_NAME`, `CONFIG_APP_NTN_TLE_LINE1` e
`CONFIG_APP_NTN_TLE_LINE2` (`app/src/modules/ntn/Kconfig.ntn`, dentro de
`APP_NTN_LEO`).

## Máquina de estados

`app/src/modules/ntn/ntn.c` define os estados em `enum ntn_module_state`:
`STATE_RUNNING → STATE_GNSS → STATE_SGP4 → STATE_NTN → STATE_IDLE`.

1. **RUNNING**: estado pai, arma a transição inicial.
2. **GNSS**: busca um fix de posição e hora.
3. **SGP4**: com o fix e o TLE (por Kconfig ou por SIB32), a predição SGP4
   calcula a próxima passada visível do satélite e arma o timer que dispara
   a entrada em NTN no horário previsto.
4. **NTN**: aguarda a passada prevista, ativa o modem em modo NTN, seleciona
   o canal, anexa à rede e envia a carga.
5. **IDLE**: volta a repousar até a próxima passada ou um novo gatilho.

## Seleção de canal e SIB

Em `state_ntn_entry` (`ntn.c`), a seleção do canal tenta primeiro
`AT%CHSELECT=2,14,<earfcn>`; se falhar, cai para
`AT%FREQRANGES=1,6,,1,"<earfcn>",""` como alternativa. Antes de entrar em
NTN, `AT%SIBCONFIG=32,1,31,0` pede ao modem o SIB32 (ephemeris) e o SIB31.

## Confirmação de envio

O socket UDP usa `setsockopt(..., SO_SENDCB, ...)` para registrar um
callback de confirmação de envio: depois de enfileirar a carga, o firmware
espera a confirmação da rede (ou o timeout de
`APP_NTN_SEND_ACK_TIMEOUT_SECONDS`) antes de reportar sucesso ou falha do
envio.

## Demonstração

O firmware não tem interface por botão como o do GEO: ele decide sozinho,
pela predição SGP4, quando entrar em modo NTN. Os traces de sinal e eventos
usados nas figuras de `../02_leo_passada/` vieram de execuções deste
firmware.
