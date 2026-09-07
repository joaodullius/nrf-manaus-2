# Wi-Fi · Lab 7 — Associação programática com `minha_rede.conf`

> **Antes de tudo: com a EB II acoplada, a VCOM do console muda.** Sem o shield, o
> console desta DK fica na `uart20`, que sai na **segunda** VCOM do chip de interface
> USB. O overlay do shield (`nrf7002eb2`) desabilita a `uart20` e move o console (e o
> `shell-uart`) para a `uart30` — e essa UART sai na **primeira** VCOM. Quem estava
> acostumado a abrir a segunda porta (firmware sem shield, por exemplo um lab de
> Channel Sounding) precisa trocar para a primeira ao gravar este lab. Esse
> reroteamento é um contorno de um conflito de pinos que existe só na revisão
> **pré-produção** da nRF54LM20-DK, presente no nRF Connect SDK v3.4.0 (Zephyr
> 4.4.0) — nossa árvore. Em versões mais novas do Zephyr o shield deixa de reroteiar
> nessa placa: o console volta para a `uart20`/segunda VCOM e o `sw3` volta a existir.
> Na dúvida, abra as duas portas seriais da DK e veja qual responde.

Este lab é a primeira aplicação com lógica própria da frente de Wi-Fi: `nrf/samples/
wifi/sta` rodando na nRF54LM20-DK (variante B) com a nRF7002 EB-II encaixada. Em vez
do shell interativo do lab 6, o firmware conecta sozinho, sem intervenção do usuário,
usando a credencial armazenada por `CONFIG_WIFI_CREDENTIALS_STATIC`. É aqui que entra
a convenção de credencial do curso — `minha_rede.conf`, um fragmento por aluno — que
os labs 9, 11, 12 e 13 também consomem.

> **Origem.** Cópia integral de `nrf/samples/wifi/sta` do **nRF Connect SDK v3.4.0**.
> Licença Nordic preservada em [LICENSE](LICENSE). `prj.conf`, `CMakeLists.txt` e
> `src/main.c` levam o cabeçalho `ORIGEM:` do curso. Duas divergências do SDK, as
> duas descritas abaixo: a credencial sai do `prj.conf` e vai para o
> `minha_rede.conf`, e o `CMakeLists.txt` ganha uma falha proposital quando esse
> fragmento não foi preenchido.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54LM20-DK** (variante B, `nrf54lm20b`) | roda o firmware; host do Wi-Fi |
| **nRF7002 EB-II** | shield companion Wi-Fi 6, encaixado no header de expansão |
| **PC** | terminal serial (VCOM) e a rede Wi-Fi da sala |

Com o shield acoplado, `sw3` some do overlay (ele não existe mais): sobram `sw0`–`sw2`
e os quatro LEDs.

## `minha_rede.conf` — a credencial do aluno

O `prj.conf` deste sample, como veio do SDK, tinha `CONFIG_WIFI_CREDENTIALS_STATIC_
SSID="Myssid"` e a senha de exemplo em texto puro. O curso tira essas duas linhas do
`prj.conf` e move a credencial para um fragmento externo, rastreado pelo git e
**vazio**:

```
CONFIG_WIFI_CREDENTIALS_STATIC_SSID=""
CONFIG_WIFI_CREDENTIALS_STATIC_PASSWORD=""
```

Cada aluno preenche o seu localmente com a rede da sala e compila com:

```
west build ... -- -DEXTRA_CONF_FILE=minha_rede.conf
```

**Nunca commitar a senha real.** Antes de qualquer commit, esvaziar o arquivo de
volta:

```
git checkout comms/07_wifi_sta/minha_rede.conf
```

## Falha proposital sem a credencial

Se o `minha_rede.conf` estiver vazio (o estado padrão do repositório) e o build for
disparado sem `-DEXTRA_CONF_FILE`, o `CMakeLists.txt` para na configuração, antes de
compilar uma linha sequer, com:

```
CMake Error at CMakeLists.txt:29 (message):
  CONFIG_WIFI_CREDENTIALS_STATIC_SSID nao definido.

  Preencha o minha_rede.conf com o SSID e a senha da rede da sala:

    CONFIG_WIFI_CREDENTIALS_STATIC_SSID="nrf-curso"
    CONFIG_WIFI_CREDENTIALS_STATIC_PASSWORD="..."

  e compile com -DEXTRA_CONF_FILE=minha_rede.conf
```

Confirmado nesta máquina: o build sem o fragmento falha exatamente com essa
mensagem, e sem gerar nenhum artefato. É intencional — um kit gravado sem
credencial não conecta em rede nenhuma, e o erro em tempo de build (segundos) é mais
barato que descobrir isso só com o log da bancada rodando.

## Passo 1 — compilar e gravar

Shield e snippet são escopados pela imagem — que o sysbuild nomeia `07_wifi_sta`,
igual ao nome da pasta. Com o `minha_rede.conf` preenchido:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/07_wifi_sta/build_lm20 C:/work/nrf-manaus-2/comms/07_wifi_sta -- -D07_wifi_sta_SHIELD="nrf7002eb2" -D07_wifi_sta_SNIPPET=nrf70-wifi -D07_wifi_sta_EXTRA_CONF_FILE=minha_rede.conf
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/07_wifi_sta/build_lm20
```

Build limpo, `exit 0`, imagem única (o nRF7002 é um companion por SPI, não um
segundo SoC). Resumo de memória (com credencial de teste preenchida, só para medir o
binário — não a rede da sala):

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 554880 B | 2036 KB | 26,61% |
| RAM | 188672 B | 511 KB | 36,06% |

O número de FLASH varia alguns bytes conforme o tamanho da credencial em
`minha_rede.conf` (SSID e senha viram string compilada na imagem) — não é motivo
para estranhar uma diferença pequena entre builds de alunos diferentes. RAM não
varia com isso.

## Passo 2 — bancada

Medido nesta bancada: nRF54LM20-DK var. B + nRF7002 EB-II, console na **primeira**
VCOM (a segunda ficou muda) — coerente com o aviso do topo.

### Cronometragem, do reset ao IP

| t (s) | evento |
|---|---|
| 0,0 | banner de boot (NCS v3.4.0 / Zephyr 4.4.0) |
| 0,3 | interface de rede sobe; sai o IPv4 estático de exemplo do `prj.conf` (não é o IP da rede real — ver "Dois IPv4 no log" abaixo) |
| 1,0 | `Waiting for Wi-Fi to be ready` |
| 2,7 | `Connection requested`, estado passa a `SCANNING` |
| 2,7–6,9 | `State: SCANNING` — cerca de **4 s de varredura**, o maior trecho do tempo total |
| 6,9 | `State: AUTHENTICATING` |
| 7,2 | `Connected` |
| 7,4 | `DHCP IP address: <ip>`, lease 14400 s, gateway `<gateway>` |

Do reset ao IP por DHCP: **cerca de 7 s**, dos quais **~4 s são a varredura**. É o
número a esperar num boot normal — se o kit demorar bem mais que isso para
conectar, o gargalo provavelmente não está no firmware.

### Checklist

- [x] Gravar com o `minha_rede.conf` preenchido com a rede real da sala.
- [x] Abrir a porta serial certa e confirmar o log de boot.
- [x] Conferir a sequência de eventos no console: `Connection requested` →
      `SCANNING` → `AUTHENTICATING` → `Connected` → `DHCP IP address: ...`.
- [x] Anotar IP, máscara e gateway recebidos (cronometragem acima; endereços
      reais não entram neste README — ver "Dois IPv4 no log").
- [ ] Desligar o AP da sala e observar a reconexão. **Não executado nesta
      rodada**: o AP desta bancada é a ONT da residência, e derrubá-lo derruba a
      rede inteira — fica para a sala de aula, com um AP dedicado. O que o código
      garante (ou não garante) nesse cenário está descrito em "O que observar"
      abaixo.

### Dois IPv4 no log — qual vale

O ponto mais importante deste log: aparecem **dois** endereços IPv4, em momentos
diferentes. O primeiro sai logo depois que a interface de rede sobe, ainda sem
Wi-Fi associado: é `CONFIG_NET_CONFIG_MY_IPV4_ADDR` (`192.168.1.99/24`, gateway
`192.168.1.1`), o valor **estático de exemplo** do `prj.conf` do sample — o próprio
log o rotula de "overridable" e ele não tem relação nenhuma com a rede real. O que
vale é o **segundo** IPv4, o que sai vários segundos depois em `DHCP IP address:
<ip>`, já com o link associado. Quem lê o log de cima para baixo e para no primeiro
número vai apontar `CONFIG_LAB_SERVIDOR_IP` (labs 9 e 13) para o endereço errado —
o estático do exemplo, não o da rede da sala.

### Aviso benigno durante a associação

Entre `AUTHENTICATING` e `Connected` aparece uma linha
`<wrn> net_if: iface 1 pkt 0x... send failure status -1`. Ela também aparece no
lab 6 nesse mesmo trecho, e a conexão completa normalmente logo em seguida — não é
sinal de falha, é esperado nessa janela da associação. Vale saber disso antes de
parar para investigar um aviso que não é nada.

## O que observar

- Este sample não tem shell de Wi-Fi: a lógica de conexão mora em `src/main.c`, que
  o curso não modifica (nenhuma divergência além do cabeçalho `ORIGEM:`). O fluxo é:
  `net_mgmt_callback_init()` registra os callbacks de `NET_EVENT_WIFI_CONNECT_
  RESULT`, `NET_EVENT_WIFI_DISCONNECT_RESULT` e `NET_EVENT_IPV4_DHCP_BOUND`; depois
  `start_app()` chama `NET_REQUEST_WIFI_CONNECT_STORED` — a credencial vem do
  subsistema `wifi_credentials` (a mesma static credential do `minha_rede.conf`), não
  de um argumento em texto.
- `LOG_INF("Connected")` sai do `handle_wifi_connect_result()`; a linha de IP sai de
  `print_dhcp_ip()`, disparada só quando o `NET_EVENT_IPV4_DHCP_BOUND` chega — ou
  seja, a associação Wi-Fi e a obtenção de IP são dois eventos distintos no log, na
  mesma ordem do lab 6.
- Se o AP cair, o firmware recebe `NET_EVENT_WIFI_DISCONNECT_RESULT`:
  `handle_wifi_disconnect_result()` loga `Received Disconnected` e marca
  `context.connected = false` — só isso. Esse handler não chama `wifi_connect()`
  nem qualquer outra rotina de reconexão. A reentrada do laço principal em
  `start_app()` também não depende desse evento: depois de uma conexão bem
  sucedida, o laço fica bloqueado em `k_sem_take(&wifi_ready_state_changed_sem,
  K_FOREVER)`, e esse semáforo só é liberado por `wifi_ready_cb()`, acionado pelos
  eventos `NET_EVENT_SUPPLICANT_READY`/`NET_EVENT_SUPPLICANT_NOT_READY`
  (`nrf/subsys/net/lib/wifi_ready/wifi_ready.c`) — prontidão do `wpa_supplicant`,
  um evento diferente do de desconexão. Ou seja, **o código deste sample não
  descreve um mecanismo explícito de reconexão após a queda do AP.** Se uma
  reconexão automática for observada na bancada, a hipótese mais provável é a
  reassociação interna do próprio `wpa_supplicant` (fora do que este `main.c`
  controla) — hipótese a verificar, não um caminho documentado neste arquivo. Ver
  o checklist do Passo 2.

## Pegadinhas

- **A VCOM muda com o shield — não é sempre a mesma porta.** Ver o aviso no topo
  deste README. Isso é diferente do que se observa comparando dois firmwares que já
  têm o shield: entre eles a VCOM não muda (é sempre a `uart30`/primeira). A troca
  só aparece quando se compara um firmware **sem** shield com um **com** shield.
- **`sw3` não existe mais.** O overlay do shield remove o botão e o alias junto.
- **Nunca commitar a credencial real.** `minha_rede.conf` é rastreado e deve
  permanecer vazio no repositório; `git checkout comms/07_wifi_sta/minha_rede.conf`
  antes de qualquer commit.
- **Build falha sem o fragmento — é o comportamento esperado**, não um bug do lab
  (ver seção "Falha proposital" acima).

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/wifi/sta`
- nRF Connect SDK v3.4.0 — `zephyr/boards/shields/nrf7002eb2` (overlay do console:
  desabilita `uart20`, habilita `uart30`, remove `sw3`)
- Medição local, 2026-09-06 — nRF54LM20-DK var. B: comparação do console entre um
  firmware sem shield (console na `uart20`, segunda VCOM) e este lab com o shield
  `nrf7002eb2` (console na `uart30`, primeira VCOM)
- Bancada `nrf-manaus-2`, 2026-09-06 — nRF54LM20-DK var. B (J-Link 1051898754) +
  nRF7002 EB-II: cronometragem do reset ao IP, sequência de eventos, o aviso
  benigno e os dois IPv4 do log (seções "Passo 2" acima)
