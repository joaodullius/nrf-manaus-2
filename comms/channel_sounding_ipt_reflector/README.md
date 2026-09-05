# Channel Sounding · Lab 3a — Reflector IPT no nRF54L15-TAG

O reflector do lab 3. Mesmo papel do lab 1 — anunciar, aceitar conexão, participar
dos procedures — com uma diferença que não aparece no código dele: **ele não expõe
dado nenhum por GATT**. Com o IPT (Inline Phase Correction Term Transfer) ligado pelo
initiator na configuração de CS, o reflector ajusta a fase do tom que devolve para
casar com a que acabou de receber. A contribuição dele viaja **dentro do tom de
rádio**, não pela conexão.

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ipt_reflector` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE).
> `src/main.c` e `prj.conf` são idênticos ao SDK; os arquivos em `boards/` também
> são da Nordic para o TAG (as duas antenas extras e o antenna switch) — o curso
> só acrescenta um bloco de RTT ao final do `.conf`. O TAG não está na lista de
> boards do sample — o build foi validado na bancada do curso.

## Gravar

TAG no `DEBUG OUT` da DK (o debugger passa a apontar para o TAG; confira
`nrfutil device device-info` = nRF54L15). O mesmo TAG do lab 1 — o endereço BLE
continua o mesmo, o firmware não muda isso.

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector/build_tag C:/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector/build_tag
```

## Log — RTT, só no `DEBUG OUT`

Igual ao lab 1: o TAG não tem UART, o
[`boards/nrf54l15tag_nrf54l15_cpuapp.conf`](boards/nrf54l15tag_nrf54l15_cpuapp.conf)
manda o log para o RTT, e na bateria não há log. O sample roda em modo minimal
(`CONFIG_NCS_SAMPLES_DEFAULTS` implica `LOG_DEFAULT_MINIMAL`), então o log sai
como linhas `I: mensagem`, não no formato `<inf> módulo: mensagem` de outros
labs. O bloco de RTT vive no fim do `boards/nrf54l15tag_nrf54l15_cpuapp.conf`
da própria Nordic.

```
"C:\Program Files\SEGGER\JLink_V924a\JLinkRTTLogger.exe" -Device NRF54L15_M33 -If SWD -Speed 4000 -RTTChannel 0 rtt.log
```

Depois de gravar, **tire o TAG** do `DEBUG OUT`: o próximo passo (lab 3b) grava a DK.

## Nome, não UUID

O `ipt_initiator` da Nordic procura o reflector pelo **nome** `Nordic CS IPT Reflector`
— não há Ranging Service para anunciar. Seis TAGs na sala terão o mesmo nome; por isso
o initiator do curso filtra também pelo endereço (lab 3b).

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ipt_reflector`
- Nordic, *Bluetooth: Channel Sounding Reflector with Inline PCT Transfer* (doc do sample — "How CS IPT works")
- Nordic, changelog do SoftDevice Controller, nRF Connect SDK v3.3.1 — suporte a IPT (DRGN-26911)
