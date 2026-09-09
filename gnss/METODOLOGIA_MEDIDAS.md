# Metodologia: repetir dispersão e tempo até o fix em outra posição

Este documento existe para que o conjunto de medidas de **uma posição de antena** seja
comparável ao de **outra**. Ele cobre só as duas famílias que dependem da vista de céu:
**dispersão** (CEP50/CEP95) e **tempo até o primeiro fix** (TTFF).

**Medidas de consumo não entram aqui** e não precisam ser repetidas: elas dependem do
firmware e do rádio, não do céu. Ver a seção de energia no `bancada.md`.

## A regra que torna tudo comparável

> **Um conjunto = uma posição de antena, sem mover nada do começo ao fim.**

Se a antena sair do lugar no meio, as linhas do conjunto deixam de ser comparáveis entre si
e o mapa do céu deixa de explicar o mapa de desvio.

**O console pode ficar ligado.** Ele custa ~430 µA de piso e invalida medida de energia, mas
não desloca nenhum instante nem nenhuma coordenada. Para dispersão ele é **obrigatório**,
porque a análise consome NMEA.

## O que anotar antes de começar

| campo | por quê |
|---|---|
| Local e descrição física | "janela entre dois prédios", "sacada", "telhado" |
| **Hora local de início** | a cintilação ionosférica tem pico entre o pôr do sol e a meia-noite |
| Antena usada | tem de ser a mesma entre posições |
| Firmware do modem | `AT+CGMR` — muda o que é possível |

## A — Dispersão (15 min)

```
# 1. gravar o build de NMEA limpo
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash   -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_03_nmea

# 2. capturar exatamente 900 s (o mesmo valor em todas as posições)
python gnss/tools/nmea_captura.py --port COM23 --seconds 900   --out gnss/capturas/<local>_<hhmm>

# 3. mapa de desvio e mapa do céu
cd gnss/tools
python desvio.py --log "<local> <hhmm>=../capturas/<local>_<hhmm>.nmea"   --png ../../doc/gnss/img/desvio_<local>.png   --json ../../doc/gnss/data/desvio_<local>.json
python ceu.py --log ../capturas/<local>_<hhmm>.nmea   --titulo "<local>, <hhmm>"   --png ../../doc/gnss/img/ceu_<local>.png   --json ../../doc/gnss/data/ceu_<local>.json
```

**900 s não é arbitrário:** o CEP95 é percentil de cauda e balança muito com poucas dezenas
de pontos. A 1 Hz, 900 s dão ~900 fixes e o número para de se mexer.

Para comparar duas posições na mesma figura, repita `--log` — o `desvio.py` aceita até quatro
e põe todos na mesma régua logarítmica:

```
python desvio.py --log "Janela=../capturas/janela_2300.nmea"                  --log "Céu aberto=../capturas/aberto_1400.nmea"                  --png ../../doc/gnss/img/desvio_comparativo.png
```

## B — Tempo até o primeiro fix

As três variantes usam **o mesmo código-fonte**, recompilado. Todas fazem partida a frio de
verdade: apagam efemérides antes de cada tentativa.

| variante | build | assistência |
|---|---|---|
| sem | `build_02_sem` | nenhuma (apaga até o almanaque) |
| mínima | `build_02_min` | almanaque de fábrica + hora da rede + posição por MCC |
| nuvem | `build_02_nuvem` | A-GNSS completo pela nRF Cloud |

Para cada uma:

```
# gravar (o hex ja compilado, sem recompilar)
nrfutil device program --firmware   C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_02_sem/01_gnss_basic/zephyr/tfm_merged.hex   --options chip_erase_mode=ERASE_ALL --serial-number <SN>
nrfutil device reset --serial-number <SN>

# capturar 25 min e extrair
python -u gnss/tools/nmea_captura.py --port COM23 --seconds 1500 --out /tmp/ttff_sem
# ou simplesmente registrar a serial num arquivo e depois:
grep -oE "Time to fix: [0-9.]+ s" <log>
grep -oE "blocked by LTE: [0-9]+ s" <log>
```

**Descarte as três primeiras amostras.** Medido em 2026-09-08: a série sem assistência deu
180, 109, 66, 35, 30, 31, 29, 30 s — as primeiras partidas pagam a busca cega, e o regime só
aparece a partir da quarta. Reportar a **mediana do regime**, e a faixa completa junto.

**Colete pelo menos 6 amostras em regime.** A 120 s de intervalo entre ciclos, isso são ~25
min por variante.

## C — O X20P na mesma posição

O X20P não roda firmware nosso: quem o dirige é o **u-center 2**. Mas as regras de
comparabilidade são as mesmas, e há uma restrição física que muda o desenho do experimento.

### A antena não pode ser compartilhada ao mesmo tempo

> **Nunca ligar a mesma antena nos dois receptores simultaneamente.** O SMA J2 da SMA-DK
> entrega 3 V à antena ativa e o EVK da u-blox entrega 3,3 V; ligados juntos, um regulador
> empurra corrente no outro. **Troca sempre com o receptor desenergizado.**

Consequência para o método: **os dois receptores não podem ser medidos ao mesmo tempo**. Não
existe captura simultânea. Então:

> **Alterne em blocos curtos e anote a hora de cada bloco.** Um bloco longo de nRF9151
> seguido de um bloco longo de X20P mistura a diferença entre receptores com a mudança do
> céu — e já medimos que só o horário muda o CEP95 pela metade.

Sugestão: blocos de 15 min, alternando `nRF9151 → X20P → nRF9151 → X20P`, com a troca de
cabo feita com os dois desligados. Duas rodadas de cada dão base para separar receptor de
horário.

### Dispersão do X20P

Grave a sessão no u-center 2. Ele escreve **dois arquivos** na pasta `.ucenter` do perfil:
um `.ubx` (fluxo cru) e um `.uc2` (o mesmo fluxo com carimbo de tempo). Copie os dois para
`gnss/capturas/` e rode as ferramentas **direto no `.uc2`** — elas leem esse formato:

```
cd gnss/tools
python desvio.py --log "X20P aberto=../capturas/x20p_<local>_<hhmm>.uc2"   --png ../../doc/gnss/img/desvio_x20p_<local>.png
python ceu.py --log ../capturas/x20p_<local>_<hhmm>.uc2 --titulo "X20P, <local> <hhmm>"   --png ../../doc/gnss/img/ceu_x20p_<local>.png
```

**As ferramentas já entendem multiconstelação.** O `nmea.py` identifica o satélite por
constelação mais PRN (`GP07` e `GA07` são satélites diferentes), lê `$GNGGA`, resolve o
`systemId` das `$GNGSA` e descarta satélites abaixo do horizonte. Sem isso, GPS e Galileo com
o mesmo número virariam um satélite só no mapa do céu.

A qualidade do `GGA` é o que separa os degraus da escada: **1** autônomo, **2** DGPS,
**5** RTK flutuante, **4** RTK fixo. O `desvio.py` já reporta a contagem por qualidade.

### Tempo até o fix do X20P

O X20P parte a frio por comando do u-center 2 (reset com apagamento de efemérides). **O
caminho exato do menu ainda não foi confirmado na bancada** — confirmar e anotar aqui na
primeira sessão com o EVK.

Válido de qualquer forma: **mesma quantidade de partidas, mesmo critério de descarte** que o
nRF9151 — descartar as três primeiras e reportar a mediana do regime.

### O que anotar a mais, só para o X20P

| campo | por quê |
|---|---|
| Constelações habilitadas | GPS, Galileo, GLONASS, BeiDou — muda tudo |
| Bandas habilitadas | L1 sozinha ou multibanda; é a diferença central para o nRF9151 |
| Firmware do X20P | decide se CLAS e Galileo HAS existem |
| Origem da correção | nenhuma, base própria, ou caster |

## Armadilhas já pagas

- **`nrfutil device program` em vez de `west flash`.** O `west flash` recompila, e a
  compilação é o que estoura memória em máquina apertada. O hex já pronto grava em 4 s.
- **`python -u` em captura de fundo.** Sem isso o stdout fica em buffer de bloco e se perde
  se o processo for morto.
- **Caminho de build curto.** O TF-M recusa mais de 90 caracteres.
- **A serial é exclusiva.** Com o u-center 2 aberto na mesma COM, a captura por script falha
  com "Acesso negado".

## Ficha da posição

Preencher uma por posição e guardar junto das capturas:

```
Local:
Data e hora local de inicio:
Antena:
Descricao da vista de ceu:
Arquivos gerados:
  dispersao:  gnss/capturas/____.nmea + .uc2
  TTFF sem:
  TTFF minima:
  TTFF nuvem:
Resultados:
  CEP50 / CEP95:
  satelites usados (media) / HDOP:
  satelites com orbita conhecida / na solucao:
  TTFF em regime (mediana e faixa), por variante:
Observacoes:
```
