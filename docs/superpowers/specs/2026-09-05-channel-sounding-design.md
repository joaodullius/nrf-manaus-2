# Channel Sounding — design da frente (dias 3–4)

**Data:** 2026-09-05
**Módulo:** `comms/` — Tecnologias de Comunicação Avançada
**SDK alvo:** nRF Connect SDK v3.4.0 (`C:\ncs\v3.4.0`)

## 1. Contexto e escopo

O bloco de Channel Sounding ocupa **~3h** das 10h dos dias 3–4, dividindo o módulo com Wi-Fi 6+ e NTN. Decisões de escopo tomadas no brainstorming:

- **Labs 100% embarcados.** O par é nRF54LM20-DK (initiator) ↔ nRF54L15-TAG (reflector). Nada no caminho crítico do aluno depende de smartphone.
- **Smartphone (Galaxy S26) é demo do instrutor**, com plano de contingência (§7).
- **Quatro labs**: os três primeiros são o núcleo; o quarto (segurança) entra conforme o tempo do dia.
- **Sem lab de step modes.** RTT e PBR são apresentados na teoria, antes do lab 3.

## 2. Estado da arte verificado no SDK

Conferido na árvore instalada, não na documentação.

`nrf/samples/bluetooth/channel_sounding/` traz quatro samples:

| Sample | Papel |
|---|---|
| `ras_initiator` | Initiator + Ranging Requestor. Algoritmo `BT_CS_DE` embarcado (exige FPU) |
| `ras_reflector` | Reflector + Ranging Responder. Traz `android_ranging.conf` |
| `ipt_initiator` | Initiator com Inline PCT Transfer — **novo na v3.4.0** |
| `ipt_reflector` | Reflector com IPT — **novo na v3.4.0** |

`zephyr/samples/bluetooth/channel_sounding/` traz `cs_test` e `connected_cs`, mais crus, úteis como apoio de teoria.

**Board targets.** O `platform_allow` dos samples RAS e IPT inclui `nrf54lm20dk/nrf54lm20a/cpuapp` e `nrf54lm20dk/nrf54lm20b/cpuapp`. O board `nrf54l15tag` existe (`zephyr/boards/nordic/nrf54l15tag`, target `nrf54l15tag/nrf54l15/cpuapp`) mas **não** consta do `platform_allow` de nenhum dos quatro — isso é gate de CI/twister, não de build. A Nordic documenta `west build -b nrf54l15tag/nrf54l15/cpuapp` para o `ras_reflector`; para o `ipt_reflector` não há documentação equivalente (item de validação, §9).

**Precisão.** A Nordic declara que o algoritmo de referência dos samples "não é representativo" do que a tecnologia entrega. O material precisa dizer isso explicitamente, sob pena de o aluno concluir que Channel Sounding é impreciso.

### 2.1 RAS e IPT — dois caminhos para o mesmo número

São duas formas de o initiator obter a contribuição do reflector. A diferença é **por onde o dado viaja**.

**RAS (Ranging Service)** é um serviço GATT padronizado. O CS acontece no rádio, cada lado guarda suas medidas cruas, e o reflector as expõe como característica GATT. O initiator descobre o serviço, assina, busca os dados pela conexão ACL, junta com os seus e só então calcula. É o "CS default" da Nordic.

**IPT (Inline Phase Correction Term Transfer)** é uma **flag ligada na criação da configuração de CS** — não é um step mode. Explora a simetria dos tons de PBR: o reflector ajusta a fase do tom que devolve para casar com a que acabou de receber, de modo que a fase medida pelo initiator já carrega a contribuição do reflector somada ao trajeto de volta. O dado viaja **dentro do próprio tom de rádio**. O initiator calcula sozinho, a partir dos seus eventos de subevent, e nunca recebe medida crua do outro lado. Suporte no SoftDevice Controller desde a v3.3.1.

| | RAS | IPT |
|---|---|---|
| Dado do reflector viaja | por GATT (ACL) | dentro da fase do tom |
| Setup | descoberta + assinatura do serviço | nenhuma |
| Taxa de atualização | menor | maior |
| Latência medida → distância | maior | menor |
| RAM e consumo | buffer nos dois lados | sem buffer |
| Abrange | mode 1 (RTT), 2 (PBR), 3 | **só PBR** (mode 2 e a parte PBR do mode 3) |
| Segurança | RTT + PBR combinados | **menor** — o sample só roda mode 2 |

As duas últimas linhas vêm da doc da Nordic, que é explícita nos dois pontos: IPT só serve para PBR (o RTT de um step mode 3 ainda precisa de RAS ou equivalente para voltar pela ACL), e o sample de IPT "não oferece a mesma proteção contra ataques de ranging" que um arranjo RAS com mode 1 + mode 2. **Os labs 3 e 4 são os dois lados desse trade-off.**

## 3. Abordagem

**Cópias adaptadas em `comms/`**, seguindo a convenção já usada em `edge_ai/`: cada lab é uma aplicação freestanding própria (`CMakeLists.txt` + `prj.conf` + `README.md`), copiada do sample NCS correspondente, com licença Nordic preservada e as divergências do curso marcadas por comentário no cabeçalho — exatamente o padrão de `edge_ai/03_central_uart`.

Alternativas descartadas:

- *Só overlays sobre os samples in-tree*: quebra a convenção freestanding do repo, o aluno nunca abre o código e o comando de build passa a depender do caminho absoluto do SDK.
- *Labs autorais sobre `bt_le_cs_*`*: reinventa o `BT_CS_DE` e não cabe em 3h.

Empréstimo pontual da primeira: o ajuste do S26 fica num fragmento `.conf` separado, para não contaminar o build dos alunos.

## 4. Os quatro labs

| # | Lab | Board target | Base no SDK |
|---|---|---|---|
| 1 | `channel_sounding_reflector/` | `nrf54l15tag/nrf54l15/cpuapp` | `ras_reflector` |
| 2 | `channel_sounding_initiator/` | `nrf54lm20dk/nrf54lm20b/cpuapp` | `ras_initiator` |
| 3 | `channel_sounding_ipt_reflector/` + `channel_sounding_ipt_initiator/` | TAG + LM20-DK | `ipt_reflector` + `ipt_initiator` |
| 4 | segurança — sem firmware novo | par do lab 2 | `ras_*` |

**Lab 1 — reflector no TAG, CS default.** O dispositivo simples: anuncia o Ranging Service, acende o LED ao conectar. Sai obrigatoriamente com OTA DFU (§5.3) e com RTT (§5.2). É gravado **uma única vez por fio**, no início do bloco; daí em diante o TAG só recebe atualização por ar.

**Lab 2 — initiator no LM20-DK, CS default.** Fecha o par e imprime distância no terminal. Primeira medida real do bloco. O `ras_initiator` sai como vem do SDK: step mode 2 com submode 1 (PBR + RTT).

**Lab 3 — IPT.** Mesmo par, mesma distância — muda por onde viaja o dado do reflector. Atrito mínimo: o reflector IPT vai para o TAG **por OTA** (é aqui que o DFU do lab 1 é usado pela primeira vez), e o initiator IPT vai para o DK. O aluno compara com o lab 2: tempo até a primeira medida, taxa de atualização, e a ausência de tráfego GATT.

**Lab 4 — segurança (conforme o tempo).** Sem firmware novo: o TAG volta ao reflector RAS por OTA e o par do lab 2 é reexaminado com outros olhos. Conteúdo: a ACL cifrada como pré-requisito e o passo "CS security enabled" no log; o RTT com payload aleatório (o SDC suporta 32/64/96/128 bits) como limite físico contra falsificação de fase; o contraste com o IPT do lab 3 (PBR sozinho); e o que o SDC **não** suporta — RTT with Sounding Sequence, Normalized Attack Detection Metric, CS AM Attack Resilience — para o aluno não sair achando que tudo da spec está no chip. Gancho para o módulo do dia 5.

## 5. Convenções transversais

### 5.1 Casamento de ID do tag

Os dois initiators do SDK usam a mesma biblioteca `bt_scan` do `central_uart`, e ambos filtram de um jeito que **não** distingue estações:

| Sample | Filtro de fábrica | Modo |
|---|---|---|
| `ras_initiator` | `BT_SCAN_FILTER_TYPE_UUID` (Ranging Service) | `bt_scan_filter_enable(..., false)` → OR |
| `ipt_initiator` | `BT_SCAN_FILTER_TYPE_NAME` (`"Nordic CS IPT Reflector"`) | `bt_scan_filter_enable(..., false)` → OR |

Com seis TAGs na sala anunciando o mesmo UUID **e** o mesmo nome, cada DK conectaria no primeiro que aparecesse e as estações se cruzariam.

O filtro fica **só no initiator** (labs 2 e 3, no LM20-DK). O TAG não muda e não sabe de nada — ele anuncia igual para todos. A solução herda literalmente a convenção de `edge_ai/03_central_uart`, inclusive os nomes dos símbolos, para o aluno reconhecer no dia 3 o que já usou no dia 1:

- `CONFIG_LAB_TAG_ADDR_VALUE` (string, default `""`) e `CONFIG_LAB_TAG_ADDR_TYPE` (default `"random"`), num `menu "Lab: filtro do tag (nrf-manaus-2)"` no `Kconfig` dos dois initiators.
- Fragmento `meu_tag.conf`, aplicado com `-DEXTRA_CONF_FILE=meu_tag.conf`. Valor vazio **quebra o build de propósito**, com mensagem explicando por quê.
- Divergência no `main.c`: `add_tag_address_filter()` e troca do `bt_scan_filter_enable(..., false)` por `true` — modo **AND**, exigindo UUID (ou nome) **e** endereço.

**O aluno reaproveita o endereço do Edge AI.** É a mesma peça física. O host obtém o endereço estático do controller pelo comando HCI vendor-specific `Read_Static_Addresses` (`vs_read_static_addr` em `zephyr/subsys/bluetooth/host/id.c`) — ele não o inventa nem o lê do settings, então é estável por peça entre firmwares. A experiência dos labs do Edge AI confirma na prática. Basta **copiar o `meu_tag.conf` de `edge_ai/03_central_uart`** para os labs 2 e 3. Não há passo de descoberta.

### 5.2 RTT no TAG é a única saída de log

O board `nrf54l15tag` não declara `zephyr,console` nem `zephyr,shell-uart` em nenhum `chosen`, e `uart` não consta do `supported:` do `.yaml`. O `CONFIG_NCS_SAMPLES_DEFAULTS` usado pelos samples apenas faz `imply LOG` — não escolhe backend. Resultado: o sample compila limpo no TAG e **não imprime nada em lugar nenhum**.

Os dois firmwares de TAG (labs 1 e 3) saem com fragmento RTT explícito:

```
CONFIG_USE_SEGGER_RTT=y
CONFIG_LOG_BACKEND_RTT=y
CONFIG_LOG_BACKEND_UART=n
CONFIG_CONSOLE=y
CONFIG_RTT_CONSOLE=y
```

O README traz o comando de leitura por CLI, como já se faz na bancada. E registra o limite, que é conteúdo e não obstáculo: **RTT só existe com o TAG encaixado no `DEBUG OUT`**. Na CR2032 não há log — a evidência de vida passa a ser o LED e a saída do initiator. É a diferença entre bancada e campo.

### 5.3 OTA DFU no TAG é regra, não opção

Todo firmware de TAG (labs 1 e 3, e o da demo) sai com:

```
# prj.conf
CONFIG_BOOTLOADER_MCUBOOT=y
CONFIG_NCS_SAMPLE_MCUMGR_BT_OTA_DFU=y

# sysbuild.conf
SB_CONFIG_BOOTLOADER_MCUBOOT=y

# sysbuild/mcuboot.conf
CONFIG_FPROTECT_ALLOW_COMBINED_REGIONS=y
CONFIG_PM_PARTITION_SIZE_MCUBOOT=0xF800
```

Sem isso, um aluno que grave um binário errado deixa o TAG dependente de fio. A restrição de 62 kB na partição do MCUboot é exigência de FPROTECT documentada pela Nordic para este sample.

O bloco faz a ida e volta por OTA: RAS (lab 1) → IPT (lab 3) → RAS (lab 4). O DFU deixa de ser requisito e vira prática.

## 6. Bancada

Seis estações, cada uma com **1 nRF54LM20-DK + 1 nRF54L15-TAG** e dois alunos. Nenhum lab precisa de mais de um DK ou mais de um TAG, então as seis rodam em paralelo sem disputa.

O TAG é gravado por fio uma única vez (lab 1, encaixado no `DEBUG OUT` da DK) e depois só recebe OTA. Isso transforma a exigência de DFU em vantagem didática: o aluno vê o reflector virar um dispositivo de campo, alimentado por moeda, atualizável sem cabo.

**Risco de RF — não documentado, inferência nossa.** Seis pares fazendo Channel Sounding simultaneamente na mesma sala é uma condição que a Nordic não cobre. Mitigação: os initiators saem com intervalo de procedure escalonado por estação (estação *n*, de 0 a 5, usa `1000 + n×250` ms — de 1000 a 2250 ms), o que espalha as janelas e ainda vira assunto de aula sobre agendamento. Plano B, se degradar: rodar as medições em duas ondas de três estações.

## 7. Demo com o Galaxy S26

A demo roda num **TAG**, não num DK: bateria de moeda, na mão, é o que impressiona.

**Lado do firmware:** lab 1 + `android_ranging.conf` + fragmento `s26.conf` com `CONFIG_BT_CTLR_SDC_MAX_CONN_EVENT_LEN_DEFAULT=1250`, isolado para não tocar no build dos alunos. O `android_ranging.conf` liga `BT_BONDABLE`, `SETTINGS`, `NVS`, `FLASH_MAP` e sobe `BT_RAS_MAX_ANTENNA_PATHS` / `BT_CTLR_SDC_CS_MAX_ANTENNA_PATHS` para 2 — e precisa conviver com as partições do MCUboot no TAG.

O TAG da demo sai com `CONFIG_BT_DEVICE_NAME="CS Reflector DEMO"`, para não se perder no meio de seis `"Nordic CS Reflector"` idênticos na lista do app.

**Lado do telefone**, em ordem de custo:

1. nRF Toolbox de prateleira. Pode já funcionar; custa cinco minutos testar.
2. Fork do nRF Toolbox (open source, Kotlin, `ChannelSoundingManager.kt`) com `min_sub_event_len = 12000`, sideloaded. É a rota que a thread do DevZone valida. **Só dá para iterar com o S26 em mãos.**
3. Contingência: a demo vira o par embarcado projetado, e o S26 entra como estudo de caso — a thread, os dois gates, a `LL_CS_REQ` rejeitada.

**Por que o ajuste é necessário.** Conforme reportado em DevZone #128985 (lido da página, não do MCP da Nordic) e confirmado pelo cliente: o `ras_reflector` pristino falha com `0x1E` (`INVALID_LMP_OR_LL_PARAMETERS`) no `LE CS Procedure Enable`, embora pareamento, descoberta RAS, troca de capacidades e criação de config passem. Dois gates, ambos devolvendo 0x1E:

- **Gate A** — o telefone pede `Min_Subevent_Len` de 1250 µs (mínimo da spec) e o reflector rejeita a `LL_CS_REQ`.
- **Gate B** — o S26+ negocia os interlúdios máximos (T_IP1 = T_IP2 = 145 µs, T_FCS = 150 µs), gerando subevent de ~23 750 µs. Com `MAX_CONN_EVENT_LEN_DEFAULT=7500` e o intervalo de conexão de 30 ms do Android, o próprio SDC rejeita o agendamento localmente.

Os dois ajustes são necessários **em conjunto**; cada um isolado falha. Isso é coerente com a documentação de scheduling do SoftDevice Controller, que deriva o offset do CS justamente de `MAX_CONN_EVENT_LEN_DEFAULT` e informa que o CS foi testado sempre com o subevent **menor** que o intervalo ACL.

Status na Nordic: sem correção oficial e sem posicionamento sobre se o comportamento é esperado. Suporte documentado hoje cobre Pixel 9 e 10 (Android 16 QPR2+ / 17 Beta 4), nRF Toolbox ≥ 4.1.4. Samsung não aparece na documentação da Nordic.

**O bloco nunca fica refém do item 2.**

## 8. Material

Deck `doc/comms/M2-01_Channel_Sounding.pptx`, no padrão dos M1-xx: por que RSSI não serve para medir distância; o que BLE 6.0 traz; **RTT × PBR (antes do lab 3, porque o IPT só existe no mundo do PBR)**; a mecânica de initiator/reflector/subevent; o Ranging Service; RAS × IPT como trade-off; o mapa de suporte atual.

Duas figuras novas geradas em `doc/_template/`: a anatomia de um procedure CS e o comparativo RAS × IPT.

## 9. Validação pendente

Nada abaixo é dedução — tem que ir na bancada:

- [ ] Os quatro firmwares compilando nos seus board targets — em especial `ipt_reflector` no TAG, que a Nordic não documenta
- [ ] Um par real (LM20-DK ↔ TAG) medindo distância com RAS
- [ ] O mesmo par medindo com IPT
- [ ] RTT do TAG lendo por CLI
- [ ] OTA DFU no TAG: ida e volta RAS → IPT → RAS
- [ ] Filtro de endereço rejeitando o TAG do colega, nos dois initiators
- [ ] Comportamento com várias estações simultâneas
- [ ] S26: itens 1 e 2 da §7

## 10. Fora de escopo

- Lab de step modes (RTT × PBR × mode 3 exploratório) — fica na teoria
- Trilateração / multi-âncora
- Medição de consumo com PPK2
- Algoritmos de ranging de terceiros / parceiros da Nordic
