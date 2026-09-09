# Referência: configurar e conferir o ZED-X20P

Tudo aqui foi **extraído dos PDFs oficiais da u-blox** e conferido no texto, não de memória:

- *ZED-X20P Integration Manual*, UBXDOC-963802114-12901 R05
- *u-blox X20 HPG 2.10 Interface description*, UBXDOC-304424225-21263 R02

## O plano de sinal é o que decide, não chave por chave

`CFG-SIGNAL-PLAN` (`0x2031003a`, tipo U1) escolhe o conjunto inteiro:

| plano | valor | GPS | Galileo | GLONASS | BeiDou | nota da u-blox |
|---|---|---|---|---|---|---|
| SP1 | 1 | L1C/A L2C L5 | E1B/C E5a E6 | **nenhum** | B1I B1C B2a B3I | *"not suitable as the default configuration"* |
| **SP2** | **2** | L1C/A L2C L5 | E1B/C E5a E6 | **L1OF L2OF** | B1C B2a B3I | **"Default and recommended"** |
| SP6 | 6 | L1C/A L2C L5 | E1B/C E5a (**sem E6**) | L1OF L2OF | B1I B1C B2a | só com PointPerfect Flex sobre IP com SPARTN |

Em todos os planos, QZSS traz L1C/A L1C/B L2C L5 L1S; NavIC traz L5; SBAS traz L1C/A.

**Para "todas as constelações", o alvo é SP2.** O SP1 não tem GLONASS nenhum.

### O que o padrão NÃO entrega

- **QZSS vem desabilitado em todos os planos.** E só pode ser habilitado se o GPS estiver
  selecionado.
- **NavIC vem desabilitado em todos os planos.**
- **GLONASS tem restrição geográfica** ("generally available, restricted in some geographical
  areas").
- Com SP6, para usar dado de navegação B1I é preciso `CFG-BDS-D1D2_NAVDATA = 1`.

## Regras que fazem o receptor recusar a configuração

- **L1 é sempre obrigatória**, em qualquer constelação.
- Uma constelação só conta como habilitada se a chave da constelação **e pelo menos uma
  banda** estiverem ligadas.
- SBAS só pode ser habilitado junto de pelo menos um entre GPS, Galileo e BeiDou.
- Combinação inválida volta como **`UBX-ACK-NAK`**, mais o aviso `"inv sig cfg"` no
  `UBX-INF` e no `NMEA-TXT`.

## A armadilha do GPS L5

**O GPS L5 é pré-operacional e os satélites o marcam como não-saudável.** A banda pode estar
habilitada e o sinal não ser usado. A u-blox dá as strings para sobrepor a saúde do L5 pela
do L1 (chave `0x10320001`):

```
RAM    B5 62 06 8A 09 00 01 01 00 00 01 00 32 10 01 DF F6
BBR    B5 62 06 8A 09 00 01 02 00 00 01 00 32 10 01 E0 FE
FLASH  B5 62 06 8A 09 00 01 04 00 00 01 00 32 10 01 E2 0E
```

Para reverter, as mesmas com o valor `00` no lugar do `01` (Tabela 9 do manual).

**Isso é conteúdo de aula:** uma banda habilitada não é uma banda usada.

## VALGET exploratório

Lê as 29 chaves de `CFG-SIGNAL` de uma vez. Mandar **as duas** e comparar: a primeira diz o
que está valendo, a segunda diz o padrão de fábrica — a diferença é o que alguém mudou.

**Camada 0, RAM (o que está valendo):**

```
B5 62 06 8B 78 00 00 00 00 00 3A 00 31 20 1F 00 31 10 01 00 31 10 03 00
31 10 04 00 31 10 21 00 31 10 07 00 31 10 09 00 31 10 0A 00 31 10 0B 00
31 10 22 00 31 10 0D 00 31 10 0F 00 31 10 0E 00 31 10 28 00 31 10 10 00
31 10 25 00 31 10 18 00 31 10 1A 00 31 10 24 00 31 10 12 00 31 10 39 00
31 10 14 00 31 10 15 00 31 10 17 00 31 10 26 00 31 10 1D 00 31 10 20 00
31 10 05 00 31 10 0F 97
```

**Camada 7, Default (o padrão de fábrica):**

```
B5 62 06 8B 78 00 00 07 00 00 3A 00 31 20 1F 00 31 10 01 00 31 10 03 00
31 10 04 00 31 10 21 00 31 10 07 00 31 10 09 00 31 10 0A 00 31 10 0B 00
31 10 22 00 31 10 0D 00 31 10 0F 00 31 10 0E 00 31 10 28 00 31 10 10 00
31 10 25 00 31 10 18 00 31 10 1A 00 31 10 24 00 31 10 12 00 31 10 39 00
31 10 14 00 31 10 15 00 31 10 17 00 31 10 26 00 31 10 1D 00 31 10 20 00
31 10 05 00 31 10 16 D8
```

## Partida a frio, para medir TTFF

`UBX-CFG-RST` com `navBbrMask = 0xFFFF` (apaga tudo) e `resetMode = 0x02` (reset controlado,
só do GNSS):

```
B5 62 06 04 04 00 FF FF 02 00 0E 61
```

Máscaras alternativas: `0x0000` partida quente, `0x0001` partida morna.

**Não espere `ACK`:** o documento avisa que versões novas de firmware não confirmam essa
mensagem, e as antigas podem não terminar de confirmar antes do reset.

## As 29 chaves de CFG-SIGNAL, com ID

| chave | ID | tipo |
|---|---|---|
| CFG-SIGNAL-PLAN | 0x2031003a | U1 |
| CFG-SIGNAL-GPS_ENA | 0x1031001f | L |
| CFG-SIGNAL-GPS_L1CA_ENA | 0x10310001 | L |
| CFG-SIGNAL-GPS_L2C_ENA | 0x10310003 | L |
| CFG-SIGNAL-GPS_L5_ENA | 0x10310004 | L |
| CFG-SIGNAL-GAL_ENA | 0x10310021 | L |
| CFG-SIGNAL-GAL_E1_ENA | 0x10310007 | L |
| CFG-SIGNAL-GAL_E5A_ENA | 0x10310009 | L |
| CFG-SIGNAL-GAL_E5B_ENA | 0x1031000a | L |
| CFG-SIGNAL-GAL_E6_ENA | 0x1031000b | L |
| CFG-SIGNAL-BDS_ENA | 0x10310022 | L |
| CFG-SIGNAL-BDS_B1_ENA | 0x1031000d | L |
| CFG-SIGNAL-BDS_B1C_ENA | 0x1031000f | L |
| CFG-SIGNAL-BDS_B2_ENA | 0x1031000e | L |
| CFG-SIGNAL-BDS_B2A_ENA | 0x10310028 | L |
| CFG-SIGNAL-BDS_B3_ENA | 0x10310010 | L |
| CFG-SIGNAL-GLO_ENA | 0x10310025 | L |
| CFG-SIGNAL-GLO_L1_ENA | 0x10310018 | L |
| CFG-SIGNAL-GLO_L2_ENA | 0x1031001a | L |
| CFG-SIGNAL-QZSS_ENA | 0x10310024 | L |
| CFG-SIGNAL-QZSS_L1CA_ENA | 0x10310012 | L |
| CFG-SIGNAL-QZSS_L1CB_ENA | 0x10310039 | L |
| CFG-SIGNAL-QZSS_L1S_ENA | 0x10310014 | L |
| CFG-SIGNAL-QZSS_L2C_ENA | 0x10310015 | L |
| CFG-SIGNAL-QZSS_L5_ENA | 0x10310017 | L |
| CFG-SIGNAL-NAVIC_ENA | 0x10310026 | L |
| CFG-SIGNAL-NAVIC_L5_ENA | 0x1031001d | L |
| CFG-SIGNAL-SBAS_ENA | 0x10310020 | L |
| CFG-SIGNAL-SBAS_L1CA_ENA | 0x10310005 | L |

`L` e booleano de um byte; `U1` e inteiro sem sinal de um byte. Isso importa ao montar um
`VALSET`: o tamanho do valor vem do tipo, e o tipo esta no proprio ID.

**Nao existem** `GLO_L4`, `GLO_L6`, `QZSS_L9`, `QZSS_L6` nem `BDS_B5`. Elas aparecem em
resumos automaticos desses PDFs e **nao estao no documento** — conferido chave por chave.
