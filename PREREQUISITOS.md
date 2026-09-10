# Pré-requisitos de Instalação

Setup necessário **antes do primeiro dia** de treinamento. A seção [Base](#base-todos-os-módulos) é obrigatória para todos; as seções por módulo adicionam ferramentas específicas.

## Base (todos os módulos)

### 1. Visual Studio Code + nRF Connect for VS Code

1. Instale o [Visual Studio Code](https://code.visualstudio.com/).
2. No VS Code, instale a extensão **nRF Connect for VS Code Extension Pack** (inclui as extensões de build, device tree, terminal serial e debug).

### 2. nRF Connect SDK v3.4.0 + toolchain

Pela própria extensão nRF Connect for VS Code:

1. Abra o painel **nRF Connect** → **Install Toolchain** → selecione **v3.4.0**.
2. Em seguida **Manage SDKs** → instale o **nRF Connect SDK v3.4.0**.

> Caminho sugerido de instalação: `C:\ncs\v3.4.0` (Windows).

### 3. nRF Connect for Desktop

Instale o [nRF Connect for Desktop](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-Desktop) e, dentro dele, os apps:

| App | Uso no curso |
|-----|--------------|
| **Programmer** | Gravação de firmware e recovery dos kits |
| **Serial Terminal** | Console UART dos labs |
| **Power Profiler** | Medições de energia (lab NPU vs CPU do Edge AI; lab 11 de Wi-Fi) — requer PPK2 |
| **Board Configurator** | Configuração dos DKs quando necessário |

### 4. Ferramentas de linha de comando

- **nRF Util** (`nrfutil`) com o comando `device`: [download](https://www.nordicsemi.com/Products/Development-tools/nRF-Util)
- **SEGGER J-Link** — instalado junto com o toolchain; se pedido, aceite a instalação dos drivers.

### 5. Apps de smartphone

| App | Plataforma | Uso |
|-----|-----------|-----|
| **nRF Connect for Mobile** | Android/iOS | Scanner/cliente BLE genérico (vários labs) |
| **nRF Toolbox** | Android/iOS | Channel Sounding com Pixel 10 como initiator |
| **nRF Connect Device Manager** | Android/iOS | FOTA assinada via BLE (módulo de segurança) |

### 6. Verificação do setup

```bash
# no terminal do VS Code (ambiente nRF Connect):
west --version
nrfutil device list   # com um DK conectado via USB
```

Build de teste (com o nRF54LM20-DK conectado):

```bash
west build -b nrf54lm20dk/nrf54lm20a/cpuapp <caminho do NCS>/zephyr/samples/basic/blinky
west flash
```

---

## Módulo Edge AI (`edge_ai/`)

### 1. Conta no Nordic Edge AI Lab

Crie uma conta em [ai.lab.nordicsemi.com](https://ai.lab.nordicsemi.com/) — é onde geramos modelos Neuton (CPU) e compilamos modelos TFLite para a Axon NPU.

> Os samples do Add-on rodam com modelos pré-instalados (conta não é obrigatória para eles), mas os labs de criação de modelo próprio exigem a conta.

### 2. Edge AI Add-on v2.3.0 para nRF Connect SDK

O Add-on ([sdk-edge-ai](https://github.com/nrfconnect/sdk-edge-ai), listado no [nRF Connect SDK Add-on Index](https://nrfconnect.github.io/ncs-app-index/)) é distribuído como **workspace west próprio**: o `west.yml` dele fixa o NCS compatível (v2.3.0 → **NCS v3.4.0**) e o `west update` baixa uma cópia do SDK dentro desse workspace (alguns GB — faça em rede boa, antes do curso).

> **Sugestão de local:** instale o workspace **dentro de `C:\ncs\`, no mesmo nível das versões do SDK** — ou seja, `C:\ncs\sdk-edge-ai` ao lado de `C:\ncs\v3.4.0`. Assim todos os SDKs e workspaces ficam num lugar só e o caminho é o mesmo para toda a turma.

```
C:\ncs\
├── v3.4.0\          (NCS "normal" — labs dos demais módulos)
├── sdk-edge-ai\     (workspace do Edge AI Add-on — labs de Edge AI)
└── toolchains\
```

**Método recomendado — VS Code (GUI):**

1. No painel nRF Connect: **Create a new application** → **Browse nRF Connect SDK Add-on Index**.
2. Selecione **Edge AI Add-on** → versão **v2.3.0** e escolha uma pasta de destino **nova** (sugerido: `C:\ncs\sdk-edge-ai`).
3. Aguarde o clone do Add-on + NCS compatível — o `west update` continua em segundo plano por vários minutos após o primeiro clone; espere concluir antes de compilar.

Layout resultante (o VS Code clona o Add-on na subpasta `edge-ai/`):

```
C:\ncs\sdk-edge-ai\
├── .west\          (marca o workspace)
├── edge-ai\        (o Add-on: applications/, samples/, tools/axon/...)
├── nrf\            (NCS v3.4.0 do workspace)
├── zephyr\
└── modules\, nrfxlib\, ...
```

**Método alternativo — linha de comando:**

⚠️ O `west init` cria um workspace novo — rode-o dentro de uma **pasta nova e vazia** (ex.: `C:\ncs\sdk-edge-ai`). **Não** rode dentro de `C:\ncs\v3.4.0` (já é um workspace west; o comando falha) nem dentro deste repositório.

```bash
# 1. entrar no ambiente do toolchain
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 --terminal

# 2. criar e entrar na pasta do workspace
mkdir C:\ncs\sdk-edge-ai && cd C:\ncs\sdk-edge-ai

# 3. inicializar e popular o workspace
west init -m https://github.com/nrfconnect/sdk-edge-ai --mr v2.3.0
west update
```

Resultado equivalente ao método GUI (pela CLI o Add-on fica em `sdk-edge-ai/` em vez de `edge-ai/`).

> Método avançado (economiza o download do NCS): `git clone --branch v2.3.0 https://github.com/nrfconnect/sdk-edge-ai` e apontar `EXTRA_ZEPHYR_MODULES` para o clone, usando o `C:\ncs\v3.4.0` existente. Fica por conta do usuário manter as versões sincronizadas.

### 3. Compilador Axon local (opcional)

Para compilar modelos TFLite → Axon **na nuvem**, use o próprio Edge AI Lab ("Compile your own model") — não precisa de nada local. Para compilar **localmente** (`sdk-edge-ai/tools/axon/compiler/scripts`):

- **Python 3.11** em ambiente virtual (recomendado Miniforge/Conda):

  ```bash
  conda create -n axon python=3.11
  conda activate axon
  cd <workspace>/sdk-edge-ai/tools/axon/compiler/scripts
  pip install -r requirements.txt
  ```

- Alternativa: **Docker** (imagem pronta do compilador).

### 4. Hardware específico dos labs

| Item | Uso |
|------|-----|
| **Sensor Evaluation Board (PCA63568)** no conector **EXP** do nRF54LM20-DK | IMU BMI270 para o app de gesture recognition no DK (alternativa: usar o nRF54L15-TAG, que já tem IMU) |
| **Microfone PDM MEMS** (testado: Adafruit 3492) | Lab wake word/KWS — fiação: `3V→VDD:IO`, `GND→GND`, `SEL→GND` (canal esquerdo), `CLK→P1.4`, `DAT→P1.5` |
| nRF54LM20-DK variante **nRF54LM20B** | A Axon NPU só existe no **B** (o app WW/KWS só tem target `nrf54lm20dk/nrf54lm20b/cpuapp`). Confirmar variante dos kits! |

### Documentação

- [Edge AI Add-on — docs](https://nrfconnectdocs.nordicsemi.com/addons/addon-edge-ai/latest/index.html)
- [Axon NPU](https://www.nordicsemi.com/Products/Technologies/Edge-AI/Axon-NPU) · [Neuton models](https://www.nordicsemi.com/Products/Technologies/Edge-AI/Neuton-models) · [Edge AI Software](https://www.nordicsemi.com/Products/Technologies/Edge-AI/Software) · [Edge AI Lab](https://www.nordicsemi.com/Products/Technologies/Edge-AI/Edge-AI-Lab)

---

## Módulo Comunicação (`comms/`)

- **Python 3.11** com `numpy`, `pyserial` e `pytest` para o lab CS 5 (`pip install -r comms/05_cs_iq_music/tools/requirements.txt`). O mesmo ambiente do Edge AI serve.
- **Trena** (≥ 5 m) por bancada, para os labs CS 2 e CS 5.
- **SEGGER J-Link** (vem com o toolchain) — o log do TAG só sai por RTT.
- Smartphone com Channel Sounding (Pixel 9/10 com Android 16 QPR2+, nRF Toolbox ≥ 4.1.4) é **opcional** e só para a demo do instrutor; o Galaxy S26 exige ajustes dos dois lados (ver `comms/01_cs_reflector/s26.conf`).
- **nRF Wi-Fi Provisioner** (Android/iOS) — é o cliente do **lab 8b** (provisionamento por
  Bluetooth LE): o celular acha a DK pelo anúncio BLE e entrega a credencial por GATT. Ver
  `comms/08b_wifi_provisioning_ble/README.md`. O **lab 8a** é o outro caminho, por SoftAP, e
  **não usa navegador nem app**: o fluxo é HTTPS com corpo em protobuf, e o cliente é o
  `scripts/provision.py` do próprio SDK — ver `comms/08a_wifi_provisioning/README.md`.
- Rede Wi-Fi de teste em sala (2.4/5 GHz) e um endpoint TCP acessível — **desejável, não
  obrigatório**: o plano B dos labs de transporte é um **hotspot** de celular ou o
  compartilhamento de conexão do PC, com o kit e o PC associados nele. **Não** serve a DK em
  SoftAP: o firmware desses labs é estação, não ponto de acesso. Wi-Fi corporativo com portal
  cativo ou WPA2-Enterprise não serve.
- **`protoc`** e o pacote Python **`protobuf`**, para o lab 8a (provisionamento): o
  cliente `provision.py` fala protobuf com a DK, e o schema (`common_pb2.py`) é gerado
  localmente a partir do `.proto` do SDK — sem `protoc`, o script falha no `import`.
- **`paho-mqtt`** (Python) e um broker **mosquitto** local, para o lab 10 (MQTT).
- **`requests`** (Python), para o lab 13 (locationing) — é quem fala HTTPS com o nRF
  Cloud.
- **`iperf` versão 2.0.5**, para o lab 12 (coexistência). **O `iperf3` não serve** — o
  gerador de tráfego (`zperf`) do Zephyr fala o protocolo do iperf 2, não o 3.

  > **Baixe o binário da arquitetura certa.** As páginas de release publicam versões
  > para x64 **e** para ARM64, e o nome do arquivo é o mesmo (`iperf.exe`). Baixar o
  > ARM64 numa máquina Intel dá um erro que **não parece** ser de arquitetura — o
  > Windows responde só *"The specified executable is not a valid application for this
  > OS platform"*, e o Git Bash, `Exec format error`. Aconteceu nesta bancada em
  > 2026-09-07 e custou tempo. Para conferir sem instalar nada, o cabeçalho PE diz a
  > arquitetura: `0x8664` é x64, `0xaa64` é ARM64.

  > **Não dá para compilar o iPerf nesta máquina.** Não há compilador nativo (`gcc`,
  > `clang`, `cl`) — o toolchain do NCS traz só cross-compilers para o
  > microcontrolador (`arm-zephyr-eabi`, `riscv64-zephyr-elf`). Compilar exigiria MSYS2
  > ou Cygwin. É a mesma razão pela qual os testes de travessia C↔Python do lab 9 ficam
  > pulados.

  **Alternativa validada:** um sorvedouro UDP em Python mede o throughput do lado do PC
  e dispensa o iPerf — foi assim que o lab 12 foi medido em 2026-09-07. A ressalva é que
  o `zperf` do kit termina com `Stats receive timeout`, porque o sorvedouro não devolve o
  relatório do protocolo iperf 2; o número válido passa a ser só o do PC.
- **PPK2** (Power Profiler Kit II), para o lab 11 (energia) — mesmo instrumento do
  módulo Edge AI, agora medindo o companion Wi-Fi na própria EB II (não no jumper de
  corrente da DK).
- **Um AP com TWT** (TP-Link EX3000, ou equivalente) como referência para a Parte B do
  lab 11 — o AP da bancada de preparação é 802.11ax confirmado, mas não é TWT capable.
- **Um segundo dispositivo Bluetooth LE** gravado com `nrf/samples/bluetooth/
  throughput` (o papel, central ou periférico, é escolhido por botão no próprio
  sample), para o lab 12 (coexistência) — o par do central BLE deste lab. O candidato
  natural é o nRF54L15-TAG do módulo de Channel Sounding.

### Ferramentas e bibliotecas Python do módulo `comms/`

Um ambiente só serve para tudo (o mesmo do Edge AI serve). Instalação de uma vez:

```
pip install -r comms/05_cs_iq_music/tools/requirements.txt
pip install -r comms/09_wifi_tcp/tools/requirements.txt
pip install -r comms/10_wifi_http_mqtt/tools/requirements.txt
pip install -r comms/13_wifi_location/tools/requirements.txt
pip install protobuf
```

| Pacote | Serve para | Sem ele |
|---|---|---|
| `numpy`, `matplotlib` | lab CS 5 (IQ/MUSIC) e o painel `cs_dash.py` | o painel não abre |
| `pyserial` | leitura de serial nos utilitários | os scripts de captura não rodam |
| `pytest` | os testes de PC dos labs 9, 10 e 13 | só perde os testes; os labs rodam |
| `paho-mqtt` (≥ 2.0) | **lab 10, variante MQTT** — o assinante `wifi_mqtt_sub.py` | o lab 10 MQTT não roda |
| `requests` (≥ 2.31) | **lab 13** — fala HTTPS com o nRF Cloud | o lab 13 não roda |
| `protobuf` + o executável **`protoc`** | **lab 8a** — gera `common_pb2.py` do schema do SDK | `provision.py` falha no `import` |

> **Um compilador C nativo é opcional, mas destrava um teste.** Sem ele, os **8 testes de
> travessia C↔Python do lab 9** (`tools/tests/test_payload_c.py`) ficam pulados — são os
> que compilam `src/payload.c` num binário de host e comparam **byte a byte** com o
> `tools/payload_ref.py`. É a tese do lab, hoje afirmada e não verificada nesta máquina.
> Não é teórico: em 2026-09-07 o `payload_ref.montar()` divergia do C em 4 dos 6 vetores
> (o C imprime `25.00`, o `json.dumps` imprimia `25.0`), e o defeito só apareceu porque
> foi comparado à mão com linhas reais capturadas do kit. Para instalar, o caminho é
> **MSYS2** (traz MinGW-w64 gcc, `make` e as autotools); o `gcc` sozinho não basta para
> projetos autotools.

Fora do Python, dois executáveis: um broker **mosquitto** local (lab 10 MQTT) e o
**`iperf` 2.0.5** (lab 12 — o `iperf3` **não** serve; ver o item acima).

### Firewall do Windows — a armadilha que mais custa tempo de aula

Os labs 9, 10, 12 e 13 sobem um servidor Python no PC que a DK precisa alcançar pela rede.
O firewall do Windows bloqueia essa entrada por padrão, e **o sintoma não avisa ninguém**:
o servidor fica ouvindo, nada chega, e nenhum erro aparece nele. Do lado do kit sai só um
código de erro (`-116`, `ETIMEDOUT`).

São **dois** problemas diferentes, e o segundo foi medido nesta bancada em 2026-09-07:

**1. Bloqueio por programa.** Se alguém já clicou em "Cancelar" num diálogo de rede do
Windows para o Python, fica registrada uma regra de **bloqueio por programa** que **vence
qualquer permissão criada por porta**. Conserto em `comms/09_wifi_tcp/README.md`, seção
"Pegadinhas".

**2. A regra é por PORTA — e cada lab usa uma porta diferente.** São **quatro** no módulo: 9000/TCP (lab 9), 8000/TCP (lab 10 HTTP), 1883/TCP (lab 10 MQTT) e **5001/UDP** (lab 12). Este é o que pega
quem já fez o lab 9 funcionar: a regra criada lá vale para a **9000** e só para ela. Ao
passar para o lab 10, o kit tenta a **8000** (HTTP) ou a **1883** (MQTT) e trava, com o
servidor mudo. Aconteceu exatamente assim nesta bancada.

Libere as três de uma vez, em **PowerShell como administrador**, antes do curso:

```powershell
New-NetFirewallRule -DisplayName "nrf-manaus lab9 TCP"   -Direction Inbound -Protocol TCP -LocalPort 9000 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "nrf-manaus lab10 HTTP" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "nrf-manaus lab10 MQTT" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "nrf-manaus lab12 UDP"  -Direction Inbound -Protocol UDP -LocalPort 5001 -Action Allow -Profile Private
```

Conferir depois (não precisa de administrador):

```
netsh advfirewall firewall show rule name=all dir=in status=enabled | findstr /C:"8000" /C:"9000" /C:"1883" /C:"5001"
```

> **A rede tem de estar classificada como "Particular"** — as regras acima usam o perfil
> `Private`. Numa rede marcada como Pública o Windows aplica outro conjunto e elas não valem.

### mosquitto: o serviço do Windows briga com o broker do lab (lab 10, MQTT)

Medido nesta bancada em 2026-09-07. O instalador do mosquitto no Windows registra um
**serviço que sobe sozinho** (`StartType: Automatic`). E o mosquitto 2.x, na configuração
padrão, **escuta só em localhost e recusa conexão anônima** — ou seja, o serviço **não**
serve para o lab: o kit nunca conseguiria falar com ele.

Por isso o lab sobe um broker próprio, com uma conf mínima:

```
listener 1883 0.0.0.0
allow_anonymous true
```

E aí nasce a confusão: passam a existir **dois brokers**. O serviço ocupa `127.0.0.1` e
`::1`; o broker do lab fica com `0.0.0.0`. O kit publica no do lab — e todo assinante que
usar `localhost` cai **no outro**, que não recebe nada. O sintoma é desconcertante: o log do
broker do lab mostra `PUBLISH` chegando normalmente, e o `wifi_mqtt_sub.py` fica mudo, como
se o kit não estivesse publicando.

Duas saídas:

- **Contorno imediato**, sem administrador: apontar o assinante para o endereço de rede do
  PC em vez de localhost — `python wifi_mqtt_sub.py --host <ip-do-pc>`. Testado e resolve.
- **Solução definitiva**, e a recomendada antes do curso (PowerShell como administrador):

```powershell
Stop-Service mosquitto
Set-Service mosquitto -StartupType Manual
```

  Com o serviço parado sobra um broker só, e `localhost` volta a funcionar.

Conferir quantos brokers existem:

```powershell
Get-Process mosquitto | Select-Object Id,ProcessName
Get-NetTCPConnection -State Listen -LocalPort 1883 | Select-Object LocalAddress,LocalPort
```

> **As três armadilhas deste bloco têm a mesma assinatura**: uma ponta funciona, a outra
> fica muda, e **nenhuma das duas dá erro**. Firewall por porta, servidor sem terminal e
> dois brokers. Vale avisar a turma disso antes, porque o instinto é culpar o firmware.

### Os servidores dos labs precisam de terminal — não rode em background

Medido nesta bancada em 2026-09-07: `wifi_server.py` (lab 9) e `wifi_http_server.py`
(lab 10) leem o teclado num laço, para aceitar os comandos de LED (`l`, `d`, `q`). Rodados
**sem terminal** — em background, com a saída redirecionada, ou por um script — o `input()`
recebe EOF imediatamente e o programa **sai em silêncio**, tendo imprimido só a linha
"Ouvindo...". Quem fizer `python wifi_server.py > log.txt &` vai jurar que o lab travou.

Rode sempre num terminal interativo. Se quiser guardar a saída, copie do terminal ou use
`tee` num shell que preserve a entrada.

### Conta nRF Cloud, para o lab 13 (locationing)

Crie uma conta e um projeto no [nRF Cloud](https://nrfcloud.com/) e gere um
**Organization Auth Token** (OAT) em **Project Settings** — não é a API key comum da
conta: a API key devolve `401 Auth token is malformed` nos serviços de localização
(Location Services). Anote também os identificadores de **organização** (Organization
Slug) e de **projeto** (Project Slug), em **Project Settings → General** — o
`tools/wifi_locate.py` do lab precisa dos três. **Localização é um serviço cobrado por
chamada** — não gaste chamadas de teste sem necessidade.

### Blobs de firmware do nRF70 — passo obrigatório, uma vez por instalação do SDK

O driver do nRF7002 precisa de binários proprietários que **não vêm no clone do SDK**. Sem
eles, qualquer build de Wi-Fi falha no CMake por arquivo ausente:

```bash
# no terminal do nRF Connect (o mesmo ambiente do west):
west blobs fetch nrf_wifi
```

Baixa cinco binários (`default`, `scan_only`, `radio_test`, `system_with_raw`,
`offloaded_raw_tx`) para `modules/lib/nrf_wifi/zephyr/blobs/`. Precisa de internet, roda em
segundos e vale para todos os projetos daquela instalação.

> **Vale também para quem só usa VS Code.** A extensão instala SDK e toolchain mas **não**
> busca os blobs — verificado nesta bancada: a instalação feita pelo toolchain manager estava
> com zero binários. No VS Code, abra `nRF Connect: Open Terminal` e rode o comando ali.
> Conferir com `west blobs list nrf_wifi`.

Documentado pela Nordic em *nRF7002 EB II → Requirements → Prerequisites*.

### Armadilhas da nRF7002-EB II no nRF54LM20-DK (medidas na bancada)

- **A EB II encaixa no conector P17 (Expansion)** do LM20-DK.
- **O console muda de porta — e de VCOM.** O overlay do shield na v3.4.0 desabilita a
  `uart20` e move o console para a `uart30` (`/* UART20 conflicts with EB-II shield */`); o
  `device list` da placa gravada confirma que só a `uart30` fica registrada. Medido nas duas
  condições no mesmo kit: **sem o shield o log sai na segunda VCOM** (`uart20`), **com o shield
  sai na primeira** (`uart30`), e a outra fica muda. Quem vem dos labs de Channel Sounding
  precisa trocar de porta ao chegar no Wi-Fi.
- **Por que a doc online diz o contrário.** O reroteamento é um contorno para um conflito de
  pinos que só existe no kit **pré-produção** do LM20-DK. Em versões de Zephyr posteriores à
  nossa, o shield deixa de reroteiar nessa placa: o console volta para a `uart20` (segunda
  VCOM) e o `sw3` volta a existir. A doc "latest" já descreve esse comportamento novo. Na
  v3.4.0, que é a do curso, vale o reroteamento.
- **Caminho de projeto curto, senão o build quebra.** Os objetos da biblioteca de segurança
  (`cracen`) têm um hash de diretório no caminho, e no Windows isso estoura o limite de tamanho
  de caminho se o projeto estiver fundo. O sintoma engana: o build morre num passo de
  arquivamento, com `arm-zephyr-eabi-ar: ... .obj: No such file or directory`, como se o
  compilador tivesse falhado. Não tem nada a ver com o código. Mantenha o repositório perto da
  raiz — `C:/work/nrf-manaus-2` funciona; um clone dentro de várias pastas aninhadas, não.
- **O botão 4 some.** O overlay apaga o nó `button_3` e o alias `sw3`. Sobram os botões 1–3
  (`sw0`–`sw2`) e os quatro LEDs.
- **Não dá para somar o microfone PDM dos labs de Edge AI.** O `pdm20` do `07_ww_kws` usa
  `P1.04` (PDM_CLK) e `P1.05` (PDM_DIN), que são exatamente o `BUCKEN` e o `IRQ` do nRF7002.
  Microfone e companion não coexistem no mesmo kit sem mudar a fiação.

---

## Módulo GNSS (`gnss/`)

- **u-center 2** ([u-blox](https://www.u-blox.com/en/product/u-center)) — configuração do EVK-X20P,
  Survey-In da base, caster e cliente NTRIP, e o **mapa de desvio** com CEP50 e CEP95 —
  inclusive a partir de **NMEA puro**, direto da porta do lab 3 ou de um log gravado.

  > **A conta u-blox tem dois fatores e precisa existir antes do curso**, criada **na máquina que
  > vai projetar** — não dá para resolver isso na hora da aula. Depois do primeiro login o programa
  > roda offline, mas mapa de fundo, NTRIP e serviço de correção continuam exigindo internet.

- **RTKLIB / RTKPLOT** — **opcional**: sobrepõe as trilhas dos dois receptores e mostra a
  diferença. Consome `$GPRMC` e `$GPGGA`, que tanto o nRF9151 quanto o X20P já emitem de fábrica.
- **Antenas GNSS ativas com visada de céu** (outdoor ou janela desobstruída) — o módulo usa
  **três** ANN-MB2, uma por receptor: **base**, **rover** e **nRF9151**, cada uma sobre um plano
  de terra de ø12 cm (um CD serve), na mesma altura. A nRF9151-SMA-DK não tem antena de bordo
  nem LNA de GNSS: sem antena externa no J2 ela não recebe nada.

  > **Nunca plugue a mesma antena em dois receptores ao mesmo tempo.** O J2 da SMA-DK entrega 3 V
  > e o EVK entrega 3,3 V para a antena ativa; com os dois ligados juntos, um regulador empurra
  > corrente para dentro do outro. Uma antena por receptor; se for preciso trocar um cabo, **sempre
  > com o receptor desenergizado**.

- **Cadastro no caster NTRIP do IBGE** — **opcional, não essencial**. Serve só ao bônus de RTK
  contra a estação pública **AMUA0** (UEA), que exige internet na sala. O módulo roda inteiro sem
  ele, com a base própria e o caster local.
- **As três nRF9151-SMA-DK integradas à nRF Cloud, com certificado** — **tarefa do instrutor,
  antes da aula**. Sem isso o terceiro degrau de assistência do lab 2 (A-GNSS por nuvem) não roda;
  os dois primeiros degraus (nenhuma e mínima) não dependem de nuvem.

---

## Módulo Segurança (`security/`)

- **nRF Connect Device Manager** no smartphone — atualização FOTA assinada via BLE.
- Demais demos usam apenas a base (kits pré-configurados pelo instrutor).
