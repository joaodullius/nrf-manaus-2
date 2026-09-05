# Channel Sounding — design da frente (dias 3–4)

**Data:** 2026-09-05
**Módulo:** `comms/` — Tecnologias de Comunicação Avançada
**SDK alvo:** nRF Connect SDK v3.4.0 (`C:\ncs\v3.4.0`)

## 1. Contexto e escopo

O bloco de Channel Sounding ocupa **~3h** das 10h dos dias 3–4, dividindo o módulo com Wi-Fi 6+ e NTN. Decisões de escopo tomadas no brainstorming:

- **Labs 100% embarcados.** O par é nRF54LM20-DK (initiator) ↔ nRF54L15-TAG (reflector). Nada no caminho crítico do aluno depende de smartphone.
- **Smartphone (Galaxy S26) é demo do instrutor**, com plano de contingência (§7).
- **Cinco labs**: os três primeiros são o núcleo; segurança (4) e melhoria do ranging (5) entram conforme o tempo do dia.
- **Sem lab de step modes.** RTT e PBR são apresentados na teoria e observados na prática no lab 2, sem firmware dedicado.
- **Sem DFU/OTA.** Já foi coberto no treinamento anterior (Sidia) e não é essencial ao CS. O TAG é gravado por fio (§5.3).

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

**Board targets.** O `platform_allow` dos samples RAS e IPT inclui `nrf54lm20dk/nrf54lm20a/cpuapp` e `nrf54lm20dk/nrf54lm20b/cpuapp`. O board `nrf54l15tag` existe (`zephyr/boards/nordic/nrf54l15tag`, target `nrf54l15tag/nrf54l15/cpuapp`) mas **não** consta do `platform_allow` de nenhum dos quatro — isso é gate de CI/twister, não de build. A Nordic documenta `west build -b nrf54l15tag/nrf54l15/cpuapp` para o `ras_reflector`; para o `ipt_reflector` não há documentação equivalente (item de validação, §9). A Nordic distribui `boards/nrf54l15tag_nrf54l15_cpuapp.{conf,overlay}` (as duas antenas extras e o antenna switch do TAG) nos quatro samples — é esse par de arquivos que os labs de TAG (1 e 3a) copiam para dentro de `boards/`.

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

### 2.2 O algoritmo de referência e o que existe fora

**Posição da Nordic, validada no MCP.** O `cs_de` é referência, não produto: *"provided just as reference algorithms — we recommend you to work with a third party algorithm partner if you require more sophisticated algorithms"* (webinar *From theory to practice*), *"the accuracy is not representative for Channel Sounding and should be replaced if accuracy is important"* (release notes 2.9.0), *"an open and free-to-use IFFT algorithm suitable for simple ranging use cases"* (página de produto). O Kconfig marca `BT_CS_DE` como `[EXPERIMENTAL]`; no DevZone #128575 a resposta oficial a um usuário insatisfeito com a precisão foi que o roadmap só se discute com vendas. Parceiro de algoritmo citado nominalmente no webinar: Metirionic.

**A nuance que viabiliza o lab 5:** a Nordic não fornece o algoritmo preciso, mas **fornece o de referência em fonte**. `subsys/bluetooth/cs_de/cs_de.c`, 328 linhas, três funções — `cs_de_rtt()`, `cs_de_phase_slope()`, `cs_de_ifft()` — sob a licença Nordic 5-Clause, que permite uso *"with or without modification"* desde que em silício Nordic. O aluno lê inteiro.

**Fora da Nordic:**

| Fonte | O que é | Uso no curso |
|---|---|---|
| `skig/waves` (github.com/skig/waves) | MIT. Firmware initiator/reflector para nRF54L15 DK (NCS 3.2.2) + toolset Python com `cs_music.py`, `cs_ifft.py`, `cs_phase_slope.py`, `cs_amplitude_response.py` | **O Python, vendorizado no lab 5.** O firmware não: é mode 2 puro sem RAS, NCS antigo, e imprime hexdump cru |
| Zephyr `connected_cs` | Apache-2.0, estimador básico | Mesma classe do `cs_de`; sem ganho |
| `mintisan/awesome-channel-sounding` | Lista curada | Só links, nenhum código de algoritmo |
| arXiv 2608.17497 *Channel Modeling for Phase-Based Ranging* | Simulador Python da camada física do CS (mode 3, 72 tons, multipath) | Material de slide |

O `cs_music.py` do waves: 70 linhas, só NumPy. Entrada: fase e amplitude por canal. MUSIC com spatial smoothing, uma fonte dominante, grade de 512 pontos de 0 a 500 ns, devolve a distância do pico do pseudo-espectro. Sem calibração.

A literatura (blog do Bluetooth SIG, *A step towards 10-cm ranging accuracy*) fala em super-resolução (MUSIC/ESPRIT) chegando a ~λ/10 contra ~1,9 m de resolução bruta do IFFT sobre 79 MHz. **Número não verificado por nós** — é o que o lab 5 mede.

## 3. Abordagem

**Cópias adaptadas em `comms/`**, seguindo a convenção já usada em `edge_ai/`: cada lab é uma aplicação freestanding própria (`CMakeLists.txt` + `prj.conf` + `README.md`), copiada do sample NCS correspondente, com licença Nordic preservada e as divergências do curso marcadas por comentário no cabeçalho — exatamente o padrão de `edge_ai/03_central_uart`.

Alternativas descartadas:

- *Só overlays sobre os samples in-tree*: quebra a convenção freestanding do repo, o aluno nunca abre o código e o comando de build passa a depender do caminho absoluto do SDK.
- *Labs autorais sobre `bt_le_cs_*`*: reinventa o `BT_CS_DE` e não cabe em 3h.

Empréstimo pontual da primeira: o ajuste do S26 fica num fragmento `.conf` separado, para não contaminar o build dos alunos.

### 3.1 Tudo que vem de fora entra no repo, com fonte

Regra geral do curso, estendida para além dos samples Nordic: **nenhum lab depende de download externo em sala**. Todo código de terceiros é vendorizado na pasta do lab, com:

- o arquivo `LICENSE` original copiado ao lado;
- cabeçalho no arquivo com `ORIGEM:` — repositório, caminho, commit/tag ou data da cópia, licença — no mesmo formato do `src/main.c` do `03_central_uart`;
- as alterações do curso marcadas por comentário (`ALTERADO PELO CURSO (nrf-manaus-2)`), nunca silenciosas;
- o `README.md` do lab com uma seção **Fontes** listando repositórios, papers e páginas usados, com URL.

Isso cobre os samples do NCS (Nordic 5-Clause), o Python do waves (MIT) e qualquer figura ou trecho de paper que apareça no material.

## 4. Os cinco labs

| # | Lab | Board target | Base |
|---|---|---|---|
| 1 | `channel_sounding_reflector/` | `nrf54l15tag/nrf54l15/cpuapp` | `ras_reflector` |
| 2 | `channel_sounding_initiator/` | `nrf54lm20dk/nrf54lm20b/cpuapp` | `ras_initiator` |
| 3 | `channel_sounding_ipt_reflector/` + `channel_sounding_ipt_initiator/` | TAG + LM20-DK | `ipt_reflector` + `ipt_initiator` |
| 4 | segurança — sem firmware novo | par do lab 2 | `ras_*` |
| 5 | `channel_sounding_iq_music/` | LM20-DK + PC | lab 2 + Python (`cs_de` reimplementado, `cs_music.py` do waves) |

**Lab 1 — reflector no TAG, CS default.** O dispositivo simples: anuncia o Ranging Service, acende o LED ao conectar. Sai com RTT (§5.2). Gravado por fio no `DEBUG OUT` da DK (§5.3).

**Lab 2 — initiator no LM20-DK, CS default. É aqui que RTT e PBR aparecem na prática.** O `ras_initiator` sai como vem do SDK (step mode 2 com submode 1, PBR + RTT) e, a cada procedure, imprime três estimativas da **mesma** distância:

```
Latest distance estimates on antenna path 0: ifft: 2.31, phase_slope: 2.44, rtt: 2.70 meters
```

| Coluna | Princípio | Como estima (`cs_de.h`) |
|---|---|---|
| `ifft` | PBR | transformada inversa de Fourier sobre a fase por canal |
| `phase_slope` | PBR | inclinação média da fase em função da frequência |
| `rtt` | RTT | tempo de ida e volta |

Roteiro guiado no README, sem firmware novo: (1) trena — TAG a 1 m, 3 m, 5 m, anota as três colunas, qual acompanha, qual oscila; (2) obstrução — corpo entre TAG e DK, TAG perto de metal; o que a física prevê é que os estimadores de PBR reajam ao multipath e o RTT seja mais grosseiro mas não "salte" — a bancada confirma (§9). Variação opcional no README: o `choice` de Kconfig do sample permite build só-RTT (`SAMPLE_RAS_INITIATOR_STEP_MODE_1`) ou só-PBR (`_2`) via fragmento `.conf`, rebuild só da DK.

**Lab 3 — IPT.** Mesmo par, mesma distância — muda por onde viaja o dado do reflector. O TAG volta ao `DEBUG OUT` e recebe o reflector IPT por fio; a DK recebe o initiator IPT. O aluno compara com o lab 2: `time_delta` entre estimativas (latência), taxa de atualização, ausência de tráfego GATT — e **a coluna `rtt` que desapareceu**, porque o `ipt_initiator` imprime só `median`, `update` e `time_delta`. É "IPT só faz PBR" visto na tela.

**Lab 4 — segurança (conforme o tempo).** Sem firmware novo: o TAG volta ao reflector RAS por fio e o par do lab 2 é reexaminado com outros olhos. Conteúdo: a ACL cifrada como pré-requisito e o passo "CS security enabled" no log; o RTT com payload aleatório (o SDC suporta 32/64/96/128 bits) como limite físico contra falsificação de fase; o contraste com o IPT do lab 3 (PBR sozinho); e o que o SDC **não** suporta — RTT with Sounding Sequence, Normalized Attack Detection Metric, CS AM Attack Resilience — para o aluno não sair achando que tudo da spec está no chip. Gancho para o módulo do dia 5.

**Lab 5 — IQ para o PC e MUSIC (conforme o tempo).** Mesmo padrão pedagógico do `05_data_forwarder` do Edge AI: o firmware vira fonte de dados, a inteligência roda no PC.

- *Firmware*: o initiator do lab 2 mais ~20 linhas. Após o `cs_de_calc()`, imprimir na serial USB da DK uma linha CSV por procedure com canal, I/Q local e remoto, indicador de tone quality e as três estimativas do `cs_de`. Tudo já está em `m_cs_de_report.iq_tones[ap]`, a estrutura que o próprio sample monta. Nada de novo no rádio. Fica numa pasta própria para o lab 2 continuar limpo.
- *PC (Python, em `tools/`)*, em três passos com uma pergunta cada:
  1. Reimplementar o IFFT do `cs_de` em NumPy e **reproduzir o número que o firmware imprimiu**. *Entendi o que o chip faz?*
  2. Rodar o `cs_music.py` (vendorizado, MIT, com `ORIGEM:`) sobre o mesmo IQ. *O que a super-resolução muda?*
  3. Trena a 1/3/5 m e com obstrução; comparar IFFT × phase slope × RTT × MUSIC. *Quanto ganhei, e em que condição?*
- *O que fica*: o algoritmo é camada de aplicação; o mesmo IQ dá respostas diferentes; o ganho de precisão é medido, não prometido.
- *Caveats no README*: antena única (o TAG tem duas, o `cs_de` usa uma); MUSIC assumindo uma fonte, que sofre em multipath forte; ganho real sobre o IFFT desconhecido até a bancada; licenças não se misturam — MIT no PC, Nordic 5-Clause no firmware.

## 5. Convenções transversais

### 5.1 Casamento de ID do tag

Os dois initiators do SDK usam a mesma biblioteca `bt_scan` do `central_uart`, e ambos filtram de um jeito que **não** distingue estações:

| Sample | Filtro de fábrica | Modo |
|---|---|---|
| `ras_initiator` | `BT_SCAN_FILTER_TYPE_UUID` (Ranging Service) | `bt_scan_filter_enable(..., false)` → OR |
| `ipt_initiator` | `BT_SCAN_FILTER_TYPE_NAME` (`"Nordic CS IPT Reflector"`) | `bt_scan_filter_enable(..., false)` → OR |

Com seis TAGs na sala anunciando o mesmo UUID **e** o mesmo nome, cada DK conectaria no primeiro que aparecesse e as estações se cruzariam.

O filtro fica **só no initiator** (labs 2, 3 e 5, no LM20-DK). O TAG não muda e não sabe de nada — ele anuncia igual para todos. A solução herda literalmente a convenção de `edge_ai/03_central_uart`, inclusive os nomes dos símbolos, para o aluno reconhecer no dia 3 o que já usou no dia 1:

- `CONFIG_LAB_TAG_ADDR_VALUE` (string, default `""`) e `CONFIG_LAB_TAG_ADDR_TYPE` (default `"random"`), num `menu "Lab: filtro do tag (nrf-manaus-2)"` no `Kconfig` de cada initiator.
- Fragmento `meu_tag.conf`, aplicado com `-DEXTRA_CONF_FILE=meu_tag.conf`. Valor vazio **quebra o build de propósito**, com mensagem explicando por quê.
- Divergência no `main.c`: `add_tag_address_filter()` e troca do `bt_scan_filter_enable(..., false)` por `true` — modo **AND**, exigindo UUID (ou nome) **e** endereço.

**O aluno reaproveita o endereço do Edge AI.** É a mesma peça física. O host obtém o endereço estático do controller pelo comando HCI vendor-specific `Read_Static_Addresses` (`vs_read_static_addr` em `zephyr/subsys/bluetooth/host/id.c`) — ele não o inventa nem o lê do settings, então é estável por peça entre firmwares. A experiência dos labs do Edge AI confirma na prática. Basta **copiar o `meu_tag.conf` de `edge_ai/03_central_uart`** para os labs de initiator. Não há passo de descoberta.

### 5.2 RTT no TAG é a única saída de log

O board `nrf54l15tag` não declara `zephyr,console` nem `zephyr,shell-uart` em nenhum `chosen`, e `uart` não consta do `supported:` do `.yaml`. O `CONFIG_NCS_SAMPLES_DEFAULTS` usado pelos samples apenas faz `imply LOG` — não escolhe backend. Resultado: o sample compila limpo no TAG e **não imprime nada em lugar nenhum**.

Os dois firmwares de TAG (labs 1 e 3) saem com fragmento RTT explícito:

```
CONFIG_USE_SEGGER_RTT=y
CONFIG_CONSOLE=y
CONFIG_RTT_CONSOLE=y
CONFIG_SEGGER_RTT_BUFFER_SIZE_UP=4096
```

Os samples rodam em `LOG_MODE_MINIMAL` (via `NCS_SAMPLES_DEFAULTS`): o log é baseado em `printk`, e as linhas saem como `I: ...`, não no formato `<inf> módulo: mensagem` do log completo. O lab 5 força `LOG_MODE_DEFERRED` para separar o log (RTT) do CSV (UART) — é o único firmware do módulo que não roda em modo minimal.

O README traz o comando de leitura por CLI, como já se faz na bancada. E registra o limite, que é conteúdo e não obstáculo: **RTT só existe com o TAG encaixado no `DEBUG OUT`**. Na CR2032 não há log — a evidência de vida passa a ser o LED e a saída do initiator. É a diferença entre bancada e campo.

### 5.3 Gravação do TAG por fio, no `DEBUG OUT` da DK

Mesma mecânica do Edge AI, e a mesma armadilha: **enquanto o TAG está encaixado e alimentado, o debugger da DK aponta para ele, não para o SoC da DK**. Gravar "a DK" nessa hora grava o TAG. A ordem é sempre:

1. TAG no `DEBUG OUT` → grava o reflector, lê o RTT se precisar;
2. tira o TAG → ele segue na CR2032, anunciando;
3. grava o initiator no SoC da DK.

Acontece duas vezes no bloco (reflector RAS no lab 1, reflector IPT no lab 3, e de volta ao RAS se o lab 4 rodar). Sem MCUboot, sem partições, sem OTA.

## 6. Bancada

Seis estações, cada uma com **1 nRF54LM20-DK + 1 nRF54L15-TAG** e dois alunos. Nenhum lab precisa de mais de um DK ou mais de um TAG, então as seis rodam em paralelo sem disputa. O lab 5 precisa do PC com Python — já é pré-requisito do Edge AI.

**Risco de RF — não documentado, inferência nossa.** Seis pares fazendo Channel Sounding simultaneamente na mesma sala é uma condição que a Nordic não cobre. Os initiators dos labs 2 e 3b saem com `CONFIG_LAB_PROCEDURE_INTERVAL=0` (o default do sample) — o escalonamento por estação é **fallback**, não default, aplicado só se a sala degradar: lab 2 usa `50 + n×12` (unidades de 20 ms), lab 3b usa `67 + n×17` (unidades de 15 ms), ambos de ~1000 a ~2300 ms para as estações 0 a 5. Isso espalha as janelas e ainda vira assunto de aula sobre agendamento. Plano B, se mesmo assim degradar: rodar as medições em duas ondas de três estações. O lab 5 é o único que sai com o intervalo já forçado (`CONFIG_LAB_PROCEDURE_INTERVAL=50`, 1 procedure/s) — não por risco de RF, mas pela largura de banda da serial (§5.2 e o README do lab).

## 7. Demo com o Galaxy S26

A demo roda num **TAG**, não num DK: bateria de moeda, na mão, é o que impressiona.

**Lado do firmware:** lab 1 + `android_ranging.conf` + fragmento `s26.conf` com `CONFIG_BT_CTLR_SDC_MAX_CONN_EVENT_LEN_DEFAULT=1250`, isolado para não tocar no build dos alunos. O `android_ranging.conf` liga `BT_BONDABLE`, `SETTINGS`, `NVS`, `FLASH_MAP` e sobe `BT_RAS_MAX_ANTENNA_PATHS` / `BT_CTLR_SDC_CS_MAX_ANTENNA_PATHS` para 2.

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

Deck `doc/comms/M2-01_Channel_Sounding.pptx`, no padrão dos M1-xx: por que RSSI não serve para medir distância; o que BLE 6.0 traz; **RTT × PBR (antes do lab 2, que os mostra lado a lado, e do lab 3, porque o IPT só existe no mundo do PBR)**; a mecânica de initiator/reflector/subevent; o Ranging Service; RAS × IPT como trade-off; "o algoritmo é camada de aplicação" (a posição da Nordic, os parceiros, o que existe aberto); o mapa de suporte atual.

Figuras novas geradas em `doc/_template/`: a anatomia de um procedure CS; o comparativo RAS × IPT; e, para o lab 5, IFFT × MUSIC sobre o mesmo IQ.

## 9. Validação pendente

Nada abaixo é dedução — tem que ir na bancada:

- [ ] Os cinco firmwares compilando nos seus board targets — em especial `ipt_reflector` no TAG, que a Nordic não documenta
- [ ] Um par real (LM20-DK ↔ TAG) medindo distância com RAS: as três colunas aparecendo
- [ ] Lab 2: o comportamento dos três estimadores sob obstrução e perto de metal é o que a física prevê?
- [ ] O mesmo par medindo com IPT; `time_delta` menor que no RAS?
- [ ] RTT do TAG lendo por CLI
- [ ] Filtro de endereço rejeitando o TAG do colega, nos dois initiators
- [ ] Lab 5: o CSV sai íntegro na serial a 1 procedure/s; o IFFT em NumPy reproduz o número do firmware; o MUSIC ganha (ou não) sobre o IFFT — e quanto
- [ ] Comportamento com várias estações simultâneas
- [ ] S26: itens 1 e 2 da §7

## 10. Fora de escopo

- DFU/OTA no TAG — coberto no treinamento anterior (Sidia); o TAG é gravado por fio
- Lab de step modes (RTT × PBR × mode 3 exploratório) — RTT e PBR aparecem no lab 2
- Trilateração / multi-âncora
- Medição de consumo com PPK2
- Algoritmos de ranging de parceiros da Nordic (Metirionic etc.)
