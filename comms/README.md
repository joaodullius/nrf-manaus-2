# Dias 3–4 — Tecnologias de Comunicação Avançada — 10h

Implementação e validação das principais tecnologias de conectividade e localização de próxima geração da plataforma Nordic.

**Hardware:** nRF54LM20-DK + nRF54L15-TAG (Channel Sounding), nRF7002-EBII (Wi-Fi 6+), nRF9151-SMA-DK (NTN).

> Os labs de GNSS ficam no módulo separado [`gnss/`](../gnss/), por usarem kits dedicados (nRF9151 e u-blox EVK-X20P).

## Labs

| Lab | Descrição | Kit | Status |
|-----|-----------|-----|--------|
| [`channel_sounding_reflector/`](channel_sounding_reflector/) | **CS 1** — Reflector RAS no TAG, CS default da Nordic. Log por RTT (o TAG não tem UART). Fragmentos da demo com smartphone | nRF54L15-TAG | ✅ |
| [`channel_sounding_initiator/`](channel_sounding_initiator/) | **CS 2** — Initiator RAS no LM20-DK: `ifft`, `phase_slope` e `rtt` lado a lado. Filtra pelo endereço do TAG do aluno (mesmo `meu_tag.conf` do Edge AI). Experimento com trena e obstrução | nRF54LM20-DK | ✅ |
| [`channel_sounding_ipt_reflector/`](channel_sounding_ipt_reflector/) + [`channel_sounding_ipt_initiator/`](channel_sounding_ipt_initiator/) | **CS 3** — O mesmo par com IPT: a contribuição do reflector viaja na fase do tom, não por GATT. A coluna `rtt` some; `time_delta` cai | TAG + LM20-DK | ✅ |
| [`channel_sounding_secure/`](channel_sounding_secure/) | **CS 4** — Roteiro: ACL cifrada, CS Security Enable, RTT como limite físico contra relé, o que o IPT abre mão, o que o SDC não suporta | par do CS 2 | ✅ (conforme o tempo) |
| [`channel_sounding_iq_music/`](channel_sounding_iq_music/) | **CS 5** — IQ para o PC: port do `cs_de` em NumPy reproduz o chip; MUSIC (skig/waves, MIT) sobre o mesmo IQ; medição de referência com trena | LM20-DK + PC | ✅ (conforme o tempo) |
| `wifi_provisioning/` | Provisionamento de dispositivo Wi-Fi 6+ com circuito companion | nRF54LM20-DK + nRF7002-EBII | planejado |
| `wifi_tcp_client/` | Envio de dados via socket TCP/IP sobre Wi-Fi | nRF54LM20-DK + nRF7002-EBII | planejado |
| `ntn_nbiot/` | Comunicação NB-IoT via satélite (NTN) — teste ao vivo dependente de janela de passada | nRF9151-SMA-DK | planejado |

### Channel Sounding — ordem de ensino

```
CS 1  reflector no TAG            "o dispositivo simples"        grava por fio, RTT
CS 2  initiator no DK             "RTT e PBR lado a lado"        trena, obstrucao
CS 3  o mesmo par com IPT         "por onde viaja o dado"        a coluna que some
CS 4  seguranca                   "o que o radio garante"        conforme o tempo
CS 5  o IQ no PC                  "o algoritmo e da aplicacao"   conforme o tempo
```

O TAG é gravado por fio, encaixado no `DEBUG OUT` da DK, duas vezes (reflector RAS
no CS 1, reflector IPT no CS 3). Enquanto ele está encaixado, o debugger da DK aponta
para ele — gravar "a DK" nessa hora grava o TAG. Sem DFU/OTA neste módulo.

Os seis TAGs da sala anunciam o mesmo UUID e o mesmo nome: todo initiator do módulo
filtra pelo endereço BLE do TAG do aluno, que é o **mesmo do Edge AI** (vem do chip,
não do firmware). Um `meu_tag.conf` serve para os três initiators.

## Tópicos teóricos

- BLE 6.0 e Channel Sounding: RTT × PBR, initiator/reflector/subevent, Ranging Service, RAS × IPT como trade-off, segurança, e "o algoritmo é camada de aplicação"
- Wi-Fi 6+ para IoT: integração com companion IC, provisionamento, TCP/IP
- Redes Não Terrestres (NTN): NB-IoT via satélite
