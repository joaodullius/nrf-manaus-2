# Wi-Fi · Lab 12 — coexistência entre BLE e Wi-Fi

> **Antes de tudo: com a EB II acoplada, a VCOM do console muda.** Sem o shield, o
> console desta DK fica na `uart20`, que sai na **segunda** VCOM do chip de interface
> USB. O overlay do shield (`nrf7002eb2`) desabilita a `uart20` e move o console (e o
> `shell-uart`) para a `uart30` — e essa UART sai na **primeira** VCOM. Quem estava
> acostumado a abrir a segunda porta (firmware sem shield, por exemplo um lab de
> Channel Sounding) precisa trocar para a primeira ao gravar este lab. Esse
> reroteamento é um contorno de um conflito de pinos que existe só na revisão
> **pré-produção** da nRF54LM20-DK, presente no nRF Connect SDK v3.4.0 (Zephyr
> 4.4.0) — nossa árvore. Em versões mais novas do Zephyr o shield deixa de reroteiar
> nessa placa: o console volta para a `uart20`/segunda VCOM e o `sw3` volta a existir.
> Na dúvida, abra as duas portas seriais da DK e veja qual responde.

A turma acabou de medir distância por Channel Sounding usando BLE na faixa de 2,4 GHz
(labs 1–5). Este lab mostra o que acontece quando o **mesmo espectro** é disputado por
dois rádios do mesmo kit ao mesmo tempo: `nrf/samples/wifi/ble_coex` roda um cliente
Wi-Fi (zperf UDP) e um central BLE (throughput) simultaneamente na nRF54LM20-DK com a
nRF7002 EB-II encaixada, e mede o throughput dos dois com o árbitro de coexistência
(`CONFIG_MPSL_CX`) ligado e desligado. É a mesma disputa de meio físico que o CS 4
(lab de segurança) evita nomear — aqui ela fica explícita e medida.

> **Origem.** Cópia integral de `nrf/samples/wifi/ble_coex` do **nRF Connect SDK
> v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE). `prj.conf`,
> `CMakeLists.txt`, `src/main.c` e `src/bt_throughput_test.c` levam o cabeçalho
> `ORIGEM:` do curso. Duas divergências do SDK, as duas descritas abaixo: a
> credencial Wi-Fi sai do `prj.conf` e vai para o `minha_rede.conf`, e o
> `CMakeLists.txt` ganha uma falha proposital quando esse fragmento não foi
> preenchido — mesmo padrão dos labs 7 e 9.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54LM20-DK** (variante B, `nrf54lm20b`) | roda este firmware; DUT com os dois rádios (Wi-Fi cliente + BLE central) |
| **nRF7002 EB-II** | shield companion Wi-Fi 6, encaixado no header de expansão, **com** o fragmento de coexistência `nrf7002eb2_coex` |
| **PC** | terminal serial (VCOM), rede Wi-Fi da sala e servidor iPerf (recebe o UDP do DUT) |
| **nRF54L15-TAG** (par BLE) | roda `nrf/samples/bluetooth/throughput` em modo periférico; par do central BLE deste lab |

> **Dependência de bancada — pendente.** Este lab precisa de um segundo dispositivo
> BLE rodando o sample `nrf/samples/bluetooth/throughput` em modo periférico para o
> central deste firmware conectar. O candidato natural é o **nRF54L15-TAG** já usado
> no módulo de Channel Sounding (labs 1–5) — mas **ele não está conectado nesta
> bancada agora**: só a nRF54LM20-DK com a EB II está montada. Gravar o TAG com o
> sample de throughput BLE, ou substituir por uma segunda DK, é pré-requisito de
> hardware para o Passo 2, e fica para quem for à bancada.

Com o shield acoplado, `sw3` não existe nesta versão do SDK (o overlay não o traz
mais): sobram `sw0`–`sw2` e os quatro LEDs.

## `minha_rede.conf` — a credencial do aluno

O `prj.conf` deste sample, como veio do SDK, tinha `CONFIG_WIFI_CREDENTIALS_STATIC_
SSID="Myssid"` e a senha de exemplo em texto puro — usadas pelo cliente Wi-Fi para
conectar ao AP antes de subir o zperf. O curso tira essas duas linhas do `prj.conf` e
move a credencial para o mesmo fragmento externo dos labs 7 e 9, rastreado pelo git e
**vazio**:

```
CONFIG_WIFI_CREDENTIALS_STATIC_SSID=""
CONFIG_WIFI_CREDENTIALS_STATIC_PASSWORD=""
```

Cada aluno preenche o seu localmente com a rede da sala e compila com o
`EXTRA_CONF_FILE` **escopado pela imagem** — o sysbuild deste lab nomeia a imagem
`12_wifi_coex`, igual ao nome da pasta:

```
-D12_wifi_coex_EXTRA_CONF_FILE=minha_rede.conf
```

**Nunca commitar a senha real.** Antes de qualquer commit, esvaziar o arquivo de
volta:

```
git checkout comms/12_wifi_coex/minha_rede.conf
```

Se o `minha_rede.conf` estiver vazio (o estado padrão do repositório) e o build for
disparado sem o fragmento, o `CMakeLists.txt` para na configuração, antes de compilar
uma linha sequer, com `CONFIG_WIFI_CREDENTIALS_STATIC_SSID nao definido` — confirmado
nesta máquina, mesmo comportamento dos labs 7 e 9.

## O shield é duplo, e a coexistência é escolha de build

Diferente dos labs 6–11, este sample precisa de **dois** fragmentos de shield ao
mesmo tempo — confirmado no `sample.yaml` do próprio sample, na entrada que já cobre
a nossa placa (`sample.54lm20dk.nrf7002eb2.ble_coex`):

```yaml
extra_args:
  - SHIELD="nrf7002eb2;nrf7002eb2_coex"
  - CONFIG_MPSL_CX=y
  - CONFIG_COEX_SEP_ANTENNAS=y
```

* `nrf7002eb2` — o shield base, o mesmo dos labs 6–11 (companion Wi-Fi por SPI).
* `nrf7002eb2_coex` — um **segundo** fragmento de shield, que só acrescenta o nó de
  devicetree `nrf_radio_coex` (as três linhas de GPIO do árbitro de coexistência —
  `status0`, `req`, `grant` — no `nordic_expansion_header`, o mesmo header físico da
  EB II). Sem ele o driver de coexistência não tem para onde apontar os pinos.

O `sample.yaml` do SDK usa o `SHIELD` **sem** prefixo de imagem para este board
target (diferente das entradas para nRF5340, que usam `ble_coex_SHIELD=` porque têm
uma segunda imagem, `ipc_radio`, no núcleo de rede). A nRF54LM20 é single-core como os
labs 6–11: por convenção do curso, o `SHIELD` e o `SNIPPET` seguem escopados pela
imagem, cujo nome no sysbuild é o nome da pasta do lab — `12_wifi_coex`.

**A coexistência liga e desliga é decidida em tempo de compilação**, não por botão ou
shell em runtime: é o Kconfig `CONFIG_MPSL_CX` (confirmado no `README.rst` original do
sample, seção "Building and running"). Por isso este lab gera **dois binários**, um
por regime:

| Regime | Kconfig |
|---|---|
| Coexistência **desligada** | `-DCONFIG_MPSL_CX=n` |
| Coexistência **ligada** | `-DCONFIG_MPSL_CX=y -DCONFIG_COEX_SEP_ANTENNAS=y` |

`CONFIG_COEX_SEP_ANTENNAS` só importa com a coexistência ligada: controla se o
driver assume antenas separadas para Wi-Fi e BLE (`y`, o caso da EB II, que tem
antena dedicada) ou compartilhada (`n`). O `TEST_TYPE_WLAN_BLE` (Wi-Fi e BLE
concorrentes, os dois ligados) é o `default` do `Kconfig` do sample e não muda entre
os dois builds.

## Passo 1 — compilar

Caminho de build curto (evita o limite de caminho do Windows no passo de
empacotamento do sysbuild): `comms/12_wifi_coex/build_on` e `.../build_off`.

Coexistência **ligada**:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/12_wifi_coex/build_on C:/work/nrf-manaus-2/comms/12_wifi_coex -- -D12_wifi_coex_SHIELD="nrf7002eb2;nrf7002eb2_coex" -D12_wifi_coex_SNIPPET=nrf70-wifi -D12_wifi_coex_EXTRA_CONF_FILE=minha_rede.conf -DCONFIG_MPSL_CX=y -DCONFIG_COEX_SEP_ANTENNAS=y
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/12_wifi_coex/build_on
```

Coexistência **desligada**:

```
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/12_wifi_coex/build_off C:/work/nrf-manaus-2/comms/12_wifi_coex -- -D12_wifi_coex_SHIELD="nrf7002eb2;nrf7002eb2_coex" -D12_wifi_coex_SNIPPET=nrf70-wifi -D12_wifi_coex_EXTRA_CONF_FILE=minha_rede.conf -DCONFIG_MPSL_CX=n
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/12_wifi_coex/build_off
```

Os dois builds fecham limpos, `exit 0`, imagem única (o nRF7002 é um companion por
SPI, não um segundo SoC). Nenhum dos dois reduz `CONFIG_MAIN_STACK_SIZE` (5200) nem
`CONFIG_NRF_WIFI_DATA_HEAP_SIZE` (168192) do sample original — são os maiores valores
vistos até aqui na frente de Wi-Fi, porque este lab soma as pilhas de rede do Wi-Fi
**e** as do throughput BLE. Resumo de memória (com credencial de teste preenchida, só
para medir o binário — não a rede da sala):

| Build | FLASH | % FLASH | RAM | % RAM |
|---|---|---|---|---|
| `build_on` (coex ligada) | 741084 B | 35,55% | 374100 B | 71,49% |
| `build_off` (coex desligada) | 740528 B | 35,52% | 374076 B | 71,49% |

A diferença é pequena (556 B de FLASH, 24 B de RAM) — é só o driver `mpsl_cx` sendo
compilado ou não; o resto do binário (Wi-Fi, BLE, zperf, throughput) é idêntico.

71,49% de RAM ainda deixa cerca de **145,7 KiB livres** dos 511 KB da região — folga
confortável. É o percentual mais alto da frente de Wi-Fi até aqui (o lab 9, por
exemplo, usa 36%) porque este é o único lab que mantém as duas pilhas de rádio — Wi-Fi
e BLE — abertas e ativas ao mesmo tempo, em vez de uma de cada vez.

## Passo 2 — bancada

> **A confirmar na bancada.**

Pré-requisitos antes de ligar qualquer coisa:

- [ ] Gravar o par BLE (nRF54L15-TAG ou segunda DK) com `nrf/samples/bluetooth/
      throughput`, papel **periférico**.
- [ ] Subir o servidor iPerf 2.0.5 no PC: `iperf -s -i 1 -u` (Wi-Fi UDP, o DUT é
      cliente). Se o firewall do Windows bloquear a porta na entrada em rede
      Private, ver a seção de pegadinhas do `comms/09_wifi_tcp/README.md` — mesmo
      sintoma (conexão trava sem erro visível dos dois lados), mesmo conserto
      (`New-NetFirewallRule`), porta do iPerf em vez de 9000.
- [ ] Gravar a nRF54LM20-DK com `build_on` (primeira rodada).
- [ ] Abrir a porta serial certa (aviso no topo deste README — primeira VCOM com o
      shield acoplado) e confirmar a conexão Wi-Fi e o pareamento BLE no log de
      boot.

Checklist de medição, uma passada por regime (`build_on`, depois `build_off`):

- [ ] Duração do teste igual nos dois rádios (`CONFIG_WIFI_TEST_DURATION` e
      `CONFIG_BLE_TEST_DURATION`, ambos 20000 ms no sample — não alterados pelo
      curso).
- [ ] Ler o throughput Wi-Fi UDP TX no terminal do iPerf, no PC.
- [ ] Ler o throughput BLE no console serial do par (nRF54L15-TAG ou segunda DK).
- [ ] Repetir para o outro binário e preencher a tabela abaixo.

### Tabela de throughput (a preencher na bancada)

| Regime | Wi-Fi UDP TX | BLE |
|---|---|---|
| Coexistência desligada | > **A confirmar na bancada.** | > **A confirmar na bancada.** |
| Coexistência ligada | > **A confirmar na bancada.** | > **A confirmar na bancada.** |

O `README.rst` original do SDK publica números de referência para o **nRF7002 DK**
(host nRF5340, antenas separadas, Wi-Fi 802.11n em 2,4 GHz): Wi-Fi-only 10,2 Mbps,
BLE-only 1107 kbps, coexistência desligada 9,9 Mbps / 145 kbps, coexistência ligada
8,3 Mbps / 478 kbps. São números da Nordic, em outro hardware — citados aqui só como
ordem de grandeza, atribuídos, e **não entram na tabela do curso**: os quatro valores
acima são os medidos nesta bancada, com este par de kits.

## Pegadinhas

- **A VCOM muda com o shield — não é sempre a mesma porta.** Ver o aviso no topo
  deste README.
- **`sw3` não existe mais** com o shield acoplado nesta versão do SDK.
- **O TAG do Channel Sounding não está conectado nesta bancada agora.** Sem um par
  BLE gravado com o sample de throughput, o central deste lab não tem para onde
  conectar — o teste concorrente não roda. Ver "Hardware" acima.
- **A coexistência é escolha de build, não de shell.** Trocar de regime exige
  recompilar e regravar (`build_on`/`build_off`), não existe comando em runtime para
  isso neste sample.
- **O firewall do Windows bloqueia servidor de rede na entrada em Private.** Mesmo
  sintoma e mesmo conserto do `comms/09_wifi_tcp/README.md`, aplicado ao iPerf em vez
  do `wifi_server.py`.
- **Nunca commitar a credencial real.** `minha_rede.conf` é rastreado e deve
  permanecer vazio no repositório; `git checkout comms/12_wifi_coex/minha_rede.conf`
  antes de qualquer commit.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/wifi/ble_coex` (`README.rst`, `sample.yaml`,
  `Kconfig`)
- nRF Connect SDK v3.4.0 — `zephyr/boards/shields/nrf7002eb2` (`nrf7002eb2_coex.
  overlay`: nó `nrf_radio_coex`, GPIOs `status0`/`req`/`grant` no
  `nordic_expansion_header`)
- Build local, 2026-09-06 — nRF54LM20-DK var. B, `build_on` e `build_off`: FLASH e
  RAM medidos nesta máquina, credencial Wi-Fi de teste (não a da sala)
