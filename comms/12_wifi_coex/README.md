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

Cada aluno preenche o seu localmente com a rede da sala e compila com:

```
-D12_wifi_coex_EXTRA_CONF_FILE=minha_rede.conf
```

Opções de Kconfig e arquivos de fragmento como este, no sysbuild, valem para a
**aplicação principal** com ou sem o prefixo de imagem — é assim de propósito, para o
mesmo comando funcionar com ou sem sysbuild. No lab 7, compilar dos dois jeitos deu
binário byte a byte idêntico.

Mesmo assim, **o curso escreve sempre a forma prefixada**, em todos os labs. Dois
motivos. O primeiro é não obrigar o aluno a guardar qual opção aceita as duas formas e
qual não aceita — para o `SHIELD` e o `SNIPPET` do Passo 1 o prefixo **é** obrigatório,
por um motivo diferente (ver a seção abaixo). O segundo é uma observação de bancada que
continua sem explicação: no lab 9, um build com `EXTRA_CONF_FILE` **sem** prefixo saiu
com a senha vazia, o que a forma prefixada não reproduziu. Não sabemos por quê, não
conseguimos reproduzir sob demanda, e não vale arriscar a aula: use a forma prefixada.

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

Aqui o prefixo importa de verdade — diferente do `EXTRA_CONF_FILE` da seção
anterior. `SHIELD` e `SNIPPET` sem prefixo de imagem, no sysbuild, valem para
**todas** as imagens do build, não só a principal; num sample com mais de uma
imagem (o próprio `ble_coex`, no nRF5340, soma a imagem `ipc_radio` do núcleo de
rede) isso pode aplicar um shield ou snippet incompatível na imagem errada e
quebrar o build. Já uma opção de Kconfig ou um arquivo de fragmento, sem
prefixo, já significa "aplicação principal" por padrão — não precisa do
prefixo para chegar lá. Como este é o lab com shield **duplo** da frente, é o
melhor lugar para fixar essa diferença: o prefixo é obrigatório para `SHIELD`/
`SNIPPET` (o valor pode ir parar na imagem errada sem ele), e opcional — só por
consistência — para `EXTRA_CONF_FILE` e demais opções de Kconfig.

**A coexistência liga e desliga é decidida em tempo de compilação**, não por botão ou
shell em runtime: é o Kconfig `CONFIG_MPSL_CX` (confirmado no `README.rst` original do
sample, seção "Building and running"). Por isso este lab gera **dois binários**, um
por regime:

| Regime | Kconfig |
|---|---|
| Coexistência **desligada** | `-D12_wifi_coex_CONFIG_MPSL_CX=n` |
| Coexistência **ligada** | `-D12_wifi_coex_CONFIG_MPSL_CX=y -D12_wifi_coex_CONFIG_COEX_SEP_ANTENNAS=y` |

`CONFIG_COEX_SEP_ANTENNAS` só importa com a coexistência ligada: controla se o
driver assume antenas separadas para Wi-Fi e BLE (`y`, o caso da EB II, que tem
antena dedicada) ou compartilhada (`n`). Com o shield de coexistência ele já vem `y`
por padrão — a linha de build o passa mesmo assim, para o regime ficar legível na
própria linha em vez de depender do que o shield decide. O `TEST_TYPE_WLAN_BLE` (Wi-Fi e BLE
concorrentes, os dois ligados) é o `default` do `Kconfig` do sample e não muda entre
os dois builds.

## O IP do servidor de tráfego — `CONFIG_NET_CONFIG_PEER_IPV4_ADDR`

Além da credencial Wi-Fi, este lab precisa saber o IP do PC que roda o servidor
de tráfego (iPerf, para o lado Wi-Fi) — o mesmo papel que `CONFIG_LAB_SERVIDOR_IP`
tem no lab 9. O `Kconfig` do sample define `CONFIG_NET_CONFIG_PEER_IPV4_ADDR`
com o padrão `192.168.1.253` — um endereço de exemplo do SDK que **não existe**
na rede da sala. Compilar sem sobrescrever esse valor grava um kit que manda
todo o tráfego Wi-Fi para um destino inexistente: o lado Wi-Fi da medida
simplesmente não acontece, sem nenhum erro que aponte para a causa.

Descubra o IP do PC na rede da sala (`ipconfig`, no PowerShell) e passe-o na
linha de build — é uma opção de Kconfig, mesma regra do `EXTRA_CONF_FILE` explicada
acima, e por isso escrita com o mesmo prefixo de imagem:

```
-D12_wifi_coex_CONFIG_NET_CONFIG_PEER_IPV4_ADDR=\"<ip-do-pc>\"
```

**Nunca commitar o IP real** — ele só entra na linha de comando, nunca em um
arquivo versionado.

## Passo 1 — compilar

Caminho de build curto (evita o limite de caminho do Windows no passo de
empacotamento do sysbuild): `comms/12_wifi_coex/build_on` e `.../build_off`.

Coexistência **ligada**:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/12_wifi_coex/build_on C:/work/nrf-manaus-2/comms/12_wifi_coex -- -D12_wifi_coex_SHIELD="nrf7002eb2;nrf7002eb2_coex" -D12_wifi_coex_SNIPPET=nrf70-wifi -D12_wifi_coex_EXTRA_CONF_FILE=minha_rede.conf -D12_wifi_coex_CONFIG_NET_CONFIG_PEER_IPV4_ADDR=\"<ip-do-pc>\" -D12_wifi_coex_CONFIG_MPSL_CX=y -D12_wifi_coex_CONFIG_COEX_SEP_ANTENNAS=y
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/12_wifi_coex/build_on
```

Coexistência **desligada**:

```
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/12_wifi_coex/build_off C:/work/nrf-manaus-2/comms/12_wifi_coex -- -D12_wifi_coex_SHIELD="nrf7002eb2;nrf7002eb2_coex" -D12_wifi_coex_SNIPPET=nrf70-wifi -D12_wifi_coex_EXTRA_CONF_FILE=minha_rede.conf -D12_wifi_coex_CONFIG_NET_CONFIG_PEER_IPV4_ADDR=\"<ip-do-pc>\" -D12_wifi_coex_CONFIG_MPSL_CX=n
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

> **Medido em 2026-09-07.** Kit nRF54LM20-DK var. B + nRF7002-EB II (shield duplo), par
> BLE na nRF54L15-DK. Os resultados estão na tabela de throughput, mais abaixo.

Pré-requisitos antes de ligar qualquer coisa:

- [x] **Par BLE: use a nRF54L15-DK, não a TAG.** Gravar com
      `nrf/samples/bluetooth/throughput` (`-b nrf54l15dk/nrf54l15/cpuapp`) e escolher o
      papel **digitando `peripheral` no shell** — o sample tem `CONFIG_SHELL=y`, então
      **não é preciso apertar botão nenhum**. Medido nesta bancada: o console dessa DK é
      a **segunda VCOM** (COM7 aqui); a primeira fica muda. A resposta esperada é
      `Peripheral. Starting advertising`.

      Com a **TAG** (que não tem console) o botão seria o único caminho, e o `README` do
      sample publica **duas numerações** conforme a placa (`Button 1/2` numas, `Button
      0/1` noutras) — mais uma razão para preferir a DK.
- [x] **Servidor de tráfego: iPerf 2.2.1 no PC.** `iperf -s -u -i 1 -p 5001`. A série 2.x
      fala o protocolo que o `zperf` do Zephyr espera; o **`iperf3` não serve**.

      > **Baixe o binário da arquitetura certa.** As páginas de release publicam x64 e
      > ARM64 com o mesmo nome de arquivo. O ARM64 numa máquina Intel falha com uma
      > mensagem que não denuncia a causa (`not a valid application for this OS platform`).
      > Aconteceu nesta bancada. Ver `PREREQUISITOS.md`.

      **Alternativa sem iPerf, se faltar o binário:** um sorvedouro UDP em Python mede o
      throughput do lado do PC. Funciona, mas não devolve o relatório do protocolo iperf 2,
      então o `zperf` do kit termina com `net_zperf: Stats receive timeout` e
      `ble_coex: UDP session error` — **esperado com esse método**, e some com o iPerf de
      verdade. Também não dá perda nem jitter.

      **Firewall:** este lab usa **UDP 5001**, a quarta porta diferente do módulo. Sem a
      regra de entrada o teste mede zero, em silêncio dos dois lados.
- [x] Gravar a nRF54LM20-DK com `build_on` (primeira rodada).
- [ ] Abrir a porta serial certa (aviso no topo deste README — primeira VCOM com o
      shield acoplado) e confirmar a conexão Wi-Fi e o pareamento BLE no log de
      boot.

Checklist de medição, uma passada por regime (`build_on`, depois `build_off`):

- [x] Duração do teste igual nos dois rádios (`CONFIG_WIFI_TEST_DURATION` e
      `CONFIG_BLE_TEST_DURATION`, ambos 20000 ms no sample — não alterados pelo
      curso).
- [x] Ler o throughput Wi-Fi UDP TX **no sorvedouro do PC** (com iPerf 2.0.5 seria no terminal dele; ver acima).
- [x] Ler o throughput BLE no console serial do par (nRF54L15-TAG ou segunda DK).
- [x] Repetir para o outro binário e preencher a tabela abaixo.

### Tabela de throughput (a preencher na bancada)

| Regime | Wi-Fi UDP TX | BLE |
|---|---|---|
| **Wi-Fi sozinho** (`TEST_TYPE_WLAN_ONLY`) | **3,07 Mbps** | — |
| **BLE sozinho** (`TEST_TYPE_BLE_ONLY`) | — | **568 kbps** |
| Ambos · coexistência **desligada** | 2,95 ± 0,03 Mbps (n=3) | 455 ± 61 kbps (n=3) |
| Ambos · coexistência **ligada** | 2,91 ± 0,02 Mbps (n=4) | 414 ± 23 kbps (n=4) |

Medido em 2026-09-07 com **iPerf 2.2.1** no PC (`iperf -s -u -i 1 -p 5001`) e o par BLE
numa nRF54L15-DK. Perda de pacotes Wi-Fi: **0%** em todas as rodadas; jitter 2,2–3,2 ms.

### Como ler esta tabela

**O custo da convivência é real e assimétrico:** pondo os dois rádios para trabalhar
juntos, o Wi-Fi perde **4%** (3,07 → 2,95 Mbps) e o BLE perde **20%** (568 → 455 kbps).
O rádio mais fraco paga a conta.

**O árbitro de coexistência não recupera nada nesta montagem** — pelo contrário, deixa os
dois marginalmente piores (Wi-Fi −1,4%, BLE dentro do ruído). Isso não é um defeito do
lab; é o resultado, e ele tem duas explicações que se somam:

1. **A chave de RF não existe aqui.** Conferido nas `.config` das duas variantes:
   `CONFIG_NRF70_SR_COEX_RF_SWITCH` fica **`n`** nos dois binários — a opção depende de
   `srrf-switch-gpios` no nó `nrf70`, que o overlay da EB II nesta placa não declara, e
   todo build emite o aviso `was assigned the value 'y' but got the value 'n'`. O que
   difere entre `build_on` e `build_off` é só o `MPSL_CX`, o árbitro de **software** (556 B
   de FLASH). Ele sinaliza, mas não há hardware para agir sobre o sinal — sobra o custo.
2. **Há pouco tráfego para arbitrar.** Nossa carga de Wi-Fi é de 3 Mbps; a referência da
   Nordic roda a 10,2 Mbps. Com menos tempo de ar disputado, há menos colisão a evitar.

O contraste com a referência mostra isso com números: lá, **sem** árbitro o BLE despenca
**87%** (1107 → 145 kbps), e o árbitro recupera boa parte (→ 478 kbps, ao custo de −19% no
Wi-Fi). Aqui o BLE perde só 20% sem árbitro — **o problema que o árbitro existe para
resolver mal aparece nesta bancada.**

### Por que o Wi-Fi só dá 3 Mbps, e não 10 — investigado por eliminação

O sample **pede** 10 Mbps: `CONFIG_WIFI_ZPERF_RATE=10000` (kbps), que o `main.c` passa
como `params.rate_kbps`. Entregamos ~3,1 — não é configuração faltando, é um teto. Três
variações foram medidas para achá-lo:

| Variação | Wi-Fi UDP TX | Perda |
|---|---|---|
| 2,4 GHz · SPI 8 MHz (padrão) | 3,07 Mbps | 0/7492 (0%) |
| 2,4 GHz · **SPI 16 MHz** | 3,15 Mbps | 4/7536 (0,05%) |
| **5 GHz** · SPI 8 MHz | 3,11 Mbps | 0/7394 (0%) |

**Dobrar o barramento não muda nada (+2,6%).** O overlay da EB II fixa
`spi-max-frequency = <DT_FREQ_M(8)>`; subindo para 16 MHz (`&nrf70 { spi-max-frequency =
<16000000>; }`) o log confirma `SPIM spi@c8000: freq = 16 MHz` — e o throughput fica onde
estava. **O SPI nunca esteve saturado.**

**Trocar de banda não muda nada.** Com `CONFIG_COEX_WLAN_2PT4G=n` o kit associa em 5 GHz
(canal 52, confirmado no log) e entrega os mesmos 3,1 Mbps. **O enlace de rádio também não
é o gargalo.**

**Sobra o host.** Por eliminação, o teto está na geração dos pacotes: o nRF54LM20 —
Cortex-M33 a 128 MHz, single-core — passando 1024 bytes por datagrama pela pilha de rede
do Zephyr e pelo `zperf`. A referência da Nordic roda num **nRF5340**, dual-core, na
nRF7002-DK. **A diferença não está no rádio: os dois usam o mesmo nRF7002.** Está em quem
alimenta o rádio.

> **Isto não foi confirmado diretamente** — seria preciso instrumentar a CPU ou variar o
> tamanho do pacote. É uma conclusão por eliminação de três hipóteses testadas, o que é
> mais forte que uma explicação plausível, mas menos que uma medida.

**Consequência para a leitura da tabela:** os 10,2 Mbps do `README.rst` do SDK são de
outro host. Comparar os nossos números com os deles compara **duas CPUs**, não duas
soluções de Wi-Fi.

**E é o que explica o efeito pequeno da coexistência.** Com 3 Mbps o rádio Wi-Fi ocupa um
terço do tempo de ar que ocuparia a 10 Mbps; sobra espaço para o BLE, que por isso perde
só 20% em vez de 87% — e o árbitro fica sem o problema que existe para resolver.

> **Lição de método, registrada de propósito.** A primeira versão deste README afirmava,
> com segurança, que o teto era o SPI de 8 MHz: a conta fechava (~38% de eficiência) e a
> comparação com o QSPI da DK era elegante. **Estava errada**, e só se soube porque o
> clock foi dobrado e medido. Explicação plausível que fecha a conta não é evidência.

> **Sobre o QSPI**, que é a pergunta natural: o **nRF54LM20 não tem o periférico** — zero
> menções nos devicetree do SoC, e nenhum shield nRF7002 traz overlay QSPI nesta versão do
> SDK. Existe no nRF5340. Mas, como o SPI não é o gargalo, o QSPI também não resolveria.

> **Sobre o número de repetições.** A primeira rodada, com uma única medida por regime,
> sugeriu que o árbitro dava +10% no BLE. A segunda deu o contrário. Só com 3–4 repetições
> ficou claro que o BLE varia de 385 a 501 kbps na mesma configuração — dispersão da ordem
> da diferença entre os regimes. **Uma medida por regime não decide nada aqui**, e vale
> dizer isso à turma: é a diferença entre medir e concluir.

O `README.rst` original do SDK publica números de referência para o **nRF7002 DK**
(host nRF5340, antenas separadas, Wi-Fi 802.11n em 2,4 GHz): Wi-Fi-only 10,2 Mbps,
BLE-only 1107 kbps, coexistência desligada 9,9 Mbps / 145 kbps, coexistência ligada
8,3 Mbps / 478 kbps. São números da Nordic, em outro hardware — citados aqui só como
ordem de grandeza, atribuídos, e **não entram na tabela do curso**: a tabela acima
está reservada para os quatro valores desta bancada, ainda não medidos — o que se
compara é a mesma imagem (mesmo firmware, mesmo par) com e sem o árbitro de
coexistência ligado.

## Os LEDs neste lab

**Nenhum.** O sample de coexistência não usa LED: o resultado é numérico e sai no
console (throughput de cada rádio) e no `iperf` do PC.

Como as duas pilhas rodam ao mesmo tempo e nada pisca, a única forma de saber que o
teste está de pé é o log — **os dois rádios anunciam o início separadamente**, e é isso
que se projeta.
## Pegadinhas

- **A VCOM muda com o shield — não é sempre a mesma porta.** Ver o aviso no topo
  deste README.
- **`sw3` não existe mais** com o shield acoplado nesta versão do SDK.
- **O IP padrão do peer Wi-Fi não existe na rede da sala.** `CONFIG_NET_CONFIG_
  PEER_IPV4_ADDR` vem `192.168.1.253` de fábrica; sem sobrescrever, o kit manda
  o tráfego Wi-Fi para um destino que não existe, sem erro nenhum que aponte
  para a causa. Ver a seção acima, antes do Passo 1.
- **O TAG do Channel Sounding não está conectado nesta bancada agora.** Sem um par
  BLE gravado com o sample de throughput, o central deste lab não tem para onde
  conectar — o teste concorrente não roda. Ver "Hardware" acima.
- **O iPerf 2.0.5 não está instalado nesta bancada.** Só a versão 3 está
  disponível, e ela não fala o mesmo protocolo que o gerador do Zephyr espera
  (2.0.5). Ver o checklist do Passo 2.
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
