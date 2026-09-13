# Hex de referência — firmware da demo NTN

| Arquivo | O que é | Origem |
|---|---|---|
| `serial_modem_v1.0.0_nrf9151dk_normal.hex` | App core: Serial Modem add-on v1.0.0, alvo `nrf9151dk/nrf9151/ns`. Expõe os comandos AT do modem e os comandos `#X...` de socket na UART | github.com/nrfconnect/ncs-serial-modem, release v1.0.0 |
| `mfw_nrf9151-ntn_1.0.1.zip` | Firmware de modem com NTN NB-IoT. **Não está no repositório** (licença Nordic); baixar em nordicsemi.com › nRF9151 SMA DK › Evaluate NTN | Nordic |

## Gravação

1. Firmware de modem: nRF Connect for Desktop › Programmer › *Add file* com o `.zip` › *Write*.
   Confirmar depois com `AT+CGMR` → `mfw_nrf9151-ntn_1.0.1`.
2. App core: `nrfutil device program --firmware serial_modem_v1.0.0_nrf9151dk_normal.hex --options chip_erase_mode=ERASE_ALL`.
3. Terminal a 115200 8N1 na porta "nRF91 Serial Modem"; `AT` responde `OK`.

O firmware de modem NTN substitui o `mfw_nrf91x1_2.0.x` usado no módulo de GNSS. Para voltar ao
GNSS com assistência, regravar o `mfw_nrf91x1`.
