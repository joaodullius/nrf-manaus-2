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

## O plano de terra faz parte da antena

> **A ANN-MB2 só cumpre o datasheet sobre um plano de terra circular de ø12 cm.** A própria
> u-blox mede assim: as especificações de RF trazem a nota "measured on a ø12 cm ground
> plane", e o centro de fase vem com o aviso de que *"any change in ground plane size or
> shape may affect the phase center offset"*.

Sem plano, a antena não está na configuração em que foi caracterizada: o diagrama de
radiação muda, a rejeição de multicaminho piora — e multicaminho é justamente o que domina
num cânion urbano — e nenhum número do datasheet se aplica.

**O plano de terra é parte da configuração da antena, e a configuração da antena é parte da
posição.** Trocar de plano entre capturas invalida a comparação tanto quanto mover a antena.

Para RTK isso vale em dobro: o deslocamento do centro de fase entra direto no resultado
centimétrico.

## O que anotar antes de começar

| campo | por quê |
|---|---|
| Local e descrição física | "janela entre dois prédios", "sacada", "telhado" |
| **Hora local de início** | a cintilação ionosférica tem pico entre o pôr do sol e a meia-noite |
| Antena usada | tem de ser a mesma entre posições |
| **Plano de terra: sim/não, material e diâmetro** | ø12 cm é a referência do datasheet; sem ele, nada do datasheet vale |
| Separação entre antenas, se forem duas | 30 cm já mudam o que cada uma enxerga num cânion |
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

O X20P parte a frio com `UBX-CFG-RST`, mandando `navBbrMask = 0xFFFF` (apaga tudo) e
`resetMode = 0x02` (reset controlado, só do GNSS). A mensagem pronta, com checksum:

```
B5 62 06 04 04 00 FF FF 02 00 0E 61
```

**Não espere `ACK`:** a própria u-blox avisa que firmware novo não confirma essa mensagem.

Antes de medir, confirme constelações e bandas com o VALGET exploratório — mensagem pronta e
a tabela das 29 chaves em [`REFERENCIA_X20P.md`](REFERENCIA_X20P.md).

Válido de qualquer forma: **mesma quantidade de partidas, mesmo critério de descarte** que o
nRF9151 — descartar as três primeiras e reportar a mediana do regime.

### O que anotar a mais, só para o X20P

| campo | por quê |
|---|---|
| Constelações habilitadas | GPS, Galileo, GLONASS, BeiDou — muda tudo |
| Bandas habilitadas | L1 sozinha ou multibanda; é a diferença central para o nRF9151 |
| Firmware do X20P | decide se CLAS e Galileo HAS existem |
| Origem da correção | nenhuma, base própria, ou caster |

## D — Medida com NTRIP (o terceiro degrau)

O RTK acrescenta dependências que as outras medidas não têm: **internet, um caster no ar, e
uma base**. Por isso ele é o único degrau que pode simplesmente não acontecer numa posição
nova — e o material tem de prever isso.

### A decisão que muda tudo ao trocar de posição

> **Se o rover se move e a base não, a baseline muda.** E a baseline entra no erro pelo termo
> de 1 ppm: 10 km de baseline são 1 cm só por esse termo, antes de qualquer outra coisa.

Duas saídas, e a escolha tem de ser anotada:

| arranjo | quando usar | o que anotar |
|---|---|---|
| **Base própria junto do rover** | caminho garantido do curso; baseline de metros | coordenada do Survey-In e a incerteza |
| **Caster público** (IBGE, AMUA0) | bônus; depende de cadastro e da estação estar no ar | distância até a estação de referência |

Com base própria numa posição nova, ou a base vai junto (novo Survey-In) ou fica onde está
(baseline maior). **As duas são válidas; misturar as duas entre capturas não é.**

### A captura tem de ser do u-center, não por script

> **Com NTRIP não existe captura por script.** O u-center 2 **é** o cliente NTRIP: ele recebe
> o RTCM do caster e o injeta no receptor **pela mesma porta serial**. Como a porta é
> exclusiva, ele tem de ser o dono dela do começo ao fim da sessão.

Isso não é limitação nossa, é como a cadeia funciona. O fluxo fica:

1. u-center 2 conecta no receptor, conecta no caster e **grava a sessão**
2. Ele escreve `.ubx` e `.uc2` na pasta `.ucenter` do perfil
3. Copie os dois para `gnss/capturas/` e analise **offline**, no `.uc2`

As ferramentas leem `.uc2` direto, e a **convergência sai da hora UTC do próprio `GGA`** —
não depende do carimbo de tempo do u-center nem de ter capturado ao vivo. O `desvio.py`
reporta convergência sozinho sempre que o log tem mais de uma qualidade de fix:

```
   convergencia (sobre os 5 fixes do log, sem filtro):
     primeira vez em autonomo           0.0 s
     primeira vez em RTK flutuante     20.0 s
     primeira vez em RTK fixo          30.0 s
     epocas em RTK fixo             40.0%  (2)
```

A convergência é calculada sobre **todos** os fixes, mesmo quando `--qualidade` filtra o CEP
— senão o filtro esconderia justamente o caminho até o fixo.

### O que medir, que é diferente dos outros degraus

O RTK tem **duas** grandezas de tempo e **duas** de dispersão:

| grandeza | o que é |
|---|---|
| **Tempo até fixo** | do início das correções até `GGA` qualidade **4**. É convergência, não TTFF |
| Tempo até flutuante | até qualidade **5**; costuma ser bem menor |
| **CEP em fixo** | dispersão contando **só** as épocas de qualidade 4 |
| Fração de épocas em fixo | quanto da sessão sustentou o fixo — sozinho já qualifica o enlace |

> **A dispersão RTK precisa ser filtrada por qualidade.** Um CEP que mistura fixo e flutuante
> não descreve nem um nem outro. O `desvio.py` tem `--qualidade` para isso:

```
cd gnss/tools
# so as epocas em RTK fixo
python desvio.py --log "X20P RTK fixo=../capturas/x20p_rtk_<hhmm>.uc2" --qualidade 4   --png ../../doc/gnss/img/desvio_rtk_fixo.png
# e o mesmo log em flutuante, para comparar
python desvio.py --log "X20P RTK flutuante=../capturas/x20p_rtk_<hhmm>.uc2" --qualidade 5
```

Ele imprime que fração dos fixes sobreviveu ao filtro — esse número **é** a fração de épocas
em fixo, e vale ser anotado.

Para a escada completa numa figura só, os três degraus vêm de logs diferentes:

```
python desvio.py --log "nRF9151 L1=../capturas/nrf9151_<hhmm>.nmea"                  --log "X20P aberto=../capturas/x20p_aberto_<hhmm>.uc2"                  --log "X20P RTK=../capturas/x20p_rtk_<hhmm>.uc2"                  --png ../../doc/gnss/img/escada_precisao.png
```

### O que anotar, só para NTRIP

| campo | por quê |
|---|---|
| Caster e mountpoint | reprodutibilidade |
| **Comprimento da baseline** | entra no erro pelo termo de 1 ppm |
| Mensagens RTCM que a base emite | 1005/1006 e MSM; a ausência de 1005/1006 é falha dura |
| Idade da correção | o rover descarta correção com mais de ~60 s |
| Fração de épocas em fixo | qualifica o enlace |

O diagnóstico fica no `UBX-RXM-COR` — `msgUsed` separa "chegou e foi descartada" de "chegou e
serviu", e o `carrSoln` do `UBX-NAV-PVT` dá 1 para flutuante e 2 para fixo. As cinco falhas
demonstráveis estão em `gnss/04_demo_rtk/README.md`.

## Estimativa de jornada

Calculada a partir dos tempos medidos em 2026-09-08/09: blocos de 25 min renderam 7 a 9
amostras de TTFF por variante, das quais 4 a 6 úteis depois de descartar as três primeiras.

| etapa | duração | precisa de gente? |
|---|---|---|
| Montagem, ficha da posição, foto | 15 min | sim |
| Dispersão nRF9151 (900 s) | 15 min | não |
| TTFF nRF9151, 6 blocos de 20 min, duas rodadas invertidas | 120 min | não |
| Troca de cabo para o X20P, desenergizado | 5 min | sim |
| Dispersão X20P (900 s) | 15 min | parcial |
| TTFF X20P | 40 min | parcial |
| Alternância entre receptores, para controlar horário | 30 min | sim, nas trocas |
| **NTRIP: Survey-In da base** (só se a base mudar de lugar) | 15 a 60 min | sim |
| **NTRIP: cliente e caster no ar** | 10 min | sim |
| **NTRIP: convergência, ~6 repetições** | 30 min | parcial |
| **NTRIP: dispersão em fixo (900 s)** | 15 min | não |
| Análise, figuras e ficha | 20 min | não |

**Completa, com NTRIP e base nova: 5 h30 a 6 h30**, das quais cerca de 1 h30 exigem presença.

Versões mais curtas, e o que cada uma perde:

| versão | tempo | o que perde |
|---|---|---|
| Completa com NTRIP | 5 h30 a 6 h30 | — |
| Completa sem NTRIP | 4 h30 | fica sem o terceiro degrau |
| Sem a segunda rodada de TTFF | 3 h | perde o controle de deriva do céu |
| Só nRF9151 | 2 h30 | sem comparativo de receptor |
| **Mínima defensável** | **1 h15** | dispersão + uma rodada de TTFF das três assistências |

A **mínima defensável** é a indicada para uma janela de oportunidade — um quarto de hotel com
vista melhor, por exemplo. Ela entrega o CEP e o TTFF nas três assistências, que é o par que
sustenta a comparação entre posições.

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
Plano de terra (material e diametro):
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
