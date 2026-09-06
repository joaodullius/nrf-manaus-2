# Wi-Fi 6+ — design da frente (dias 3–4)

**Data:** 2026-09-06
**Módulo:** `comms/` — Tecnologias de Comunicação Avançada
**SDK alvo:** nRF Connect SDK v3.4.0 (`C:\ncs\v3.4.0`)
**Hardware:** nRF54LM20-DK (variante **B**) + nRF7002-EB II (PCA63571)

## 1. Contexto e escopo

A súmula do treinamento promete, para Wi-Fi:

> **Wi-Fi 6+ para IoT** — integração com circuito companion, provisionamento, protocolos
> TCP/IP sobre Wi-Fi.
> **Exemplo prático:** provisionamento de dispositivo Wi-Fi 6+ e envio de dados via socket
> TCP/IP.

A frente ocupa **~3h** das 10h dos dias 3–4, dividindo o módulo com Channel Sounding (já
entregue, ~3h), GNSS e NTN. Decisões de escopo tomadas no brainstorming:

- **Cinco labs**, os quatro primeiros cobrindo a súmula inteira; o quinto entra conforme o
  tempo, como o CS 4 e o CS 5.
- **Nada depende da rede da sala.** A rede ainda não foi definida. O lab de provisionamento
  não precisa de AP nenhum (a DK *é* o AP) e os labs de transporte têm plano B com o PC
  conectado ao SoftAP da própria DK.
- **Provisionamento por SoftAP é o lab; por BLE é demo do instrutor** — mesmo padrão que o
  smartphone no Channel Sounding.
- **Três transportes, um payload.** TCP puro (o que a súmula pede literalmente), HTTP e MQTT
  sobre o mesmo firmware, com o transporte escolhido em Kconfig.
- **Sem integração com o microfone dos labs de Edge AI.** Impossível no mesmo kit (§2.3).
- **Sem coexistência BLE+Wi-Fi.** A súmula não promete, e é superfície de falha extra em
  sala. Fica anotado como extensão.

## 2. Estado da arte verificado

Conferido na árvore instalada e no MCP da Nordic, não de memória.

### 2.1 O par LM20-DK + EB II é alvo de primeira classe

O shield `nrf7002eb2` vive em `zephyr/boards/shields/nrf7002eb2/` e traz overlay para a
**variante B** (`boards/nrf54lm20dk_nrf54lm20b_cpuapp.overlay`), que é a dos nossos kits.

Ao contrário do `nrf54l15tag` no Channel Sounding — que não constava de nenhum
`platform_allow` —, aqui **16 samples de Wi-Fi citam o `nrf54lm20` no próprio
`sample.yaml`**, com `SHIELD="nrf7002eb2"`: `sta`, `shell`, `scan`, `softap`,
`provisioning/softap`, `throughput`, `twt`, `ble_coex`, entre outros. É combinação testada
pela CI da Nordic.

**Build de fumaça validado nesta bancada** (2026-09-06):

```
west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild nrf/samples/wifi/sta \
  -- -Dsta_SHIELD="nrf7002eb2" -Dsta_SNIPPET=nrf70-wifi
→ FLASH: 554.848 B / 2.036 KB (26,61%)   RAM: 188.672 B / 511 KB (36,06%)
```

A EB II encaixa no conector **P17 (Expansion)** do LM20-DK.

### 2.2 Blobs do nRF70 — pré-requisito que não é opcional

O driver do nRF7002 precisa de binários proprietários que **não vêm no clone do SDK**:

```bash
west blobs fetch nrf_wifi
```

Baixa cinco binários (`default`, `scan_only`, `radio_test`, `system_with_raw`,
`offloaded_raw_tx`) para `modules/lib/nrf_wifi/zephyr/blobs/`. Sem eles o CMake falha por
arquivo ausente.

**Verificado nesta bancada:** a instalação do NCS v3.4.0 feita pelo toolchain manager do nRF
Connect estava com **zero** blobs. Ou seja, **quem usa só VS Code também precisa rodar o
comando** — a extensão instala SDK e toolchain, mas não busca blobs. Documentado pela Nordic
em *nRF7002 EB II → Requirements → Prerequisites*. Registrado em `PREREQUISITOS.md` (commit
`09110ce`).

### 2.3 Três armadilhas do shield, verificadas no overlay

Todas custam tempo de aula se descobertas em sala:

**O console muda de porta.** O overlay do shield na v3.4.0 desabilita a `uart20` e move
console, shell e mcumgr para a `uart30`:

```dts
/* UART20 conflicts with EB-II shield; use UART30 */
&uart20 { status = "disabled"; };
chosen { zephyr,console = &uart30; ... };
```

Com a EB II acoplada, **o log sai em outra VCOM**. A documentação online "latest" afirma o
contrário para o LM20 (*"não é afetado, UART20 continua sendo o console"*) — descreve uma
versão diferente da que usamos. Item de validação em bancada (§8).

**O botão 4 some.** O mesmo overlay apaga o nó `button_3` e o alias `sw3`. Restam os botões
1–3 (`sw0`–`sw2`) e os quatro LEDs (P1.22/25/27/28, nenhum na lista da EB II).

**Microfone e companion não coexistem.** O `pdm20` do `edge_ai/07_ww_kws` usa `P1.04`
(PDM_CLK) e `P1.05` (PDM_DIN) — exatamente o **BUCKEN** (liga o regulador do nRF7002) e o
**IRQ** do companion. Não há remapeamento por software que resolva: o microfone teria de sair
do conector onde está montado. Os dois também disputam a `uart30`. **Consequência de projeto:
o gatilho do lab 9 é um botão, não um comando de voz.**

### 2.4 Provisionamento: o que o sample realmente faz

`nrf/samples/wifi/provisioning/` tem três variantes:

| Variante | Transporte | Uso no curso |
|---|---|---|
| `softap/` | SoftAP + **HTTPS na porta 443** + **protobuf** | **lab 8** |
| `ble/` | BLE + app nRF Wi-Fi Provisioner (Android/iOS) | demo do instrutor |
| `internal/` | nenhum — só decodifica e loga o protocolo | não usado |

**O SoftAP não é um formulário em navegador.** A DK sobe o AP `nrf-wifiprov` com servidor
DHCP e serve HTTPS com certificado próprio (`certs/` no sample), falando protobuf. Quem
provisiona é o script `scripts/provision.py` da Nordic:

1. o notebook conecta no AP da DK;
2. `protoc --proto_path=<nrf>/subsys/net/lib/softap_wifi_provision/proto --python_out=. common.proto`;
3. `python3 provision.py --certificate ../certs/server_certificate.pem`;
4. o script busca `/prov/networks`, lista **as redes que a DK enxergou** (SSID, RSSI, banda,
   canal, auth) e pede qual e a senha; escreve em `/prov/configure`.

É melhor didaticamente do que um formulário: o aluno vê o **dispositivo escaneando por ele** e
escolhe da lista que o dispositivo alcança. É o padrão do curso outra vez — o firmware fornece
os dados, o PC decide.

Custo: `protoc` e o pacote `protobuf` entram nos pré-requisitos (decisão do instrutor).

O `platform_allow` do `softap/` lista `nrf54lm20dk/nrf54lm20b/cpuapp`, mas `boards/` só tem
`.conf` da variante **A** — item de validação (§8).

### 2.5 Credenciais e transporte

`wifi/sta` recebe as credenciais **em tempo de build**:

```
CONFIG_WIFI_CREDENTIALS_STATIC_SSID="..."
CONFIG_WIFI_CREDENTIALS_STATIC_PASSWORD="..."
```

É o análogo exato do `meu_tag.conf` do Channel Sounding, e vira `minha_rede.conf` (§5.1).

Não existe sample de socket TCP em `nrf/samples/wifi`. O TCP vem do Zephyr
(`zephyr/samples/net/sockets/`) ou de `nrf/samples/net/`. O lab 9 é **código do curso**.

## 3. Abordagem

### 3.1 Um payload, três transportes

O curso já tem um movimento característico: **segurar o dado e variar a camada**. Foi assim no
CS 3 (mesma medida, RAS × IPT) e no CS 5 (mesmo IQ, quatro algoritmos). Os labs 9 e 10 repetem:
mesmo firmware, mesmo payload, transporte escolhido em Kconfig.

Isso torna a comparação honesta — bytes no fio, flash gasto, o que o outro lado precisa ter de
pé — e permite que o lab 10 fique como referência sem parecer incompleto.

### 3.2 O downlink é o que separa os protocolos

O dispositivo do lab 9 é um IoT completo em miniatura, com **três gestos**:

| Gesto | Direção | TCP puro | HTTP | MQTT |
|---|---|---|---|---|
| Telemetria periódica | ↑ | você enquadra | POST por amostra, cabeçalho a cada vez | `publish` |
| Botão pressionado | ↑ | mesmo socket | POST | `publish` |
| **PC acende o LED** | ↓ | mesmo socket, trivial | **incômodo** — request/response não empurra; vira polling | **`subscribe`** |

A última linha é o melhor argumento didático para a existência do MQTT, e **só existe se
houver downlink**. Sem o LED, os três protocolos parecem equivalentes e o aluno não entende a
escolha. Foi por isso que o botão e o LED entraram no desenho.

### 3.3 O payload não é o estado do link

Descartada a ideia inicial de enviar RSSI como espinha: mandar o estado do link pelo próprio
link é auto-referente — a telemetria degrada junto com o que ela mede, e no momento mais
interessante (o aluno se afasta até cair) não chega um RSSI baixo, chega **silêncio**.

O payload é uma linha JSON com:

| Campo | Origem | Por que |
|---|---|---|
| `seq` | contador | ensina perda e reconexão: o buraco na sequência é informação honesta sobre o link, obtida sem depender dele para se descrever |
| `uptime_ms` | `k_uptime_get()` | referência temporal |
| `temp_c` | `temp_sensor` do SoC (`&temp` já habilitado no LM20-DK) | grandeza física de verdade, independente do rádio; muda se o aluno encostar o dedo no chip |
| `rssi_dbm` | `net_mgmt` / `wifi status` | um campo entre outros, como um produto faz — não o ponto |
| `button` | evento do `sw0` | o gesto de uplink |

JSON de uma linha por amostra porque é o formato natural de HTTP e MQTT, e mantém **um só
payload** nos três transportes.

### 3.4 Tudo que vem de fora entra no repo, com fonte

Mesma convenção do Channel Sounding: cada lab é uma app freestanding em `comms/`, copiada do
SDK com cabeçalho `ORIGEM:` e cada divergência marcada `ALTERADO PELO CURSO (nrf-manaus-2)`.
Cópias de `LICENSE` junto. O `common_pb2.py` gerado pelo `protoc` **não** é versionado — o
aluno gera (decisão do instrutor: `protoc` nos pré-requisitos).

## 4. Os cinco labs

Numerados na sequência da aula, continuando o módulo (`06`–`10`, depois dos cinco de CS).

| # | Pasta | Base | Kit | Súmula |
|---|---|---|---|---|
| 6 | `06_wifi_shell/` | `nrf/samples/wifi/shell` | LM20-DK + EB II | circuito companion |
| 7 | `07_wifi_sta/` | `nrf/samples/wifi/sta` | idem | circuito companion |
| 8 | `08_wifi_provisioning/` | `nrf/samples/wifi/provisioning/softap` | idem + notebook | **provisionamento** |
| 9 | `09_wifi_tcp/` | código do curso, esqueleto do `sta` | idem + servidor no PC | **socket TCP/IP** |
| 10 | `10_wifi_http_mqtt/` | o mesmo do 9, transporte por Kconfig | idem + broker | bônus |

### 4.1 Lab 6 — o companion visível

O `shell` como veio. `wifi scan` acha as redes da sala, `wifi connect`, `wifi status`,
`net iface`. Vinte minutos.

É aqui que o aluno leva **de propósito** o susto do console em outra VCOM (§2.3), com o
professor junto — a mesma pedagogia do TAG no `DEBUG OUT` no CS 1. O README abre com esse
aviso.

Divergência do curso: nenhuma.

### 4.2 Lab 7 — associação programática

O `sta` com `minha_rede.conf`, fragmento rastreado e **vazio** no repo, que o aluno preenche
com o SSID e a senha da rede da sala — mesma mecânica e mesma justificativa do `meu_tag.conf`
(o build falha de propósito se ficar vazio).

O aluno observa os eventos de `net_mgmt` (conectado, IP obtido, desconectado) e o
comportamento de reconexão ao desligar o AP.

Divergência do curso: o `minha_rede.conf` e a falha de build proposital.

### 4.3 Lab 8 — provisionamento

O `provisioning/softap` como veio, com o roteiro de quatro passos do §2.4. O aluno vê a
**própria DK escaneando** e escolhe da lista.

**Demo do instrutor:** o mesmo por BLE (`provisioning/ble`) com o app nRF Wi-Fi Provisioner
no celular do instrutor — amarra com o BLE que a turma acabou de ver no Channel Sounding.

Divergência do curso: nenhuma no firmware; o README traz o roteiro do `protoc` e do script.

### 4.4 Lab 9 — o dispositivo IoT completo

**Código do curso**, com o esqueleto de conexão do `sta`. Três gestos (§3.2):

- telemetria periódica (payload do §3.3), intervalo em Kconfig;
- `sw0` pressionado → evento sobe na hora;
- comando do servidor → LED 1 acende/apaga.

No PC, `tools/wifi_server.py` — servidor TCP de ~40 linhas que imprime cada linha recebida e
aceita um comando de teclado para mandar o LED. Mesmo papel do `cs_capture.py`/`cs_dash.py`:
o aluno vê os dois lados.

**Plano B sem rede:** a DK em SoftAP e o PC conectado nela; o lab roda sem infraestrutura.

### 4.5 Lab 10 — o mesmo payload, outro transporte

`CONFIG_LAB_TRANSPORTE` escolhe `TCP` (default), `HTTP` ou `MQTT`. Mesmo payload, mesmos três
gestos. O aluno mede: bytes no fio, flash, e o que o outro lado exige.

O MQTT é o último da fila por logística: precisa de um broker (`mosquitto` no PC do
instrutor), que numa rede indefinida é mais uma peça para dar errado. Se a RAM não fechar
(§8), o MQTT fica como referência lida, não rodada.

## 5. Convenções transversais

### 5.1 `minha_rede.conf`

Um fragmento por aluno, rastreado e vazio no repo, com `CONFIG_WIFI_CREDENTIALS_STATIC_SSID`
e `..._PASSWORD`. Serve aos labs 7, 9 e 10. Nunca commitar credenciais reais — mesma regra do
`meu_tag.conf`.

### 5.2 Build

```
west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild \
  -- -D<app>_SHIELD="nrf7002eb2" -D<app>_SNIPPET=nrf70-wifi -DEXTRA_CONF_FILE=minha_rede.conf
```

No VS Code, shield e snippet vão em **Extra CMake arguments**. O `SHIELD` é escopado por
imagem no sysbuild (`<app>_SHIELD`), como nos `sample.yaml` da Nordic.

### 5.3 Console

Com a EB II acoplada, o console está na **`uart30`** (§2.3) — outra VCOM. Todo README abre
com esse aviso, e o `PREREQUISITOS.md` já o registra.

## 6. Bancada

- 6 × nRF54LM20-DK (variante B) + 6 × nRF7002-EB II, uma por aluno
- notebook do aluno: Python com `protobuf`, `protoc` no PATH
- PC do instrutor: `wifi_server.py`, e `mosquitto` se o lab 10 rodar
- rede da sala **a definir** — todos os labs têm plano B (§1)

## 7. Material

Deck **M2-04** (Wi-Fi), no mesmo toolkit dos M2-01/02/03: companion IC e o que o nRF7002 é,
os blobs, provisionamento, e a tabela dos três transportes (§3.2) com os números medidos.

## 8. Validação pendente

Nada aqui foi rodado em hardware ainda, além do build de fumaça do §2.1.

1. **Console na `uart30`** — a árvore diz que sim, a doc "latest" diz que não. Confirmar em
   qual VCOM sai o log com o shield acoplado.
2. **`provisioning/softap` na variante B** — `platform_allow` lista, mas `boards/` só tem
   `.conf` da variante A. Compila? Precisa de um `.conf` novo?
3. **Fluxo completo do `provision.py`** — `protoc`, certificado, `/prov/networks`,
   `/prov/configure`, e a DK associando depois.
4. **RAM com MQTT** — o `sta` sozinho já usa 36% de 511 KB. Medir os três transportes.
5. **Botões e LEDs com o shield** — confirmar `sw0`–`sw2` e os quatro LEDs; confirmar que
   `sw3` sumiu.
6. **Temperatura do die** — o sensor está habilitado no board; confirmar leitura plausível.
7. **Plano B em SoftAP** — o PC conectar no AP da DK e o TCP funcionar sem infraestrutura.

## 9. Fora de escopo

- **Coexistência BLE+Wi-Fi** (`ble_coex`, shield `nrf7002eb2_coex`): a súmula não promete e é
  risco extra em sala. Anotado como extensão no README do lab 10.
- **Gateway TAG → DK → nuvem**: exigiria a coexistência acima. Fica como extensão escrita.
- **Comando de voz como gatilho**: impossível no mesmo kit (§2.3).
- **TWT, throughput, raw TX, promiscuous, Wi-Fi locationing**: samples existem e são alvos do
  LM20, mas nada disso está na súmula e competem por tempo com GNSS e NTN.
- **Wi-Fi 6 "6+" como certificação**: o material trata do que o nRF7002 entrega (dual-band,
  TWT como recurso citado), sem entrar em certificação.
