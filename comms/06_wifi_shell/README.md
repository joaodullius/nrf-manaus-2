# Wi-Fi · Lab 6 — O companion visível

> **Antes de tudo: o console mudou de porta.** Com a nRF7002-EB II acoplada, o overlay do
> shield desabilita a `uart20` e move o console para a `uart30` — ou seja, **outra VCOM**.
> Se você abrir a COM de sempre, não verá nada. Abra as duas e veja qual responde.

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

> **A confirmar na bancada.** VCOM observada ao gravar: `COMxx` (preencher depois de
> abrir as duas portas seriais da DK e ver qual responde ao `Enter`).

O motivo já está confirmado na árvore do SDK, mesmo sem a DK na mesa: o overlay do
shield (`zephyr/boards/shields/nrf7002eb2/nrf54lm20.overlay`) traz o comentário

```
/* UART20 conflicts with EB-II shield; use UART30 */
```

e move `zephyr,console`, `zephyr,shell-uart` e companhia para `&uart30`, desabilitando
`&uart20`. A EB-II usa os mesmos pinos que a UART20 da DK reserva para o console normal
— por isso o console muda de porta só por causa do shield, antes mesmo de qualquer
config do sample. O que falta é só a etiqueta: qual VCOM o Windows enumera para a
`uart30` nessa DK específica.

## Passo 3 — explorar

Com o prompt do shell respondendo:

```
wifi scan
wifi connect -s <ssid> -k 1 -p <senha>
wifi status
net iface
```

- `wifi scan` — lista as redes ao alcance, com banda, canal e RSSI de cada uma.
- `wifi connect -s <ssid> -k 1 -p <senha>` — conecta na rede da sala (`-k 1` = WPA2-PSK).
- `wifi status` — banda, canal e RSSI da conexão atual.
- `net iface` — mostra a interface Wi-Fi e o IP obtido por DHCP.

> **A confirmar na bancada.** Resultado de `wifi scan` na sala: (preencher com as redes
> e níveis de RSSI observados).

## O que observar

- O `wifi_shell` não tem lógica de aplicação nenhuma: cada comando fala direto com o
  driver `nrf_wifi` e o `wpa_supplicant` embarcado (`CONFIG_WIFI_NM_WPA_SUPPLICANT=y`).
  É o companion "cru", sem nada do curso por cima — a base para comparar com os labs
  seguintes, que escondem esses comandos atrás de uma aplicação.
- `net iface` só mostra IP depois que o DHCP completa; `wifi status` já responde assim
  que a associação com o AP termina, antes do DHCP.

## Pegadinhas

- **Console mudo na COM de sempre.** Se a DK já foi usada em outro lab sem shield, o
  hábito é abrir a mesma VCOM de novo — mas com a EB-II acoplada o console trocou de
  UART (ver Passo 2). Abra as duas portas seriais da DK e veja qual responde.
- **`sw3` não existe mais.** O overlay do shield remove o botão e o alias junto — não é
  bug do sample, é o pino que a EB-II ocupa.
- **Sem o blob do driver, o build para no CMake.** Este lab depende de
  `west blobs fetch nrf_wifi` já ter rodado nesta instalação do SDK (já rodou). Se o
  CMake reclamar de blob ausente em outra máquina, é isso que falta.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/wifi/shell`
- nRF Connect SDK v3.4.0 — `zephyr/boards/shields/nrf7002eb2` (overlay do console e
  comentário sobre o conflito de UART)
