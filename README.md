# nRF Manaus 2 — Treinamento In-Company

Repositório de exemplos do treinamento avançado com a plataforma Nordic Semiconductor.

- **SDK alvo:** nRF Connect SDK **v3.4.0**
- **Formato:** aplicações freestanding (cada lab tem seu próprio `CMakeLists.txt` + `prj.conf`), compiladas contra o NCS instalado via toolchain nRF Connect for VS Code.

## Agenda

| Dias | Módulo | Carga | Pasta |
|------|--------|-------|-------|
| 1–2 | Inteligência Artificial Embarcada (Edge AI) | 10h | [`edge_ai/`](edge_ai/) |
| 3–4 | Tecnologias de Comunicação Avançada | 10h | [`comms/`](comms/) |
| 3–4 | GNSS e Localização de Precisão | (parte dos dias 3–4) | [`gnss/`](gnss/) |
| 5 | Segurança Embarcada | 4h | [`security/`](security/) |

Cada pasta de módulo tem um `README.md` com a lista de labs e instruções de build/flash.

> **Antes do curso:** siga o [`PREREQUISITOS.md`](PREREQUISITOS.md) para instalar o toolchain e as ferramentas de cada módulo.

## Kits utilizados

| Qtd | Item | Papel no treinamento |
|-----|------|----------------------|
| 6 | Nordic nRF54LM20-DK | Base dos labs de Edge AI (Neuton e NPU) e Channel Sounding |
| 6 | Nordic nRF54L15-TAG | Reflector de Channel Sounding e fonte de dados de movimento (IMU) |
| 6 | Nordic nRF7002-EBII | Wi-Fi 6+, acoplado ao nRF54LM20-DK |
| 3 | Nordic nRF9151-SMA-DK | GNSS e Redes Não Terrestres (NTN) |
| 2 | u-blox EVK-X20P | GNSS multi-banda de alta precisão (L1+L2+L5+L6) |
| 6 | Microfone PDM MEMS | Lab de wake word e comandos de voz com NPU |

## Build rápido

```bash
# exemplo: lab de channel sounding initiator para o nRF54LM20-DK
west build -b nrf54lm20dk/nrf54lm20a/cpuapp comms/channel_sounding_initiator
west flash
```

O board target de cada lab está indicado no `README.md` do próprio lab.

## Material de apoio

Slides e material complementar ficam na pasta local `doc/` (não versionada) e são distribuídos separadamente durante o treinamento. A pasta local `referencias/` (também não versionada) guarda material de referência usado no preparo do curso.
