# Wi-Fi · Lab 8 — Provisionamento por SoftAP

> **Antes de tudo: com a EB II acoplada, a VCOM do console muda.** Sem o shield, o
> console desta DK fica na `uart20`, que sai na **segunda** VCOM do chip de interface
> USB. O overlay do shield (`nrf7002eb2`) desabilita a `uart20` e move o console (e o
> `shell-uart`) para a `uart30` — e essa UART sai na **primeira** VCOM. Quem estava
> acostumado a abrir a segunda porta (firmware sem shield, por exemplo um lab de
> Channel Sounding) precisa trocar para a primeira ao gravar este lab. O `device
> list` de um firmware com este shield mostra só a `uart30` — a `uart20` some da
> lista. Esse reroteamento é um contorno de um conflito de pinos que existe só na
> revisão **pré-produção** da nRF54LM20-DK, presente no nRF Connect SDK v3.4.0
> (Zephyr 4.4.0) — nossa árvore. Em versões mais novas do Zephyr o shield deixa de
> reroteiar nessa placa: o console volta para a `uart20`/segunda VCOM e o `sw3` volta
> a existir. Na dúvida, abra as duas portas seriais da DK e veja qual responde.

Este lab é a segunda aplicação com lógica própria da frente de Wi-Fi: `nrf/samples/
wifi/provisioning/softap` rodando na nRF54LM20-DK (variante B) com a nRF7002 EB-II
encaixada. Diferente do lab 7 (credencial fixa em `minha_rede.conf`), aqui o
provisionamento acontece em tempo de execução: a DK sobe como Access Point próprio,
escaneia as redes ao seu redor e recebe a credencial por HTTPS de um cliente
conectado a essa rede temporária.

> **Origem.** Cópia integral de `nrf/samples/wifi/provisioning/softap` do **nRF
> Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE). `prj.conf`,
> `CMakeLists.txt`, `src/main.c` e `scripts/provision.py` levam o cabeçalho
> `ORIGEM:` do curso; nenhum dos quatro diverge do SDK. O `README.rst` original do
> sample não foi trazido — este `README.md` substitui.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54LM20-DK** (variante B, `nrf54lm20b`) | roda o firmware; sobe como AP durante o provisionamento |
| **nRF7002 EB-II** | shield companion Wi-Fi 6, encaixado no header de expansão |
| **PC / notebook** | terminal serial (VCOM); cliente Wi-Fi que provisiona a DK; roda o `provision.py` |

Com o shield acoplado, `sw3` some do overlay (ele não existe mais): sobram `sw0`–`sw2`
e os quatro LEDs. `sw0` (botão 1 na numeração da aplicação) tem função própria neste
sample: reseta o provisionamento (apaga a credencial salva e volta ao modo AP).

## A pergunta da variante B — desfecho

O `boards/` do sample, como veio do SDK, só traz `.conf` para a variante **A**
(`nrf54lm20dk_nrf54lm20a_cpuapp.conf`, com `CONFIG_WIFI_CREDENTIALS`, `CONFIG_FLASH*`
e `CONFIG_SETTINGS`). Não existe `nrf54lm20dk_nrf54lm20b_cpuapp.conf`.

Antes de criar qualquer arquivo, o build foi tentado direto para a variante B:

```
west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild ... -- -D08_wifi_provisioning_SHIELD="nrf7002eb2" -D08_wifi_provisioning_SNIPPET=nrf70-wifi
```

**Compilou sem erro, `exit 0`, sem precisar de `.conf` novo para a variante B.** O
próprio `sample.yaml` do SDK já lista `nrf54lm20dk/nrf54lm20a/cpuapp` e
`nrf54lm20dk/nrf54lm20b/cpuapp` juntos, com o mesmo `extra_args` (só o `SHIELD`) — já
era indício de que o sample trata as duas variantes de forma idêntica. Conferindo o
`.conf` da variante A (`CONFIG_WIFI_CREDENTIALS`, `CONFIG_FLASH*`,
`CONFIG_SETTINGS`): todas essas opções **já estão** no `prj.conf` geral do sample,
que vale para qualquer board. Ou seja, o `.conf` da A é redundante ali (não faz mal,
só reafirma o que o `prj.conf` já liga) — e a variante B nunca precisou do seu
próprio arquivo porque não falta nada para ela. **Nenhum `.conf` de board foi criado
neste lab.**

## Passo 1 — compilar e gravar

Shield e snippet são escopados pela imagem — que o sysbuild nomeia
`08_wifi_provisioning`, igual ao nome da pasta:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/08_wifi_provisioning/build_lm20 C:/work/nrf-manaus-2/comms/08_wifi_provisioning -- -D08_wifi_provisioning_SHIELD="nrf7002eb2" -D08_wifi_provisioning_SNIPPET=nrf70-wifi
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/08_wifi_provisioning/build_lm20
```

Build limpo, `exit 0`, imagem única (o nRF7002 é um companion por SPI, não um
segundo SoC; sem partition manager — `SB_CONFIG_PARTITION_MANAGER=n` no
`sysbuild.conf` do sample). Resumo de memória:

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 728012 B | 2036 KB | 34,92% |
| RAM | 271789 B | 511 KB | 51,94% |

Os únicos avisos do CMake são os do próprio sample (credenciais em memória
não segura, `__ASSERT()` habilitado globalmente) — nada relacionado à variante da
board.

## O que este sample realmente é

**Não é um formulário no navegador.** A DK sobe um Access Point próprio (SSID padrão
`nrf-wifiprov`, definido por `CONFIG_SOFTAP_WIFI_PROVISION_SSID`) e um servidor
HTTPS na porta 443 (`CONFIG_SOFTAP_WIFI_PROVISION_TCP_PORT`), com um certificado
autoassinado embutido em `certs/`. O protocolo de conteúdo é **protobuf**, não HTML:
o cliente busca `GET https://wifiprov.local/prov/networks` e recebe a lista de redes
que a DK escaneou, serializada segundo o schema `common.proto`; para configurar,
envia `POST https://wifiprov.local/prov/configure` com um `WifiConfig` serializado
(SSID/BSSID da rede escolhida + senha). O cliente de referência do próprio sample é
o script `scripts/provision.py` — não existe página HTML nenhuma para abrir no
navegador.

O nome `wifiprov.local` vem de mDNS (`CONFIG_NET_HOSTNAME="wifiprov"` +
`CONFIG_MDNS_RESPONDER`), resolvido pelo cliente sem precisar digitar o IP do AP
(`192.168.0.1` por padrão, `CONFIG_SOFTAP_WIFI_PROVISION_IPV4_ADDRESS`).

**O momento didático deste lab é a DK escanear por você.** Ao contrário de um
provisionamento típico onde o usuário digita o SSID de cabeça, aqui a DK já fez o
`wifi scan` sozinha antes de o cliente se conectar — o protobuf devolvido por
`/prov/networks` é exatamente a lista de redes que ela viu, com SSID, BSSID, RSSI,
banda, canal e modo de autenticação de cada uma. O aluno escolhe de uma lista real,
não digita um SSID de memória.

LEDs: o `src/main.c` acende `DK_LED1` ao entrar em modo AP (provisionamento em
andamento) e `DK_LED2` ao conectar na rede provisionada. Esses são os nomes dos
macros da biblioteca `dk_buttons_and_leds`, não o número físico do LED — a
biblioteca varre os filhos do nó `leds` do devicetree em ordem, então `DK_LED1` é
o primeiro da lista (`led0`, rotulado `Green LED 0`) e `DK_LED2` é o segundo
(`led1`, `Green LED 1`). Na serigrafia da nRF54LM20-DK, que numera a partir de 0
igual ao devicetree, isso é **LED0** (modo AP) e **LED1** (conectado) — sem
deslocamento na placa, só entre o nome do macro e o índice que ele usa.

## O certificado de servidor

O provisionamento roda HTTPS na porta 443, então o firmware precisa de um
certificado de servidor. O sample traz um autoassinado de desenvolvimento,
registrado **no boot, antes de qualquer rede subir** — o log mostra
`Registering self-signed server certificate` logo na inicialização, medido nesta
bancada em ~0,03 s (ver a tabela do Passo 3).

O certificado embutido em `certs/server_certificate.pem` tem `CN=wifiprov.local`,
Subject Alternative Name `DNS:wifiprov.local` e `DNS:*.wifiprov.local`, válido de
22/mai/2024 a 20/mai/2034 (chave EC `prime256v1`/P-256, a mesma curva que o
`prj.conf` habilita via `CONFIG_PSA_WANT_ECC_SECP_R1_256`). O hostname bate com o
`CONFIG_NET_HOSTNAME="wifiprov"` do `prj.conf` — é por isso que o SNI do handshake
TLS confere com o nome que o cliente resolve por mDNS.

**A chave privada é pública.** `certs/server_private_key.pem` já está no SDK da
Nordic e agora neste repo — qualquer pessoa com acesso a um dos dois tem a chave.
Ela serve para este laboratório e para nada além disso: em produto real, cada
dispositivo tem seu próprio par, gerado e provisionado fora da árvore de código, e
chave privada nunca entra em repositório.

**Quando regenerar é obrigatório:** se `CONFIG_NET_HOSTNAME` mudar, o certificado
precisa ser refeito com o SAN apontando para o novo hostname, senão o SNI falha no
handshake TLS — documentado no `README.rst` do sample. Comando para gerar um par
novo, autoassinado, com o SAN correto:

```
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
  -keyout server_private_key.pem -out server_certificate.pem -days 3650 -nodes \
  -subj "/CN=<novo-hostname>.local" \
  -addext "subjectAltName=DNS:<novo-hostname>.local,DNS:*.<novo-hostname>.local"
```

Os dois arquivos gerados substituem os que estão em `certs/`.

## Passo 2 — preparar o lado do PC

O schema protobuf do sample não é versionado como Python pronto — ele é gerado do
`.proto` do próprio SDK com `protoc`. **`protoc` é pré-requisito** desta etapa
(nesta máquina, `protoc` 25.3; pacotes Python `requests` e `protobuf` já
disponíveis):

```
cd comms/08_wifi_provisioning/scripts
protoc --proto_path=C:/ncs/v3.4.0/nrf/subsys/net/lib/softap_wifi_provision/proto --python_out=. common.proto
```

Gera `scripts/common_pb2.py`. Rodado localmente sem erro. Esse arquivo **não é
versionado** — está no `.gitignore` do lab, porque é derivado do `.proto` da árvore
do SDK, não código do curso.

## Passo 3 — bancada: o fluxo completo

> **Parcialmente confirmado na bancada** — o boot até o SoftAP no ar foi medido; o
> fluxo do `provision.py` e a confirmação externa de que o SoftAP está no ar ainda
> faltam (motivos abaixo).

Medido nesta bancada, no console (primeira VCOM, mesmo comportamento dos labs 6 e
7 — aviso no topo deste README):

| t (s) | evento |
|---|---|
| 0,0 | SPI do nRF7002 sobe; armazenamento de credenciais (`fs_zms`) montado |
| 0,03 | `Registering self-signed server certificate` — certificado registrado no boot |
| 0,08 | `Network interface brought up` |
| 0,09 | `Waiting for IPv4 HTTP connections on port 443` — servidor HTTPS já escutando |
| 0,10 | `Scanning for Wi-Fi networks...` |
| 4,7 | `NET_EVENT_WIFI_SCAN_DONE` — a varredura levou **~4,6 s** |
| 4,8 | `Protobuf payload prepared, scan results encoded, size: 194` — o log diz **protobuf** com todas as letras, no payload de 194 bytes que vira a lista de redes |
| 5,6 | `NET_EVENT_WIFI_AP_ENABLE_RESULT`, `Provisioning started` — SoftAP no ar |
| 5,7 | servidor DHCPv4 no ar |

Do boot até o SoftAP no ar: **~5,6 s** (publicado em `comms/TEMPOS_WIFI.md`). SSID
confirmado na `.config` gerada: `CONFIG_SOFTAP_WIFI_PROVISION_SSID="nrf-wifiprov"`.
Pré-requisitos do PC também conferidos nesta bancada: `protoc` 25.3 e o módulo
Python `protobuf` (7.35.0) presentes.

**O que ainda falta, e por quê:**

- **O fluxo completo do `provision.py`.** Exige tirar o PC da rede atual e entrar
  no SoftAP `nrf-wifiprov`, o que derrubaria a máquina no meio da sessão de
  bancada — fica para a sala, com o roteiro abaixo.
- **A confirmação externa de que o SoftAP está no ar.** Ficou **inconclusiva, não
  negativa**: o adaptador Wi-Fi do PC, enquanto conectado a outra rede, só reporta
  essa rede no `netsh wlan show networks`, mesmo com `mode=bssid` — não dá para
  concluir daí que o `nrf-wifiprov` não esteja no ar. Do lado da DK a evidência é
  forte (`AP_ENABLE_RESULT`, `Provisioning started`, servidor DHCP iniciado).

Checklist para fechar esses dois pontos, na UART correta:

- [ ] Conectar o notebook na rede Wi-Fi `nrf-wifiprov` (fecha o item que ficou
      inconclusivo nesta bancada — confirma de fato que o SoftAP está visível).
- [ ] Rodar `python provision.py --certificate ../certs/server_certificate.pem`.
- [ ] Conferir que o script **lista as redes que a DK viu** (SSID, RSSI, banda,
      canal, tipo de autenticação) — não uma lista digitada pelo usuário.
- [ ] Escolher a rede da sala na lista e digitar a senha (rede WPA2-PSK, sem WPA3).
- [ ] Confirmar no console da DK que ela recebeu a credencial, saiu do modo AP e
      associou na rede da sala (LED1 acende; `net_mgmt` reporta a conexão).

Anotar cada saída observada (mensagens do console, conteúdo da listagem do
`provision.py`, IP obtido) na próxima rodada deste README.

## Pegadinhas

- **A VCOM muda com o shield — não é sempre a mesma porta.** Ver o aviso no topo
  deste README.
- **`sw3` não existe mais.** O overlay do shield remove o botão e o alias junto.
- **Não é um formulário web.** Quem espera abrir um navegador e preencher SSID/senha
  vai se confundir — o fluxo é HTTPS + protobuf pelo `provision.py` (ou pelo app
  oficial da Nordic, fora do escopo deste curso). Ver seção "O que este sample
  realmente é" acima.
- **`protoc` é pré-requisito do PC, não da DK.** Sem ele, `scripts/common_pb2.py`
  não existe e `provision.py` falha no `import common_pb2`.
- **`scripts/common_pb2.py` nunca é commitado.** Está no `.gitignore` do lab —
  é gerado localmente pelo `protoc` a partir do schema do SDK.
- **Rede da sala é WPA2-PSK, sem WPA3.** O schema protobuf tem `WPA3_PSK` como
  modo de autenticação possível, mas não é o caso desta bancada.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/wifi/provisioning/softap`
- nRF Connect SDK v3.4.0 — `nrf/subsys/net/lib/softap_wifi_provision` (biblioteca,
  Kconfig com os valores padrão de SSID, porta TCP e IP do AP; schema
  `proto/common.proto`)
- nRF Connect SDK v3.4.0 — `zephyr/boards/shields/nrf7002eb2` (overlay do console:
  desabilita `uart20`, habilita `uart30`, remove `sw3`)
- Medição local, 2026-09-06 — nRF54LM20-DK var. B: build limpo para
  `nrf54lm20dk/nrf54lm20b/cpuapp` com `-D08_wifi_provisioning_SHIELD="nrf7002eb2"
  -D08_wifi_provisioning_SNIPPET=nrf70-wifi`, sem `.conf` de board para a variante B;
  `protoc` 25.3 gerando `common_pb2.py` sem erro
- Medição local, 2026-09-06 — `openssl x509` sobre `certs/server_certificate.pem`:
  `CN=wifiprov.local`, SAN `DNS:wifiprov.local`/`DNS:*.wifiprov.local`, validade
  22/mai/2024–20/mai/2034, chave EC `prime256v1`
- Medição de bancada, 2026-09-06 — nRF54LM20-DK var. B com nRF7002 EB-II: log do
  boot até o SoftAP no ar, `protoc` e módulo `protobuf` do Python conferidos no
  PC; tempo total publicado em `comms/TEMPOS_WIFI.md`
- `zephyr/boards/nordic/nrf54lm20dk/nrf54lm20dk_common.dtsi` e
  `nrf/lib/dk_buttons_and_leds/dk_buttons_and_leds.c` — numeração física dos LEDs
  (`Green LED 0`..`3`) e como os macros `DK_LED1`/`DK_LED2` mapeiam para os
  índices 0/1 dessa lista
