# GNSS e Localização de Precisão

Labs de geolocalização outdoor, separados do módulo de comunicação por usarem kits dedicados com fluxos distintos: o nRF9151 (GNSS integrado ao modem) e o u-blox EVK-X20P (receptor multi-banda de alta precisão).

**Hardware:** nRF9151-SMA-DK, u-blox EVK-X20P.

## Labs planejados

| Lab | Descrição | Kit |
|-----|-----------|-----|
| `gnss_basic/` | Aquisição de posição outdoor via satélite (fix, NMEA, tracking) | nRF9151-SMA-DK |
| `gnss_rtk_ublox/` | GNSS multi-banda (L1+L2+L5+L6) de alta precisão com recepção de correção RTK via internet (NTRIP) | u-blox EVK-X20P |

## Tópicos teóricos

- Constelações e bandas GNSS; fontes de erro e técnicas de correção
- GNSS no nRF9151: coexistência com LTE, assistência (A-GNSS)
- RTK: estações de referência, NTRIP, precisão centimétrica
