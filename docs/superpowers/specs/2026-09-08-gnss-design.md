# GNSS e Localização de Precisão — design do módulo

**Data:** 2026-09-08
**Módulo:** `gnss/` — GNSS e Localização de Precisão (parte dos dias 3–4)
**SDK alvo:** nRF Connect SDK v3.4.0 (`C:\ncs\v3.4.0`)
**Hardware:** nRF9151-SMA-DK (PCA10201) × 3, u-blox EVK-X20P × 2
**Local:** SIDIA Amazon Tower, Av. Darcy Vargas 654, Chapada, Manaus

## 1. Contexto e escopo

O `gnss/README.md` promete hoje dois labs e três blocos teóricos:

> - Constelações e bandas GNSS; fontes de erro e técnicas de correção
> - GNSS no nRF9151: coexistência com LTE, assistência (A-GNSS)
> - RTK: estações de referência, NTRIP, precisão centimétrica

Decisões de escopo tomadas no brainstorming:

- **Orçamento de 2 horas** para GNSS e NTN somados.
- **GNSS e NTN ficam em pastas separadas**, `gnss/` e `comms/ntn_nbiot/`, mas foram
  desenhados juntos por compartilharem o kit.
- **Formato:** duplas fixas nos três nRF9151-SMA-DK, todos ao mesmo tempo. Os dois
  EVK-X20P ficam na demo conduzida pelo instrutor.
- **O NTN sai do bloco de 2 horas.** Vira roteiro entregue, executado se houver janela de
  passada. Motivo em §8.
- **PPP-RTK entra**, embora não esteja na súmula. Pedido do instrutor, **como teoria apenas**.
- **A correção garantida do módulo é o RTK da base local.** O RTK contra a estação pública da
  UEA entra como **bônus** (§3.5), porque depende de cadastro externo e de internet. O resto da
  taxonomia é ensinado sem bancada, o que torna os diagramas de §7.7 material de primeira
  classe e não ilustração.
- **A coexistência com LTE deixa de ser tópico solto** e vira o quarto eixo do módulo,
  ancorado nos modos de fix e no fato de o rádio ser chaveado (§7.3).

O orçamento fica assim, sem folga:

| Bloco | Minutos |
|---|---|
| Teoria de GNSS e correções | 35 |
| Lab 1 — fix, satélites e precisão | 25 |
| Lab 2 — o rádio compartilhado | 25 |
| Demo da escada de precisão | 25 |
| **Total** | **110** |

O corte final é decisão do instrutor com tempo real na mão, como no módulo de Wi-Fi.

## 2. Estado da arte verificado

Tudo nesta seção foi conferido no SDK instalado ou em documento oficial do fabricante.
Onde não deu para confirmar, está dito.

### 2.1 O nRF9151 é receptor de banda única

O nRF9151 recebe **dois sinais, os dois em 1575,42 MHz**:

| Sinal | |
|---|---|
| GPS L1 C/A | |
| QZSS L1 C/A | |

Não há Galileo, não há GLONASS, não há BeiDou, e não há L2, L5 ou L6. GPS L1 C/A não pode ser
desabilitado.

Fonte: nRF9151 Product Specification, capítulo do receptor de GPS, que lista como recursos
"GPS L1 C/A reception" e "QZSS L1 C/A reception" e nada mais; e o guia de recursos da série
nRF91, que diz que "an nRF91 Series device supports both GPS L1 C/A and QZSS L1C/A at
1575.42 MHz". A lista de firmware do SiP repete: "GPS L1 C/A and QZSS L1C/A positioning".

**Aviso de variante:** GNSS só existe na variante **SICA**. Não há GNSS nas variantes SIAA e
SIBA. Conferir a variante do kit antes da aula.

Isso não é limitação a corrigir, é a premissa do módulo: a diferença para o X20P é de
classe de receptor, não de qualidade.

#### 2.1.1 Afirmação RETIRADA — não ressuscitar

**Retirada em 2026-09-08:** *"o nRF9151 recebe três sinais, GPS L1 C/A, QZSS L1 C/A e
Galileo E1 OS."*

Estava errada. Eu li as constantes de `nrf_modem_gnss.h` como se fossem a lista de sinais **deste
SiP**, quando elas são a lista da **interface**, que serve a vários dispositivos e firmwares de
modem. O próprio cabeçalho avisa, nos campos de assistência de Galileo, que aquilo "is only
supported by devices with Galileo support". O nRF9151 não é um deles.

Consequência para o material: **o contraste com o X20P fica ainda mais forte**, porque são dois
sinais de uma banda contra dezenas de sinais em quatro bandas. E some do deck qualquer menção a
Galileo do lado Nordic.

### 2.1.2 Os números do pé da escada, com fonte

nRF9151 Product Specification, tabela de especificação elétrica do receptor de GPS. Condições
declaradas: **céu aberto, 25 °C, relógio TCXO, e com LNA externo com filtro SAW**. O intervalo
de fix do modo periódico é de 2 minutos, e o A-GPS inclui os parâmetros do modelo ionosférico
NeQuick.

| Grandeza | Valor |
|---|---|
| TTFF a frio | 30,5 s |
| TTFF a quente | 1,3 s |
| TTFF com A-GPS | 1,3 s |
| Precisão 2D (CEP50), rastreio contínuo | 2,0 m |
| Precisão 2D (CEP50), contínuo com A-GPS | 1,8 m |
| Precisão 2D (CEP50), periódico | 3,4 m |
| Precisão 2D (CEP50), periódico com A-GPS | 3,1 m |
| Sensibilidade a frio / a quente / em rastreio | −146,5 / −152,5 / −156,5 dBm |

**O par que justifica o lab 2 inteiro:** 30,5 s a frio contra 1,3 s com assistência. É a razão de
A-GNSS existir, e agora é número do fabricante, não retórica.

A especificação também diz, com todas as letras, que **"GPS receiver operation is time
multiplexed with the LTE modem"**, e que GNSS opera enquanto o modem está em RRC idle, em PSM ou
desativado. É a tese de §7.3 na fonte primária.

**Atenção ao comparar com o X20P:** os números da Nordic são **CEP50** e os do X20P são **CEP**
em medição estática de 24 h. O material precisa dizer isso ao pôr os dois lado a lado, senão
compara grandezas diferentes.

### 2.2 O sample da Nordic já entrega os observáveis

`nrf/samples/cellular/gnss` roda em `nrf9151dk/nrf9151/ns` e imprime, sem alteração de
código:

- `Accuracy: X m` — o campo `accuracy` do PVT, definido como **2D 1-sigma em metros**.
- `Tracking: N Using: N Unhealthy: N` — satélites rastreados, usados no fix, e insalubres.
- `Distance from reference: X` — distância até uma coordenada de referência configurável.
- As quatro mensagens de coexistência listadas em §7.3.

O mascaramento de NMEA já habilita as cinco sentenças, `RMC`, `GGA`, `GLL`, `GSA` e `GSV`.
Isso importa porque o RTKPLOT exige `GPRMC` e `GPGGA`, e porque é o mesmo conjunto que o
EVK-X20P emite por padrão. Os dois receptores falam o mesmo dialeto de saída de fábrica.

Opções relevantes do `Kconfig` do sample:

| Opção | Papel no módulo |
|---|---|
| `GNSS_SAMPLE_MODE_CONTINUOUS` | Lab 1 |
| `GNSS_SAMPLE_MODE_PERIODIC` | Lab 2, com `PERIODIC_INTERVAL` e `PERIODIC_TIMEOUT` |
| `GNSS_SAMPLE_MODE_TTFF_TEST` | Lab 2, com `TTFF_TEST_COLD_START` |
| `GNSS_SAMPLE_ASSISTANCE_NONE` | Degrau 1 de assistência |
| `GNSS_SAMPLE_ASSISTANCE_MINIMAL` | Degrau 2, de graça |
| `GNSS_SAMPLE_ASSISTANCE_NRF_CLOUD` | Degrau 3, cobrado |
| `GNSS_SAMPLE_LTE_ON_DEMAND` | Entrega explícita do rádio |
| `GNSS_SAMPLE_POWER_SAVING_*` | Ciclo de trabalho do rastreio |
| `GNSS_SAMPLE_REFERENCE_LATITUDE/LONGITUDE` | Recebe a coordenada levantada pela base RTK |
| `GNSS_SAMPLE_LOW_ACCURACY` | Fix com 3 satélites |

### 2.3 Assistência tem três degraus, não dois

- **Nenhuma.** O receptor busca tudo sozinho.
- **Mínima.** Almanaque de fábrica embutido, hora da rede LTE e posição grosseira pelo
  código do país. **Não custa chamada de nuvem e não exige onboarding.**
- **Por nuvem.** A-GNSS da nRF Cloud por CoAP. **Exige o dispositivo integrado à nRF Cloud
  com certificado válido**, feito com o nRF Cloud Utils, e é cobrado por chamada, como o
  lab 13 de Wi-Fi.

O almanaque de fábrica de `factory_almanac_v3.h` foi gerado em **2026-06-02**. O próprio
arquivo avisa que ele perde exatidão com o tempo. Verificar a idade antes do curso.

### 2.4 Antena: o SMA DK alimenta, e não tem nada de bordo

Do guia de hardware do nRF9151 SMA DK:

- **J1** é o conector de LTE, DECT NR+ e NTN. **J2** é o de GNSS. São separados.
- A placa **não transmite nem recebe sem antena externa**. Não há antena de bordo, nem
  LNA de GNSS de bordo. A tabela de solder bridges não tem nenhuma entrada de GNSS.
- **J2 já fornece 3 V DC** para alimentar um LNA externo, vindos do nPM1300 da placa. Dá
  para cortar removendo o indutor L3, e dá para mudar a tensão reprogramando o nPM1300.
- **Corrente máxima em J2: não documentada.** Não achei número em nenhum documento Nordic.

Do lado da u-blox:

| Item | Valor |
|---|---|
| ANN-MB2 (antena do kit EVK) | 3,0 a 5,0 V, típ. 15 mA, ganho total 23 dB, multibanda, SMA |
| Conector RF IN do EVK | 3,3 V, proteção de curto em 60 mA |
| Ganho externo exigido pelo ZED-X20P | mínimo 17 dB, máximo 50 dB |

Consequências para a montagem:

1. **Antena ativa é obrigatória** no SMA DK, porque não há LNA de bordo.
2. **A antena do ponto de medida tem que ser a ANN-MB2**, porque ela é multibanda e cobre
   L1 junto. A antena Kyocera que vem com a SMA DK provavelmente cobre só L1 e não serve ao
   X20P. **Modelo, bandas e se é ativa: não confirmado.**
3. Os 3 V do SMA DK estão dentro da faixa da ANN-MB2, mas no limite de baixo. A u-blox
   especifica o ganho a 5 V e **não publica o desempenho a 3 V**.
4. **Nunca deixar os dois receptores no mesmo cabo.** Um alimenta com 3 V e o outro com
   3,3 V; ligados juntos, um regulador empurra corrente para dentro do outro. A troca é
   sempre com o receptor desenergizado.
5. Alimentar os dois ao mesmo tempo exigiria divisor GNSS com passagem de DC em **exatamente
   uma** porta, e cabos de mesmo comprimento. Não é necessário para este desenho.

### 2.5 Configuração de antena no NCS: uma linha, e um detalhe

`nrf/lib/modem_antenna/Kconfig`:

- A biblioteca é `default y` para o alvo do nRF9151 DK, e a escolha padrão é
  **`MODEM_ANTENNA_GNSS_ONBOARD`**. O lab precisa mudar isso explicitamente.
- `CONFIG_MODEM_ANTENNA_GNSS_EXTERNAL=y` é **a única configuração necessária**. O
  `%XMAGPIO` é vazio para esta placa.
- Com a antena de bordo o NCS envia `AT%XCOEX0=1,1,1565,1586`, que faz o pino COEX0 subir
  na banda 1565 a 1586 MHz para ligar o LNA de bordo. Com a externa envia `AT%XCOEX0` sem
  parâmetros, ou seja, não configura controle do pino.
- **Nuance honesta para o deck:** no SMA DK não existe LNA de bordo, então o comando é
  inócuo no hardware. Ainda assim a opção externa é a correta, porque o alvo de build é
  compartilhado com a DK comum e o padrão acionaria o COEX0 sem necessidade.

**Aviso para o README do lab:** um aluno que apareça com uma nRF9151 DK comum compila e
roda o mesmo firmware, mas fica preso à antena de bordo. Nessa placa, forçar a opção externa
desabilita o LNA de bordo e o desempenho cai.

### 2.6 O ZED-X20P e os números da escada

Do datasheet ZED-X20P-01B, medição estática de 24 h, RTK com baseline de 1 km:

| Regime | Horizontal | Vertical | Convergência |
|---|---|---|---|
| Autônomo | 1,2 m CEP | 2,0 m | — |
| SBAS | 0,6 m | 1,0 m | — |
| PPP (Galileo HAS) | < 0,20 m | < 0,40 m | não consta |
| PPP-RTK (SPARTN) | < 0,06 m | < 0,10 m | < 40 s |
| PPP-RTK (CLAS) | < 0,04 m | < 0,06 m | < 70 s |
| RTK (RTCM3) | 0,006 m + 1 ppm | 0,01 m + 1 ppm | < 7 s |

O datasheet diz textualmente que são valores observados, não limites de projeto garantidos,
e que o RTK exclui erros de phase center offset. **Citar essa ressalva em aula.**

Bandas e constelações: L1, L2, L5 e L6, com GPS, Galileo, GLONASS, BeiDou, QZSS, NavIC e
SBAS. Detalhe didático: **a "banda L6" são três coisas distintas na mesma vizinhança**,
Galileo E6 e QZSS L6 em 1278,75 MHz e BeiDou B3I em 1268,52 MHz.

**Depende da revisão e do firmware.** GLONASS aparece na revisão -01B. CLAS exige firmware
HPG 2.10 e Galileo HAS exige HPG 2.11, e o HAS vem **desabilitado por padrão**. NavIC L1-SPS
está marcado como em desenvolvimento. Primeira coisa a fazer na bancada é ler a versão.

### 2.7 RTK em Manaus: por que o caminho óbvio não existe

Verificado por consulta direta ao sourcetable do caster do IBGE em 2026-09-08.

- **O serviço RBMC-IP existe, é gratuito e exige cadastro.** Caster em
  `gps-ntrip.ibge.gov.br`, porta 2101, autenticação HTTP Basic, máximo de 1000 acessos
  simultâneos. Prazo de liberação: **não confirmado**, entre imediato e cerca de um dia útil.
- **A estação NAUS não está no serviço de tempo real.** Ela é de pós-processamento. E os
  arquivos diários dela **desapareceram a partir de 2026-08-23** e não voltaram.
- **A estação de tempo real de Manaus é a AMUA0**, na Universidade do Estado do Amazonas,
  dentro da cidade. Ela transmite **RTCM 3.0 legado, com 1004 e 1012, sem MSM**.
- **O X20P como rover decodifica RTCM legado.** A Tabela 6 do datasheet -01B, que é a tabela
  de **entrada**, tem 26 linhas e inclui 1001 a 1004, 1009 a 1012, 1007, 1033, MSM4, MSM5,
  MSM7, 1005, 1006, 1230 e 4072.0. O texto é "*operating as a rover, ZED-X20P can decode the
  RTCM 3.4 messages listed in Table 6*".

- **Assimetria que vira conteúdo.** Como **base**, o X20P só fala MSM: a Tabela 7, de saída,
  tem 12 linhas e não traz nenhuma mensagem legada. Não existem itens
  `CFG-MSGOUT-RTCM_3X_TYPE1004_*` nem `TYPE1012_*` no banco de configuração, e a Interface
  Description marca as legadas como **Input** apenas. Ou seja, o receptor moderno **não
  produz** o formato antigo, mas continua **entendendo** o formato antigo, por compatibilidade
  com bases de terceiros. É uma boa aula sobre evolução de protocolo.

### 2.7.1 Afirmação RETIRADA — não ressuscitar

**Retirada em 2026-09-08:** *"a AMUA0 manda RTCM legado sem MSM, o X20P não aceita essas
mensagens, e por isso o rover não fixaria em Manaus."*

Estava errada. A primeira leitura da documentação pegou só a lista de saída e a tomou por lista
de entrada. A tabela de entrada inclui as legadas, e a AMUA0 transmite 1004, 1012, 1006 e 1033,
todas decodificáveis pelo rover.

**O que sobra de pé sobre RTK em Manaus:**

| Fato | Força |
|---|---|
| NAUS é de pós-processamento e seus arquivos sumiram desde 2026-08-23 | observação direta |
| A AMUA0 existe, é de tempo real e fica **dentro da cidade**, na UEA | observação direta |
| A AMUA0 é **GPS e GLONASS apenas**, sem Galileo nem BeiDou, com observáveis legados de L1 e L2 | observação direta |
| O céu equatorial castiga a fase da portadora (§2.8) | literatura |
| Que o rover recusaria o formato | **refutado** |

**Consequência para o material:** o bloco de Manaus deixa de ser "não há correção utilizável" e
passa a ser mais honesto e mais interessante — **há base na cidade, e ainda assim RTK ali é
difícil**, por menos constelações disponíveis para resolver ambiguidade e por cintilação. A
baseline, que seria o suspeito natural, **não é o problema neste caso**, porque a estação é
local. O argumento de baseline continua válido como física geral (D4), não como diagnóstico de
Manaus.
- **A estação seguinte com MSM está a 365 km.** Com o termo de 1 ppm, que vale 1 mm por km,
  isso põe o erro de baseline na casa de 36 cm.
- O caster comunitário RTK2go tem **doze estações no Brasil e nenhuma no Amazonas**.

### 2.8 Cintilação ionosférica: Manaus é caso de estudo

Manaus fica a 3,1°S e 59,9°W, com **latitude de dip magnético de 6,2°N**, ou seja dentro da
crista da anomalia de ionização equatorial, onde a cintilação é mais severa do planeta.

- O efeito operacional não é perder um pouco de precisão. A **fase da portadora**, que é o
  observável do RTK, fica ruidosa, o receptor perde lock e as ambiguidades não resolvem. O
  sintoma é o rover cair de fixo para flutuante e não voltar.
- É fenômeno **pós-pôr-do-sol**, pior nos **equinócios**. Setembro é equinócio.
- O ciclo solar 25 passou do máximo em outubro de 2024 e está em queda, então 2026 tende a
  ser menos intenso que 2024, mas não ausente.
- **Não existe métrica publicada de taxa de fixação de RTK especificamente em Manaus.** Não
  citar número.

## 3. Abordagem

### 3.1 A escada de precisão, no mesmo ponto físico

Uma antena fixa marca o ponto de medida. Os receptores se revezam nela, com troca de cabo e
sempre desenergizados.

| Degrau | Receptor | Correção |
|---|---|---|
| 1 | nRF9151, banda única | nenhuma |
| 2 | X20P, multibanda | nenhuma |
| 3 | X20P, multibanda | RTK da base local |

Uma segunda antena, alguns metros ao lado, é a **base**. A baseline de metros elimina o termo
de ppm e faz as duas antenas verem rigorosamente a mesma atmosfera, o que também neutraliza a
cintilação que seria fatal numa baseline longa.

**O laço que fecha o módulo:** a coordenada verdadeira do ponto de medida sai do próprio fix
RTK e volta como `GNSS_SAMPLE_REFERENCE_LATITUDE/LONGITUDE` no firmware do nRF9151. A partir
daí a placa do aluno não reporta uma posição, reporta **o próprio erro contra uma verdade
medida em sala**.

**Ressalva metodológica que o material precisa carregar:** os três degraus acontecem com
minutos de diferença, não no mesmo instante. A u-blox recomenda comparação em paralelo por
divisor e testes de 24 h. Como a diferença entre metros e centímetros é enorme perto da deriva
de geometria em poucos minutos, a comparação se sustenta — **desde que o material não afirme
simultaneidade**.

### 3.2 Base e rover locais, sem internet

A página do produto do EVK-X20P diz que são necessários dois kits para fazer base e rover. O
caster NTRIP roda **dentro do u-center 2**, na máquina da base, e o rover se conecta ao IP que
o próprio u-center 2 mostra no rodapé da janela. Isso é **rede local**: Wi-Fi da sala, cabo
entre os notebooks, ou um deles como ponto de acesso. O RTK entre os kits não toca a internet.

Regras que decidem se fixa:

- **Lista recomendada pela u-blox para base estacionária:** 1005, 1006, 1074, 1084, 1094,
  1124 e 1230. É **MSM4**, não MSM7.
- **A saída do X20P tem 12 mensagens ao todo**: 1005, 1006, MSM4 e MSM7 das quatro
  constelações, 1230 e 4072.0. Não há MSM5 na saída, nem nada legado.
- **Dependência de firmware:** 1006 e 4072.0 na saída exigem **HPG 2.10**. Num EVK com HPG
  2.02 a base só emite **1005**, o que basta, já que o rover aceita 1005 ou 1006.
- **Não misturar MSM4 e MSM7.** O manual avisa que isso pode setar errado o bit de múltiplas
  mensagens. Todas as constelações usam o mesmo tipo.
- **1230 é obrigatório na prática.** Sem ele, ou sem 1033, as ambiguidades de GLONASS ficam
  em float mesmo com o rover em fixo.
- Todas as mensagens de observação vão no **mesmo rate**. Os rates em Hz **não são
  especificados** pela u-blox.
- **Desmarcar "Get configuration automatically"** no u-center 2. O padrão transmite tudo e
  causa latência.
- Escolher uma **porta liberada no firewall**. Na primeira execução o Windows pergunta, e uma
  negativa distraída faz o rover não conectar sem sintoma que aponte para a causa.

### 3.3 A base é levantada uma vez e gravada como fixa

Se a base ficar em modo Survey-In gravado na flash, ela **refaz o levantamento a cada boot** e
produz uma coordenada um pouco diferente toda vez. O manual é explícito: qualquer erro na
posição da base se traduz diretamente em erro no rover.

O procedimento correto, feito na montagem e não em aula:

1. Rodar o Survey-In uma vez. O guia sugere começar com 5000 mm de precisão alvo e 60 s.
   Acompanhar por `NAV-SVIN`. A mensagem 1005 só sai depois que o Survey-In conclui.
2. Anotar a coordenada.
3. Gravar a base em `CFG-TMODE-MODE = FIXED`, com os campos de alta precisão.
4. Salvar na **flash**, com o botão Save do u-center 2.

Isso resolve três coisas: a base sobe pronta em segundos, a coordenada é idêntica entre
sessões, e essa coordenada é a referência de verdade do §3.1.

**Memória:** configuração gravada na flash sobrevive ao ciclo de energia. O kit **não vem com
bateria de backup**, então efemérides, almanaque e última posição se perdem e **todo boot do
X20P é partida a frio**, cerca de 25 s.

### 3.4 O que fica fora, e por quê

- **Fio direto entre base e rover.** Os padrões de fábrica da UART2 do módulo já são de
  correção, com RTCM saindo e entrando. Mas o guia do EVK diz que os pinos **não conseguem
  excitar cabo** e limita o comprimento a **25 cm**, e a u-blox não documenta essa topologia.
  Serve para demonstrar o conceito com os kits lado a lado, não para base e rover separados.
- **PPP-RTK.** Decisão de 2026-09-08: não será testado. Permanece como conteúdo (§7.7). Isso
  inclui o acesso ao PointPerfect Flex pela aba EVK do u-center 2, que sai do desenho.

- **NTRIP de terceiro: reaberto como bônus** (§3.5). A decisão original de 2026-09-08 foi
  tomada sob a premissa, depois refutada (§2.7.1), de que o formato da estação local não
  serviria. A estação da UEA é pública e está a distância útil, então o teste volta à mesa —
  **como extra, não como espinha**. A base própria continua sendo o caminho garantido.
- **PointPerfect por L-band nativo no X20P.** Documentação conflitante entre o product
  summary e o integration manual. **Não afirmar em aula.**

### 3.5 Bônus: RTK contra a estação pública da UEA

A estação **AMUA0** fica na Universidade do Estado do Amazonas e está publicada no caster do
IBGE, que é **gratuito mediante cadastro**. A linha do sourcetable, lida em 2026-09-08:

```
STR;AMUA0;Manaus - UEA;RTCM 3.0;1004(1),1006(1),1008(10),1012(1),1013(10),
1019(10),1020(10),1033(10);2;GPS+GLO;RBMC-IP;BRA;-3.09;-60.02;...;B;N;1500
```

**O conjunto necessário para RTK está completo**, e cada peça tem par na tabela de entrada do
X20P:

| Mensagem | Papel | Aceita pelo X20P? |
|---|---|---|
| 1004 a 1 Hz | Observáveis GPS estendidos de L1 e L2 | sim |
| 1012 a 1 Hz | Observáveis GLONASS de L1 e L2 | sim |
| 1006 a 1 Hz | Posição da antena da base, com altura | sim |
| 1033 a cada 10 s | Descrição da antena | sim |

Dois detalhes que fecham o caso:

- **O requisito de viés de GLONASS é satisfeito por 1033**, e não por 1230. O manual aceita
  uma ou outra; sem nenhuma das duas, as ambiguidades de GLONASS ficariam em float.
- **As duas mensagens de observação vão no mesmo rate**, 1 Hz, que é a regra que o manual
  impõe.
- As demais (1008, 1013, 1019, 1020) **não estão na tabela de entrada** do X20P e serão
  ignoradas. Isso não atrapalha, e ainda rende demonstração: elas aparecem no status de
  correção sem suporte de entrada (§7.2.2).

**Condições para o bônus acontecer**, nenhuma sob controle total do instrutor:

1. Cadastro no serviço do IBGE, gratuito, com prazo de liberação **não confirmado**, entre
   imediato e cerca de um dia útil. Fazer com antecedência.
2. Internet na sala. O RTK da base própria não precisa; este precisa.
3. ~~Baseline entre o local do curso e a UEA.~~ **Resolvida, e a favor.** O curso é na **SIDIA
   Amazon Tower, Avenida Darcy Vargas, 654, Chapada**. A estação fica na Escola Superior de
   Tecnologia da UEA, **Avenida Darcy Vargas, 1200**, Parque 10 de Novembro. **Mesma avenida.**
   A baseline é da ordem de **1 km**, muito dentro da faixa confortável, e o termo de 1 ppm
   contribui com cerca de 1 mm. A distância exata **é medida em aula**, porque a coordenada da
   base chega na mensagem 1006 assim que o rover conecta.
4. Cintilação. É fenômeno pós-pôr-do-sol, então aula diurna joga a favor.

**O que o bônus entrega, e com a baseline resolvida ele virou experimento controlado.** Duas
soluções RTK no mesmo rover, no mesmo ponto, na mesma hora:

| Fonte de correção | Baseline | Constelações |
|---|---|---|
| Base própria | metros | GPS, GLONASS, Galileo e BeiDou |
| AMUA0, na UEA | ~1 km | GPS e GLONASS apenas |

Como as duas baselines são curtas, **a distância deixa de ser a variável** e o que resta é o
número de constelações disponíveis para resolver ambiguidade. O aluno vê o efeito de ter duas
contra quatro constelações, isolado, sem confundir com o efeito da distância. É a melhor
demonstração do módulo, e ela nasceu do acaso de o curso ser na mesma avenida da estação.

O termo de 1 ppm, que não aparece aqui porque as duas baselines são curtas, continua vivendo na
figura D4, como física geral.

**Se não rodar**, nada do módulo cai. O material trata o bônus como bônus, e o texto **não pode
prometer ao aluno um lab que depende de cadastro externo e de internet**.

### 3.6 Ferramentas

| Ferramenta | Papel | Observação |
|---|---|---|
| u-center 2 | Configurar o X20P, Survey-In, caster, cliente NTRIP, dispersão nativa | Exige conta u-blox com dois fatores no primeiro uso |
| u-center clássico | Dispersão do NMEA do nRF9151 | A view de dispersão do u-center 2 depende de `UBX-NAV-PVT` e fica vazia com NMEA |
| RTKPLOT (RTKLIB) | Opcional: as duas trilhas sobrepostas e a diferença | Exige `GPRMC` e `GPGGA`, que os dois receptores já emitem |
| PPK2 | Geração de material, não lab de aluno | §7.4 |

O instrutor **verificou na bancada** que o u-center lê NMEA do nRF9151. Isso vale mais que a
documentação, que só declara suporte a receptores u-blox das gerações 10 e 20 no u-center 2 e
perdeu, nessa versão, a frase de suporte a NMEA genérico que o clássico tinha.

## 4. Os labs

Quatro builds do mesmo código fonte, no padrão que o módulo de Wi-Fi já usa.

### 4.1 `gnss/01_gnss_basic/` — o fix e o que ele custa

Modo contínuo com PVT. O aluno vê o fix a frio acontecer, lê a precisão em metros, e vê a
contagem de satélites rastreados contra usados no fix. Saída NMEA disponível.

Fecha o que a tabela do README promete: fix, NMEA e tracking.

### 4.2 `gnss/02_gnss_radio/` — o rádio compartilhado

Recompila o mesmo código em modo periódico e em modo de teste de TTFF, cobrindo assistência e
coexistência nas mesmas execuções. Detalhe do conteúdo em §7.3.

Entrega três tempos até o primeiro fix, um por degrau de assistência, e as mensagens de
coexistência que aparecem enquanto isso.

### 4.3 `gnss/03_nmea/` — o build que entra no u-center

**Não ocupa bloco próprio no orçamento de tempo.** É o firmware que o instrutor grava numa das
DKs para o primeiro degrau da demo (§4.4), e que fica entregue ao aluno para uso posterior.

Saída só NMEA, com **log de console desligado**, para que a porta carregue apenas sentença
NMEA. O modo NMEA do sample ainda imprime a distância até a referência quando há fix válido, e
o log do Zephyr continua na mesma porta; os dois saem neste build.

Isso também rende um ponto de aula: é por isso que receptor comercial tem porta de dados
separada da porta de depuração.

### 4.4 A demo da escada

Conduzida pelo instrutor, com os dois EVK-X20P e a antena fixa, na sequência do §3.1. É onde
a teoria de correções encontra número medido.

## 5. Convenções transversais

- **Alvo de build:** `nrf9151dk/nrf9151/ns` para os três labs. A SMA DK é PCA10201 e usa o
  mesmo alvo da DK comum; não existe board separado no NCS v3.4.0.
- **`CONFIG_MODEM_ANTENNA_GNSS_EXTERNAL=y` em todos os `prj.conf`**, com comentário
  explicando por quê.
- **A coordenada de referência não é versionada com valor.** Ela vem da base RTK e é local da
  sala, como o `minha_rede.conf` do módulo de Wi-Fi. Fica vazia no repo.
- **Credenciais nunca entram no repo.** Conta u-blox, credencial do RBMC-IP e token da
  nRF Cloud vivem fora do versionamento.
- **`gnss/hex/`** segue o molde de `edge_ai/hex/` e `comms/hex/`, separando variantes públicas
  das que levam coordenada ou credencial local.

## 6. Bancada

### 6.1 O que testar primeiro

Três coisas destravam o resto e ainda não têm resposta:

1. **Uma instância do u-center 2 dá conta dos dois receptores?** O guia fala em "o dispositivo
   ativo", no singular, ao descrever o caster, e nunca mostra caster numa fonte e cliente
   noutra. Rodar duas instâncias na mesma máquina **não é documentado nem proibido**. As portas
   COM não conflitam e o login persiste. Se falhar, o arranjo é **dois notebooks**.
2. **A versão do firmware do modem** nas três SMA DK. Decide se há Galileo, e decide o que é
   possível no NTN.
3. **A versão do firmware do X20P.** Decide se CLAS e Galileo HAS existem.

Depois desses, o Survey-In inicial que gera a coordenada fixa da base.

### 6.2 Armadilhas registradas

- **Nunca mover a chave deslizante entre I2C e SPI com o EVK ligado.** O guia diz que pode
  danificar o chip GNSS. Se a chave estiver em SPI, o DB9 e os pinos de UART do conector
  frontal ficam desativados, e o sintoma é "a porta COM não manda nada".
- **Nunca dois receptores no mesmo cabo de antena** (§2.4).
- **Troca de cabo sempre com o receptor desenergizado.**
- A u-blox avisa: usar o conector RF apenas com antena GNSS ou simulador. Ligar a sistemas de
  distribuição por cabo pode danificar o EVK.
- Todo boot do X20P é partida a frio, porque não há bateria de backup.
- O botão RST do EVK apaga a memória volátil e força partida a frio.

### 6.3 Kits e antenas

| Item | Quantidade | Uso |
|---|---|---|
| nRF9151-SMA-DK | 3 | Duplas, labs 1 a 3, cada uma com a antena que veio no kit |
| EVK-X20P | 2 | Base e rover da demo |
| ANN-MB2 | 2 | Uma na base, uma no ponto de medida compartilhado |

A antena do ponto de medida **precisa ser a multibanda**, porque ela serve aos dois receptores;
a do kit da Nordic provavelmente não serve ao X20P (§2.4).

## 7. Material

### 7.1 A pergunta que organiza a teoria

O bloco teórico não é catálogo de técnicas. A pergunta é: **por que existem tantas técnicas de
correção, e como se escolhe entre elas?** A resposta é geografia e infraestrutura, e a cidade
da aula é o estudo de caso.

Sequência: constelações e bandas, fontes de erro, e então as técnicas de correção organizadas
pelo que cada uma exige de infraestrutura — SBAS, RTK, PPP e PPP-RTK.

### 7.2 Manaus, com os três fatos que convergem

1. A única base de tempo real da cidade transmite **GPS e GLONASS apenas**, com observáveis
   legados, o que reduz o número de satélites disponíveis para resolver ambiguidade (§2.7).
2. O céu da cidade fica sob a crista da anomalia de ionização equatorial, e a cintilação
   ataca justamente a fase da portadora, que é o observável do RTK (§2.8).
3. O receptor moderno **não produz** o formato antigo, embora ainda o **entenda** — a
   assimetria entre as tabelas de entrada e de saída do X20P (§2.7).

**Não usar o argumento de baseline como diagnóstico de Manaus.** A estação é local; a baseline
não é o problema aqui. O termo de 1 ppm é física geral e vive na D4, não neste bloco.

**Manaus é um estudo de caso de por que RTK é difícil**, e isso é melhor de ensinar do que um
lab onde tudo fixa em cinco segundos. A base própria mostra o RTK funcionando; o PPP-RTK
mostra o caminho que dispensa base local.

**Regra de redação para este bloco.** Os fatos têm forças diferentes e o material não pode
nivelar tudo como certeza. O conjunto de mensagens da estação e as tabelas do receptor são
**observação direta**. A cintilação é **literatura**, e **não existe métrica publicada de taxa
de fixação de RTK para a cidade** — nenhum número inventado. Nada aqui foi medido em bancada.

É por decisão de escopo, e não por indisponibilidade, que a base própria é **o único caminho de
RTK do módulo** (§3.4).

### 7.2.1 As falhas de RTK que dá para demonstrar sem caster

Como a taxonomia de correção não pode ser testada, o que **pode** ser demonstrado com os dois
EVK-X20P ganha importância. Cinco modos de falha são **documentados e determinísticos**, e
todos se montam mexendo na configuração da base.

| # | Como provocar | O que o manual garante |
|---|---|---|
| A | Base emite só MSM, **sem 1005 nem 1006** | O rover exige observação **e** posição da base; sem a mensagem de estação de referência ele não computa posição. Falha total e limpa |
| B | ID de estação de referência da base diferente do filtro do rover | O ID precisa bater com o das mensagens MSM, senão o rover **não computa a posição RTK fixa** |
| C | GLONASS ligado, base sem 1230 nem 1033 | As ambiguidades ficam em **float mesmo em modo fixo**, com desempenho degradado |
| D | Interromper o stream | O rover descarta correção com mais de **60 s** e cai para 3D ou 3D/DGNSS. Reversível e muito visual |
| E | Base em modo fixo com coordenada errada em mais de ~50 m | O receptor emite `UBX-INF-WARNING` com "base station position seems incorrect" |

**Não usar a variante "base emite só GLONASS".** O manual não descreve o comportamento quando
falta a observação de uma constelação inteira, então a demo não é determinística.

Roteiro sugerido: **A** para a falha dura, **C** para a degradação silenciosa, **D** para o
timeout, **E** para separar precisão relativa de acurácia absoluta.

### 7.2.2 Mostrar **por que** não fixou, e não só que não fixou

`UBX-RXM-COR` é emitido ao parsear com sucesso cada correção de entrada, **independentemente de
a mensagem ser suportada ou usada**. Os campos que importam:

| Campo | Uso didático |
|---|---|
| `msgUsed` | **1 = recebida mas não usada**, 2 = usada. Separa "chegou e foi descartada" de "chegou e serviu" |
| `correctionId` | O ID de estação de referência da mensagem, que é o que denuncia a falha B |
| `msgType` | O número da mensagem. **A ausência de RXM-COR de um tipo significa que ele não chegou** |
| `msgInputHandle` | Se o receptor tem suporte de entrada para aquela mensagem |
| `errStatus` | Livre de erro contra errônea |

Na tela, cada demo tem assinatura própria. Na A chegam correções de MSM e **nenhuma** de 1005
ou 1006. Na B chega a de MSM com `msgUsed` em "não usada" e o `correctionId` que não bate. Na D
os `RXM-COR` simplesmente param.

Complementos por satélite e por sinal: `UBX-NAV-SAT` marca quais satélites têm dado válido e em
quais a correção foi de fato aplicada; `UBX-NAV-PVT` traz `carrSoln`, com 1 para float e 2 para
fixo. No NMEA, a qualidade do `GGA` é 4 para fixo e 5 para float, o que também aparece no
u-center clássico.

A sequência de estados que o manual manda mostrar é **3D → 3D/DGNSS → Float → Fixed**, e ela
vale um slide sozinha.

### 7.3 O rádio é um só, e é chaveado

Este é o eixo mais específico da plataforma. Tudo decorre de haver **uma cadeia de rádio
multiplexada no tempo**: LTE e GNSS nunca operam no mesmo instante. Há três níveis de
chaveamento.

**Dentro do GNSS.** Três modos de economia: desligado e duas políticas, uma orientada a
desempenho e outra a consumo. As duas fazem **exatamente o mesmo ciclo**, e o que muda é a
agressividade com que o GNSS entra nele. Em ciclo de trabalho o receptor **rastreia 20% do
tempo**. Só afeta o modo de navegação contínuo.

**Entre GNSS e LTE.** Modo contínuo contra periódico. No periódico há intervalo e tempo limite
de fix, e o rádio fica livre entre tentativas. A sutileza: quando o GNSS conclui que precisa
baixar efemérides ou almanaque da transmissão dos satélites, ele **ignora temporariamente o
intervalo e as tentativas** e faz download programado até terminar. Existe um bit que desliga
isso, recomendado com A-GNSS. Desligar sem assistência faz o receptor nunca receber certos
dados, entre eles as **correções ionosféricas**, e a precisão cai.

Esse é o nó do módulo: disciplina de agenda, assistência e precisão são a mesma decisão vista
de três lados. E a ionosfera reaparece aqui, no receptor de banda única, depois de ter
aparecido na cintilação e no motivo pelo qual o X20P usa várias bandas.

**Do lado do LTE.** PSM e LTE sob demanda. O `prj.conf` do sample pede TAU periódico de
**8 horas** e tempo ativo de **6 segundos**. No modo sob demanda o firmware ativa o LTE só para
buscar assistência e depois devolve o rádio, com chamadas explícitas de mudança de modo
funcional. O aluno vê a entrega do rádio acontecendo em uma linha de código.

Há ainda o modo de baixa exatidão, que aceita fix com **três satélites em vez de quatro**, com
erro maior. É mais um botão no mesmo compromisso.

**As evidências que o sample imprime:**

- operação de GNSS bloqueada pelo LTE
- janelas de tempo de GNSS insuficientes
- períodos de sono entre notificações de PVT
- download de dados de navegação programado
- a contagem de vezes em que o prazo foi perdido

### 7.4 O PPK2 entra na geração de material

Decisão do instrutor: o PPK2 é usado **na preparação**, não como passo de aluno. O que vai
para o material são os números e as figuras, no mesmo padrão do lab 11 de Wi-Fi, onde os dados
ficam em `doc/comms/data/*.json` e as figuras são copiadas para a pasta do lab.

O que medir: corrente em rastreio contínuo, nas duas políticas de ciclo de trabalho, no modo
periódico entre fixes, em PSM, e com LTE sob demanda contra LTE sempre ativo.

Isso faz a rima estrutural com o módulo de Wi-Fi ficar explícita: lá a escada é de energia,
aqui é de precisão, e o eixo de energia aparece na documentação em vez de tomar tempo de sala.

**Pendência de bancada:** confirmar o ponto de medida de corrente do SMA DK antes de montar. A
armadilha registrada no módulo de Edge AI vale de aviso — com o PPK2 no lugar do jumper de
corrente da LM20-DK, o SoC ficou sem alimentação normal e o depurador falhou.

### 7.5 Reescrita do `gnss/README.md`

O texto atual promete correção RTK **via internet, por NTRIP**. O desenho entrega NTRIP de
verdade, com caster local e base própria, sem internet. A palavra internet continua coberta
pelo bônus da estação pública da UEA (§3.5) e pelo bloco teórico. O README descreve o bônus
**como bônus**, com as condições explícitas, e **não promete ao aluno um lab de NTRIP pela
internet**, porque ele depende de cadastro externo e de internet na sala.

O README passa a refletir o desenho, e não o contrário. O PPP-RTK, que não estava na súmula,
entra como entrega adicional.

### 7.6 Reescrita da seção GNSS do `PREREQUISITOS.md`

O texto atual pede três coisas. Com o desenho fechado, ele muda inteiro:

| Linha atual | O que fazer |
|---|---|
| u-center 2 para configurar o EVK | **Mantém**, e ganha o aviso da conta u-blox com dois fatores, feita antes do curso na máquina que vai projetar |
| Credenciais de um caster NTRIP, definidas pelo instrutor | **Vira opcional e ganha nome.** Cadastro gratuito no serviço do IBGE, para o bônus da estação AMUA0 da UEA (§3.5). Marcado como não essencial: sem ele o módulo roda inteiro com a base própria |
| Antenas com visada de céu | **Mantém**, e ganha a montagem de duas antenas, base e ponto de medida |

Entram três linhas novas: u-center clássico para a dispersão do NMEA do nRF9151, RTKLIB como
opcional, e a integração das três DKs à nRF Cloud com certificado, que é tarefa do instrutor
antes da aula e sem a qual o degrau de A-GNSS por nuvem não roda (§2.3).

### 7.7 Os sete diagramas — especificação em texto

**Por que esta seção existe.** A única correção que o módulo mede é o RTK da base local. SBAS,
DGNSS, RTK em rede, PPP e PPP-RTK serão ensinados sem bancada. Num repositório cujo hábito é
medir antes de afirmar, isso é exceção, e a compensação não é falar mais: é **mostrar o
mecanismo**. Estes diagramas não ilustram o texto, eles carregam o argumento.

**Decisão do instrutor em 2026-09-08:** as figuras **não são geradas por script**. Ficam
especificadas em texto aqui, e serão desenhadas depois, na montagem das apresentações finais.
Esta seção é o que sobrevive, e tem de bastar para desenhar sem reabrir a discussão.

Regra que vale para as sete: **cada figura mostra um mecanismo, não uma taxonomia**. Se a figura
puder ser trocada por uma lista de bullets sem perda, ela falhou.

Os números com fonte vivem em `doc/gnss/data/x20p_datasheet.json` e
`doc/gnss/data/nrf9151_gnss_spec.json`, que **permanecem**, porque são dados e não imagem.

---

#### D2 — OSR contra SSR

**A figura central do módulo.** Se só uma sobreviver ao corte de tempo, é esta.

Duas colunas. À esquerda, OSR: uma base RTK de posição fixa manda **observações brutas**,
pseudodistância e fase por época, e o rover **diferencia contra a base**. À direita, SSR: uma
rede de estações de referência alimenta um serviço que **modela as causas**, e difunde órbita,
relógio do satélite, vieses e modelo de atmosfera.

O argumento está na **geometria da validade**, não em texto. À esquerda, um círculo pequeno em
volta da base, com rovers dentro e **pelo menos um rover marcado como fora**, rotulado "fora do
entorno". À direita, uma região larga com vários rovers, todos válidos, rotulada "muitos rovers,
mesmo modelo".

**Sem nenhum número.** A diferença de alcance é só o tamanho das duas regiões. É isso que
responde, de uma vez, por que RTK exige base perto e PPP-RTK não.

#### D5 — A ionosfera atravessa o módulo

**A figura que dá unidade.** Sem ela, as três aparições da ionosfera parecem coincidência.

Três painéis **estruturalmente idênticos**, mesma altura de cabeçalho e mesma posição de
satélite, meio e receptor, para o olho comparar sem esforço.

1. **nRF9151.** Um observável só, GPS L1 C/A e QZSS L1 C/A na mesma frequência. Não separa o
   atraso ionosférico de outros efeitos. O motivo é subdeterminação: **faltam equações**, e a
   figura diz isso sem usar matemática.
2. **X20P.** Duas bandas cancelam o atraso de primeira ordem por combinação.
3. **Céu de Manaus.** A cintilação pós-pôr-do-sol quebra a fase da portadora
   **independentemente de quantas bandas**. É mecanismo diferente do atraso de grupo dos dois
   painéis anteriores, e o subtítulo precisa dizer isso, senão o painel 3 parece contradizer o 2.

#### D1 — Orçamento de erro e o que cada técnica remove

Grade de seis linhas por quatro colunas. Linhas: relógio do satélite, órbita, ionosfera,
troposfera, multicaminho, ruído. Colunas: autônomo, SBAS, RTK de base própria, PPP-RTK.

Cada célula tem dois estados apenas, **resta** ou **removida**, e a célula **nunca muda de
tamanho**, para não sugerir grandeza onde não há número.

A matriz, conferida célula a célula:

| | Autônomo | SBAS | RTK | PPP-RTK |
|---|---|---|---|---|
| Relógio do satélite | resta | removida | removida | removida |
| Órbita | resta | removida | removida | removida |
| Ionosfera | resta | removida | removida | removida |
| Troposfera | resta | **resta** | removida | removida |
| Multicaminho | resta | resta | resta | resta |
| Ruído | resta | resta | resta | resta |

**Dois pontos que a figura tem de deixar óbvios.** O SBAS **não** corrige troposfera. E
multicaminho e ruído **sobrevivem a todas** as técnicas, porque são locais da antena e do
receptor. Esse é o remate, e é o que mais ensina.

**RTK e PPP-RTK terminam no mesmo piso** nesta figura, de propósito. O que os separa é geografia
(D2) e tempo de convergência (D3), não o orçamento de erro.

**Esquemático de mecanismo, sem escala numérica alegada.** O subtítulo diz isso com todas as
letras.

#### D3 — Precisão contra convergência

Dispersão com precisão horizontal em escala logarítmica.

Os regimes que **declaram** convergência entram num eixo com tempo: RTK por RTCM3, PPP-RTK
SPARTN, PPP-RTK CLAS. Os que **não declaram** vão para uma faixa separada, sem eixo de tempo,
rotulada "sem convergência declarada": autônomo, SBAS, PPP por Galileo HAS, e o nRF9151.
**Nenhum valor inventado para preencher eixo.**

**O subtítulo carrega as condições, e isto não é opcional.** Os números do X20P são de medição
estática de 24 h, com RTK em baseline de 1 km, e o datasheet diz que são valores observados e
não limites de projeto garantidos. O número do nRF9151 é de céu aberto, 25 °C, relógio TCXO e
LNA externo com filtro SAW.

**Aviso obrigatório de grandeza:** a Nordic mede em **CEP50** e a u-blox em **CEP**. Pôr os dois
no mesmo eixo sem dizer isso compara grandezas diferentes.

**O contraste de TTFF fica FORA desta figura.** Misturaria duas noções diferentes de tempo no
mesmo eixo, já que convergência de correção e tempo até o primeiro fix não são a mesma coisa.
Ele merece figura própria, se houver espaço.

#### D4 — A baseline e o termo de 1 ppm

Reta de erro contra distância à base: termo fixo mais 1 mm por quilômetro. O termo fixo aparece
como linha horizontal, e a área entre as duas é o que o ppm acrescenta.

Três marcas: base própria em metros, 10 km, e 30 km, esta rotulada como onde a solução fixa
deixa de se sustentar em base única.

**Honestidade obrigatória no subtítulo: física geral, não diagnóstico de Manaus.** A estação
pública fica a cerca de 1 km do local do curso, então baseline não é o problema local. Sem essa
frase a figura mente por omissão.

#### D6 — O rádio é um só

Três painéis esquemáticos, no mesmo padrão visual de D5.

1. **O ciclo do LTE.** Bloco "ativo, 6 s" seguido de "RRC idle ou PSM, rádio livre", sob um
   colchete de "1 ciclo TAU, 8 h". Só nesse intervalo livre o GNSS usa o rádio.
2. **O ciclo de trabalho do GNSS.** Dentro da janela livre, o GNSS ainda rastreia só **20% do
   tempo**. As duas políticas de economia fazem o **mesmo** ciclo; o que muda é a agressividade
   com que ele entra. Só afeta o modo contínuo.
3. **O download atropela a agenda.** Quando falta efeméride ou almanaque, o download programado
   ignora o intervalo e as tentativas configurados, e empurra a tentativa seguinte. Sem ele, o
   receptor nunca recebe certas correções, entre elas as ionosféricas.

**Por que os blocos NÃO são proporcionais ao tempo.** TAU de 8 horas e tempo ativo de 6 segundos
diferem por mais de três ordens de grandeza; numa régua proporcional o bloco ativo sumiria. Os
blocos têm largura fixa, cada número real está escrito dentro do bloco, e **o subtítulo avisa
que é impossível desenhar na mesma régua**. A alternativa esconderia o tempo ativo, que seria
mentira por omissão visual.

**Os únicos números com fonte aqui são três:** 20% de rastreio, TAU de 8 h, tempo ativo de 6 s.

Vale a citação textual da especificação do produto: "GPS receiver operation is time multiplexed
with the LTE modem". É a tese da seção 7.3 na fonte primária.

#### D7 — A montagem

Fluxo horizontal. Antena A, da base, ligada ao EVK que faz Survey-In uma vez e é gravado em modo
fixo na flash. Dele sai RTCM3 por serial para o notebook que roda o caster. Do caster sai uma
seta rotulada **rede local, sem internet** até o ponto de medida.

No ponto de medida, a antena B se ramifica para o nRF9151, que é o degrau 1, ou para o EVK rover,
que são os degraus 2 e 3, com o rótulo **um de cada vez**.

**Aviso obrigatório no rodapé:** 3 V do lado da placa Nordic contra 3,3 V do lado do EVK, e a
troca de cabo é sempre com o receptor desenergizado.

**Nenhuma distância numérica.** A separação entre as duas antenas é "alguns metros", como em
§3.1, e é essa frase que vai na figura.

---

**Honestidade nas sete.** D1, D5, D6 e D7 são esquemáticos de mecanismo e **não alegam escala
numérica**. D3 e D4 têm eixo numérico e **só usam número com fonte**, com as condições no
subtítulo. Nenhuma pode sugerir que os regimes não testados foram medidos aqui.

## 8. NTN

Fica em `comms/ntn_nbiot/`, **fora do bloco de 2 horas**, como roteiro entregue.

Verificado no NCS v3.4.0:

- A biblioteca existe: `CONFIG_NTN`, `include/modem/ntn.h`, `lib/ntn/`, doc em
  `libraries/modem/ntn.rst`. O único sample que a usa é o `modem_shell`, pelo comando `ntn`.
- **Exige o firmware de modem `mfw_nrf9151-ntn`.** É troca de firmware de modem, não Kconfig.
- **O GNSS interno não funciona com NTN NB-IoT no system mode.** A doc manda parar o GNSS e só
  então habilitar o NTN. GNSS e NTN nunca rodam no mesmo firmware.
- A biblioteca monitora pedidos de atualização de localização do modem, por `AT%LOCATION`, e a
  aplicação responde com a posição corrente e um tempo de validade. A frequência necessária
  depende da velocidade máxima do dispositivo.
- A Nordic recomenda explicitamente a **SMA DK** para desenvolvimento de NTN.

Motivos de ficar fora do bloco: troca de firmware de modem no meio da aula, dependência de SIM
habilitada, e dependência de janela de passada.

## 9. Pendências

Itens sem resposta, todos marcados no texto:

1. Uma instância do u-center 2 com dois receptores, ou duas instâncias na mesma máquina.
2. ~~Versão do firmware do modem nas SMA DK.~~ **Fechada em 2026-09-08, lida na bancada por
   `AT+CGMR`: `mfw_nrf91x1_2.0.4`**, que é o firmware padrão, **não** o de NTN. Confirma §8: NTN
   exige troca de firmware de modem. Falta só a versão do firmware do X20P.
2b. Se o `mfw_nrf91x1_2.0.4` tem Galileo. As consultas AT não dizem; aparece na contagem de
    satélites do lab 1.
3. ~~Se o X20P realmente recusa RTCM 1004 e 1012 da estação AMUA0.~~ **Fechada por refutação.**
   A tabela de entrada do X20P inclui as mensagens legadas; o rover as decodifica. A afirmação
   original foi retirada — ver §2.7.1, e **não ressuscitar**.
4. Modelo, bandas e tipo da antena Kyocera que vem com a SMA DK.
5. Corrente máxima disponível no bias de 3 V do J2.
6. Desempenho da ANN-MB2 a 3 V.
7. Prazo e custo do acesso ao PointPerfect Flex pela aba EVK do u-center 2.
8. Prazo de liberação do cadastro no RBMC-IP.
8b. ~~Baseline entre o local do curso e a UEA.~~ **Fechada em 2026-09-08:** curso na SIDIA
    Amazon Tower, mesma avenida da estação, baseline da ordem de 1 km (§3.5).
9. Porta padrão do caster NTRIP do u-center 2.
10. Ponto de medida de corrente do SMA DK para o PPK2.
