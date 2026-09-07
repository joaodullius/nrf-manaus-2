# Dias 3–4 — Tecnologias de Comunicação Avançada — 10h

Implementação e validação das principais tecnologias de conectividade e localização de próxima geração da plataforma Nordic.

**Hardware:** nRF54LM20-DK + nRF54L15-TAG (Channel Sounding), nRF7002-EBII (Wi-Fi 6+), nRF9151-SMA-DK (NTN). Um AP com TWT (TP-Link EX3000) serve de referência para o lab de energia.

> Os labs de GNSS ficam no módulo separado [`gnss/`](../gnss/), por usarem kits dedicados (nRF9151 e u-blox EVK-X20P).

## Labs

| Lab | Descrição | Kit | Status |
|-----|-----------|-----|--------|
| [`01_cs_reflector/`](01_cs_reflector/) | **CS 1** — Reflector RAS no TAG, CS default da Nordic. Log por RTT (o TAG não tem UART). Fragmentos da demo com smartphone | nRF54L15-TAG | ✅ |
| [`02_cs_initiator/`](02_cs_initiator/) | **CS 2** — Initiator RAS no LM20-DK: `ifft`, `phase_slope` e `rtt` lado a lado. Filtra pelo endereço do TAG do aluno (mesmo `meu_tag.conf` do Edge AI). Experimento com trena e obstrução | nRF54LM20-DK | ✅ |
| [`03_cs_ipt/reflector/`](03_cs_ipt/reflector/) + [`03_cs_ipt/initiator/`](03_cs_ipt/initiator/) | **CS 3** — O mesmo par com IPT: a contribuição do reflector viaja na fase do tom, não por GATT. A coluna `rtt` some; `time_delta` cai | TAG + LM20-DK | ✅ |
| [`04_cs_seguranca/`](04_cs_seguranca/) | **CS 4** — Roteiro: ACL cifrada, CS Security Enable, RTT como limite físico contra relé, o que o IPT abre mão, o que o SDC não suporta | par do CS 2 | ✅ (conforme o tempo) |
| [`05_cs_iq_music/`](05_cs_iq_music/) | **CS 5** — IQ para o PC: port do `cs_de` em NumPy reproduz o chip; MUSIC (skig/waves, MIT) sobre o mesmo IQ; dois caminhos de antena e a escolha entre eles; obstrução; painel ao vivo (`cs_dash.py`). Tese: o firmware fornece os dados, a distância é do algoritmo | LM20-DK + TAG + PC | ✅ (conforme o tempo) |
| [`06_wifi_shell/`](06_wifi_shell/) | **Wi-Fi 6** — Shell de Wi-Fi da própria Nordic (`wifi scan`/`connect`/`status`) puro sobre a EB II, sem lógica de aplicação. Base dos labs seguintes; primeira aparição da troca de console (VCOM) e do achado de que "802.11ax no rótulo" não garante TWT | nRF54LM20-DK + nRF7002-EBII | ✅ |
| [`07_wifi_sta/`](07_wifi_sta/) | **Wi-Fi 7** — Associação programática por `minha_rede.conf`: o firmware conecta e sobe IP sozinho, sem shell; falha proposital de build sem a credencial preenchida | nRF54LM20-DK + nRF7002-EBII | ✅ (bancada pendente) |
| [`08_wifi_provisioning/`](08_wifi_provisioning/) | **Wi-Fi 8** — Provisionamento por SoftAP: a DK sobe como AP, escaneia sozinha e recebe a credencial por HTTPS/protobuf via `provision.py` — sem formulário web | nRF54LM20-DK + nRF7002-EBII | ✅ (bancada pendente) |
| [`09_wifi_tcp/`](09_wifi_tcp/) | **Wi-Fi 9** — Lab central da frente: telemetria por socket TCP puro, mesmo payload do lab 10; reconexão com backoff e queda de conexão como o próprio ponto do lab | nRF54LM20-DK + nRF7002-EBII | ✅ |
| [`10_wifi_http_mqtt/`](10_wifi_http_mqtt/) | **Wi-Fi 10** — O mesmo payload do lab 9 recompilado sobre HTTP e MQTT: comparação medida de bytes por amostra, FLASH/RAM, e o custo estrutural do polling HTTP | nRF54LM20-DK + nRF7002-EBII | ✅ |
| [`11_wifi_twt/`](11_wifi_twt/) | **Wi-Fi 11** — A escada de economia de energia: DTIM e listen interval medidos por latência com o firmware do lab 6 (Parte A); TWT preparado para medida de corrente com PPK2 (Parte B), dependente de AP com TWT | nRF54LM20-DK + nRF7002-EBII | ✅ (Parte B pendente) |
| [`12_wifi_coex/`](12_wifi_coex/) | **Wi-Fi 12** — Coexistência BLE×Wi-Fi no mesmo kit: cliente Wi-Fi (zperf) e central BLE (throughput) simultâneos, árbitro de coexistência ligado/desligado por build — o lab mais pesado de RAM da frente | nRF54LM20-DK + nRF7002-EBII + par BLE (nRF54L15-TAG) | ✅ (bancada pendente) |
| [`13_wifi_location/`](13_wifi_location/) | **Wi-Fi 13** — Locationing sem GPS: o kit varre os APs vizinhos e o nRF Cloud resolve a posição pelo banco de mapeamento — fecha o módulo pelo lado de dentro do prédio | nRF54LM20-DK + nRF7002-EBII | ✅ (precisão real pendente) |
| `ntn_nbiot/` | Comunicação NB-IoT via satélite (NTN) — teste ao vivo dependente de janela de passada | nRF9151-SMA-DK | planejado |

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
não do firmware). Um `meu_tag.conf` serve para os três initiators.

### Wi-Fi 6+ — ordem de ensino

```
Wi-Fi 6   shell da Nordic          "o companion visivel"           scan, connect, status
Wi-Fi 7   associacao programada    "conectar sem intervencao"      minha_rede.conf
Wi-Fi 8   provisionamento SoftAP   "a DK escaneia por voce"        HTTPS + protobuf, sem web
Wi-Fi 9   telemetria TCP           "o lab central"                 payload reaproveitado no lab 10, backoff
Wi-Fi 10  HTTP e MQTT              "um payload, tres transportes"  bytes por amostra, polling
Wi-Fi 11  economia de energia      "a escada de tres degraus"      DTIM, listen interval, TWT
Wi-Fi 12  coexistencia BLE x Wi-Fi "duas pilhas de radio juntas"   espectro disputado, medido
Wi-Fi 13  locationing sem GPS      "a posicao nao esta no kit"     varredura + nRF Cloud
```

O par nRF54LM20-DK + nRF7002 EB-II é o mesmo do lab 6 ao 13; só o lab 12 soma um
segundo dispositivo (o par BLE do teste de coexistência). A troca de console — o
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
qualquer build desta frente — ver `PREREQUISITOS.md`.

## Tópicos teóricos

- BLE 6.0 e Channel Sounding: RTT × PBR, initiator/reflector/subevent, Ranging Service por dentro (o serviço GATT do SIG e o que ele carrega), configuração de stack e otimização de pacotes (MTU, DLE, buffers ACL, intervalo de procedure), RAS × IPT como trade-off, segurança, e "o algoritmo é camada de aplicação"
- Wi-Fi 6+ para IoT: integração com companion IC, provisionamento por SoftAP,
  transporte (TCP, HTTP, MQTT sobre o mesmo payload), economia de energia (DTIM,
  listen interval, TWT), coexistência com BLE, e locationing por varredura de APs
- Redes Não Terrestres (NTN): NB-IoT via satélite
