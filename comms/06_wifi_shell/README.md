# Wi-Fi · Lab 6 — O companion visível

> **Antes de tudo: o console troca de VCOM.** Com a nRF7002-EB II acoplada, o overlay
> do shield move o console (e o `shell-uart`) da `uart20` para a `uart30` — e isso
> troca também a porta serial do PC. Quem vem dos labs de Channel Sounding (sem
> shield), acostumado com a **segunda** VCOM da DK, precisa abrir a **primeira**
> aqui. Abra as duas e veja qual responde.

Este lab não escreve nenhuma linha de aplicação: é o shell de Wi-Fi da própria Nordic,
`nrf/samples/wifi/shell`, rodando na nRF54LM20-DK com a nRF7002 EB-II encaixada. O que
antes era invisível — o companion Wi-Fi 6 conversando com o host por SPI — vira uma
sessão interativa de shell: `wifi scan`, `wifi connect`, `wifi status`, `net iface`. É a
base de que os labs 7, 8, 11 e 12 partem, e o lugar onde a convenção de cabeçalho e o
aviso de console deste curso aparecem pela primeira vez para Wi-Fi.

> **Origem.** Cópia integral de `nrf/samples/wifi/shell` do **nRF Connect SDK v3.4.0**.
> Licença Nordic preservada em [LICENSE](LICENSE). `prj.conf` e `CMakeLists.txt` levam o
> cabeçalho `ORIGEM:` do curso; nenhum dos dois diverge do SDK.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54LM20-DK** (variante B, `nrf54lm20b`) | roda o firmware; host do Wi-Fi |
| **nRF7002 EB-II** | shield companion Wi-Fi 6, encaixado no header de expansão |
| **PC** | terminal serial (VCOM) e a rede Wi-Fi da sala |

Com o shield acoplado, `sw3` some do overlay nesta versão do SDK (ele não existe
mais): sobram `sw0`–`sw2` e os quatro LEDs. É um comportamento específico do kit
pré-produção — ver a nota de versão no Passo 2.

## Passo 1 — compilar e gravar

Shield e snippet são escopados pela imagem — que o sysbuild nomeia `06_wifi_shell`,
igual ao nome da pasta:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/06_wifi_shell/build_lm20 C:/work/nrf-manaus-2/comms/06_wifi_shell -- -D06_wifi_shell_SHIELD="nrf7002eb2" -D06_wifi_shell_SNIPPET=nrf70-wifi
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/06_wifi_shell/build_lm20
```

Build limpo, `exit 0`, imagem única (o nRF7002 é um companion por SPI, não um segundo
SoC — não há domínio de rede separado para gravar). Resumo de memória:

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 746740 B | 2036 KB | 35,82% |
| RAM | 353824 B | 511 KB | 67,62% |

## Passo 2 — achar o console

Medido nas duas condições, no mesmo kit (nRF54LM20-DK var. B, J-Link 1051898754,
PCA10184):

| Firmware | Console em | Porta | Observado |
|---|---|---|---|
| lab de Channel Sounding (sem shield) | `uart20` (P1.16/P1.17) | **COM22**, a segunda VCOM | sai o boot banner |
| Este lab (com `nrf7002eb2`) | `uart30` (P0.06/P0.07) | **COM21**, a primeira VCOM | sai o prompt |

Em cada condição a outra porta fica muda (0 bytes): **a VCOM muda de fato** entre um
firmware e outro. O motivo já estava confirmado na árvore do SDK antes de ligar a
DK: o overlay do shield (`zephyr/boards/shields/nrf7002eb2/nrf54lm20.overlay`) traz
o comentário

```
/* UART20 conflicts with EB-II shield; use UART30 */
```

e move `zephyr,console`, `zephyr,shell-uart` e companhia da `uart20` para a `uart30`,
desabilitando a `uart20`. No shell deste lab, `device list` mostra só a
`uart@104000` (a `uart30`) registrada — a `uart20` não aparece mais.

### Nota de versão: por que a documentação "latest" da Nordic descreve outro comportamento

O reroteamento é um contorno para um conflito de pinos que existe **só no kit
pré-produção** do nRF54LM20-DK. Em versões de Zephyr posteriores à v3.4.0 usada
neste curso, o shield deixa de reroteiar nessa placa: o console volta para a
`uart20` e o `sw3` deixa de ser apagado. Não é contradição entre fontes — é versão.
Ao comparar com a documentação online, confira sempre o overlay da árvore
efetivamente instalada, não a versão "latest".

## Passo 3 — a sessão completa, comando a comando

Tudo abaixo foi capturado nesta bancada em 2026-09-07 (nRF54LM20-DK var. B, J-Link
1051898754, AP Askey 802.11ax). **São respostas reais, não exemplos.** Cada campo está
explicado, e onde faz diferença está dito a que geração de Wi-Fi ele pertence.

### 1. `device list` — o companion apareceu?

Antes de qualquer comando de rádio, confirme que a EB II foi enumerada:

```
wifi_shell:~$ device list
devices:
- spi@c8000 (READY)    DT node labels: spi22 nordic_expansion_spi
- wlan0 (READY)        DT node labels: wlan0
- uart@104000 (READY)  DT node labels: uart30
```

| O que procurar | Por quê |
|---|---|
| `spi@c8000 (READY)` | é o barramento SPI que liga o host ao nRF7002. Sem ele, o shield não está encaixado ou não foi detectado |
| `wlan0 (READY)` | a interface de rede que o driver `nrf_wifi` criou por cima do SPI |
| só `uart@104000` (a `uart30`) | a `uart20` **sumiu** — é a troca de VCOM avisada no topo deste README |

Se `wlan0` não aparecer, não adianta tentar `wifi scan`.

### 2. `wifi scan` — o que existe no ar

```
wifi_shell:~$ wifi scan
Scan requested
Num | SSID           (len) | Chan (Band)   | RSSI | Security        | BSSID             | MFP
1   | #CLARO-WIFI    11    | 4    (2.4GHz) | -34  | OPEN            | 02:01:12:96:C4:5E | Disable
3   | PepeuNet-6G    11    | 6    (2.4GHz) | -43  | WPA2-PSK        | 44:89:6D:61:58:CF | Disable
5   | PepeuNet-6G    11    | 52   (5GHz  ) | -50  | WPA2-PSK        | 44:89:6D:61:58:CE | Disable
21  |                0     | 6    (2.4GHz) | -83  | WPA2 Enterprise | 5C:F7:96:FD:A7:90 | Disable
...
Scan request done
```

Nesta captura vieram **26 redes**. Campo a campo:

| Campo | O que é |
|---|---|
| `SSID` / `(len)` | o nome da rede e seu comprimento. **`len 0` é rede oculta** — o AP não anuncia o nome |
| `Chan (Band)` | canal e banda. Canais 1–14 são 2,4 GHz; 36 e acima são 5 GHz |
| `RSSI` | potência recebida em dBm, sempre negativa. −34 é forte, −90 é no limite |
| `Security` | `OPEN`, `WPA-PSK`, `WPA2-PSK`, `WPA2 Enterprise`. **Define o `-k` do `connect`** |
| `BSSID` | o MAC do **rádio** do AP — não do AP inteiro |
| `MFP` | *Management Frame Protection*, do **802.11w**: protege os quadros de gerência, como um `deauth` forjado |

**A observação que rende aula:** a rede da bancada aparece **duas vezes**, com o mesmo
SSID e **BSSIDs diferentes** (`...58:CF` no canal 6, `...58:CE` no canal 52). É *um* AP
com *dois* rádios. O aluno escolhe qual usar com o `-b` do `connect` — e vai medir
consumo diferente em cada um (lab 11).

### 3. `wifi connect` — associar

```
wifi_shell:~$ wifi connect -s PepeuNet-6G -k 1 -p <senha> -b 5
<inf> wpa_supp: wlan0: WPA: Key negotiation completed with 44:89:6d:61:58:ce [PTK=CCMP GTK=CCMP]
<inf> wpa_supp: wlan0: CTRL-EVENT-CONNECTED - Connection to 44:89:6d:61:58:ce completed
<inf> net_dhcpv4: Received: 192.168.15.19
```

| Opção | Significado |
|---|---|
| `-s <ssid>` | o nome da rede |
| `-k <n>` | o modo de segurança. **`1` = WPA2-PSK**, `0` = aberta, `2` = WPA2-EAP, `3` = WPA3-SAE. Tem de bater com a coluna `Security` do scan |
| `-p <senha>` | a chave pré-compartilhada |
| `-b <2/5/6>` | a banda — **é o que decide qual dos dois rádios do AP** você usa |

**Três eventos distintos em cerca de 250 ms**, e vale separá-los para a turma:

1. **`Key negotiation completed ... [PTK=CCMP GTK=CCMP]`** — o *4-way handshake* do WPA2.
   A **PTK** protege o tráfego só desta estação; a **GTK** protege o que o AP manda em
   broadcast e multicast para todas. `CCMP` é a cifra, baseada em AES. Isto é **WPA2, de
   2004** — não há nada de Wi-Fi 6 nesta etapa.
2. **`CTRL-EVENT-CONNECTED`** — a associação terminou; o link existe.
3. **`net_dhcpv4: Received: ...`** — só agora há **IP**. Associação e endereço são coisas
   separadas, e o lab 7 mostra isso ainda mais claramente.

### 4. `wifi status` — o estado do link

```
wifi_shell:~$ wifi status
Status: successful
==================
State: COMPLETED          Interface Mode: STATION
Link Mode: UNKNOWN        SSID: PepeuNet-6G
BSSID: 44:89:6D:61:58:CE  Band: 5GHz           Channel: 52
Security: WPA2-PSK        MFP: Optional        RSSI: -50
Beacon Interval: 100      DTIM: 3              TWT: Not supported
Current PHY TX rate (Mbps) : 537179.8
```

| Campo | O que é | Geração |
|---|---|---|
| `State: COMPLETED` | associado. Outros valores: `SCANNING`, `AUTHENTICATING`, `DISCONNECTED` | — |
| `Interface Mode: STATION` | é cliente, não ponto de acesso (o lab 8a mostra o outro modo) | — |
| `Link Mode` | a geração negociada: `WIFI 4 (802.11n)`, `WIFI 5 (ac)`, **`WIFI 6 (802.11ax/HE)`** | ver abaixo |
| `Beacon Interval: 100` | o AP anuncia a cada 100 ms | 802.11 original |
| **`DTIM: 3`** | a cada 3 beacons, um carrega o DTIM — **300 ms**. **Quem decide é o AP**; a estação só lê | 802.11 original |
| **`TWT`** | se o AP negocia *Target Wake Time* | **Wi-Fi 6** |
| `MFP: Optional` | 802.11w. Note que o scan dizia `Disable` e aqui diz `Optional` | 802.11w |

**Duas armadilhas medidas neste comando:**

- **`Link Mode: UNKNOWN` em 5 GHz.** Reconectando o **mesmo AP** em 2,4 GHz, o campo vem
  `WIFI 6 (802.11ax/HE)`. Não significa que a BSS de 5 GHz não seja `ax` — é o driver não
  preenchendo o campo naquela BSS. **A evidência positiva de que o AP é Wi-Fi 6 vem do
  rádio de 2,4 GHz.**
- **`Current PHY TX rate` não serve como métrica.** Logo depois de conectar veio
  **537179,8 Mbps**, um valor impossível; segundos depois, 1,0 e 8,6 Mbps. Não use esse
  campo para nada.

### 5. `net iface` — a visão da pilha IP

```
wifi_shell:~$ net iface
Interface wlan0 (WiFi) [1]
Link addr : F4:CE:36:00:D2:10       MTU : 1492
Status    : oper=UP, admin=UP, carrier=ON
Ethernet capabilities supported: TX checksum offload, RX checksum offload, ...
IPv4 unicast addresses (max 1): 192.168.15.19/255.255.255.0 DHCP preferred
IPv4 gateway : 192.168.15.1         DHCPv4 lease time : 14400
IPv6 unicast addresses: fe80::f6ce:36ff:fe00:d210
                        2804:7f4:c013:9aa9:f6ce:36ff:fe00:d210
```

Três coisas para apontar:

- **`Link addr` é o MAC do nRF7002**, gravado na OTP do próprio companion.
- **Aparece "Ethernet capabilities" numa interface Wi-Fi.** Não é erro: o nRF7002 é
  **FullMAC** — o 802.11 roda dentro dele, e o host troca **quadros Ethernet** pelo SPI.
  Para a pilha do Zephyr, `wlan0` é uma placa de rede comum.
- **Um IPv6 global subiu sozinho** (`2804:...`), por SLAAC, sem ninguém pedir.

### 6. `wifi ps` — o estado de economia de energia

```
wifi_shell:~$ wifi ps
PS status: Power save enabled     PS mode: Legacy power save
PS listen_interval: 10            PS wake up mode: DTIM
PS timeout: 100 ms                PS exit strategy: Custom algorithm
No TWT flows
```

| Campo | O que é |
|---|---|
| `PS status` | **já vem ligado** — o rádio dorme entre beacons por padrão |
| `PS mode: Legacy` | o algoritmo clássico; a alternativa é `WMM` |
| `PS listen_interval: 10` | quantos beacons a estação **pode** pular. Só vale se o modo de acordar for `listen_interval` |
| `PS wake up mode: DTIM` | acordando no DTIM — 300 ms aqui. A alternativa é `listen_interval` |
| `PS timeout: 100 ms` | o *inactivity timer* do **dynamic power save**: depois de tráfego, o rádio fica acordado 100 ms antes de voltar a dormir |
| `No TWT flows` | nenhuma sessão TWT ativa — coerente com o `TWT: Not supported` do `status` |

O `PS timeout` explica um comportamento que confunde muita gente: **pings em rajada medem
~8 ms** e escondem completamente o efeito do power save, porque depois do primeiro pacote
o rádio fica acordado. O lab 11 mede isso direito, com pings isolados.

### Os LEDs neste lab

**Nenhum.** O `wifi_shell` não aciona LED algum — tudo acontece no console. Vale dizer,
porque os labs 7, 8a, 8b, 9 e 10 usam LEDs e o aluno pode ficar procurando sinal na placa.
## TWT — Wi-Fi 6 não garante TWT

O AP da bancada é 802.11ax confirmado (seção anterior). Mesmo assim, ele **não é
TWT capable**. É um bom material de aula por si só: TWT é um recurso opcional do
padrão 802.11ax, não obrigatório — "AP Wi-Fi 6" não implica "AP com TWT".

Antes de tentar negociar, o rádio do DK já estava em power save — isso descarta a
hipótese de falso negativo do nosso lado. (Os termos abaixo — power save, DTIM,
TWT — ganham a explicação completa, a escada de três degraus, no lab 11; aqui
bastam para ler o resultado.)

```
PS status: Power save enabled
PS mode: Legacy power save
PS wake up mode: DTIM
No TWT flows
```

`wifi status` também reporta `TWT: Not supported` nas duas bandas. A tentativa de
negociação:

```
wifi twt quick_setup 65024 524288
```

devolveu, nas duas bandas:

```
TWT setup with TWT individual negotiation failed, reason : Peer not TWT capable
```

Conclusão medida: o AP desta bancada não anuncia TWT Responder. O lab 11 (TWT)
continua dependendo de um AP que implemente TWT (TP-Link EX3000) — esta sonda não
muda esse plano, só fecha a dúvida com evidência de que "Wi-Fi 6" sozinho não
resolve.

## O que observar

- O `wifi_shell` não tem lógica de aplicação nenhuma: cada comando fala direto com o
  driver `nrf_wifi` e o `wpa_supplicant` embarcado (`CONFIG_WIFI_NM_WPA_SUPPLICANT=y`).
  É o companion "cru", sem nada do curso por cima — a base para comparar com os labs
  seguintes, que escondem esses comandos atrás de uma aplicação.
- `net iface` só mostra IP depois que o DHCP completa; `wifi status` já responde assim
  que a associação com o AP termina, antes do DHCP.
- Um AP "802.11ax" no rótulo não é garantia de TWT, nem de link mode reportado em
  todas as bandas — o shell mostra os dois lados dessa lacuna (seção TWT acima e o
  `UNKNOWN` do 5 GHz).

## Pegadinhas

- **Console na porta errada.** Quem vem de um lab de Channel Sounding (sem shield)
  está acostumado com a segunda VCOM da DK; aqui o console está na primeira. Abra as
  duas e confirme (ver Passo 2).
- **`sw3` não existe mais nesta versão do SDK.** O overlay do shield remove o botão e
  o alias junto — não é bug do sample, é o contorno do conflito de pinos do kit
  pré-produção (some nesta versão, volta em versões futuras do Zephyr).
- **Sem o blob do driver, o build para no CMake.** Este lab depende de
  `west blobs fetch nrf_wifi` já ter rodado nesta instalação do SDK (já rodou). Se o
  CMake reclamar de blob ausente em outra máquina, é isso que falta.
- **`wifi twt setup` na forma longa (por opções) é frágil.** A variante com `-n -c
  -t -f -r -T -I -a -w -p -D -d -e -m` exige exatamente 25 argumentos e devolve
  "Too many arguments" ao menor deslize. É um caso diferente da forma **posicional**
  do material online (`wifi twt setup 0 0 1 1 ...`), que falha com outro erro
  (`wrong parameter count` — ver lab 11). Para o lab, usar a forma curta:
  `wifi twt quick_setup <wake_interval_us> <interval_us>`.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/wifi/shell`
- nRF Connect SDK v3.4.0 — `zephyr/boards/shields/nrf7002eb2` (overlay do console e
  comentário sobre o conflito de UART)
- Nordic, guia de migração de versões do Zephyr (consultado via MCP
  `nordic-semiconductor`) — confirma que o reroteamento de UART é específico do kit
  pré-produção do nRF54LM20-DK e não se repete em versões futuras
- Bancada `nrf-manaus-2`, 2026-09-06 — nRF54LM20-DK var. B (J-Link 1051898754) +
  nRF7002 EB-II, AP 802.11ax da sala
