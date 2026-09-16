# Dias 3–4 — Tecnologias de Comunicação Avançada — 10h

Implementação e validação das principais tecnologias de conectividade e localização de próxima geração da plataforma Nordic.

**Hardware:** nRF54LM20-DK + nRF54L15-TAG (Channel Sounding), nRF7002-EBII (Wi-Fi 6+). Um AP com TWT (TP-Link EX3000) ainda não chegou à bancada; quando chegar, serve de referência para a Parte B (TWT) do lab de energia — sem ele, a Parte A do mesmo lab (DTIM e listen interval) roda normalmente.

> Os labs de GNSS ficam no módulo separado [`gnss/`](../gnss/), por usarem kits dedicados (nRF9151 e u-blox EVK-X20P). Redes Não Terrestres (NTN) ficam no módulo separado [`ntn/`](../ntn/), por usar um kit dedicado (nRF9151-SMA-DK com SIM Skylo).

## Labs

| Lab | Descrição | Kit | Status |
|-----|-----------|-----|--------|
| [`01_cs_reflector/`](01_cs_reflector/) | **CS 1** — Reflector RAS no TAG, CS default da Nordic. Log por RTT (o TAG não tem UART). Fragmentos da demo com smartphone | nRF54L15-TAG | ✅ |
| [`02_cs_initiator/`](02_cs_initiator/) | **CS 2** — Initiator RAS no LM20-DK: `ifft`, `phase_slope` e `rtt` lado a lado. Filtra pelo endereço do TAG do aluno, digitado na serial no boot (como no Edge AI). Experimento com trena e obstrução | nRF54LM20-DK | ✅ |
| [`03_cs_ipt/reflector/`](03_cs_ipt/reflector/) + [`03_cs_ipt/initiator/`](03_cs_ipt/initiator/) | **CS 3** — O mesmo par com IPT: a contribuição do reflector viaja na fase do tom, não por GATT. A coluna `rtt` some; `time_delta` cai | TAG + LM20-DK | ✅ |
| [`04_cs_seguranca/`](04_cs_seguranca/) | **CS 4** — Roteiro: ACL cifrada, CS Security Enable, RTT como limite físico contra relay attack, o que o IPT abre mão, o que o SDC não suporta | par do CS 2 | ✅ (conforme o tempo) |
| [`05_cs_iq_music/`](05_cs_iq_music/) | **CS 5** — IQ para o PC: port do `cs_de` em NumPy reproduz o chip; MUSIC (skig/waves, MIT) sobre o mesmo IQ; dois caminhos de antena e a escolha entre eles; obstrução; painel ao vivo (`cs_dash.py`). Tese: o firmware fornece os dados, a distância é do algoritmo | LM20-DK + TAG + PC | ✅ (conforme o tempo) |
| [`06_wifi_shell/`](06_wifi_shell/) | **Lab 6** — Shell de Wi-Fi da própria Nordic (`wifi scan`/`connect`/`status`) puro sobre a EB II, sem lógica de aplicação. Base dos labs seguintes; primeira aparição da troca de console (VCOM) e do achado de que "802.11ax no rótulo" não garante TWT | nRF54LM20-DK + nRF7002-EBII | ✅ |
| [`07_wifi_sta/`](07_wifi_sta/) | **Lab 7** — Associação programática por `minha_rede.conf`: o firmware conecta e sobe IP sozinho, sem shell; falha proposital de build sem a credencial preenchida | nRF54LM20-DK + nRF7002-EBII | ✅ |
| [`08a_wifi_provisioning/`](08a_wifi_provisioning/) | **Lab 8a** — Provisionamento por SoftAP: a DK sobe como AP, escaneia sozinha e recebe a credencial por HTTPS/protobuf via `provision.py` — sem formulário web | nRF54LM20-DK + nRF7002-EBII | ✅  |
| [`08b_wifi_provisioning_ble/`](08b_wifi_provisioning_ble/) | **Lab 8b** — O mesmo provisionamento pelo outro transporte: a DK anuncia por Bluetooth LE (`PVxxxxxx`, nome derivado do MAC) e o app nRF Wi-Fi Provisioner entrega a credencial por GATT — o celular nunca sai da rede em que já está | nRF54LM20-DK + nRF7002-EBII + celular | ✅  |
| [`09_wifi_tcp/`](09_wifi_tcp/) | **Lab 9** — Lab central da frente: telemetria por socket TCP puro, mesmo payload do lab 10; reconexão com backoff e queda de conexão como o próprio ponto do lab | nRF54LM20-DK + nRF7002-EBII | ✅ |
| [`10_wifi_http_mqtt/`](10_wifi_http_mqtt/) | **Lab 10** — O mesmo payload do lab 9 recompilado sobre HTTP e MQTT: comparação medida de bytes por amostra, FLASH/RAM, e o custo estrutural do polling HTTP | nRF54LM20-DK + nRF7002-EBII | ✅ |
| [`11_wifi_twt/`](11_wifi_twt/) | **Lab 11** — A escada de economia de energia: DTIM e listen interval medidos por latência com o firmware do lab 6 (Parte A, Passo 1) e por corrente no PPK2 (Parte A, Passo 2 — 51,3 mA sem economia, 2,29 mA em DTIM 3, 31 µA no listen interval 600, com o downlink morrendo pelo caminho); TWT (Parte B) depende de um AP que negocie | nRF54LM20-DK + nRF7002-EBII | ✅ (Parte A medida; Parte B pendente do AP com TWT) |
| [`12_wifi_coex/`](12_wifi_coex/) | **Lab 12** — Coexistência BLE×Wi-Fi no mesmo kit: cliente Wi-Fi (zperf) e central BLE (throughput) simultâneos, árbitro de coexistência ligado/desligado por build — o lab mais pesado de RAM da frente | nRF54LM20-DK + nRF7002-EBII + par BLE (nRF54L15-TAG) | ✅ |
| [`13_wifi_location/`](13_wifi_location/) | **Lab 13** — Locationing sem GPS: o kit varre os APs vizinhos e o nRF Cloud resolve a posição pelo banco de mapeamento — fecha o módulo pelo lado de dentro do prédio | nRF54LM20-DK + nRF7002-EBII | ✅ |

### Channel Sounding — ordem de ensino

```
CS 1  reflector no TAG            "o dispositivo simples"        grava por fio, RTT
CS 2  initiator no DK             "RTT e PBR lado a lado"        trena, obstrucao
CS 3  o mesmo par com IPT         "por onde viaja o dado"        a coluna que some
CS 4  seguranca                   "o que o radio garante"        conforme o tempo
CS 5  o IQ no PC                  "o algoritmo e da aplicacao"   conforme o tempo
```

O TAG é gravado por fio, encaixado no `DEBUG OUT` da DK, duas vezes (reflector RAS
no CS 1, reflector IPT no CS 3). Enquanto ele está encaixado, o debugger da DK aponta
para ele — gravar "a DK" nessa hora grava o TAG. Sem DFU/OTA neste módulo.

Os seis TAGs da sala anunciam o mesmo UUID e o mesmo nome: todo initiator do módulo
filtra pelo endereço BLE do TAG do aluno, que é o **mesmo do Edge AI** (vem do chip,
não do firmware). Os três initiators pedem o endereço no terminal serial a cada boot,
como o `03_central_uart` do Edge AI — nada a preencher antes do build.

### Wi-Fi 6+ — ordem de ensino

```
Lab 6   shell da Nordic          "o companion visivel"           scan, connect, status
Lab 7   associacao programada    "conectar sem intervencao"      minha_rede.conf
Lab 8a  provisionamento SoftAP   "a DK escaneia por voce"        HTTPS + protobuf, sem web
Lab 8b  provisionamento BLE      "o mesmo, por outro radio"      app da Nordic, GATT + protobuf
Lab 9   telemetria TCP           "o lab central"                 payload reaproveitado no lab 10, backoff
Lab 10  HTTP e MQTT              "um payload, tres transportes"  bytes por amostra, polling
Lab 11  economia de energia      "a escada de tres degraus"      DTIM, listen interval, TWT
Lab 12  coexistencia BLE x Wi-Fi "duas pilhas de radio juntas"   espectro disputado, medido
Lab 13  locationing sem GPS      "a posicao nao esta no kit"     varredura + nRF Cloud
```

O par nRF54LM20-DK + nRF7002 EB-II é o mesmo do lab 6 ao 13; só o lab 8b (celular com
o app nRF Wi-Fi Provisioner) e o lab 12 (o par BLE do teste de coexistência) somam um
segundo dispositivo. A troca de console — o
shield move `zephyr,console` da `uart20` (segunda VCOM) para a `uart30` (primeira) —
é medida e documentada uma vez no lab 6 e vale para todos os que seguem. O fragmento
de credencial `minha_rede.conf`, rastreado pelo git e vazio, aparece pela primeira vez
no lab 7 e é reaproveitado pelos labs 9, 11, 12 e 13; nenhum dos cinco compila sem ele
preenchido — é falha proposital, não bug. O payload de telemetria do lab 9
(`src/payload.c`, uma amostra JSON) é reaproveitado só pelo lab 10, que recompila o
mesmo firmware sobre outro transporte; o lab 13 manda outra coisa — uma linha por
ponto de acesso visto (`AP,<bssid>,<rssi>,<frequência>,<ssid>`) — porque o dado é de
outra natureza (vizinhança de rede, não telemetria do dispositivo).

Blobs de firmware do nRF70 (`west blobs fetch nrf_wifi`) são pré-requisito de
qualquer build desta frente — ver [`PREREQUISITOS.md`](../PREREQUISITOS.md).

### Hex de referência

[`hex/`](hex/) tem um binário pronto de cada passo que **pode** ser distribuído, para
gravar sem compilar — os cinco de Channel Sounding e os três labs de Wi-Fi que não
embutem credencial (6, 8a, 8b). Os outros seis labs de Wi-Fi levam a senha da rede
dentro do binário e por isso **não são versionados**; o `hex/build_all.py` gera esses na
sala, com a credencial da sala, para fora do repo.

### Wi-Fi 6+ — os módulos da solução, e como reconhecê-los no log

"O Wi-Fi" desta frente não é uma peça: são **seis camadas** entre a aplicação do lab e
a antena, cada uma de um lugar diferente da árvore. Saber quem é quem é o que permite
ler um log de falha sem abrir o código — o prefixo da linha já diz em qual camada o
problema está.

```
   aplicacao do lab              nosso codigo         lab_wifi_tcp: / sta: / wifi_prov:
          |  net_mgmt(...)  <-- UNICO ponto de contato
   +------v-----------------+
   | TCP/IP, DHCP, sockets  |   Zephyr net           net_config: net_dhcpv4: net_if:
   +------+-----------------+
   | Wi-Fi management (L2)  |   Zephyr l2/wifi       net_wifi_mgmt: wifi_nm:
   +------+-----------------+                        net_wifi_shell:  (o shell do lab 6)
   | wpa_supplicant         |   fork do hostap       wpa_supp:
   +------+-----------------+
   | driver nrf_wifi        |   nRF Connect SDK      wifi_nrf:
   +------+-----------------+
   | barramento (SPI)       |   zephyr/modules       wifi_nrf_bus:
   +------+-----------------+
          |  spi22, ~8 MHz
   +------v-----------------+
   | nRF7002: MAC + PHY     |   blob binario na RAM do companion
   +------------------------+
```

| Camada | O que faz | Onde mora | Prefixo no log |
|---|---|---|---|
| **Aplicação** | a lógica do lab | `comms/NN_*/src/` | o que o lab registrar (`lab_wifi_tcp:`, `sta:`, `wifi_prov:`) |
| **TCP/IP, DHCP, sockets** | endereço, rotas, `zsock_*` | `zephyr/subsys/net/` | `net_config:`, `net_dhcpv4:`, `net_if:` |
| **Wi-Fi management (L2)** | traduz pedidos (`CONNECT`, `SCAN`, `PS`) em chamadas ao gerente de rede; hospeda o `wifi` do shell | `zephyr/subsys/net/l2/wifi/` | `net_wifi_mgmt:`, `wifi_nm:`, `net_wifi_shell:` |
| **wpa_supplicant** | política de varredura, máquina de estados de associação, *4-way handshake*, WPA2/WPA3, credenciais | `modules/lib/hostap/` (fork do hostap) | `wpa_supp:` |
| **Driver `nrf_wifi`** | fala com o companion, carrega o *blob* de firmware, mapeia a API do Zephyr no protocolo do chip | `zephyr/drivers/wifi/nrf_wifi/` + `modules/lib/nrf_wifi/` | `wifi_nrf:` |
| **Barramento** | o transporte físico até o companion: SPI (aqui) ou QSPI (em placas que têm) | `zephyr/modules/nrf_wifi/bus/` | `wifi_nrf_bus:` |
| **nRF7002** | MAC 802.11 e PHY, **dentro do silício** | o companion na EB II | não loga — é outro chip |

**O ponto de contato é um só: `net_mgmt()`.** A aplicação nunca chama o supplicant nem
o driver. Ela emite um pedido (`NET_REQUEST_WIFI_CONNECT_STORED`,
`NET_REQUEST_WIFI_PS`, ...) e assina eventos (`NET_EVENT_WIFI_CONNECT_RESULT`,
`NET_EVENT_IPV4_DHCP_BOUND`). É a mesma forma nos labs 7, 9, 10, 11 e 13, e é por isso
que trocar de transporte (lab 10) ou de regime de energia (lab 11) não mexe em nada
abaixo da aplicação.

**FullMAC: o 802.11 não roda no nosso SoC.** O nRF7002 implementa MAC e PHY em
silício, e o que atravessa o SPI são **quadros Ethernet**, não quadros 802.11. Duas
consequências que aparecem na bancada: o `net iface` do lab 6 lista "Ethernet
capabilities" numa interface Wi-Fi — não é erro —, e o host não gasta ciclo com
retransmissão, agregação ou temporização de rádio. Em compensação, **tudo o que o chip
não implementa não existe** para nós: foi assim que o TWT ficou pendente de um AP no
lab 11, e é por isso que o `nrf7002eb2` precisa do *blob*
(`west blobs fetch nrf_wifi`, em [`PREREQUISITOS.md`](../PREREQUISITOS.md)) — sem ele
o companion não tem firmware para rodar.

**A camada de barramento é uma linha de log que vale conhecer.** O `wifi_nrf_bus:` é o
mais baixo que aparece no console, e é onde surge a falha mais assustadora da frente —
**`RPU is unresponsive for 10 sec`**, o companion sem alimentação ou sem responder ao
SPI. No lab 11 ela aparece toda vez que o PPK2 abre a chave de medição antes de a placa
resetar; foi o custo de três reinícios de bancada. Se a falha estiver nessa linha, o
problema é elétrico ou de encaixe, **não** de configuração de rede.

**O wpa_supplicant é o módulo que mais surpreende**, por três motivos práticos:

1. **Ele é uma thread, e demora a subir.** O lab 7 espera por
   `CONFIG_WIFI_READY_LIB` antes de conectar; sem essa espera, o pedido de conexão
   volta **`-ENOTSUP`** — o driver está pronto e o supplicant ainda não.
2. **Ele reconecta sozinho.** Na queda do AP medida no lab 7, as retentativas saem a
   cada ~9,7 s **sem** a aplicação pedir nada — o log não mostra um segundo
   `Connection requested`. Quem reassocia é ele.
3. **Ele é a maior parte da conta de RAM da frente.** É a razão de o lab 12
   (coexistência) ser o build mais pesado do módulo, porque ali ele divide a memória
   com a pilha de Bluetooth LE.

**Dois módulos que só aparecem em alguns labs:**

- **`wifi_credentials`** — o cofre de credenciais por trás do
  `NET_REQUEST_WIFI_CONNECT_STORED` dos labs 7, 8a e 8b. A API é a mesma nos três,
  **o backend não**: o lab 7 usa `WIFI_CREDENTIALS_STATIC`, com a credencial compilada
  a partir do `minha_rede.conf` — some se você mudar de rede, e é isso que justifica o
  provisionamento; os labs 8a e 8b gravam em memória não volátil (`SETTINGS_ZMS` e
  `SETTINGS_NVS`, respectivamente), e é por isso que o kit provisionado volta sozinho à
  rede depois de um reset.
- **`wifi_prov_core`** — a máquina de provisionamento e o **protobuf** compartilhados
  pelos labs 8a e 8b. A diferença entre os dois é **só o transporte** (HTTPS sobre o
  SoftAP contra GATT sobre Bluetooth LE); a codificação da credencial é a mesma nos
  dois, e é por isso que o mesmo app do celular atende aos dois.
## Tópicos teóricos

- BLE 6.0 e Channel Sounding: RTT × PBR, initiator/reflector/subevent, Ranging Service por dentro (o serviço GATT do SIG e o que ele carrega), configuração de stack e otimização de pacotes (MTU, DLE, buffers ACL, intervalo de procedure), RAS × IPT como trade-off, segurança, e "o algoritmo é camada de aplicação"
- Wi-Fi 6+ para IoT: integração com companion IC, provisionamento por SoftAP,
  transporte (TCP, HTTP, MQTT sobre o mesmo payload), economia de energia (DTIM,
  listen interval, TWT), coexistência com BLE, e locationing por varredura de APs
