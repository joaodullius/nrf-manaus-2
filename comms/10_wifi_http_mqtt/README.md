# Wi-Fi · Lab 10 — HTTP e MQTT sobre o mesmo payload

> **O console continua na primeira VCOM.** Este lab regrava a placa com o shield
> acoplado, então vale a mesma troca dos labs 6 a 9: com a nRF7002-EB II, o console vai
> para a `uart30` e sai na **primeira** VCOM da DK, não na segunda. Está medido e
> explicado no lab 9 (`comms/09_wifi_tcp/README.md`, no topo); aqui não muda nada,
> porque é o mesmo firmware.
>
> Esta pasta também não tem `.gitignore` próprio, ao contrário dos outros sete: ela não
> gera diretório de build (o build sai em `comms/09_wifi_tcp/build_*`), e o `.gitignore`
> da raiz já cobre `build*/` e `__pycache__/`.

Este lab não tem firmware próprio: ele **recompila o firmware do lab 9**
(`comms/09_wifi_tcp/`) escolhendo outra opção da choice `LAB_TRANSPORTE` do
Kconfig. O `src/main.c` não muda uma linha — monta a mesma amostra, chama os
mesmos quatro nomes (`transporte_abrir/enviar/receber/fechar`). O que muda é
qual implementação de `src/transporte.c` entra no binário: TCP puro (lab 9),
HTTP (POST por amostra) ou MQTT (publish/subscribe). É a tese do bloco —
**um payload, três transportes** — fechada com número medido em vez de
afirmação.

## O que muda (e o que não muda)

| | TCP (lab 9) | HTTP | MQTT |
|---|---|---|---|
| Formato da amostra | `src/payload.c`, igual nos três | igual | igual |
| Uplink (telemetria) | `send()` no socket já aberto | `POST /telemetria` | `PUBLISH` no tópico `CONFIG_LAB_MQTT_TOPICO` |
| Downlink (comando de LED) | linha `LED 1`/`LED 0` no mesmo socket, empurrada pelo servidor a qualquer momento | `GET /comando` — o kit tem que perguntar | `SUBSCRIBE` em `<tópico>/comando`, empurrado pelo broker |
| Conexão | um socket aberto o tempo todo | uma conexão nova por requisição (sem estado entre chamadas) | um socket aberto o tempo todo, para o broker |
| Ferramenta de PC | `../09_wifi_tcp/tools/wifi_server.py` | `tools/wifi_http_server.py` | `tools/wifi_mqtt_sub.py` + broker (mosquitto) |

Nenhuma das duas variantes novas reescreve o payload: `tools/payload_ref.py`
não existe nesta pasta de propósito — é o mesmo módulo do lab 9
(`../09_wifi_tcp/tools/payload_ref.py`), que os dois scripts deste lab
importam por caminho relativo.

## As camadas — o que é reaproveitado e o que é trocado

Esta seção é a base do diagrama comparativo do material. A ideia central: **os três
transportes trocam uma única peça no meio da pilha.** Tudo abaixo dela é o mesmo código,
o mesmo binário do Zephyr, a mesma configuração.

```
          +----------------------------------------------+
          |   APLICAÇÃO  —  src/main.c  (534 linhas)      |   IDÊNTICA
          |   3 threads, sensores, botão, LED, backoff    |   nos três
          +----------------------------------------------+
          |   PAYLOAD  —  src/payload.c  (26 linhas)      |   IDÊNTICO
          |   a linha JSON, sempre a mesma                |   nos três
          +----------------------------------------------+
          |   transporte.h — abrir/enviar/receber/fechar  |   A MESMA
          |   + o contrato de erro                        |   interface
          +======== É AQUI QUE MUDA ====================+
          |  TCP puro   |    HTTP      |     MQTT        |
          |  215 linhas |   262 linhas |    431 linhas   |
          |  (nenhuma   |  http_client |    mqtt_lib     |
          |   lib extra)|              |                 |
          +----------------------------------------------+
          |   SOCKETS BSD do Zephyr (zsock_*)            |   IDÊNTICO
          +----------------------------------------------+
          |   TCP/IP + DHCPv4 cliente                    |   IDÊNTICO
          +----------------------------------------------+
          |   wpa_supplicant + driver nrf_wifi           |   IDÊNTICO
          +----------------------------------------------+
          |   SPI  →  nRF7002  (MAC + PHY)               |   IDÊNTICO
          +----------------------------------------------+
```

### O que é literalmente o mesmo

Conferido nas três `.config` geradas:

| Camada do Zephyr | TCP | HTTP | MQTT |
|---|---|---|---|
| `CONFIG_NET_SOCKETS` (sockets BSD) | ✅ | ✅ | ✅ |
| `CONFIG_NET_TCP` | ✅ | ✅ | ✅ |
| `CONFIG_NET_IPV4`, `CONFIG_NET_DHCPV4` | ✅ | ✅ | ✅ |
| `CONFIG_NET_BUF` | ✅ | ✅ | ✅ |
| `CONFIG_WIFI_NM_WPA_SUPPLICANT` | ✅ | ✅ | ✅ |
| `CONFIG_WIFI_CREDENTIALS` | ✅ | ✅ | ✅ |

**Os três falam TCP.** Nenhum usa UDP para a telemetria. HTTP e MQTT não substituem o TCP:
eles se **empilham** sobre ele. É o mal-entendido mais comum sobre esse trio.

### O que cada um acrescenta

| | Biblioteca extra do Zephyr | Linhas em `transporte.c` |
|---|---|---|
| **TCP puro** | **nenhuma** — fala direto com `zsock_*` | 215 |
| **HTTP** | `CONFIG_HTTP_CLIENT` + `CONFIG_HTTP_PARSER` | 262 |
| **MQTT** | `CONFIG_MQTT_LIB` (+ `MQTT_KEEPALIVE`) | 431 |

Nenhum dos três usa `CONFIG_DNS_RESOLVER`: o endereço do servidor é um IP literal
(`CONFIG_LAB_SERVIDOR_IP`), não um nome. Num produto real isso mudaria, e o DNS entraria
como mais uma camada comum aos três.

### O custo de cada escolha, medido

| | FLASH | RAM | Ciclo de telemetria |
|---|---|---|---|
| TCP puro | 555.664 B (26,65%) | 191.952 B (36,68%) | 2050 ms |
| HTTP | 567.160 B (27,20%) | 192.200 B (36,73%) | 2095 ms |
| MQTT | 560.992 B (26,91%) | 193.392 B (36,96%) | 2053 ms |

Com `CONFIG_LAB_INTERVALO_MS=2000` nos três. A diferença de FLASH entre o mais leve e o
mais pesado é de **11,5 KB** — pouco, para três protocolos de aplicação diferentes, e é
a evidência de que a parte cara da pilha (Wi-Fi, supplicant, TCP/IP) é a mesma nos três.

> **Os ciclos nem sempre foram iguais.** Até 2026-09-07 o TCP e o MQTT mediam ~3000 ms
> contra ~2095 ms do HTTP, e parecia vantagem do HTTP. Era um defeito: a thread de
> recepção segurava o mutex do transporte durante o segundo inteiro do `poll`, atrasando
> quem queria enviar. Corrigido (ver o comentário em `transporte_receber()` dos dois),
> os três convergiram. Fica o aviso metodológico: **medir os três lado a lado revelou um
> bug que a leitura do código não revelou.**

### Para o diagrama: as três perguntas que separam os transportes

| | Quem inicia o downlink? | Quantas conexões? | Quem conhece quem? |
|---|---|---|---|
| **TCP** | o **servidor** empurra quando quer | uma, aberta o tempo todo | kit ↔ servidor, ponto a ponto |
| **HTTP** | o **kit** pergunta (`GET /comando`) | uma **nova por requisição** | kit ↔ servidor, ponto a ponto |
| **MQTT** | o **broker** empurra (assinatura) | uma, aberta o tempo todo | ninguém: kit e assinante só conhecem o **broker** |

A terceira coluna é a que mais rende em aula: no TCP e no HTTP o kit precisa saber o
endereço de quem consome os dados. No MQTT, **não** — kit e assinante nunca trocam
endereço, só o nome do tópico. Foi o que se viu na bancada: o assinante rodava em outra
máquina lógica (`localhost` vs. IP) e o kit não teve de saber de nada disso.


## Kconfig novo (em `comms/09_wifi_tcp/Kconfig`)

```
choice LAB_TRANSPORTE
    ...
config LAB_TRANSPORTE_HTTP
    bool "HTTP (POST por amostra)"
    select HTTP_CLIENT

config LAB_TRANSPORTE_MQTT
    bool "MQTT (publish/subscribe)"
    select MQTT_LIB
    select MQTT_CLEAN_SESSION
endchoice

config LAB_MQTT_TOPICO
    string "Topico MQTT"
    default "nrf-manaus/telemetria"
    depends on LAB_TRANSPORTE_MQTT
```

`CONFIG_HTTP_CLIENT` e `CONFIG_MQTT_LIB`/`CONFIG_MQTT_CLEAN_SESSION` entram
via `select` na opção da choice, **não** como `CONFIG_X=y` solto no
`prj.conf`. Se fossem soltos no `prj.conf`, valeriam para as três variantes
ao mesmo tempo — a comparação de FLASH da tabela abaixo deixaria de ser
justa, porque a build TCP pagaria o custo do cliente HTTP e da biblioteca
MQTT sem usar nenhum dos dois. Com `select`, cada biblioteca só entra no
binário quando o transporte correspondente é o escolhido.

`CONFIG_LAB_PORTA` (já existia no lab 9) passou a servir três papéis
dependendo do transporte: porta do TCP puro, porta do `wifi_http_server.py`,
ou porta do broker MQTT. O padrão (9000) só faz sentido para TCP — para
HTTP e MQTT, passe a porta certa na linha de build (ver abaixo).

## Compilar as três variantes

Com `minha_rede.conf` preenchido (mesma convenção do lab 9) e o IP do PC em
mãos:

```bash
cd C:\ncs\v3.4.0

# TCP (igual ao lab 9, porta 9000)
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/09_wifi_tcp/build_TCP C:/work/nrf-manaus-2/comms/09_wifi_tcp -- -D09_wifi_tcp_SHIELD="nrf7002eb2" -D09_wifi_tcp_SNIPPET=nrf70-wifi -D09_wifi_tcp_EXTRA_CONF_FILE=minha_rede.conf -D09_wifi_tcp_CONFIG_LAB_SERVIDOR_IP=\"<ip-do-pc>\" -D09_wifi_tcp_CONFIG_LAB_TRANSPORTE_TCP=y

# HTTP (wifi_http_server.py, porta 8000)
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/09_wifi_tcp/build_HTTP C:/work/nrf-manaus-2/comms/09_wifi_tcp -- -D09_wifi_tcp_SHIELD="nrf7002eb2" -D09_wifi_tcp_SNIPPET=nrf70-wifi -D09_wifi_tcp_EXTRA_CONF_FILE=minha_rede.conf -D09_wifi_tcp_CONFIG_LAB_SERVIDOR_IP=\"<ip-do-pc>\" -D09_wifi_tcp_CONFIG_LAB_TRANSPORTE_HTTP=y -D09_wifi_tcp_CONFIG_LAB_PORTA=8000

# MQTT (broker mosquitto, porta 1883)
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/09_wifi_tcp/build_MQTT C:/work/nrf-manaus-2/comms/09_wifi_tcp -- -D09_wifi_tcp_SHIELD="nrf7002eb2" -D09_wifi_tcp_SNIPPET=nrf70-wifi -D09_wifi_tcp_EXTRA_CONF_FILE=minha_rede.conf -D09_wifi_tcp_CONFIG_LAB_SERVIDOR_IP=\"<ip-do-pc>\" -D09_wifi_tcp_CONFIG_LAB_TRANSPORTE_MQTT=y -D09_wifi_tcp_CONFIG_LAB_PORTA=1883
```

Os três builds ficam em `comms/09_wifi_tcp/build_TCP`, `build_HTTP` e
`build_MQTT` — caminho curto de propósito (Constraints globais da frente).
Gravar com `west flash -d <pasta do build>`, igual ao lab 9.

## FLASH e RAM medidos

Mesmo board (`nrf54lm20dk/nrf54lm20b/cpuapp`), mesmo `prj.conf` de base,
única variável é `CONFIG_LAB_TRANSPORTE_*`. **Os três binários abaixo não
são só tamanho compilado**: código equivalente foi gravado e exercitado com
hardware real, nos dois sentidos (telemetria subindo, comando de LED
descendo — ver "Roteiro de bancada" mais adiante) — a tabela é tamanho de
binário que comprovadamente roda, não só que compila limpo.

| Transporte | FLASH | % FLASH (2036 KB) | RAM | % RAM (511 KB) |
|---|---|---|---|---|
| TCP | 555512 B | 26,64% | 191952 B | 36,68% |
| HTTP | 567184 B | 27,20% | 192200 B | 36,73% |
| MQTT | 560904 B | 26,90% | 193392 B | 36,96% |

**O tamanho exato varia alguns bytes com o comprimento do SSID e da senha**,
porque `minha_rede.conf` é compilado no binário (`CONFIG_WIFI_CREDENTIALS_
STATIC_SSID`/`PASSWORD`) — os números acima vêm de um build com uma
credencial de preenchimento (`minha_rede.conf` não pode ficar vazio, ver o
lab 9), não da rede real de nenhuma sala. Comparando com a mesma imagem TCP
no lab 9 (`../09_wifi_tcp/README.md`, medida com a credencial real de uma
bancada): **555508 B**, 4 bytes a menos que aqui — a diferença é só o
comprimento da credencial, não uma divergência de código. Se o seu número
depois de compilar não bater exatamente com esta tabela, é essa a causa
mais provável, não um erro seu.

As três cabem com folga (RAM entre 36,68% e 36,96% dos 511 KB — a diferença
entre elas é pequena, ~0,28 ponto percentual). **O MQTT não precisou virar
referência lida**. HTTP custa mais FLASH que os outros dois (+11672 B sobre
o TCP, o parser HTTP embutido do Zephyr) mas pouco RAM a mais (+248 B) — o
grosso do custo de HTTP é código, não estado. MQTT soma +1440 B de RAM sobre
o TCP: é o preço de **dois slots** (`struct mqtt_slot`, ~720 B cada — dois
buffers de 256 B para RX/TX do cliente MQTT mais o resto do estado da
conexão), não um só. Ter dois slots em vez de um é o que corrige o item 2 da
rodada de correção 1 (ver a seção seguinte): a reconexão MQTT monta e
conecta o slot novo inteiro antes de trocar, em vez de reescrever o único
slot existente enquanto outra thread ainda pode estar usando ele.

## Comparação de pilha e heap com o precedente da Nordic

Nenhuma das duas variantes novas usa TLS: `CONFIG_MAIN_STACK_SIZE` continua
em 5200 (o mesmo valor que o próprio lab 9 já usa, herdado do
`nrf/samples/wifi/sta`) e nenhum heap de mbedTLS foi tocado. O precedente que
se aplicaria a uma variante com TLS — `nrf/samples/wifi/provisioning/softap`,
que sobe `CONFIG_MAIN_STACK_SIZE` para 6200 e ainda define
`CONFIG_WIFI_NM_WPA_SUPPLICANT_THREAD_STACK_SIZE=8192` e
`CONFIG_MBEDTLS_HEAP_SIZE=49152` — **não se aplica aqui**, porque este lab
optou por manter HTTP e MQTT sem TLS.

**Essa é uma escolha deliberada, não uma omissão**: o objetivo do lab 10 é
comparar transporte (como o mesmo payload viaja), não criptografia. TLS
somaria uma variável nova (handshake, certificados, heap) a uma comparação
que já tem três braços — a tabela de FLASH/RAM acima deixaria de isolar "o
que cada transporte custa" e passaria a misturar isso com "o que TLS custa
em cada um deles", que é uma pergunta diferente e, para HTTP e MQTT, também
diferente entre si (HTTPS via `http_client_req()` com socket TLS vs. MQTT
sobre `MQTT_TRANSPORT_SECURE`). Um lab de segurança de transporte, com o
precedente do `softap` (pilha 6200, heap mbedTLS 49152), é trabalho
separado.

As threads que chamam `transporte_*` (`telemetria_id`, `botao_id`,
`recepcao_id`, todas em `src/main.c`) foram redimensionadas na rodada de
correção 1 da revisão desta task: de 2048/1024/2048 bytes para **3072 bytes
as três**. O piso é o próprio sample de referência do Zephyr para
`http_client_req()` (`zephyr/samples/net/sockets/http_client/prj.conf`
reserva 3072 bytes de `CONFIG_MAIN_STACK_SIZE` para uma thread que só faz
isso) — o caminho mais fundo que qualquer uma das três pode percorrer, já
que a mesma `http_client_req()` roda tanto em `transporte_enviar()`
(`telemetria_id`/`botao_id`, via `POST /telemetria`) quanto em
`transporte_receber()` (`recepcao_id`, via `GET /comando`) quando o HTTP é o
transporte escolhido. `telemetria_id` e `botao_id` chamam a mesma função
(`montar_e_enviar()`), então não há motivo para uma ter menos pilha que a
outra — a assimetria anterior (2048 vs. 1024) não vinha de nenhuma análise
de caminho, só nunca tinha estourado. **Confirmado na bancada**: os três
transportes — TCP, HTTP (POST de telemetria e GET de comando) e MQTT
(PUBLISH de telemetria e o comando de LED via assinatura) — rodaram com
hardware real sobre esse dimensionamento sem `USAGE FAULT`, nos dois
sentidos, **e também sob reconexão** (broker MQTT derrubado e religado com
o kit conectado, backoff de 1 a 8 s até voltar — ver "Roteiro de bancada"
abaixo). Não é mais uma leitura de precedente sem exercício real: é
evidência de bancada, sob os três caminhos que o dimensionamento precisava
cobrir.

## Bytes por amostra — medido em loopback

Sem hardware nesta tarefa (quem grava e mede na bancada é o instrutor), os
bytes de aplicação de cada transporte foram medidos com o código real rodando
em loopback (127.0.0.1): o `ServidorHTTP` real deste lab respondendo a uma
requisição HTTP montada byte a byte igual ao que
`zephyr/subsys/net/lib/http/http_client.c` produz para os campos que
`src/transporte.c` preenche (conferido lendo o fonte da biblioteca); e um
cliente `paho-mqtt` real, com a mesma sequência do firmware (CONNECT,
SUBSCRIBE no tópico de comando, PUBLISH no tópico de telemetria), falando
com um mosquitto real através de um proxy TCP local que grava os bytes e
recorta os pacotes MQTT pelo cabeçalho fixo. **Não inclui os cabeçalhos de
Ethernet/IP/TCP-UDP** — esses são iguais nos três transportes e não fazem
parte do que muda entre eles; uma captura de Wireshark na bancada real soma
esse overhead fixo por igual às três linhas da tabela.

Amostra representativa usada na medição:
`{"seq":42,"uptime_ms":123456,"temp_c":25.37,"rssi_dbm":-52,"botao":false}\n`
(74 bytes).

| Transporte | Uplink por amostra | Downlink (por consulta/evento) |
|---|---|---|
| TCP | 74 B (só o `send()`, sem resposta de aplicação) | 6 B (`LED 1\n`/`LED 0\n`), só quando o operador manda um comando — sem custo quando não manda |
| HTTP | 269 B (176 B de requisição `POST` + 93 B de resposta `200 OK`) | 147 B **a cada consulta** de `GET /comando` (46 B de requisição + 101 B de resposta `204`), mesmo sem comando pendente |
| MQTT | 99 B (pacote `PUBLISH`; `CONNECT` 32 B + `SUBSCRIBE` 36 B são custo único de conexão, não por amostra) | 38 B (pacote `PUBLISH` em `<tópico>/comando` — o nome do tópico completo viaja em toda publicação, por isso custa mais que o payload `LED 1` sozinho), só quando alguém publica |

TCP e MQTT ficam próximos no uplink (74 B vs. 99 B — a diferença é o
cabeçalho fixo do `PUBLISH` mais o nome do tópico, que viaja em toda
publicação porque este lab usa QoS 0 sem tópico curto/alias). HTTP é o mais
caro dos três, e não só no uplink: cada amostra custa 269 B (quase 3,6× o
TCP) e ainda paga 147 B **por segundo** de polling no downlink, tenha ou não
comando pendente — é o número que sustenta a seção seguinte.

## Por que o downlink separa os três

TCP e MQTT são simétricos: o comando chega **empurrado**, sem o kit
perguntar — TCP porque o servidor escreve na mesma conexão aberta a
qualquer momento (`enviar_comando()` do `wifi_server.py` do lab 9), MQTT
porque o broker entrega uma mensagem publicada no tópico assinado assim que
ela existe (`SUBSCRIBE` feito uma vez, em `transporte_abrir()`). Nos dois
casos, não haver comando pendente não custa banda nenhuma.

HTTP não tem como fazer isso: não existe um jeito de o servidor iniciar uma
conexão para o kit (o kit não está ouvindo em porta nenhuma, e frequentemente
está atrás de NAT/DHCP). A única saída é o kit perguntar — `GET /comando`,
em `transporte_receber()` (`src/transporte.c`) — e cada pergunta custa 147 B
mesmo quando a resposta é "nada" (`204 No Content`). Com a thread de
recepção perguntando a cada 1 s (`thread_recepcao()`, `src/main.c`,
`K_SECONDS(1)`), isso é **147 B/s de tráfego constante só para descobrir que
não há novidade** — contra zero do TCP e do MQTT no mesmo cenário. É o
argumento concreto, não uma preferência de estilo: HTTP request/response não
tem primitiva de push: o preço do polling é estrutural do protocolo, não um
detalhe de implementação deste lab.

## Ferramentas de PC

### `tools/wifi_http_server.py`

```bash
cd comms/10_wifi_http_mqtt/tools
pip install -r requirements.txt
python wifi_http_server.py --porta 8000
```

`POST /telemetria` imprime a amostra; `GET /comando` devolve o comando
pendente (`200`, corpo `LED 1` ou `LED 0`) ou `204` se não houver nenhum —
consumido na hora (o mesmo comando não aparece de novo no próximo `GET`).
Teclas: `l` liga o LED1, `d` apaga, `q` sai. A classe `ServidorHTTP`
(`porta`, `ao_receber`) é o que os testes exercitam sem hardware, mesmo
padrão do `Servidor` do lab 9: `porta=0` deixa o SO escolher a porta,
`porta_real` devolve a efetiva.

### `tools/wifi_mqtt_sub.py`

Precisa de um broker MQTT rodando — este curso usa o **mosquitto** local
(`C:\Program Files\mosquitto`, já instalado e verificado nesta bancada).

**Atenção, pegadinha confirmada na bancada: o mosquitto 2.x (2.0.22 aqui)
fechou os padrões de fábrica.** Subido sem arquivo de configuração, ele
escuta só em `localhost` e recusa cliente anônimo — e isso engana, porque
`wifi_mqtt_sub.py`, rodando no mesmo PC, conecta normalmente (é loopback:
`localhost` alcança `localhost`). Só o kit falha, porque chega pela rede,
não por loopback, e a porta nem está aberta para a rede. O sintoma no
firmware é `Falha ao mandar o CONNECT MQTT (-116)` — aponta para rede
(IP/porta errados, firewall), não para o broker, que é onde o problema de
fato está. O aluno vê o assinante conectado e conclui, errado, que o broker
está no ar para qualquer um.

O remédio é subir o mosquitto com um arquivo de configuração de duas linhas
(local, não versionado — não faz parte deste repositório):

```
listener 1883 0.0.0.0
allow_anonymous true
```

```bash
"C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf
```

`listener 1883 0.0.0.0` faz o broker escutar em todas as interfaces de rede
do PC, não só `localhost` — na mesma porta que o firmware usa
(`CONFIG_LAB_PORTA`; 1883 no exemplo de build deste README, mas o número
tem que bater dos dois lados). `allow_anonymous true` aceita conexão sem
usuário/senha, porque o kit não manda nenhum. **Isso é aceitável só para o
laboratório**: um broker de produto real pede credencial e roda atrás de
TLS — abrir mão dos dois de propósito para um kit numa rede de sala fechada
é uma escolha de ambiente de ensino, não algo que se leva para produção.

Como qualquer servidor deste lab ouvindo em rede, a porta também precisa
estar liberada no firewall do Windows — mesma pegadinha do lab 9, seção
"O firewall do Windows" logo abaixo.

Em outro terminal:

```bash
cd comms/10_wifi_http_mqtt/tools
pip install -r requirements.txt
python wifi_mqtt_sub.py --host localhost --porta 1883 --topico nrf-manaus/telemetria
```

Assina `nrf-manaus/telemetria`, imprime cada amostra válida e publica em
`nrf-manaus/telemetria/comando` pelo teclado (`l`/`d`/`q`, mesmo esquema dos
outros dois servidores). A classe `AssinanteMQTT` (`host`, `porta`,
`topico`, `ao_receber`) é o que os testes exercitam contra um mosquitto real
subido pelo próprio teste — sem mock de MQTT.

### O firewall do Windows (mesma pegadinha do lab 9, portas diferentes)

O lab 9 já documenta (`../09_wifi_tcp/README.md`, seção "Pegadinhas") que o
Windows bloqueia por padrão a entrada de conexão para um processo Python
ouvindo no perfil de rede Private, mesmo com IP e porta corretos — o sintoma
engana dos dois lados (nada chega, nenhum erro aparece). Os dois servidores
deste lab sofrem do mesmo problema, cada um na sua porta:

```powershell
New-NetFirewallRule -DisplayName "Lab 10 Wi-Fi HTTP (curso nrf-manaus-2)" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private

New-NetFirewallRule -DisplayName "Lab 10 Wi-Fi MQTT (curso nrf-manaus-2)" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 1883 -Profile Private
```

A segunda regra é para o **mosquitto**, não para o Python: é o broker quem
escuta a porta 1883 e aceita a conexão do kit, `wifi_mqtt_sub.py` só fala
com o broker via loopback. Sem essa regra, o sintoma é o mesmo do lab 9: o
kit tenta conectar, o broker está de pé e ouvindo, e a conexão nunca chega.

## Testes automáticos (PC, sem hardware)

```bash
cd comms/10_wifi_http_mqtt/tools
python -m pytest -q
```

`10 passed` nesta bancada:

- `tests/test_http_server.py` (6 testes) sobe um `ServidorHTTP(porta=0)` de
  verdade e conversa com ele por HTTP de verdade, cobrindo o caminho feliz
  (`POST` válido chama `ao_receber`) e os casos ruins: JSON inválido e campo
  faltando (nenhum dos dois chama `ao_receber`, e devolvem `400`), rota
  desconhecida (`404`) e o consumo do comando pendente (`GET /comando`
  devolve o comando uma vez só — a segunda chamada logo em seguida devolve
  `204`).
- `tests/test_mqtt_sub.py` (4 testes) sobe um **mosquitto real** num
  processo à parte (porta livre escolhida pelo SO, sem arquivo de
  configuração) e um `AssinanteMQTT` de verdade contra ele — sem mock de
  MQTT. Cobre o caminho feliz (mensagem válida chega e é interpretada), o
  caso ruim central (uma mensagem inválida publicada no meio de duas válidas
  não aparece em `ao_receber` **e não derruba a assinatura** — a próxima
  mensagem válida ainda chega), que `publicar_comando()` publica no tópico
  `<tópico>/comando` de verdade (conferido por um assinante de teste
  independente) e que conectar numa porta fechada devolve `False` sem
  levantar exceção (em vez de um traceback cru na cara de quem só quer saber
  se o broker está de pé). **Pulados com mensagem clara** se o mosquitto não
  for encontrado no PATH nem em `C:\Program Files\mosquitto` — mesmo
  critério de `../09_wifi_tcp/tools/tests/test_payload_c.py` para um
  compilador de host ausente.

## Roteiro de bancada

Gravar cada variante com o servidor certo rodando no PC:
- `build_TCP` → `python ../09_wifi_tcp/tools/wifi_server.py --porta 9000`
- `build_HTTP` → `python tools/wifi_http_server.py --porta 8000`
- `build_MQTT` → mosquitto com o arquivo de configuração da seção
  `tools/wifi_mqtt_sub.py` acima, depois `python tools/wifi_mqtt_sub.py --porta 1883`

**Já confirmado na bancada, com hardware real — os três transportes, nos
dois sentidos (telemetria subindo, comando de LED descendo):**
- **TCP**: telemetria e comando de LED (`l`/`d` no `wifi_server.py` →
  LED1) confirmados visualmente pelo instrutor.
- **HTTP**: telemetria e comando de LED (`l`/`d` no `wifi_http_server.py`
  → LED1) confirmados visualmente pelo instrutor.
- **MQTT**: telemetria com sequência (`seq`) contínua, e o comando de LED
  (`l`/`d` no `wifi_mqtt_sub.py` → assinatura do kit em `<tópico>/comando`
  → LED1) confirmado pelo console do próprio kit:
  ```
  lab_transporte: MQTT conectado em <ip>:<porta>, publicando em nrf-manaus/telemetria
  lab_wifi_tcp: LED1 aceso (comando do servidor)
  lab_wifi_tcp: LED1 apagado (comando do servidor)
  ```
- **Reconexão sob perda de serviço** (MQTT, broker derrubado com o kit
  conectado e religado 25 s depois):
  ```
  MQTT desconectado (-104)
  Servidor fechou a conexao; reconectando
  Falha ao enviar a amostra 6 (-128); reconectando
  Falha ao mandar o CONNECT MQTT (-116); nova tentativa em 1000 ms
                                          nova tentativa em 2000 / 4000 / 8000 ms
  MQTT conectado em <ip>:1883, publicando em nrf-manaus/telemetria
  ```
  A porta do log real desta bancada foi 9000 (reuso de uma regra de
  firewall já existente, sem privilégio de administrador para criar outra)
  — não é a porta que este README recomenda; redigida para 1883 aqui, para
  o exemplo ficar coerente com o resto do lab (o `mosquitto.conf`, a regra
  de firewall e o comando de build acima usam 1883). Qualquer porta livre
  serve, desde que a mesma esteja em `CONFIG_LAB_PORTA` (build), no
  `mosquitto.conf` e na regra de firewall — os três precisam bater.

  A queda foi detectada por **dois caminhos ao mesmo tempo** — a thread de
  recepção (`MQTT desconectado`) e a de telemetria (`Falha ao enviar`) — e
  mesmo assim só houve **uma** reconexão, não duas concorrentes: é a
  evidência, sob concorrência real e não só em teste, de que a
  serialização de `reconectar_transporte()` (`src/main.c`) segura o caso
  para o qual foi desenhada. O backoff dobrou de 1 a 8 s até o broker
  voltar, como documentado no lab 9.

**Ainda a confirmar na bancada:**
- Botão (amostra imediata com `"botao":true`) nas três variantes — o caminho é
  herdado do lab 9, mas **lá o gesto também não foi exercitado**: o `sw0` ainda não
  foi apertado por ninguém em nenhum dos dois labs. O código está revisado nos dois;
  o que falta é o dedo na placa.
- Captura com Wireshark ou `tcpdump` no PC durante uma amostra de cada
  variante, para confirmar os números da tabela "Bytes por amostra" contra
  tráfego de Wi-Fi de verdade (a medição deste README é em loopback — ver a
  ressalva na própria seção).

## Plano B — sem rede utilizável na sala, ou com isolamento de cliente

Mesmo remédio do lab 9 (`../09_wifi_tcp/README.md`, seção "Plano B"): não
muda nada de firmware nem de servidor, só a rede à qual PC e kit se
associam. Vale para os três transportes deste lab.
