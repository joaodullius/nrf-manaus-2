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

> 🚧 **Em preparação** — instruções de instalação do Edge AI Add-on e ferramentas associadas serão adicionadas.

Itens previstos:

- **Conta no Nordic Edge AI Lab** — criar em [ai.lab.nordicsemi.com](https://ai.lab.nordicsemi.com) (geração de modelos Neuton e LiteRT/Axon NPU).
- **Edge AI Add-on para nRF Connect SDK v1.3.0** (alinhado ao NCS v3.4.0).
- **Python 3.10+** — ferramenta de coleta de dados (sensor → BLE → CSV).
- (A confirmar) Toolchain do compilador Axon para desenvolvimento local.

---

## Módulo Comunicação (`comms/`)

- **nRF Toolbox** no smartphone — opcionalmente Pixel 10 como Channel Sounding initiator.
- **nRF Wi-Fi Provisioner** (Android/iOS) — provisionamento do nRF7002-EBII.
- Rede Wi-Fi de teste disponível em sala (2.4/5 GHz) e um endpoint TCP acessível (pode ser um PC na mesma rede com `ncat`/Python).

---

## Módulo GNSS (`gnss/`)

- **u-center 2** ([u-blox](https://www.u-blox.com/en/product/u-center)) — configuração e visualização do EVK-X20P.
- Credenciais de um **caster NTRIP** para correção RTK (definidas pelo instrutor antes do curso).
- Antenas GNSS posicionadas com visada de céu (labs outdoor ou janela).

---

## Módulo Segurança (`security/`)

- **nRF Connect Device Manager** no smartphone — atualização FOTA assinada via BLE.
- Demais demos usam apenas a base (kits pré-configurados pelo instrutor).
