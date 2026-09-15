# Channel Sounding · Lab 1 — Reflector no nRF54L15-TAG

O lado simples do Channel Sounding: o TAG anuncia o **Ranging Service**, aceita a
conexão de um initiator, participa dos procedimentos de CS e expõe as suas medidas
cruas por GATT. Ele **não calcula distância** — quem calcula é o initiator (lab 2).

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ras_reflector` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE).
> `src/main.c` e `prj.conf` são idênticos ao SDK. Os arquivos em `boards/` também
> são da Nordic para o TAG (as duas antenas extras e o antenna switch) — o curso
> só acrescenta um bloco de RTT ao final do `.conf`. Os fragmentos de demo são a
> única coisa fora do sample.

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
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/01_cs_reflector/build_tag C:/work/nrf-manaus-2/comms/01_cs_reflector
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/01_cs_reflector/build_tag
```

No VS Code: build configuration com board target `nrf54l15tag/nrf54l15/cpuapp`, sem
fragmentos extras.

## Ler o log — só por RTT, só no `DEBUG OUT`

O TAG **não tem UART**. O board não declara console nenhum, e o sample roda em modo
minimal de log (`CONFIG_NCS_SAMPLES_DEFAULTS` implica `LOG_DEFAULT_MINIMAL`) — sem
console configurado, compila limpo e fica mudo. O bloco de RTT acrescentado ao final
do [`boards/nrf54l15tag_nrf54l15_cpuapp.conf`](boards/nrf54l15tag_nrf54l15_cpuapp.conf)
da própria Nordic (o resto do arquivo já configura as duas antenas do TAG) liga o
console por RTT e aumenta o buffer de saída (senão a rajada de boot corta o
`Identity:`). Por estar em modo minimal, as linhas saem como `I: mensagem`, não no
formato `<inf> módulo: mensagem` de outros labs.

```
"C:\Program Files\SEGGER\JLink_Vxxx\JLinkRTTLogger.exe" -Device NRF54L15_M33 -If SWD -Speed 4000 -RTTChannel 0 rtt.log
```

Troque `Vxxx` pela versão instalada em `C:\Program Files\SEGGER\`.

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

As duas antenas do TAG já saem configuradas pelos board files da Nordic; o
initiator do lab 2 usa só um caminho, então a diferença só aparece mais adiante,
no lab 5. O esquema abaixo mostra o que está por trás: uma chave de RF **SKY13348**
comandada por `P1.09`/`P1.10`, que o overlay do sample entrega ao SoftDevice
Controller (`nordic,bt-cs-antenna-switch`). Quem decide usar uma ou duas antenas é
o **initiator**; o TAG só anuncia que as tem e comuta a chave quando o controller
manda — a aplicação não participa.

![Duas antenas no TAG: a chave de RF e quem a comanda](cs_antenas_hw.png)

## O endereço do seu TAG

É o mesmo do Edge AI: o endereço BLE estático vem do próprio chip e não muda com o
firmware. É o mesmo endereço que você digitou no central do `edge_ai/03_central_uart`,
e os initiators dos labs 2, 3 e 5 pedem do mesmo jeito: na serial, a cada boot.
Se precisar reler, ele está na linha `Identity:` do boot, no RTT.

## Pegadinhas

- **RTT mostra log velho.** Logo depois de regravar, o bloco RTT do firmware anterior
  pode continuar na RAM. `nrfutil device reset` e ler de novo.
- **Gravou a DK em vez do TAG (ou vice-versa).** Com o TAG encaixado, `west flash`
  grava o TAG; sem ele, grava a DK. Sempre conferir `device-info` antes.
- **Um initiator antigo esquecido numa DK rouba o TAG** (só aceita 1 conexão).
  `nrfutil device recover` na DK esquecida.
- **O TAG sumiu depois de regravar a DK (ou de qualquer queda de conexão).** Ao
  desconectar, o sample faz `sys_reboot()` — e com o J-Link acoplado no `DEBUG OUT`
  esse reboot nem sempre volta a anunciar. `nrfutil device reset` no TAG (ou tirar e
  recolocar a bateria) resolve. O sintoma no initiator é ficar parado em
  `Filtrando pelo tag ...` sem nunca conectar — igualzinho a um endereço errado.

## Demo do instrutor com smartphone

Não faz parte do lab do aluno. O telefone é o initiator (Android `RangingManager`), o
TAG é o reflector, e o app mostra a distância na tela.

```
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/01_cs_reflector/build_tag_demo C:/work/nrf-manaus-2/comms/01_cs_reflector -- "-DEXTRA_CONF_FILE=android_ranging.conf;demo.conf;s26.conf"
```

| Fragmento | O que faz |
|---|---|
| `android_ranging.conf` (do SDK) | bonding + settings em NVS, e 2 caminhos de antena — o que o Android exige |
| `demo.conf` | nome `CS Reflector DEMO`, para achar o TAG certo entre seis iguais |
| `s26.conf` | `MAX_CONN_EVENT_LEN_DEFAULT=1250` — sem isso o Galaxy S26 falha com `0x1E` no *Procedure Enable* |

Suporte documentado pela Nordic hoje: Pixel 9 e 10 (Android 16 QPR2+ / 17), nRF Toolbox
≥ 4.1.4. O S26 exige o `s26.conf` **e** um ajuste do lado do telefone
(`min_sub_event_len` ≥ 2250 µs; o autor da thread do DevZone usa 12000) que o nRF Toolbox da loja não expõe — precisa de um
build próprio do app (open source, Kotlin). Se não houver telefone compatível no dia, a
demo é o par embarcado (labs 1 + 2) projetado na tela.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ras_reflector`
- Nordic, *Bluetooth: Channel Sounding Reflector with Ranging Responder* (doc do sample)
- Nordic DevZone, *Introducing the nRF54L15 Tag* — o TAG como reflector e o build para `nrf54l15tag/nrf54l15/cpuapp`
