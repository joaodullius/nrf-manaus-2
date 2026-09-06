# Wi-Fi · Lab 6 — O companion visível

> **Antes de tudo: o console muda de UART, não necessariamente de porta.** Com a
> nRF7002-EB II acoplada, o overlay do shield desabilita a `uart20` e move o console
> (e o `shell-uart`) para a `uart30` — são periféricos diferentes, e por isso um
> firmware compilado sem o shield e um compilado com o shield **não são
> intercambiáveis**: o console de um não fala na UART do outro. Isso não quer dizer
> que a porta serial do PC muda: na bancada em que este lab foi validado, as duas
> UARTs saem na mesma VCOM (a interface USB do kit não diferencia uma da outra), e o
> prompt respondeu na porta de sempre. Trate isso como precaução, não como previsão —
> abra as duas portas seriais da DK e veja qual responde.

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

Com o shield acoplado, `sw3` some do overlay (ele não existe mais): sobram `sw0`–`sw2`
e os quatro LEDs.

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

O DK expõe duas VCOMs para o PC. Na bancada em que este lab foi validado (J-Link
1051898754, PCA10184): **o prompt respondeu na primeira VCOM (a de sempre); a
segunda ficou muda** — nenhum byte saiu dela.

O motivo já estava confirmado na árvore do SDK antes mesmo de ligar a DK: o overlay
do shield (`zephyr/boards/shields/nrf7002eb2/nrf54lm20.overlay`) traz o comentário

```
/* UART20 conflicts with EB-II shield; use UART30 */
```

e move `zephyr,console`, `zephyr,shell-uart` e companhia da `uart20` para a `uart30`,
desabilitando a `uart20`. A bancada confirmou o lado do dispositivo: no shell,
`device list` mostra só a `uart@104000` (a `uart30`) registrada — a `uart20` não
aparece mais. E confirmou também o lado do PC: as duas UARTs, apesar de serem
periféricos diferentes do SoC, saem fisicamente na **mesma** VCOM do chip de
interface USB desta DK — por isso a porta de sempre continuou respondendo. Essa
coincidência de fiação é do kit, não do overlay; **não assuma que se repete em outra
DK ou instalação** — daí a orientação de abrir as duas portas por precaução.

## Passo 3 — explorar

Antes de qualquer comando de rádio, confirme que o companion apareceu:

```
wifi_shell:~$ device list
```

Espera-se `wlan0 (READY)` e `spi@c8000 (spi22 / nordic_expansion_spi)` na lista — é
assim que se sabe que a EB II está acoplada e enumerada, antes de gastar tempo
tentando `wifi scan` num companion que não subiu.

```
wifi scan
wifi connect -s <ssid> -k 1 -p <senha> -b 5
wifi status
net iface
```

- `wifi scan` — lista as redes ao alcance, com banda, canal e RSSI de cada uma.
- `wifi connect -s <ssid> -k 1 -p <senha> -b 5` — conecta na rede da sala (`-k 1` =
  WPA2-PSK; `-b` escolhe a banda, `2` ou `5`).
- `wifi status` — banda, canal e RSSI da conexão atual.
- `net iface` — mostra a interface Wi-Fi e o IP obtido por DHCP.

### `wifi scan` — o que apareceu na bancada

25 redes ao todo. A rede da bancada apareceu duas vezes — uma por banda, com BSSIDs
diferentes:

| SSID | Canal | Banda | RSSI | Segurança | BSSID |
|---|---|---|---|---|---|
| `<ssid>` (rede da bancada) | 6 | 2,4 GHz | -35 | WPA2-PSK | 44:89:6D:61:58:CF |
| `<ssid>` (rede da bancada) | 52 | 5 GHz | -48 | WPA2-PSK | 44:89:6D:61:58:CE |

MFP apareceu como `Disable` no scan e `Optional` depois de associado. Sem WPA3 nesta
rede — `-k 1` (WPA2-PSK) é o modo certo.

### `wifi connect` e `net iface`

Associação, 4-way handshake e DHCP fecharam em cerca de 1 s. IP obtido:
`192.168.15.11/24`, gateway `192.168.15.1`, lease de 14400 s (4 h). Um endereço
IPv6 global também sobe, do prefixo do provedor.

### `wifi status` — o modo de link por banda

| Banda | Canal | Link Mode reportado | RSSI |
|---|---|---|---|
| 2,4 GHz | 6 | **WIFI 6 (802.11ax/HE)** | -38 |
| 5 GHz | 52 | UNKNOWN | -47 / -53 |

O 5 GHz reportou `UNKNOWN` em duas conexões seguidas, mesmo depois de deixar o link
assentar — não é evidência de que o 5 GHz não seja `ax`, é o driver não preenchendo
esse campo para essa BSS. O 2,4 GHz é a evidência positiva de que o AP é Wi-Fi 6 de
verdade.

> **Cuidado com o `Current PHY TX rate`.** Logo depois de conectar, esse campo veio
> com um valor absurdo (537179,8 Mbps); segundos depois, valores plausíveis (1,0 /
> 8,6 Mbps). Não usar esse campo como métrica no curso — ele não é confiável logo
> após a associação.

## TWT — Wi-Fi 6 não garante TWT

O AP da bancada é 802.11ax confirmado (seção anterior). Mesmo assim, ele **não é
TWT capable**. É um bom material de aula por si só: TWT é um recurso opcional do
padrão 802.11ax, não obrigatório — "AP Wi-Fi 6" não implica "AP com TWT".

Antes de tentar negociar, o rádio do DK já estava em power save — isso descarta a
hipótese de falso negativo do nosso lado:

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

- **Console mudo numa das duas VCOMs.** Se a DK já foi usada em outro lab sem
  shield, o hábito é abrir a mesma porta de novo. Nesta bancada isso funcionou (as
  duas UARTs saem na mesma VCOM), mas é fiação do kit, não garantia do overlay —
  abra as duas e confirme (ver Passo 2).
- **`sw3` não existe mais.** O overlay do shield remove o botão e o alias junto — não é
  bug do sample, é o pino que a EB-II ocupa.
- **Sem o blob do driver, o build para no CMake.** Este lab depende de
  `west blobs fetch nrf_wifi` já ter rodado nesta instalação do SDK (já rodou). Se o
  CMake reclamar de blob ausente em outra máquina, é isso que falta.
- **`wifi twt setup` na forma longa é frágil.** A variante com `-n -c -t -f -r -T -I
  -a -w -p -D -d -e -m` exige exatamente 25 argumentos e devolve "Too many
  arguments" ao menor deslize. Para o lab, usar a forma curta:
  `wifi twt quick_setup <wake_interval_us> <interval_us>`.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/wifi/shell`
- nRF Connect SDK v3.4.0 — `zephyr/boards/shields/nrf7002eb2` (overlay do console e
  comentário sobre o conflito de UART)
- Bancada `nrf-manaus-2`, 2026-09-06 — nRF54LM20-DK var. B (J-Link 1051898754) +
  nRF7002 EB-II, AP 802.11ax da sala
