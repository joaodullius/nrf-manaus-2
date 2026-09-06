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
  instrutor; o lab de provisionamento é por SoftAP e usa o navegador do próprio notebook.
- Rede Wi-Fi de teste em sala (2.4/5 GHz) e um endpoint TCP acessível — **desejável, não
  obrigatório**: os labs têm plano B com a própria DK em SoftAP, e o PC do aluno se conecta
  a ela. Wi-Fi corporativo com portal cativo ou WPA2-Enterprise não serve.

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

### Armadilhas da nRF7002-EB II no nRF54LM20-DK (verificadas na árvore do v3.4.0)

- **A EB II encaixa no conector P17 (Expansion)** do LM20-DK.
- **O console muda de porta.** O overlay do shield na v3.4.0 desabilita a `uart20` e move o
  console para a `uart30` (`/* UART20 conflicts with EB-II shield */`). Ou seja: com o shield
  acoplado, o log sai em **outra VCOM**. A documentação online "latest" afirma o contrário
  para o LM20 — descreve uma versão diferente da que usamos; confie no overlay da sua árvore.
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
