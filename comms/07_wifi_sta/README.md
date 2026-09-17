# Wi-Fi · Lab 7 — Associação programática com a rede digitada no terminal

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
do shell interativo do lab 6, o firmware conecta sozinho, com a credencial que a
biblioteca `wifi_credentials` guarda em settings. É aqui que entra o módulo do curso
`src/lab_rede.c`: no primeiro boot ele pede SSID e senha no terminal serial e grava;
nos boots seguintes usa o que está gravado. O mesmo arquivo é copiado igual nos labs
9, 11, 12 e 13.

> **Origem.** Cópia integral de `nrf/samples/wifi/sta` do **nRF Connect SDK v3.4.0**.
> Licença Nordic preservada em [LICENSE](LICENSE). `prj.conf`, `CMakeLists.txt` e
> `src/main.c` levam o cabeçalho `ORIGEM:` do curso. Divergências do SDK, descritas
> abaixo: `src/lab_rede.c` e `src/lab_rede.h` (arquivos do curso) entram no
> `target_sources` do `CMakeLists.txt`; `main()` chama `lab_rede_ler()` antes de
> qualquer outra coisa; e o `prj.conf` troca `CONFIG_WIFI_CREDENTIALS_STATIC` pelo
> backend de settings (`CONFIG_SETTINGS`, `CONFIG_FLASH`, `CONFIG_FLASH_MAP`,
> `CONFIG_FLASH_PAGE_LAYOUT`, `CONFIG_ZMS`, `CONFIG_SETTINGS_ZMS`,
> `CONFIG_WIFI_CREDENTIALS_MAX_ENTRIES=1`).

## Hardware

| Peça | Papel |
|---|---|
| **nRF54LM20-DK** (variante B, `nrf54lm20b`) | roda o firmware; host do Wi-Fi |
| **nRF7002 EB-II** | shield companion Wi-Fi 6, encaixado no header de expansão |
| **PC** | terminal serial (VCOM) e a rede Wi-Fi da sala |

Com o shield acoplado, `sw3` some do overlay (ele não existe mais): sobram `sw0`–`sw2`
e os quatro LEDs.

## A rede da sala — digitada no terminal, gravada em settings

O binário não carrega credencial nenhuma. No primeiro boot, `lab_rede_ler()` pede na
console (115200 8N1; com a EB II encaixada é a **primeira** VCOM):

```
=== Rede Wi-Fi ===
SSID da rede: <ssid>
Senha (Enter vazio = rede aberta): <senha>
Gravado. Rede "<ssid>".
```

A senha é ecoada em claro. SSID tem de 1 a 32 caracteres; senha WPA2, de 8 a 63.
Entrada inválida repete só aquele campo; não há prompt periódico. O módulo grava pela
biblioteca `wifi_credentials`, com o backend de settings (ZMS na `storage_partition`
da placa), e a conexão segue por `NET_REQUEST_WIFI_CONNECT_STORED`, o mesmo caminho
do sample.

Nos boots seguintes o firmware mostra o que tem e abre uma janela única:

```
=== Rede Wi-Fi ===
Rede gravada: "<ssid>" (com senha)
Enter (ou nada em 5 s) usa essa; qualquer outra tecla troca:
```

Sem tecla em 5 s, ou com Enter, usa a gravada; qualquer outra tecla pede SSID e senha
de novo. Um `west flash` ou `nrfutil device program` normal não apaga a
`storage_partition`, então a rede sobrevive à regravação do firmware. `nrfutil device
recover` (ou `west flash --erase`) apaga a partição e o prompt volta.

## Passo 1 — compilar e gravar

Shield e snippet são escopados pela imagem — que o sysbuild nomeia `07_wifi_sta`,
igual ao nome da pasta:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/07_wifi_sta/build_lm20 C:/work/nrf-manaus-2/comms/07_wifi_sta -- -D07_wifi_sta_SHIELD="nrf7002eb2" -D07_wifi_sta_SNIPPET=nrf70-wifi
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/07_wifi_sta/build_lm20
```

Para gravar sem compilar, o hex pronto está em `comms/hex/07_wifi_sta_lm20.hex`
(público: não tem credencial dentro).

Build limpo, `exit 0`, imagem única (o nRF7002 é um companion por SPI, não um
segundo SoC). Resumo de memória:

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 565940 B | 2036 KB | 27,15% |
| RAM | 188920 B | 511 KB | 36,10% |

## Passo 2 — bancada

Medido nesta bancada: nRF54LM20-DK var. B + nRF7002 EB-II, console na **primeira**
VCOM (a segunda ficou muda) — coerente com o aviso do topo.

### Cronometragem, do prompt ao IP

O `t = 0` da tabela é o Enter do prompt de rede (ou o fim da janela de 5 s, quando a
rede já está gravada), não o reset: até ali o firmware está parado em
`lab_rede_ler()`, esperando o teclado.

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

Do prompt ao IP por DHCP: **cerca de 7 s**, dos quais **~4 s são a varredura**. É o
número a esperar num boot normal — se o kit demorar bem mais que isso para
conectar, o gargalo provavelmente não está no firmware.

### Checklist

- [x] Gravar e digitar a rede da sala no primeiro boot.
- [x] Abrir a porta serial certa e confirmar o log de boot.
- [x] Conferir a sequência de eventos no console: `Connection requested` →
      `SCANNING` → `AUTHENTICATING` → `Connected` → `DHCP IP address: ...`.
- [x] Anotar IP, máscara e gateway recebidos (cronometragem acima; endereços
      reais não entram neste README — ver "Dois IPv4 no log").
- [x] Desligar o AP e observar a reconexão. **Executado em 2026-09-07**, com um hotspot
      de celular no lugar da ONT (derrubar a ONT derrubaria a casa). **O kit reconecta
      sozinho** — o resultado completo está na seção seguinte.

### Dois IPv4 no log — qual vale

O ponto mais importante deste log: aparecem **dois** endereços IPv4, em momentos
diferentes. O primeiro sai logo depois que a interface de rede sobe, ainda sem
Wi-Fi associado: é `CONFIG_NET_CONFIG_MY_IPV4_ADDR` (`192.168.1.99/24`, gateway
`192.168.1.1`), o valor **estático de exemplo** do `prj.conf` do sample — o próprio
log o rotula de "overridable" e ele não tem relação nenhuma com a rede real. O que
vale é o **segundo** IPv4, o que sai vários segundos depois em `DHCP IP address:
<ip>`, já com o link associado. Quem lê o log de cima para baixo e para no primeiro
número vai digitar, no prompt de IP do servidor dos labs 9 e 13, um endereço da
sub-rede errada — a do exemplo estático, não a da rede da sala.

### Aviso benigno durante a associação

Entre `AUTHENTICATING` e `Connected` aparece uma linha
`<wrn> net_if: iface 1 pkt 0x... send failure status -1`. Ela também aparece no
lab 6 nesse mesmo trecho, e a conexão completa normalmente logo em seguida — não é
sinal de falha, é esperado nessa janela da associação. Vale saber disso antes de
parar para investigar um aviso que não é nada.

## A queda do AP — medida, e quem reconecta não é este código

Executado em 2026-09-07 com um hotspot de celular (a ONT da bancada não pode ser
desligada). Sequência completa, do log:

| t | linha | leitura |
|---|---|---|
| 15:40,557 | `sta: Received Disconnected` | o hotspot foi desligado; o **LED0 apaga** |
| 15:45,584 | `State: COMPLETED` com **`RSSI: -9999`** | status obsoleto: o estado ainda diz conectado, mas o RSSI é o sentinela de "sem medida" |
| 15:50,200 | `Connection failed (4)` | 1ª retentativa |
| 15:59,826 | `Connection failed (4)` | 2ª, **~9,6 s** depois |
| 16:09,568 | **`Connected`** | 3ª, ~9,7 s depois, já com o hotspot de volta |
| 16:09,589 | `DHCP IP address: 10.151.38.218` | **21 ms** depois, e o **mesmo IP** de antes |

**O ponto central: em nenhum momento aparece um segundo `Connection requested`.** Essa
linha só sai de `wifi_connect()`, chamada **uma única vez** pelo laço de `start_app()`.
Logo, as retentativas a cada ~9,7 s **não vêm da aplicação** — vêm do `wpa_supplicant`,
que reassocia por conta própria. Isso confirma, com medida, a hipótese que este README
levantava sem poder testar.

**Para o aluno:** o kit **volta sozinho**, em até ~10 s depois de o AP voltar, sem reset.
O que o código deste sample faz na queda é apenas logar `Received Disconnected` e apagar
o LED0.

### Dois detalhes que valem citar

- **`RSSI: -9999`** é o valor que aparece enquanto o link está caído. Não é bug: é o
  sentinela de "não há medida". Bom sinal visual de link morto.
- **O IP volta idêntico e em 21 ms.** O *lease* de 3599 s ainda valia, então o cliente
  DHCP **renovou** em vez de refazer o DORA completo. Não confundir com o boot, em que
  obter endereço leva centenas de ms.

O mesmo mecanismo aparece na **associação inicial**: nesta bancada houve um
`Connection failed (4)` em 00:12:37 e um `Connected` em 00:12:42 — 5,5 s depois, também
**sem** um novo `Connection requested`. Uma falha na primeira tentativa se resolve
sozinha, e o aluno pode nem notar.
## O fluxograma do `main.c` — e a linha de log de cada caixa

O firmware não tem shell nem comandos: tudo acontece sozinho. O desenho abaixo é o
esqueleto, e cada caixa está amarrada à linha que ela **produz no console** — é assim que
se lê o log sem abrir o código.

```
          main()
            |
  +---------v-----------+   "=== Rede Wi-Fi ===" e os prompts
  | lab_rede_ler()      |   (ou "Rede gravada: ..." + janela de 5 s)
  | (codigo do curso)   |   -> grava SSID/senha no wifi_credentials
  +---------+-----------+
            |
  +---------v-----------+   registra callbacks de
  | net_mgmt_callback   |   CONNECT_RESULT, DISCONNECT_RESULT,
  | _init()             |   IPV4_DHCP_BOUND                       (sem log)
  +---------+-----------+
            |
  +---------v-----------+
  | espera o supplicant |   "Aguardando o supplicant..."
  | (CONFIG_WIFI_READY) |   -> sem isto, conectar falha com -ENOTSUP
  +---------+-----------+
            |
  +---------v-----------+
  | NET_REQUEST_WIFI_   |   "Connection requested"
  | CONNECT_STORED      |   (credencial vem do wifi_credentials,
  +---------+-----------+    gravada pelo lab_rede_ler)
            |
  +---------v-----------+
  | laco de status      |   "State: SCANNING" a cada 300 ms
  | ate connect_result  |   -> ~4 s, o maior trecho do boot
  +---------+-----------+   "State: AUTHENTICATING"
            |
  +---------v-----------+
  | (callback) associou |   "Connected"        <- LINK, ainda SEM IP
  +---------+-----------+
            |
  +---------v-----------+
  | (callback) DHCP     |   "DHCP IP address: <ip>"   <- agora sim
  +---------+-----------+
            |
  +---------v-----------+
  | k_sem_take(FOREVER) |   (nada mais e impresso)
  +---------------------+

   em paralelo:  thread do LED  ---> pisca LED0 a 5 Hz enquanto conectado
                 handler de queda ---> "Received Disconnected" e apaga o LED0
```

**A caixa que mais engana é a penúltima.** `Connected` e `DHCP IP address` são **dois
eventos diferentes**, separados por ~150 ms nesta bancada. Quem trata os dois como o
mesmo momento erra ao explicar por que o kit "conectou mas não responde".

### Os LEDs neste lab

| LED | Significado |
|---|---|
| **LED0**, piscando a 5 Hz | associado ao Wi-Fi. É a thread `toggle_led()`, que só olha `context.connected` |
| **LED0** apagado | sem associação |

Repare no que o LED **não** indica: **ele não sabe se há IP.** Pisca a partir do
`Connected`, antes do DHCP. Um kit com LED piscando e sem endereço é possível.
## O que observar

- Este sample não tem shell de Wi-Fi: a lógica de conexão mora em `src/main.c`, e a
  única linha que o curso acrescenta a ela é a chamada a `lab_rede_ler()` no início
  de `main()`. O fluxo é: `net_mgmt_callback_init()` registra os callbacks de
  `NET_EVENT_WIFI_CONNECT_RESULT`, `NET_EVENT_WIFI_DISCONNECT_RESULT` e
  `NET_EVENT_IPV4_DHCP_BOUND`; depois `start_app()` chama
  `NET_REQUEST_WIFI_CONNECT_STORED` — a credencial vem do subsistema
  `wifi_credentials` (backend de settings, gravada pelo `lab_rede_ler()`), não de um
  argumento em texto.
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
- **O kit "não faz nada" depois do boot.** Está parado no prompt de rede, esperando
  o teclado — abra a primeira VCOM. Se a rede já está gravada, a janela de 5 s passa
  sozinha e a conexão começa.
- **Rede errada gravada.** No boot seguinte, tecle qualquer coisa que não seja Enter
  dentro da janela de 5 s e digite de novo. `nrfutil device recover` também apaga a
  `storage_partition`, mas regravar o firmware por `west flash` não.

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
