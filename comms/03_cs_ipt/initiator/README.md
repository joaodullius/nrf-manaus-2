# Channel Sounding · Lab 3b — Initiator IPT: a mesma distância por outro caminho

Mesmo par do lab 2, mesma distância — o que muda é **por onde viaja** a contribuição
do reflector. No lab 2 (RAS) ela vem por GATT, pela conexão; aqui (IPT) ela vem
codificada na **fase do tom** que o reflector devolve. O initiator calcula sozinho,
dos seus próprios eventos de subevent, e nunca recebe medida crua do outro lado.

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ipt_initiator` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE). A
> divergência única do curso está marcada no cabeçalho de `src/main.c`.

## IPT não é step mode

Step mode é *o que se mede* num step (1 = RTT, 2 = PBR, 3 = os dois). IPT é uma
**flag ligada na criação da configuração de CS** — `CS configuration creation with
CS IPT enabled`, é o initiator quem liga — e atua sobre os tons de PBR (mode 2 e a
parte PBR do mode 3). Os dois eixos são independentes.

## O que comparar com o lab 2

| | Lab 2 — RAS | Lab 3 — IPT |
|---|---|---|
| Setup antes da 1ª medida | descoberta do Ranging Service + assinaturas | nenhum |
| Dado do reflector | por GATT (ACL) | dentro da fase do tom |
| O que o log imprime | `ifft`, `phase_slope`, **`rtt`** | `median`, `update`, `time_delta` |
| Abrange | RTT + PBR | **só PBR** |

A coluna `rtt` **sumiu**. Não é omissão do log: o IPT só existe no mundo do PBR. Se
você quiser RTT, precisa do RAS (ou equivalente) para trazer o tempo de volta pela
conexão. E `time_delta` é a latência entre estimativas, medida pelo próprio sample —
compare com a cadência do lab 2.

## Passo 1 — o TAG com o reflector IPT

Lab 3a: TAG no `DEBUG OUT`, grava, tira. É o mesmo TAG, o endereço não muda.

## Passo 2 — o endereço

O mesmo `meu_tag.conf` do lab 2 (e do Edge AI):

```
copy ..\..\02_cs_initiator\meu_tag.conf meu_tag.conf
```

## Passo 3 — compilar e gravar a DK

TAG fora do `DEBUG OUT`.

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/03_cs_ipt/initiator/build_lm20 C:/work/nrf-manaus-2/comms/03_cs_ipt/initiator -- -DEXTRA_CONF_FILE=meu_tag.conf
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/03_cs_ipt/initiator/build_lm20
```

## Passo 4 — ler e comparar

Serial USB da DK, 115200 8N1:

```
I: Filtrando pelo tag EC:EF:40:2D:5E:46 (random)
...
I: Distance estimates: median: 1.05m, update: 1.02m, time_delta: 44ms
```

Repita o experimento A do lab 2 (1 m, 3 m, 5 m) e anote `median` e `time_delta`. O
que ganhou (latência, setup) e o que perdeu (RTT) é o assunto do lab 4.

## Várias bancadas na mesma sala

O IPT roda uma procedure a cada ~30 ms por padrão (`time_delta` na bancada) — o mais
exigente dos labs para uma sala compartilhada. Seis pares medindo ao mesmo tempo não
é condição documentada pela Nordic. Se as medidas degradarem, escalone o intervalo de
procedure por estação:

```
-- -DEXTRA_CONF_FILE=meu_tag.conf -DCONFIG_LAB_PROCEDURE_INTERVAL=<67 + n*17>
```

com `n` = número da estação (0 a 5). O valor está em intervalos de conexão de 15 ms:
67 ≈ 1 s. Zero (default) mantém a escolha do sample. Plano B, se mesmo assim
degradar: duas ondas de três bancadas.

## As duas divergências do curso

1. **`src/main.c` — filtro por endereço.** O upstream filtra só pelo nome
   `Nordic CS IPT Reflector` em modo OR — e todos os TAGs da sala têm esse nome. Aqui
   `add_tag_address_filter()` acrescenta o endereço de `CONFIG_LAB_TAG_ADDR_VALUE` e
   `bt_scan_filter_enable()` passa a `match_all = true`.
2. **`src/main.c` — intervalo de procedure.** `CONFIG_LAB_PROCEDURE_INTERVAL`, quando
   diferente de 0, sobrescreve o intervalo escolhido pelo sample.

E `prj.conf` ganha `CONFIG_BT_SCAN_ADDRESS_CNT=1`, o slot do filtro.

## Pegadinhas

- **Não conecta.** O endereço em `meu_tag.conf` é o do **seu** TAG? A linha
  `Filtrando pelo tag ...` mostra o que o firmware está usando. Se o TAG estava
  conectado quando você regravou a DK, ele pode ter parado de anunciar: reset no
  TAG (ver pegadinhas do lab 1).

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ipt_initiator`
- Nordic, *Bluetooth: Channel Sounding Initiator with Inline PCT Transfer* — "How CS IPT works", "Benefits", "Drawbacks"
- Nordic, *LE Channel Sounding* (doc do SoftDevice Controller) — T_IP2_IPT e T_SW_IPT
