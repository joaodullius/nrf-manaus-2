# Dia 5 — Segurança Embarcada — 4h

Mecanismos de segurança embarcada da plataforma Nordic, em formato teórico e demonstrativo (demos conduzidas pelo instrutor com kits pré-configurados).

**Hardware:** nRF54LM20-DK.

## Demos planejadas

| Lab | Descrição |
|-----|-----------|
| `secure_fota_ble/` | Atualização de firmware assinada via BLE, com autenticação obrigatória para a sessão de atualização |
| `trustzone_partition/` | Particionamento secure/non-secure com Arm TrustZone |
| `tfm_secure_service/` | Chamada de serviço seguro via Trusted Firmware-M (criptografia, armazenamento seguro, execução isolada) |
| `pqc_demo/` | Criptografia pós-quântica em camada de aplicação (condicionada à disponibilidade na plataforma na data do treinamento) |

## Tópicos teóricos

- Root of Trust (RoT) e Secure Boot — princípios de inicialização segura
- Isolamento de hardware via Arm TrustZone
- Trusted Firmware-M (TF-M)
- Criptografia e certificação — diretrizes de segurança para dispositivos conectados; estado atual e roadmap para criptografia pós-quântica
