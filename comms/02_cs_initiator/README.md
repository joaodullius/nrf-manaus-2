# Channel Sounding · Lab 2 — Initiator no nRF54LM20-DK: RTT e PBR lado a lado

Fecha o par com o TAG do lab 1 e imprime distância no terminal. É **aqui** que os dois
princípios físicos do Channel Sounding aparecem na prática — a cada procedure, o sample
imprime **três estimativas da mesma distância**:

```
Latest distance estimates on antenna path 0: ifft: 2.31, phase_slope: 2.44, rtt: 2.70 meters
```

| Coluna | Princípio | Como estima (`include/bluetooth/cs_de.h`) |
|---|---|---|
| `ifft` | **PBR** — fase | transformada inversa de Fourier sobre a fase por canal; o pico é o caminho mais curto |
| `phase_slope` | **PBR** — fase | inclinação média da fase em função da frequência |
| `rtt` | **RTT** — tempo | tempo de ida e volta médio dos steps de mode 1 |

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ras_initiator` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE). As duas
> divergências do curso estão marcadas no cabeçalho de `src/main.c`.

> **Precisão.** A própria Nordic classifica o algoritmo deste sample (`cs_de`, marcado
> `[EXPERIMENTAL]`) como referência: "*the accuracy is not representative for Channel
> Sounding and should be replaced if accuracy is important*". Os números que você vai
> ver são o que **um algoritmo simples** tira dos dados — não o teto da tecnologia. O
> lab 5 mostra o que muda com um algoritmo melhor.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54L15-TAG** | reflector do lab 1, **na bateria, fora do `DEBUG OUT`** |
| **nRF54LM20-DK** | roda este firmware; initiator, calcula e imprime |

## Passo 1 — o endereço do seu TAG

É o **mesmo do Edge AI**: o endereço BLE estático vem do próprio chip e não muda com
o firmware. Como no `edge_ai/03_central_uart`, o initiator **pede o endereço no
terminal serial a cada boot** — não é config de build, e o mesmo binário serve para
qualquer aluno. Se precisar reler: é a linha `Identity:` do boot do TAG, no RTT (lab 1).

## Passo 2 — compilar e gravar a DK

TAG **fora** do `DEBUG OUT` (senão o debugger grava o TAG). Confira com
`nrfutil device device-info`: tem que aparecer nRF54LM20.

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/02_cs_initiator/build_lm20 C:/work/nrf-manaus-2/comms/02_cs_initiator
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/02_cs_initiator/build_lm20
```

No VS Code: board target `nrf54lm20dk/nrf54lm20b/cpuapp`, sem fragmento.

## Passo 3 — responder o prompt e ler

Serial USB da DK, **115200 8N1**. A DK enumera duas portas COM; o log sai numa delas
(na bancada, a segunda). No boot o initiator pergunta o endereço e repete a pergunta a
cada 5 s até receber um válido — tanto faz abrir o terminal antes ou depois do reset:

```
Endereco BLE do tag (ex.: EC:EF:40:2D:5E:46 random): EC:EF:40:2D:5E:46
Procurando o tag EC:EF:40:2D:5E:46 (random)...
```

Aceita `EC:EF:40:2D:5E:46`, `... random` ou `... (random)`; sem o tipo, assume
`random`. Inválido é recusado e o prompt volta. Não existe valor padrão: um initiator sem
filtro conectaria no TAG do colega, e os seis TAGs da sala anunciam o mesmo UUID. Só
depois do `Procurando` o scan começa. Sequência esperada:

```
I: Filtrando pelo tag EC:EF:40:2D:5E:46 (random)
I: Connected ...
I: CS capability exchange completed.
I: CS config creation complete. ID: 0
I: CS security enabled.
I: CS procedures enabled.
I: Latest distance estimates on antenna path 0: ifft: 1.02, phase_slope: 1.11, rtt: 1.35 meters
I: Latest distance estimates on antenna path 0: ifft: 0.98, phase_slope: 1.09, rtt: 0.90 meters
```

## Passo 4 — o experimento: RTT × PBR

Sem recompilar nada. Trena na mão.

**A. Distâncias conhecidas.** TAG a 1 m, 3 m e 5 m da DK, linha de visada. Para cada
uma, anote dez linhas. Perguntas:

- Qual coluna acompanha a trena? Qual tem o menor espalhamento?
- `ifft` e `phase_slope` medem a **mesma fase** por métodos diferentes — quanto
  divergem entre si?
- `rtt` mede **tempo**. Um erro de 1 ns em tempo de voo são 30 cm. Qual a resolução
  que você vê nele?

**B. Obstrução e multipath.** TAG a 3 m: (1) corpo entre TAG e DK; (2) TAG encostado
numa superfície metálica. O que a física prevê: os estimadores de **fase** reagem ao
multipath (o sinal refletido soma-se ao direto e distorce a fase), o de **tempo** é
mais grosseiro mas não "salta". Confira se é isso que aparece — e anote onde não é.

**C. Registre.** Média e desvio das três colunas por condição. É o dado que o lab 5
vai revisitar com outro algoritmo.

## Variações (opcional)

O sample tem um `choice` de Kconfig para o step mode. Dois fragmentos deixam isolar
um princípio de cada vez — rebuild **só da DK**, o TAG não muda:

```
-- -DEXTRA_CONF_FILE=pbr_only.conf   # so mode 2: ifft e phase_slope
-- -DEXTRA_CONF_FILE=rtt_only.conf   # so mode 1: rtt
```

## Várias bancadas na mesma sala

Seis pares medindo ao mesmo tempo não é condição documentada pela Nordic. Se as medidas
degradarem, escalone o intervalo de procedure por estação:

```
-- -DCONFIG_LAB_PROCEDURE_INTERVAL=<50 + n*12>
```

com `n` = número da estação (0 a 5). O valor está em intervalos de conexão de 20 ms:
50 = 1 s. Zero (default) mantém a escolha do sample (100–200 ms).

## As duas divergências do curso

1. **`src/main.c` + `src/lab_tag_addr.c` — filtro por endereço.** O upstream filtra só
   pelo UUID do Ranging Service em modo OR. Aqui `lab_tag_addr_read()` lê o endereço
   digitado na serial (`uart_poll_in` na console, sem shell), `add_tag_address_filter()`
   o acrescenta ao scan e `bt_scan_filter_enable()` passa a `match_all = true`. Mesmo
   mecanismo do `edge_ai/03_central_uart`; o `lab_tag_addr.c` é copiado igual nos labs 3 e 5.
2. **`src/main.c` — intervalo de procedure.** `CONFIG_LAB_PROCEDURE_INTERVAL`, quando
   diferente de 0, sobrescreve o intervalo escolhido pelo sample.

E `prj.conf` ganha `CONFIG_BT_SCAN_ADDRESS_CNT=1`, o slot do filtro.

## Pegadinhas

- **Gravou o TAG achando que era a DK.** Com o TAG no `DEBUG OUT`, o `west flash` vai
  para o TAG. Tire-o antes.
- **Não conecta.** O endereço que você digitou é o do **seu** TAG? A linha
  `Filtrando pelo tag ...` mostra o que o firmware está usando; um reset na DK
  pergunta de novo. Se o TAG estava
  conectado quando você regravou a DK, ele pode ter parado de anunciar: reset no
  TAG (ver pegadinhas do lab 1).
- **Conectou e não mede.** Um segundo initiator (outra DK, um telefone) já pegou o
  TAG — ele só aceita uma conexão. Desligue o outro; `nrfutil device recover` numa DK
  esquecida com firmware antigo.

## Configuração de stack e otimização de pacotes

Tudo isto já vem no `prj.conf` (é o do sample da Nordic). Vale saber o que é e por
que está lá, porque é o que muda quando o produto tem outro telefone, outra antena
ou outro ritmo:

| Ajuste | Valor | Por quê |
|---|---|---|
| `CONFIG_BT_L2CAP_TX_MTU` | 498 | o Ranging Data de um procedure tem ~512 B por lado; o Ranging Profile pede MTU ≥ 247 |
| `CONFIG_BT_BUF_ACL_TX_SIZE` / `_RX_SIZE` | 502 | buffer ACL acima da MTU, senão o L2CAP fragmenta |
| `CONFIG_BT_CTLR_DATA_LENGTH_MAX` | 251 | Data Length Extension: 251 B por PDU em vez de 27 — uma notificação de Ranging Data em 1–2 PDUs em vez de 10 |
| `CONFIG_BT_ATT_PREPARE_COUNT` | 3 | escritas longas no RAS Control Point |
| `CONFIG_BT_RAS_MAX_ANTENNA_PATHS` | 1 aqui, 2 no lab 5 | dimensiona o buffer de Ranging Data por caminho de antena |
| `CONFIG_BT_CTLR_SDC_MAX_CONN_EVENT_LEN_DEFAULT` | 1250, só em `s26.conf` do lab 1 | evento de conexão maior para o Galaxy S26 conseguir negociar o procedure (sem isso, `0x1E`) |
| `CONFIG_LAB_PROCEDURE_INTERVAL` | 0 (default do sample) | intervalo entre procedures em intervalos de conexão; 50 no lab 5 (1/s), 25 na demo (2/s), `50 + n×12` para escalonar seis bancadas |

O log do initiator mostra a MTU negociada logo no início (`MTU exchange success`).
O sample lê as **RAS Features** do reflector e escolhe o fluxo: se o reflector
anunciar *real-time ranging data*, assina a característica `0x2C15` e recebe o dado
assim que o procedure termina; se não, assina *Ranging Data Ready* e busca cada
procedure pelo *Control Point* — é o caso desta bancada, e é por isso que o
intervalo do sample cai para 10 (200 ms) em vez de 5 (100 ms). O lab 3 mostra a
otimização definitiva: com IPT o dado do reflector nem sai do rádio.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ras_initiator` e
  `subsys/bluetooth/cs_de/cs_de.c` (os três estimadores, em fonte)
- Nordic, *Bluetooth Channel Sounding Distance Estimation* (doc da biblioteca `cs_de`)
- Nordic, release notes do nRF Connect SDK v2.9.0 — a nota sobre a precisão do sample
- Nordic, webinar *Bluetooth Channel Sounding: From theory to practice on the nRF54L Series and Android*
