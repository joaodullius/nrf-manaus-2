# Dias 3–4 — Tecnologias de Comunicação Avançada — 10h

Implementação e validação das principais tecnologias de conectividade e localização de próxima geração da plataforma Nordic.

**Hardware:** nRF54LM20-DK + nRF54L15-TAG (Channel Sounding), nRF7002-EBII (Wi-Fi 6+), nRF9151-SMA-DK (GNSS/NTN), u-blox EVK-X20P (GNSS multi-banda).

## Labs planejados

| Lab | Descrição | Kit |
|-----|-----------|-----|
| `channel_sounding_initiator/` | Initiator de Channel Sounding (BLE 6.0) — ranging sub-métrico via troca de fase/tempo de voo | nRF54LM20-DK |
| `channel_sounding_reflector/` | Reflector de Channel Sounding (opcionalmente smartphone compatível como initiator) | nRF54L15-TAG |
| `wifi_provisioning/` | Provisionamento de dispositivo Wi-Fi 6+ com circuito companion | nRF54LM20-DK + nRF7002-EBII |
| `wifi_tcp_client/` | Envio de dados via socket TCP/IP sobre Wi-Fi | nRF54LM20-DK + nRF7002-EBII |
| `gnss_basic/` | Aquisição de posição outdoor via satélite | nRF9151-SMA-DK |
| `gnss_rtk/` | GNSS multi-banda de alta precisão com correção RTK via internet | u-blox EVK-X20P |
| `ntn_nbiot/` | Comunicação NB-IoT via satélite (NTN) — teste ao vivo dependente de janela de passada | nRF9151-SMA-DK |

## Tópicos teóricos

- BLE 6.0 e Channel Sounding: stack, Custom GATT Services, otimização de pacotes
- Wi-Fi 6+ para IoT: integração com companion IC, provisionamento, TCP/IP
- GNSS e localização de precisão outdoor
- Redes Não Terrestres (NTN): NB-IoT via satélite
