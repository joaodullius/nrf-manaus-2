# Channel Sounding · Lab 1 — Reflector no nRF54L15-TAG

O lado simples do Channel Sounding: o TAG anuncia o **Ranging Service**, aceita a
conexão de um initiator, participa dos procedimentos de CS e expõe as suas medidas
cruas por GATT. Ele **não calcula distância** — quem calcula é o initiator (lab 2).

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ras_reflector` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE).
> `src/main.c` e `prj.conf` são idênticos ao SDK; o que o curso acrescenta está em
> `boards/` e nos fragmentos de demo.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54L15-TAG** | roda este firmware; reflector, alimentado pela CR2032 |
| **nRF54LM20-DK** | só grava o TAG (ele encaixa no `DEBUG OUT`) e lê o RTT |

## Gravar

O TAG fica encaixado no `DEBUG OUT` da DK. Enquanto ele está lá, **o debugger da DK
aponta para o TAG, não para o SoC da DK** — é isso que permite gravá-lo, e é isso
que faz "gravar a DK" nessa hora gravar o TAG por engano. Confira com
`nrfutil device device-info`: tem que aparecer nRF54L15.

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag C:/work/nrf-manaus-2/comms/channel_sounding_reflector
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag
```

No VS Code: build configuration com board target `nrf54l15tag/nrf54l15/cpuapp`, sem
fragmentos extras.

## Ler o log — só por RTT, só no `DEBUG OUT`

O TAG **não tem UART**. O board não declara console nenhum, e o sample da Nordic não
escolhe backend de log — compila limpo e fica mudo. O
[`boards/nrf54l15tag_nrf54l15_cpuapp.conf`](boards/nrf54l15tag_nrf54l15_cpuapp.conf)
liga o RTT e aumenta os dois buffers de log (senão a rajada de boot corta o `Identity:`).

```
"C:\Program Files\SEGGER\JLink_V924a\JLinkRTTLogger.exe" -Device NRF54L15_M33 -If SWD -Speed 4000 -RTTChannel 0 rtt.log
```

O que esperar, com um initiator conectando (texto do próprio sample):

```
I: Connected to xx.xx.xx.xx.xx.xx (random) (err 0x00)
I: CS capability exchange completed.
I: CS config creation complete. ID: 0
I: CS security enabled.
I: CS procedures enabled.
```

Assim que o TAG sai do `DEBUG OUT` para a bateria, **o log acaba**. A partir daí a
evidência de vida é o LED 1 (aceso = conectado) e a saída do initiator. É a diferença
entre bancada e campo — e é assim que um reflector de verdade vive.

## O endereço do seu TAG

É o mesmo do Edge AI: o endereço BLE estático vem do próprio chip e não muda com o
firmware. Reaproveite o `meu_tag.conf` do `edge_ai/03_central_uart` nos labs 2, 3 e 5.
Se precisar reler, ele está na linha `Identity:` do boot, no RTT.

## Pegadinhas

- **RTT mostra log velho.** Logo depois de regravar, o bloco RTT do firmware anterior
  pode continuar na RAM. `nrfutil device reset` e ler de novo.
- **Gravou a DK em vez do TAG (ou vice-versa).** Com o TAG encaixado, `west flash`
  grava o TAG; sem ele, grava a DK. Sempre conferir `device-info` antes.
- **Um initiator antigo esquecido numa DK rouba o TAG** (só aceita 1 conexão).
  `nrfutil device recover` na DK esquecida.

## Demo do instrutor com smartphone

Ver [`demo.conf`](demo.conf) e [`s26.conf`](s26.conf). Não faz parte do lab do aluno.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ras_reflector`
- Nordic, *Bluetooth: Channel Sounding Reflector with Ranging Responder* (doc do sample)
- Nordic DevZone, *Introducing the nRF54L15 Tag* — o TAG como reflector e o build para `nrf54l15tag/nrf54l15/cpuapp`
