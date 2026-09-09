# GNSS · Lab 3 — NMEA limpo

**Esta pasta não tem código.** É uma receita de build sobre `gnss/01_gnss_basic`, no mesmo
molde de `comms/10_wifi_http_mqtt/`: mesmo código-fonte, outra configuração. O que muda aqui
não é o que o firmware faz, é **quem tem direito de escrever no console**.

O objetivo é uma porta serial que carrega **só sentença NMEA**, sem nada mais no meio: um
fluxo que o u-center clássico consegue abrir e plotar, e que dá para gravar em arquivo e
reproduzir depois — o seguro contra o dia em que a janela de céu não colaborar.

## Três coisas disputam o mesmo UART

O lab 1 deixa as três ligadas, e é por isso que o console dele é legível para uma pessoa e
ilegível para um programa:

| O que escreve | Opção | Neste lab |
|---|---|---|
| O bloco PVT formatado do sample (satélites, flags, precisão) | `CONFIG_GNSS_SAMPLE_NMEA_ONLY` | ligada — suprime o bloco, sobra o NMEA |
| O log do Zephyr (`LOG_INF` do sample e das bibliotecas) | `CONFIG_LOG` | desligada |
| A biblioteca de AT host, que despeja no mesmo UART o que o modem responde | `CONFIG_AT_HOST_LIBRARY` | desligada |

As duas últimas vêm ligadas do `prj.conf` do SDK. Desligar as três é o lab inteiro.

## Passo 1 — compilar e gravar

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_03_nmea C:/work/nrf-manaus-2/gnss/01_gnss_basic -- -D01_gnss_basic_CONFIG_GNSS_SAMPLE_NMEA_ONLY=y -D01_gnss_basic_CONFIG_LOG=n -D01_gnss_basic_CONFIG_AT_HOST_LIBRARY=n
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_03_nmea
```

O prefixo `01_gnss_basic_` nas três opções é o nome da imagem de aplicação no sysbuild, igual
ao nome da pasta do lab 1 — sem ele o `-D` cairia no sysbuild e não na aplicação.

### FLASH e RAM medidos

Imagem de aplicação (`01_gnss_basic`), comparada com o lab 1, que é o mesmo código com as
três opções na outra posição:

| Build | FLASH | RAM |
|---|---|---|
| Lab 1 (PVT + log + AT host) | 83052 B (8,45%) | 33044 B (15,62%) |
| Lab 3 (só NMEA) | 68352 B (6,95%) | 27308 B (12,90%) |

Desligar o log e a biblioteca de AT host devolve **14700 B de FLASH e 5736 B de RAM** — o
custo de manter as duas portas no mesmo lugar, medido.

## Passo 2 — abrir a porta

Mesma porta serial (VCOM) da DK, 115200 bps. A diferença aparece no primeiro segundo: em vez
do bloco redesenhado a cada PVT, saem linhas soltas, todas começando com `$`.

Confirmado na bancada: numa captura de 10 s saíram **63 linhas, todas começando com `$` e
nenhuma com checksum inválido** — só os cinco tipos de sentença da tabela acima. Nenhuma
linha de log, nenhum código de terminal.

É isso que torna a porta consumível por outro programa. O u-center 2 abre esta porta direto
e monta o mapa de desvio a partir dela; a porta do lab 1 ele até aceita, mas descarta toda
linha que não fecha checksum — e o log do Zephyr, entremeado com as sentenças, faz
exatamente isso acontecer. Para gravar a sessão e reprocessar depois, use
`gnss/04_demo_rtk/tools/nmea_captura.py`, que salva o mesmo fluxo em `.nmea` e em `.uc2`.

Com o fluxo limpo, a porta serve para duas coisas que o console do lab 1 não serve:

- **u-center clássico** — abre a porta direto e plota a dispersão do nRF9151, que é o primeiro
  degrau da demo da escada de precisão.
- **Gravar log NMEA** — o arquivo gravado pode ser reproduzido depois, sem antena e sem céu.
  É o plano B do dia da aula.

## As cinco sentenças

O sample chama `nrf_modem_gnss_nmea_mask_set()` com as cinco de sempre, e faz isso
**independentemente desta configuração** — `NMEA_ONLY` não escolhe sentença, só cala o resto:

`$GPRMC`, `$GPGGA`, `$GPGLL`, `$GPGSA`, `$GPGSV`

Duas consequências que importam para o módulo:

- **É o mesmo conjunto que o EVK-X20P emite de fábrica.** Os dois receptores da escada de
  precisão falam o mesmo dialeto de saída sem que ninguém configure nada.
- **As duas que o RTKPLOT exige, `$GPRMC` e `$GPGGA`, estão nas duas pontas.** A ferramenta
  que compara os traços dos dois receptores lê os dois arquivos com o mesmo parser.

## Por que este build existe

O ponto de aula é este: **receptor comercial tem porta de dados separada da de depuração.**
Um módulo GNSS de produto entrega NMEA (ou um protocolo binário) numa porta, e mensagem de
diagnóstico noutra, justamente para que o consumidor do dado não tenha que filtrar texto de
log. Aqui as duas nascem no mesmo UART, e o lab mostra o preço: para ter a porta de dados,
foi preciso apagar a de depuração.

Ou seja — este firmware é o **oposto** do que se quer em bancada. Sem log e sem AT host, não
há como perguntar `AT+CGMR` pela versão do firmware do modem, nem ver por que a conexão
falhou. Grave o lab 1 para investigar, e o lab 3 para colher.

## `verifica_nmea.sh`

```
sh gnss/03_nmea/verifica_nmea.sh gnss/01_gnss_basic/build_03_nmea
```

Esperado: `OK: build de NMEA limpo`. O script confere as três opções no `.config` da imagem
de aplicação — a que falta e as duas que sobram. Rodado contra o build do lab 1, acusa as
três, que é exatamente a diferença entre os dois labs.

## Pegadinhas

- **Sem `CONFIG_LOG`, um erro de rede é silencioso.** O firmware não fica mudo por defeito;
  ele fica mudo por projeto. Se nada sai da porta, grave o lab 1 antes de suspeitar da antena.
- **Sem `CONFIG_AT_HOST_LIBRARY`, não há comando AT.** A leitura da versão do firmware do
  modem (`AT+CGMR`) é feita no lab 1, não aqui.
- **O modo TTFF do lab 2 também liga `NMEA_ONLY`** — o `Kconfig` do sample tem
  `select GNSS_SAMPLE_NMEA_ONLY` dentro de `GNSS_SAMPLE_MODE_TTFF_TEST`. Mesmo assim o
  console do lab 2 continua sujo, porque lá o log e o AT host seguem ligados. `NMEA_ONLY`
  sozinho não entrega porta limpa.
- **A distância até a referência não é impressa.** `CONFIG_GNSS_SAMPLE_REFERENCE_LATITUDE` e
  `..._LONGITUDE` ficam vazias no repositório por decisão de escopo, e
  `print_distance_from_reference()` sai cedo quando não há referência. Se alguém preencher as
  duas, essa linha passa a sair no meio do NMEA e suja o fluxo.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/cellular/gnss` (`Kconfig`, `src/main.c`)
- `gnss/01_gnss_basic/` — o código que este lab recompila
- Spec do módulo — `docs/superpowers/specs/2026-09-08-gnss-design.md`, §sentenças NMEA
