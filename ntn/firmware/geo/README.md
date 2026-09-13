# Firmware GEO — Asset Tracker Template por botões e LEDs

## Origem

Snapshot do repositório `Asset-Tracker-Template` (west workspace da Nordic),
branch `geo_skylo_buttons`, commit `baf1e93e`, criada a partir de
`origin/ntn_usecase`. Extraído com:

```bash
git archive baf1e93e app | tar -x -C ntn/firmware/geo
```

## O que este snapshot é

O diretório `app/` inteiro do branch, menos os overlays de Memfault
(`overlay-memfault.conf`, `overlay-upload-modem-traces-to-memfault.conf`) —
eles apontavam para um projeto e uma chave de conta Memfault que não fazem
parte deste material. Nenhum outro arquivo foi alterado.

Este snapshot **não compila fora do west workspace do Asset Tracker
Template**: falta o manifesto west (`west.yml`), os módulos dos quais `app/`
depende (`app`, `zephyr`, drivers do nRF9151, etc.) e o restante da árvore
que o `west init`/`west update` do ATT normalmente traz.

## Como reconstruir

```bash
west init -m <url do Asset-Tracker-Template>
west update
# substituir o app/ do workspace pelo conteúdo desta pasta
```

Build de campo (NTN, Skylo, SIM eminify):

```bash
west build --board nrf9151dk/nrf9151/ns -- "-DEXTRA_CONF_FILE=overlay-ntn-skylo-eminify.conf"
```

Build de validação (TN, Cat-M1, SIM comum — para testar máquina de estados,
botões, LEDs e socket em bancada, sem esperar satélite):

```bash
west build --board nrf9151dk/nrf9151/ns -- "-DEXTRA_CONF_FILE=overlay-tn-catm1.conf"
```

Os comandos `west` acima rodam através do gerenciador de toolchain da Nordic,
que fixa a versão do NCS usada no curso (v3.4.0):

```bash
C:\ncs\toolchain\...\nrfutil toolchain-manager launch --ncs-version v3.4.0 -- west build ...
```

A build de validação também habilita um comando de shell
`att_ntn btn <1-4>` (injeta um clique de botão) e um log a cada mudança de
LED — os dois existem porque uma interface feita de botões físicos e LEDs
visíveis não pode ser exercitada nem observada por nada automatizado. Ambos
podem ser ligados numa build de campo com
`-DCONFIG_APP_NTN_BUTTON_INJECT_SHELL=y` e `-DCONFIG_APP_NTN_STATUS_LEDS_TRACE=y`.

## Interface: botões e LEDs

Resumo de `app/src/modules/ntn/README.md` (no snapshot).

### Botões

| Botão | Faz | Notas |
| --- | --- | --- |
| 1 | Tentar agora | Inicia o anexo ao satélite. Se o kit ainda não tem fix, ele busca um primeiro e depois anexa. Ignorado enquanto uma tentativa está em curso ou o link já está de pé |
| 2 | Enviar um pacote | Só com o link conectado; o log avisa quando não está |
| 3 | Parar | Encerra o que estiver rodando, busca de fix ou anexo, e derruba o link. O kit volta a esperar o botão 1 |
| 4 | Novo fix de GNSS | Pressionar depois de mover o kit. Encerra um anexo em curso |

### LEDs

| LED | Apagado | Heartbeat | Piscando | Aceso fixo |
| --- | --- | --- | --- | --- |
| 1 | Parado, sem fix | Fix bom, esperando o botão 1 | Lento: buscando fix. Rápido: conectando | Conectado |
| 2 | Sem problema | — | Rápido: nenhuma célula encontrada, ou a tentativa falhou | — |
| 3 | Nada enviado ainda | — | Cai por um instante a cada pacote novo | Um pacote foi enviado |
| 4 | Reservado para a resposta do servidor; não lido nesta versão | — | — | — |

O LED 1 conta a história inteira do progresso (parado → buscando fix →
conectando → conectado); os outros três guardam cada um um único
significado.

## O que a demonstração mostra

Este firmware é o material de uma demonstração operada só por botões e
LEDs, sem terminal e sem comando AT algum — diferente do roteiro por
comandos AT de `../01_geo_live` (que fala com o Serial Modem add-on pela
porta serial). Ele mostra o ciclo completo do caso de uso GEO — busca de
GNSS, anexo à rede não terrestre da Skylo, envio de um pacote e retorno ao
repouso — como uma sequência de estados visível a olho nu. A build Cat-M1
(`overlay-tn-catm1.conf`) exercita a mesma sequência com uma SIM terrestre; a
build de campo usa a SIM Skylo (`overlay-ntn-skylo-eminify.conf`).
