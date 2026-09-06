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

A frente divide as 10h dos dias 3–4 com Channel Sounding (já entregue, ~3h), GNSS e NTN.

**O tamanho final é decisão do instrutor, tomada depois da bancada.** Os oito labs serão
escritos e medidos; o corte acontece com tempo real na mão, não com estimativa. Somados dão
~5h contra as ~3h que caberiam à frente hoje — logo, alguma coisa sai, e a spec não decide o
quê. Cada lab traz seu tempo medido em §4 quando a validação (§8) fechar.

Decisões de escopo tomadas no brainstorming:

- **Oito labs.** Os quatro primeiros cobrem a súmula; os quatro seguintes cobrem TWT,
  coexistência e locationing, que o instrutor classificou como importantes, mais o transporte
  alternativo.
- **Nada depende da rede da sala.** A rede ainda não foi definida. O lab de provisionamento
  não precisa de AP nenhum (a DK *é* o AP) e os labs de transporte têm plano B com o PC
  conectado ao SoftAP da própria DK.
- **Provisionamento por SoftAP é o lab; por BLE é demo do instrutor** — mesmo padrão que o
  smartphone no Channel Sounding.
- **Três transportes, um payload.** TCP puro (o que a súmula pede literalmente), HTTP e MQTT
  sobre o mesmo firmware, com o transporte escolhido em Kconfig.
- **Sem integração com o microfone dos labs de Edge AI.** Impossível no mesmo kit (§2.3).
- **Coexistência BLE+Wi-Fi, TWT e locationing entram** por decisão do instrutor, embora a
  súmula não os prometa. São o que diferencia Wi-Fi 6 de "Wi-Fi que já existia".

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

**O console muda de porta — e de VCOM.** O overlay do shield na v3.4.0 desabilita a `uart20`
e move console, shell e mcumgr para a `uart30`:

```dts
/* UART20 conflicts with EB-II shield; use UART30 */
&uart20 { status = "disabled"; };
chosen { zephyr,console = &uart30; ... };
```

**Medido na bancada (2026-09-06), nas duas condições e no mesmo kit:**

| Firmware | Console em | VCOM | Observado |
|---|---|---|---|
| lab de Channel Sounding (sem shield) | `uart20` (P1.16/P1.17) | segunda | boot banner sai aqui |
| lab 6 de Wi-Fi (com `nrf7002eb2`) | `uart30` (P0.06/P0.07) | primeira | prompt sai aqui |

Em cada caso a outra porta fica muda. O `device list` da imagem com shield mostra só a
`uart30` — a `uart20` some. **A VCOM muda.**

**Por que a doc online "latest" afirma o contrário.** O reroteamento é um contorno para um
conflito de pinos que existe apenas no kit **pré-produção** do LM20-DK. Em versões de Zephyr
posteriores à nossa o shield deixa de reroteiar nessa placa: o console volta para a `uart20`
(segunda VCOM) e o `sw3` deixa de ser apagado. A doc "latest" descreve esse comportamento
novo; a v3.4.0 do curso ainda tem o antigo. Não é contradição, é versão.

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

### 2.5 TWT, coexistência e locationing — os três que o instrutor pediu

**TWT (Target Wake Time)** — `nrf/samples/wifi/twt`, com `nrf54lm20dk/nrf54lm20b/cpuapp` e
`twt_SHIELD="nrf7002eb2"` no `sample.yaml`. Estabelece um fluxo TWT com o AP e usa um gerador
de tráfego para medir. É *o* recurso de Wi-Fi 6 para IoT: o dispositivo combina com o AP
quando vai acordar, e dorme o resto.

**Requisito duro:** exige um **AP que suporte TWT** — Wi-Fi 6 com o recurso habilitado.
Hotspot de celular e roteador comum não negociam. Este é o único lab da frente **sem plano B**
(§3.5), e o único que obriga a decidir a rede da sala.

**Coexistência** — `nrf/samples/wifi/ble_coex`, com `nrf54lm20dk/nrf54lm20b/cpuapp` no
`platform_allow` e `SHIELD="nrf7002eb2;nrf7002eb2_coex"`. Mede throughput de Wi-Fi e de BLE
rodando ao mesmo tempo na banda de 2,4 GHz, com o mecanismo de coexistência ligado e
desligado. Amarra direto com o Channel Sounding: a turma acabou de medir distância por BLE, e
aqui vê o que acontece quando o Wi-Fi divide a mesma banda.

**Locationing** — dois caminhos, e o do SDK é o pior para uma sala de aula:

| | `wifi/nrf_cloud` (o do SDK) | Scan + resolução no PC (o do curso) |
|---|---|---|
| Alvo | `nrf54lm20dk/nrf54lm20b/cpuapp/**ns**` — build TF-M | `cpuapp` normal |
| Conta nRF Cloud | uma por dispositivo, com onboarding dos 6 kits | uma chave de API, no PC do instrutor |
| Internet | **no dispositivo** | **só no PC** |
| O que o aluno vê | uma coordenada aparecendo | a lista de BSSID que o kit viu **e** a coordenada |

O caminho do curso: a DK faz `wifi scan`, manda **BSSID + RSSI** pelo mesmo socket TCP do lab
9, e o PC resolve a posição chamando a API REST de location do nRF Cloud com a chave do
instrutor. Reaproveita o lab que já existe, dispensa TF-M e onboarding, e ensina o princípio
de verdade: **a localização não está no dispositivo, está no banco de dados de quem mapeou os
APs**. O `nrf_cloud` fica como referência escrita e demo.

Nota: a documentação do nRF Cloud diz que o suporte é "nRF54L20 DK com nRF7002 EB2"; a árvore
do v3.4.0 diz `nrf54lm20dk`. Vale a árvore.

### 2.6 Credenciais e transporte

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

### 3.4 O que cada lab novo mede

Os três labs novos não são "mais um sample rodando": cada um produz um **número** que o aluno
compara.

- **TWT:** corrente média com e sem TWT, medida com o **PPK2** — o mesmo instrumento e o mesmo
  gesto do `11_benchmark_npu_vs_cpu` do Edge AI. É o argumento de bateria do Wi-Fi 6, medido.
- **Coexistência:** throughput de Wi-Fi e de BLE, simultâneos, com e sem o mecanismo ligado.
  Duas linhas numa tabela dizem mais que um slide sobre árbitro de rádio.
- **Locationing:** quantos APs o kit enxerga, e a coordenada que sai deles — com o erro contra
  a posição real da sala. Complementa o módulo de GNSS pelo lado de dentro do prédio.

### 3.5 Plano B por lab

A rede da sala não foi definida, então cada lab declara do que depende:

| Lab | Depende de | Plano B |
|---|---|---|
| 6, 7 | um AP qualquer | SoftAP da própria DK |
| 8 | nada | é o próprio AP |
| 9, 10 | AP + PC na mesma rede | PC conectado ao SoftAP da DK |
| 11 (TWT) | **AP Wi-Fi 6 com TWT** | **nenhum** — sem o AP, o lab não roda |
| 12 (coex) | um AP qualquer + um par BLE | SoftAP + o TAG do CS como par |
| 13 (location) | scan de APs; **internet no PC** | nenhum para a internet do PC; o kit não precisa |

### 3.6 Tudo que vem de fora entra no repo, com fonte

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
| 11 | `11_wifi_twt/` | `nrf/samples/wifi/twt` | idem + **AP Wi-Fi 6** + PPK2 | bônus (Wi-Fi 6) |
| 12 | `12_wifi_coex/` | `nrf/samples/wifi/ble_coex` | idem + par BLE | bônus |
| 13 | `13_wifi_location/` | código do curso, reusa o 9 | idem + internet no PC | bônus |

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

### 4.6 Lab 11 — TWT: o argumento de bateria do Wi-Fi 6

O `twt` como veio, com `minha_rede.conf`. O aluno estabelece o fluxo TWT com o AP e mede a
**corrente média com e sem TWT** usando o PPK2 — mesmo instrumento e mesmo gesto do
`11_benchmark_npu_vs_cpu` do Edge AI.

É o lab que responde "por que Wi-Fi 6 e não Wi-Fi qualquer" com número em vez de slide.

**Sem AP Wi-Fi 6 com TWT o lab não acontece** (§3.5). É o único da frente sem plano B, e a
razão pela qual a rede da sala precisa ser decidida.

Divergência do curso: o `minha_rede.conf`.

### 4.7 Lab 12 — coexistência com o BLE que eles acabaram de usar

O `ble_coex` com `SHIELD="nrf7002eb2;nrf7002eb2_coex"`. Mede throughput de Wi-Fi e de BLE
simultâneos, com o mecanismo de coexistência **ligado e desligado**.

A amarração com o Channel Sounding é o ponto: a turma passou o bloco anterior medindo
distância por BLE em 2,4 GHz; aqui vê o que o Wi-Fi faz com esse mesmo espectro, e como o
árbitro de coexistência divide o meio. O par BLE pode ser o próprio TAG do CS.

Divergência do curso: a definir na implementação (provavelmente só o `minha_rede.conf`).

### 4.8 Lab 13 — locationing sem nuvem no dispositivo

**Código do curso**, reusando o cliente TCP do lab 9. A DK faz `wifi scan`, monta a lista de
**BSSID + RSSI** e manda pelo socket. No PC, `tools/wifi_locate.py` chama a API REST de
location do nRF Cloud com a chave do instrutor e imprime coordenada e raio de incerteza.

O aluno vê **as duas metades**: a lista de APs que o kit enxergou e a coordenada que saiu
dela. Fica claro que a localização não está no dispositivo — está no banco de dados de quem
mapeou aqueles APs. Complementa o módulo de GNSS pelo lado de dentro do prédio.

Requer no mínimo dois APs visíveis (regra do serviço) e **internet no PC**, não no kit.

O `wifi/nrf_cloud` (build `/ns` com TF-M, onboarding por dispositivo) fica como referência
escrita no README e demo do instrutor, se houver tempo.

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

Com a EB II acoplada, o console está na **`uart30`** (§2.3) — **outra VCOM**, a primeira,
enquanto os labs sem shield usam a segunda. Todo README abre com esse aviso, e o
`PREREQUISITOS.md` já o registra.

## 6. Bancada

- 6 × nRF54LM20-DK (variante B) + 6 × nRF7002-EB II, uma por aluno
- notebook do aluno: Python com `protobuf`, `protoc` no PATH
- PC do instrutor: `wifi_server.py`; `mosquitto` se o lab 10 rodar; chave de API do nRF Cloud
  e internet para o lab 13
- **PPK2** para o lab 11 — o mesmo do módulo de Edge AI
- **AP Wi-Fi 6 com TWT: TP-Link EX3000** (AX3000, 1 WAN + 3 LAN gigabit, 160 MHz) —
  obrigatório para o lab 11, desejável para todos. Escolhido por ser o único dos candidatos
  avaliados em que "Target Wake Time" consta da **especificação oficial do modelo**. Descartados:
  Mercusys MR80X (TWT só na nota de rodapé de marketing; o manual de 83 páginas não tem controle
  de TWT em *Advanced → Wireless → Additional Settings*), Archer AX23 (a própria TP-Link responde
  na comunidade que "doesn't support" TWT e não há toggle) e Huawei AX2S (evidência só de
  revendas; a doc de TWT da Huawei é da linha enterprise)
- par BLE para o lab 12 — pode ser o nRF54L15-TAG do Channel Sounding
- rede da sala **a definir**; todos os labs têm plano B **menos o 11** (§3.5)

### 6.1 O AP de desenvolvimento, e por que ele não substitui o EX3000

A bancada de preparação usa a ONT da casa: **Askey RTF8225VW-SV** (Vivo Fibra, SW
`BR_SG_g2.5_RTF_TEF004_V3.9`, HW REV4), dual-band 2.4/5 GHz.

Medido em 2026-09-06 com o firmware do lab 6:

| Banda | Canal | `Link Mode` | `TWT` | `wifi twt quick_setup` |
|---|---|---|---|---|
| 2.4 GHz | 6 | WIFI 6 (802.11ax/HE) | Not supported | `Peer not TWT capable` |
| 5 GHz | 52 | UNKNOWN | Not supported | `Peer not TWT capable` |

O power save do nRF7002 estava ligado (`Legacy power save`, wake-up por DTIM) antes de cada
tentativa, o que descarta falso negativo do lado do DK.

**A conclusão vale como material de aula, não só como nota de bancada:** este é um AP
802.11ax de verdade — a associação em 2.4 GHz negocia HE — e ainda assim não anuncia TWT
Responder. TWT é **opcional** no 802.11ax. "AP Wi-Fi 6" não implica "AP com TWT", e o aluno
pode conferir isso na própria rede dele com um comando. O EX3000 continua obrigatório para o
lab 11.

Duas ressalvas do mesmo teste, que os READMEs devem carregar:

- O `Link Mode` do 5 GHz veio `UNKNOWN` em conexões repetidas, mesmo com o link assentado.
  Não é evidência de que aquela BSS não seja ax — é campo não preenchido pelo driver.
- O `Current PHY TX rate` reporta valor absurdo logo após conectar (537179,8 Mbps observado).
  Não serve como métrica em nenhum lab.

## 7. Material

Deck **M2-04** (Wi-Fi), no mesmo toolkit dos M2-01/02/03: companion IC e o que o nRF7002 é,
os blobs, provisionamento, e a tabela dos três transportes (§3.2) com os números medidos.

### 7.1 Beacon, TIM, DTIM e TWT — o bloco que precisa ficar claro

Os termos costumam ser apresentados como alternativas concorrentes. Não são. Três deles são
partes de um mesmo mecanismo, e a economia de energia do Wi-Fi é uma **escada de três degraus**,
não uma escolha entre antigo e moderno. Esta é a ordem de apresentação.

#### O quadro e seus elementos

**Beacon.** O AP transmite um quadro periódico anunciando a rede, no *beacon interval*. Medido
na bancada: 100 unidades de tempo, ou seja ~102,4 ms.

**TIM — Traffic Indication Map.** É um **elemento dentro do beacon**, não um quadro separado.
Carrega um bitmap de AIDs dizendo quais estações têm quadros **unicast** guardados no AP.

**DTIM — Delivery TIM.** É um TIM **especial**, que aparece a cada N beacons, onde N é o
*DTIM period* definido no AP. Ele anuncia o tráfego **de grupo** — broadcast e multicast — que o
AP transmite logo depois desse beacon.

A relação que o aluno precisa levar: **todo beacon carrega um TIM; um beacon a cada N é um
DTIM.** DTIM não é outro mecanismo, é uma ocorrência privilegiada do TIM. Quadros de grupo saem
só depois do DTIM; quadros unicast a estação busca quando o bit dela aparece em qualquer TIM.

#### Como a estação busca o unicast

Duas variantes, e o nRF70 usa a primeira por padrão:

- **Legacy Power Save.** A estação vê o próprio AID no TIM e manda um **PS-Poll**. O AP
  responde com **um** quadro por vez, sinalizando no subcampo **More Data** se ainda há fila. A
  estação repete até o More Data zerar e volta a dormir.
- **WMM Power Save.** Em vez do PS-Poll, a estação abre um *Service Period* com um quadro de
  disparo, e o AP entrega vários quadros até marcar o bit **EOSP** no último. Na prática não há
  diferença relevante de consumo em relação ao Legacy.

#### A escada de três degraus

| Degrau | Quem controla o intervalo de dormida | Precisa de Wi-Fi 6 | Perde broadcast/multicast |
|---|---|---|---|
| **DTIM Power Save** | o **AP** | não | não |
| **Extended Power Save** (listen interval) | a **estação** | não | **sim** |
| **TWT** (deep sleep) | **negociado** entre estação e AP | **sim** | **sim** |

**Degrau 1 — DTIM.** Padrão do nRF70 assim que conecta. A estação dorme e acorda alinhada ao
DTIM. Quem manda no período é o AP, e a estação **não pode pedir alteração**. Período maior
economiza mais e adiciona latência ao tráfego de descida. Medido na bancada: `Beacon Interval:
100`, `DTIM: 3`, ou seja um acordar a cada ~307 ms — o mesmo número que a documentação da Nordic
usa como exemplo.

**Degrau 2 — Extended Power Save, ou listen interval.** O degrau que quase todo mundo esquece, e
o mais útil no nosso caso: **não depende de Wi-Fi 6**. A estação acorda a cada *listen interval*
beacons em vez de a cada DTIM, arredondado para o múltiplo mais próximo do período de DTIM — com
listen interval 10 e DTIM 3, acorda a cada 9 beacons; com DTIM 4, a cada 8. O preço é perder os
quadros de grupo, que saem logo após o DTIM. O listen interval vai no quadro de associação e por
isso deve ser configurado **antes de conectar**. Medido na bancada: `PS listen_interval: 10`, e
a troca de modo em tempo de execução funciona nos dois sentidos.

**Degrau 3 — TWT.** Aqui sim é Wi-Fi 6. A estação **negocia com o AP o seu próprio horário**, em
vez de herdar o calendário coletivo. Dorme de segundos a horas. O preço é o mesmo do degrau 2 e
mais explícito: não acorda para os beacons de DTIM, logo não recebe broadcast nem multicast
enquanto a sessão estiver de pé. Se a aplicação precisar de quadros de grupo, derruba a sessão e
volta ao DTIM.

#### Dynamic power save e o temporizador de inatividade

Transversal aos três degraus, e fácil de confundir com eles. O nRF70 sai do modo de economia
sozinho quando há tráfego e volta quando a MAC fica ociosa por um tempo — o *inactivity timer*,
100 ms por padrão. Zerar esse temporizador mantém a estação sempre em economia, inclusive
durante a transmissão, o que derruba a vazão de descida. É um botão separado do degrau escolhido.

#### Quando cada um ganha

DTIM é melhor para vazão alta e latência baixa, porque a estação acorda com frequência e recebe
os quadros de grupo. TWT é melhor para dormidas da ordem de dezenas de segundos para cima, com
tráfego periódico previsível. O listen interval fica no meio, e é a resposta para quem não tem
AP com TWT. **Não escrever "TWT é o moderno, DTIM é o legado".**

#### A dependência que o lab prova

TWT é um **acordo**: exige que o AP anuncie suporte. A ONT da bancada é 802.11ax confirmado e
responde `Peer not TWT capable` (§6.1). Os degraus 1 e 2 não dependem disso e são medíveis em
qualquer rede.

#### A escada aparece na latência, e isso dispensa o PPK2

O instrumento óbvio é o PPK2, mas o conceito fecha com um `ping`. O AP só entrega o quadro
quando a estação acorda, então o regime de economia se lê direto na **latência de descida**.
Medido nesta bancada, 20 pings por regime (detalhe em `bancada-dtim.md`):

| Regime | mediana | máximo |
|---|---|---|
| sem economia | 12 ms | 269 ms |
| DTIM 3, o padrão | 168 ms | 332 ms |
| listen interval 10 | 525 ms | 938 ms |

A teoria prevê os números. Em DTIM o quadro espera uma fração aleatória do período de 307 ms,
logo média perto da metade e máximo perto do período: medido 175 e 332. Com listen interval 10
sobre DTIM 3 a estação acorda a cada 9 beacons, 922 ms: medido mediana 525 e máximo 938.

Escalando o listen interval, o máximo cresce de forma monotônica — 913 ms com 10, 2038 ms com
30, 5130 ms com 60.

**Armadilha de método que precisa ir para o README.** Quando o período de dormida passa do
intervalo entre pings, vários pedidos ficam bufferizados no AP e são entregues **juntos** numa
mesma janela. Só o primeiro paga a latência cheia, e os demais puxam a mediana para baixo. Com
dormida longa, a estatística que significa alguma coisa é o **máximo**.

**Pegadinha de comando, medida.** O comando é `wifi ps_listen_interval`, não
`wifi listen_interval`. Errar o nome **não devolve erro**: o shell imprime o help e o valor
continua o anterior, produzindo uma medição que parece válida e não é. Sempre conferir com
`wifi ps` depois de setar. Trocar o **modo** de despertar funciona em tempo de execução; trocar
o **valor** do listen interval exige reconectar, porque ele viaja no quadro de associação.

#### Modo Broadcast do TWT: fora do escopo

No nRF Connect SDK v3.4.0 o driver do nRF70 implementa só o TWT **Individual** — registra a
operação `set_twt` e não registra `set_btwt`. O shell do Zephyr expõe um comando
`wifi twt btwt_setup`, mas ele não tem driver por trás nesta versão. O lab usa
`wifi twt quick_setup` e `wifi twt setup`, ambos individuais.

### 7.2 O que aproveitamos do material da Nordic, e onde ele não serve direto

O curso *Wi-Fi Fundamentals* da Nordic Academy, o guia de *power profiling* do nRF70 e o post do
DevZone sobre TWT cobrem esse bloco bem, e a estrutura conceitual do §7.1 vem deles. Três coisas
**não** transferem para a nossa bancada, e cada uma vira uma nota no README do lab 11:

**1. A sintaxe do comando de TWT mudou.** O material da Nordic usa a forma posicional, por
exemplo `wifi twt setup 0 0 1 1 0 1 1 1 8 60000`. Testado no nosso shell (Zephyr 4.4.0, NCS
v3.4.0): **falha** com `setup: wrong parameter count`. A forma atual é por opções longas, com 25
argumentos (`-n -c -t -f -r -T -I -a -w -p -D -d -e -m`), ou o atalho
`wifi twt quick_setup <wake_interval_us> <interval_us>`. O aluno que copiar o comando do material
online recebe erro — o README precisa avisar.

**2. As instruções do PPK2 são do nRF7002 DK, e o ponto certo aqui é outro.** A Nordic
documenta remover o jumper P23 e ligar Vout ao P23 pino 1 — isso é do **nRF7002 DK**, host
nRF5340. Levantado na documentação de hardware das nossas duas placas, o quadro é este:

| O que se quer medir | Placa | Conector | Preparo | Modo do PPK2 |
|---|---|---|---|---|
| SoC hospedeiro (nRF54LM20B) | LM20-DK | **P14** (VDD nRF CURRENT MEASURE) | tirar o jumper de P14, Vout no pino do meio, GND no GND do mesmo header | *source meter* |
| Companion nRF7002, domínio VBAT | EB II | **P10** | pôr P10 em série com a carga e **cortar o solder bridge SB10** | *ampere meter* |
| Companion nRF7002, domínio IOVDD | EB II | **P4** | análogo, com o solder bridge correspondente | *ampere meter* |

Para voltar ao funcionamento normal da EB II depois da medida: jumper em P10, ou refazer o
curto de SB10.

A EB II tem **exatamente dois** solder bridges, ambos fechados de fábrica: **SB10** corta o
VBAT e **SB9** corta o IOVDD. Não há caminho sem solda para medir o companion — os dois
domínios passam por um bridge fechado, e é isso que garante o funcionamento normal fora da
medição. Com o PPK2 o modo é **ampere meter**, ligado entre os pinos de P10, com o GND em P9 ou
no próprio P10; a EB II continua alimentada pela placa e o PPK2 só fica em série.

Para o nosso caso, o domínio que interessa é o **VBAT** — é ele que alimenta o rádio. O IOVDD é
a interface.

**Armadilha de instrumentação que precisa ir para o README do lab 11.** A documentação da EB II
avisa que um amperímetro comum só dá média válida se o ciclo de carga for **curto, abaixo de
100 ms**, para que ele integre ciclos inteiros e não pedaços. Os nossos regimes violam isso de
propósito: DTIM 3 já são ~307 ms, listen interval 10 são ~922 ms, e TWT pode ser de minutos. Um
multímetro em modo corrente daria um número sem sentido nessas condições. O PPK2 não tem essa
limitação porque amostra rápido e a média é feita sobre a janela que o operador escolhe — por
isso ele é o instrumento certo aqui, e não uma conveniência. A alternativa documentada é
osciloscópio com um resistor de 10 Ω entre os pinos de P10, que é o mesmo princípio.

**Detalhes do PPK2 que entram no roteiro.** Ele mede de 200 nA a 1 A, amostrando a 100 kSa/s,
com resolução entre 100 nA e 1 mA conforme a faixa. Em **modo amperímetro** ele não alimenta
nada: exige que a fonte externa entregue entre 0,8 V e 5 V ao alvo — no nosso caso quem alimenta
é a própria DK, então a condição já está satisfeita. É por isso que este é o modo certo aqui, e
não o modo fonte que a Nordic usa no nRF7002 DK.

Duas coisas que confundem na primeira vez, e que o README deve antecipar:

- **"Enable power output" precisa ser ligado mesmo em modo amperímetro.** Ali ele não liga
  fonte nenhuma: só fecha o circuito interno de medição, deixando a corrente passar para o
  alvo. Sem isso o alvo simplesmente não recebe corrente pelo caminho medido.
- **Alimentação do próprio PPK2.** Um cabo USB entrega até 500 mA através dele; para chegar a
  1 A são necessários dois cabos. Vale conferir o pico de transmissão do nRF7002 na primeira
  captura antes de confiar nas médias.

**Oportunidade que vale considerar para o lab.** O PPK2 tem entradas digitais que funcionam
como analisador lógico simples, sincronizadas com a corrente. Ligando uma delas a um GPIO que o
firmware chaveia no início e no fim da janela de despertar, o gráfico mostra a corrente e o
evento de código lado a lado — é a forma mais direta de mostrar que o pico coincide com o
despertar negociado, em vez de pedir para o aluno acreditar na coincidência temporal.

**O P14 mede só o nRF54LM20B, e não pega o nRF7002.** Isso não é dedução, está na
documentação de hardware da DK. O P14 fica em série com o domínio **VDD:nRF**, que alimenta
apenas o SoC — tanto que a DK continua com serial, LEDs e botões funcionando quando o SoC é
alimentado por ali de fora. O domínio **VDD:IO**, que é o que chega à EB II pelos pinos de
alimentação do conector de expansão, é um **seguidor de tensão bufferizado** do VDD:nRF, feito
de propósito para que correntes de fuga não sejam puxadas do SoC durante medidas de baixo
consumo. Ou seja, VDD:IO fica **fora** do caminho de corrente do P14.

A confirmação vem por um detalhe da própria doc: a memória flash externa é alimentada por
VDD:IO por padrão e **não** entra na conta do P14; para incluí-la é preciso cortar SB23 e
fechar SB24, e a doc avisa que aí sim o consumo dela "é somado à corrente do SoC medida em
P14". Se fosse preciso mexer em solder bridge para somar a flash, nada mais do lado VDD:IO
entra por acidente.

**A consequência de projeto é grande, e precisa ser decidida antes do lab 11.** A corrente que
muda entre DTIM, listen interval e TWT é a do **companion**, e o P14 não a enxerga. O ponto sem
solda mede a coisa errada, e o ponto certo **exige cortar o SB10 na EB II**.

Três saídas, em ordem de preferência:

1. **Um kit do instrutor com SB10 cortado**, e a medida projetada para a turma. Os alunos rodam
   os regimes e leem a diferença no `wifi ps` e na latência (§7.1); a corrente aparece uma vez,
   no kit preparado. Custo: uma solda, num kit só.
2. **Medir o hospedeiro em P14 em todos os kits**, deixando claro no README que aquilo é o
   consumo do SoC e **não** o do rádio Wi-Fi. Serve para falar de instrumentação, não para
   provar a economia do Wi-Fi.
3. **Cortar SB10 nos seis kits.** Dá a medida certa em todas as bancadas e custa seis soldas
   mais o retrabalho de restaurar depois. Só se o instrutor quiser.

Enquanto essa decisão não sai, o lab 11 se sustenta na medida por latência (§7.1), que não
precisa de PPK2 nem de solda.

**3. Os números não são nossos.** As correntes que a Nordic publica (~2 mA em DTIM de 200 ms,
~15 µA dormindo, ~24-28 µA de média com TWT de 5 a 10 minutos) são de nRF7002 DK com host
nRF5340. O nosso host é o nRF54LM20. Servem como ordem de grandeza na aula, sempre atribuídas à
fonte, e **nunca** entram numa tabela nossa como se fossem medição da bancada.

## 8. Validação pendente

Nada aqui foi rodado em hardware ainda, além do build de fumaça do §2.1.

1. ~~**Console na `uart30`**~~ — **fechado em 2026-09-06.** Console na `uart30`, primeira
   VCOM; sem shield fica na `uart20`, segunda VCOM. Medido nas duas condições. Ver §2.3.
2. **Varredura de DTIM com o PPK2 na rede do instrutor** — medir a corrente média para
   valores diferentes de *DTIM period* configurados no roteador, fechando a escada do §7.1 com
   corrente e não só com latência. **Duas dependências:** o ponto de medição do PPK2 nesta
   combinação (item 3) e o roteador expor o período de DTIM na administração. A ONT Askey da
   bancada pode não expor — ONT de operadora costuma não expor. Confirmar antes de planejar a
   medida; se não expuser, a varredura fica só no listen interval, que é todo do lado da
   estação.
3. ~~**Ponto de medicao do PPK2 no LM20-DK + EB II**~~ — **fechado em 2026-09-06.** LM20-DK
   mede o SoC em P14; a EB II mede o companion em P10 (VBAT) ou P4 (IOVDD), e **exige cortar o
   solder bridge SB10**. Ver §7.2. Fica **pendente de decisao do instrutor** qual das tres
   saidas adotar.
4. **`provisioning/softap` na variante B** — `platform_allow` lista, mas `boards/` só tem
   `.conf` da variante A. Compila? Precisa de um `.conf` novo?
5. **Fluxo completo do `provision.py`** — `protoc`, certificado, `/prov/networks`,
   `/prov/configure`, e a DK associando depois.
6. **RAM com MQTT** — o `sta` sozinho já usa 36% de 511 KB. Medir os três transportes.
7. **Botões e LEDs com o shield** — confirmar `sw0`–`sw2` e os quatro LEDs; confirmar que
   `sw3` sumiu.
8. **Temperatura do die** — o sensor está habilitado no board; confirmar leitura plausível.
9. **Plano B em SoftAP** — o PC conectar no AP da DK e o TCP funcionar sem infraestrutura.
10. **TWT — o teste de cinco minutos, a fazer no dia em que o EX3000 chegar.** Decide se o lab
   11 existe; se falhar, dá tempo de trocar dentro do prazo de devolução:

   1. no EX3000: *Advanced → Wireless → Wireless Settings*, procurar **TWT** e habilitar (na
      linha Archer o padrão é desabilitado; se não houver toggle, seguir assim mesmo);
   2. gravar o lab 6 (`wifi/shell`) e conectar: `wifi connect -s <ssid> -k 1 -p <senha>`;
   3. `wifi twt setup` e ler a resposta;
   4. `wifi status` deve mostrar o modo de power save/TWT ativo.

   O que confirma: o AP aceita TWT **individual** — o modo que o nRF70 usa; a Nordic diz que
   broadcast não é suportado nesta release. Depois disso, medir corrente com e sem TWT no PPK2.
11. **Coexistência** — compilar com o shield duplo, medir throughput dos dois rádios com o
   mecanismo ligado e desligado, e confirmar que o TAG serve como par BLE.
12. **Locationing** — quantos APs a DK enxerga na sala, resposta da API do nRF Cloud, e erro
    contra a posição real.
13. **Tempo de cada lab** — cronometrar os oito. É o número que decide o corte (§1).

## 9. Fora de escopo

- **Gateway TAG → DK → nuvem**: exigiria BLE e Wi-Fi ativos ao mesmo tempo na aplicação, o que
  o lab 12 mede mas não usa como arquitetura. Fica como extensão escrita.
- **Comando de voz como gatilho**: impossível no mesmo kit (§2.3).
- **Throughput, raw TX, promiscuous, P2P, Thread coex, WFA QT**: samples existem e são alvos do
  LM20, mas competem por tempo com GNSS e NTN.
- **`wifi/nrf_cloud` como lab**: exige TF-M e onboarding dos 6 kits; entra como referência e
  demo (§4.8).
- **Wi-Fi 6 "6+" como certificação**: o material trata do que o nRF7002 entrega (dual-band,
  TWT como recurso citado), sem entrar em certificação.
