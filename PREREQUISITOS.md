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
| **Power Profiler** | Medições de energia (lab NPU vs CPU) — requer PPK2 |
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
- **nRF Wi-Fi Provisioner** (Android/iOS) — só para a demo de provisionamento por BLE do
  instrutor. O lab de provisionamento é por SoftAP e **não usa navegador**: o fluxo é HTTPS com
  corpo em protobuf, e o cliente é o `scripts/provision.py` do próprio SDK. Ver
  `comms/08_wifi_provisioning/README.md`.
- Rede Wi-Fi de teste em sala (2.4/5 GHz) e um endpoint TCP acessível — **desejável, não
  obrigatório**: o plano B dos labs de transporte é um **hotspot** de celular ou o
  compartilhamento de conexão do PC, com o kit e o PC associados nele. **Não** serve a DK em
  SoftAP: o firmware desses labs é estação, não ponto de acesso. Wi-Fi corporativo com portal
  cativo ou WPA2-Enterprise não serve.
- **`protoc`** e o pacote Python **`protobuf`**, para o lab 8 (provisionamento): o
  cliente `provision.py` fala protobuf com a DK, e o schema (`common_pb2.py`) é gerado
  localmente a partir do `.proto` do SDK — sem `protoc`, o script falha no `import`.
- **`paho-mqtt`** (Python) e um broker **mosquitto** local, para o lab 10 (MQTT).
- **`requests`** (Python), para o lab 13 (locationing) — é quem fala HTTPS com o nRF
  Cloud.
- **`iperf` versão 2.0.5**, para o lab 12 (coexistência). **O `iperf3` não serve** — o
  gerador de tráfego (`zperf`) do Zephyr fala o protocolo do iperf 2, não o 3.
- **PPK2** (Power Profiler Kit II), para o lab 11 (energia) — mesmo instrumento do
  módulo Edge AI, agora medindo o companion Wi-Fi na própria EB II (não no jumper de
  corrente da DK).
- **Um AP com TWT** (TP-Link EX3000, ou equivalente) como referência para a Parte B do
  lab 11 — o AP da bancada de preparação é 802.11ax confirmado, mas não é TWT capable.
- **Um segundo dispositivo Bluetooth LE** gravado com `nrf/samples/bluetooth/
  throughput` (o papel, central ou periférico, é escolhido por botão no próprio
  sample), para o lab 12 (coexistência) — o par do central BLE deste lab. O candidato
  natural é o nRF54L15-TAG do módulo de Channel Sounding.

### Firewall do Windows — bloqueia os servidores Python dos labs Wi-Fi por padrão

Os labs 9, 10, 12 e 13 sobem um servidor Python no PC (TCP, HTTP, ou o broker
mosquitto) que a DK precisa alcançar pela rede. O firewall do Windows bloqueia essa
entrada por padrão em rede classificada como Private, e o sintoma não avisa ninguém:
o servidor fica ouvindo e nada chega, sem erro nenhum. Pior — se o aluno já tiver
clicado em "Cancelar" num diálogo de rede do Windows para o Python alguma vez, fica
registrada uma regra de **bloqueio por programa** que **vence qualquer permissão
criada só por porta**. O conserto completo (dois comandos em PowerShell como
administrador: remover as regras de bloqueio do Python e liberar a porta do lab) está
em `comms/09_wifi_tcp/README.md`, seção "Pegadinhas" — resolva lá, testando com o
próprio lab 9, antes do curso.

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

- **u-center 2** ([u-blox](https://www.u-blox.com/en/product/u-center)) — configuração e visualização do EVK-X20P.
- Credenciais de um **caster NTRIP** para correção RTK (definidas pelo instrutor antes do curso).
- Antenas GNSS posicionadas com visada de céu (labs outdoor ou janela).

---

## Módulo Segurança (`security/`)

- **nRF Connect Device Manager** no smartphone — atualização FOTA assinada via BLE.
- Demais demos usam apenas a base (kits pré-configurados pelo instrutor).
