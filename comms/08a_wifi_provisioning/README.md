# Wi-Fi · Lab 8a — Provisionamento por SoftAP

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
encaixada. Diferente do lab 7 (credencial digitada no terminal serial), aqui o
provisionamento acontece sem cabo: a DK sobe como Access Point próprio,
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
west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild ... -- -D08a_wifi_provisioning_SHIELD="nrf7002eb2" -D08a_wifi_provisioning_SNIPPET=nrf70-wifi
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

## `meu_softap.conf` — o SSID do seu kit

Numa sala com vários kits, **todos anunciariam o mesmo SSID** (`nrf-wifiprov`, o
padrão da biblioteca) e não haveria como saber em qual deles você entrou. O SoftAP
é uma rede **aberta** — a biblioteca não expõe opção de senha —, então o SSID é a
única coisa que distingue um kit do outro no ar.

Por isso este lab tem um fragmento de Kconfig por aluno:

```
CONFIG_SOFTAP_WIFI_PROVISION_SSID="nrf-wifiprov"
```

Ele **já vem com o valor padrão** — o mesmo que o app da Nordic sugere — e é o que
sai da caixa funcionando. Para ter o seu próprio nome, troque o valor e compile com
`-D08a_wifi_provisioning_EXTRA_CONF_FILE=meu_softap.conf`.

> **Cuidado ao escolher o nome, se for usar o app.** O campo **"Edit SSID"** do
> nRF Wi-Fi Provisioner tem um defeito, observado nesta bancada em 2026-09-07: a tela
> se redesenha sozinha e o teclado **volta para as letras** toda vez que se troca para
> a página de símbolos. Dá para digitar letras com paciência, mas **não** se consegue
> pôr um `-`. Como o próprio padrão `nrf-wifiprov` tem hífen, isso significa que, pelo
> app, só é digitável um SSID **sem caracteres especiais**. Duas saídas:
>
> - escolha um nome **só com letras e números** (ex.: `nrfprov07`) — o app digita; ou
> - use o `scripts/provision.py`, que **não olha o SSID do SoftAP**: você entra na rede
>   na mão e ele fala com `wifiprov.local`. Por script, qualquer nome serve.

Duas observações sobre esse fragmento:

- **Este valor não é segredo.** Pode ser commitado à vontade; não há senha nenhuma
  aqui — é só o nome do AP que a DK anuncia. A senha da rede da sala nunca entra em
  arquivo nenhum do repo: neste lab chega pelo provisionamento, nos labs 7, 9, 11, 12
  e 13 é digitada no terminal.
- **Não mexa no `CONFIG_NET_HOSTNAME` por causa disto.** O certificado do servidor
  HTTPS é amarrado ao **hostname** (`wifiprov.local`), não ao SSID, e é o hostname que
  o `provision.py` resolve. Mudar só o SSID **não** obriga a regerar certificado
  (ver "O certificado de servidor"). O hostname pode continuar igual em todos os
  kits sem colidir: cada SoftAP é uma rede isolada, com o kit em `192.168.0.1`, e o
  PC entra em uma de cada vez.

## Passo 1 — compilar e gravar

Shield e snippet são escopados pela imagem — que o sysbuild nomeia
`08a_wifi_provisioning`, igual ao nome da pasta:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/08a_wifi_provisioning/build_lm20 C:/work/nrf-manaus-2/comms/08a_wifi_provisioning -- -D08a_wifi_provisioning_SHIELD="nrf7002eb2" -D08a_wifi_provisioning_SNIPPET=nrf70-wifi -D08a_wifi_provisioning_EXTRA_CONF_FILE=meu_softap.conf
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/08a_wifi_provisioning/build_lm20
```

Build limpo, `exit 0`, imagem única (o nRF7002 é um companion por SPI, não um
segundo SoC; sem partition manager — `SB_CONFIG_PARTITION_MANAGER=n` no
`sysbuild.conf` do sample). Resumo de memória:

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 728140 B | 2036 KB | 34,93% |
| RAM | 271813 B | 511 KB | 51,95% |

Os únicos avisos do CMake são os do próprio sample (credenciais em memória
não segura, `__ASSERT()` habilitado globalmente) — nada relacionado à variante da
board.

## O que este sample realmente é

**Não é um formulário no navegador.** A DK sobe um Access Point próprio (SSID padrão
`nrf-wifiprov`, trocado pelo seu em `meu_softap.conf` — ver a seção acima) e um servidor
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

## Os nomes e endereços deste lab — quem é quem

Este é o lab com mais nomes circulando ao mesmo tempo, e a confusão típica é achar
que são o mesmo. **Há dois SSIDs e um hostname**, e eles vivem em camadas diferentes:

| O quê | Valor | De onde vem | Em que camada vive | Único por kit? |
|---|---|---|---|---|
| **SSID do SoftAP** | `nrf-prov-XX` | `meu_softap.conf` | rádio — é a rede que aparece na lista do PC | **sim** |
| **SSID da rede-alvo** | a rede da sala | digitado no `provision.py`, em tempo de execução | rádio — é o que está sendo provisionado | não (é a mesma para todos) |
| **Hostname** | `wifiprov` → `wifiprov.local` | `CONFIG_NET_HOSTNAME` + `CONFIG_MDNS_RESPONDER` | nome, resolvido por mDNS dentro do SoftAP | não |
| **Certificado** | `CN`/SAN = `wifiprov.local` | `certs/*.pem`, registrado no boot | TLS — prova que o servidor é quem diz ser | não |
| **IP do AP** | `192.168.0.1` | `CONFIG_SOFTAP_WIFI_PROVISION_IPV4_ADDRESS` | IP — e é a base do servidor DHCP do kit | não |
| **Porta** | `443` | `CONFIG_SOFTAP_WIFI_PROVISION_TCP_PORT` | TCP | não |
| **`sec_tag`** | `88` | `CONFIG_SOFTAP_WIFI_PROVISION_CERTIFICATE_SEC_TAG` | índice do cofre de credenciais TLS | não |

**Por que só o SSID do SoftAP precisa ser único.** Ele é a única coisa que os kits
disputam: todos anunciam no mesmo ar, e o aluno escolhe pelo nome. Todo o resto vive
*dentro* de um SoftAP, e cada SoftAP é uma rede isolada — seis kits têm seis redes
separadas, cada uma com um `wifiprov.local` em `192.168.0.1`, sem se enxergarem. O PC
entra em uma de cada vez.

**Por que o certificado se amarra ao hostname e não ao SSID.** No TLS, o cliente
verifica se o nome que ele pediu aparece no certificado do servidor. O
`provision.py` pede `https://wifiprov.local/...`; o certificado traz
`SAN: DNS:wifiprov.local`. Bate, o handshake fecha. O SSID nunca entra nessa
verificação — ele é o nome da *rede*, não o nome do *servidor*. Por isso trocar o
SSID não obriga a regerar nada, e trocar o **hostname** obriga a regerar o
certificado **e** a editar a URL no `provision.py`, que a tem fixa no código.

**A cadeia de nomes, do começo ao fim:** o aluno vê `nrf-prov-XX` na lista de redes
do PC → entra nela e recebe um IP do servidor DHCP do kit → o `provision.py` resolve
`wifiprov.local` por mDNS e chega em `192.168.0.1` → abre TLS na porta 443 e confere o
certificado contra esse nome → pede `/prov/networks` e recebe protobuf → devolve
`/prov/configure` com o SSID da rede-alvo e a senha.

**Sem `--certificate`, o TLS não autentica ninguém.** Essa flag do `provision.py` vira
o `verify=` do `requests`, e o **default é `False`**: a conexão continua criptografada,
mas o cliente aceita qualquer certificado — inclusive o de um impostor que tenha subido
um `nrf-prov-XX` falso. Passar `--certificate ../certs/server_certificate.pem` é o que
diz ao PC em quem confiar. Vale rodar as duas formas em aula: as duas "funcionam", e a
diferença entre elas é justamente o que o certificado existe para resolver.

**Onde a credencial vai parar.** Depois do `/prov/configure`, o kit grava SSID e senha
no armazenamento persistente (`CONFIG_WIFI_CREDENTIALS` sobre `fs_zms`, o
`9 Sectors of 4096 bytes` que aparece na primeira linha do boot). Nos próximos boots ele
**não** sobe mais o SoftAP: lê a credencial e conecta direto. Para voltar ao modo de
provisionamento, `sw0` apaga a credencial salva.

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
cd comms/08a_wifi_provisioning/scripts
protoc --proto_path=C:/ncs/v3.4.0/nrf/subsys/net/lib/softap_wifi_provision/proto --python_out=. common.proto
```

Gera `scripts/common_pb2.py`. Rodado localmente sem erro. Esse arquivo **não é
versionado** — está no `.gitignore` do lab, porque é derivado do `.proto` da árvore
do SDK, não código do curso.

## Passo 3 — bancada: o fluxo completo

> **Confirmado na bancada em 2026-09-07, ponta a ponta.** O boot até o SoftAP no ar foi
> medido (tabela abaixo) e o **fluxo completo de provisionamento** também — ver a seção
> "O fluxo completo, medido" mais adiante, que traz o log do lado do kit, o hex dump da
> credencial e o diagnóstico do Verify.

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

Do boot até o SoftAP no ar: **~5,6 s** (medido na bancada). SSID
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

- [x] Conectar o notebook na rede Wi-Fi do **seu** kit (o SSID que você pôs em
      `meu_softap.conf`) — fecha o item que ficou
      inconclusivo nesta bancada — confirma de fato que o SoftAP está visível).
- [ ] Rodar `python provision.py --certificate ../certs/server_certificate.pem`.
- [ ] Conferir que o script **lista as redes que a DK viu** (SSID, RSSI, banda,
      canal, tipo de autenticação) — não uma lista digitada pelo usuário.
- [ ] Escolher a rede da sala na lista e digitar a senha (rede WPA2-PSK, sem WPA3).
- [x] Confirmar no console da DK que ela recebeu a credencial, saiu do modo AP e
      associou na rede da sala (LED1 acende; `net_mgmt` reporta a conexão).

Anotar cada saída observada (mensagens do console, conteúdo da listagem do
`provision.py`, IP obtido) na próxima rodada deste README.

## Sugestão de expansão — e por que este lab não é um formulário web

A pergunta aparece sempre: *por que não uma página no navegador, o aluno digita SSID e
senha e pronto?* Vale explicitar a diferença, porque ela ensina mais que a resposta.

### O que este lab faz

O kit expõe uma **API máquina-a-máquina**: dois recursos HTTPS que trocam **protobuf**
(`/prov/networks` e `/prov/configure`), com TLS autenticado por um certificado ligado ao
hostname. Não há HTML em lugar nenhum — o "cliente" é o app da Nordic ou o
`provision.py`. É o desenho de um **produto**: o app do fabricante fala um protocolo
binário, versionável e compacto, sobre um canal autenticado.

### O que seria um provisionamento por navegador

O kit serviria uma **página HTML** com um formulário; o aluno digitaria SSID e senha e
enviaria um `POST` comum (`application/x-www-form-urlencoded`); o firmware guardaria a
credencial, derrubaria o SoftAP e conectaria como estação. Sem app, sem script, sem
`protoc`.

### O que já existe no SDK, e o que não existe

| Peça | Situação no NCS v3.4.0 (Zephyr 4.4) |
|---|---|
| Servidor HTTP com HTML estático embutido | **existe** — `CONFIG_HTTP_SERVER`, com exemplo em `zephyr/samples/net/sockets/http_server` (o `index.html` é comprimido em build e incluído como array) |
| SoftAP + servidor DHCP | **existe** — é o que este lab já usa |
| Guardar credencial | **existe** — `wifi_credentials_set_personal()` |
| Sample que junte HTTP server **com** SoftAP | **não existe** |
| Provisionamento por página web / captive portal | **não existe** — a palavra "captive" não aparece no SDK |
| **Servidor DNS** | **não existe** — há só cliente DNS, mDNS e LLMNR |

### O que teria de mudar, e o que ficaria para investigar

- **Trocar protobuf por formulário.** Um recurso `GET /` devolvendo HTML e um `POST` que
  entenda `ssid=...&senha=...` (com *percent-decode*), chamando o mesmo
  `wifi_credentials_set_personal()`.
- **Trocar HTTPS por HTTP.** O certificado autoassinado faz o navegador barrar, e dentro
  da mini-janela de portal do celular o erro de TLS costuma não ser contornável. Preço a
  declarar em aula: **a senha passaria em claro na camada de aplicação** — mitigável
  pondo senha no próprio SoftAP (WPA2), que cifra o enlace.
- **Sem DNS, não há captive portal de verdade.** Android e iOS decidem "esta rede tem
  internet?" buscando uma URL fixa; sem sequestrar DNS, a janelinha não abre sozinha e o
  aluno digita `http://192.168.0.1` na mão. Escrever um respondedor DNS mínimo é
  possível, mas é código novo.
- **`wifiprov.local` não ajuda no Android**, que não resolve `.local` no navegador.
- **A investigar:** se o `http_server` do Zephyr sobe junto com o SoftAP nesta placa
  (nenhum sample combina os dois), quanta RAM sobra depois do `wpa_supplicant` e do
  mbedTLS, e como um navegador real se comporta — ele abre várias conexões em paralelo e
  pede `/favicon.ico`, enquanto este sample atende **uma conexão por vez**.
- **Caminho preferível, se for tentar:** *não* modificar a biblioteca
  `softap_wifi_provision` (as funções que despacham URL são internas, sem ponto de
  extensão — mexer nelas obriga a manter um fork a cada versão do SDK), e sim escrever um
  app pequeno usando só API pública: `NET_REQUEST_WIFI_AP_ENABLE`, `CONFIG_HTTP_SERVER`,
  `wifi_credentials_set_personal()` e `NET_REQUEST_WIFI_AP_DISABLE`.

### Conclusão

Fica como **sugestão de expansão**, não como tarefa. Para o tempo de um lab, o caminho
atual entrega mais: protobuf e TLS são justamente o que se vê num produto real, e o
navegador esconderia os dois. Um meio-termo barato, se o objetivo for só ver uma página
servida pelo kit, é um lab **separado** com o `http_server` do Zephyr rodando sobre a
rede **já provisionada** — mostra o servidor web embarcado sem nenhuma das armadilhas
acima. Note, porém, que esse lab **não provisiona**: para abrir a página o kit já
precisa estar na rede, ou seja, já teria a credencial.

## O fluxo completo, medido — provisionando pelo app

Executado em 2026-09-07 com o **nRF Wi-Fi Provisioner** no celular. É o caminho mais
provável em sala: não exige tirar o PC da rede nem gerar o `common_pb2.py`.

### A pegadinha nº 1: o app abre no transporte errado

O app suporta três transportes e **abre em Bluetooth LE por padrão** — que serve ao
*outro* sample (`provisioning/ble`, o nosso lab 8b). Nesse modo ele varre BLE, não acha
nada, e diz **"nenhum aparelho encontrado"** — com o kit funcionando ao lado.

É preciso escolher **"Provision over Wi-Fi"**. Depois: `Start` → o Android pergunta
*"Conectar ao aparelho? O nRF Wi-Fi Provisioner usará uma rede Wi-Fi temporária"* →
`Conectar`. **O próprio app entra na rede do kit**; não é preciso ir às configurações do
Android.

### O que o kit registra

| t | linha do log | o que é |
|---|---|---|
| 00:02:34 | `Client STA connected, MAC: 04:9A:43:B8:C1:38` | o celular entrou no SoftAP |
| 00:02:40 | `on_url: > /prov/networks` (GET) | é a tela "Wi-Fi Access Points" do app |
| 00:03:19 | `on_url: > /prov/configure` (POST), `on_body length: 42` | a credencial indo para o kit |
| 00:03:19 | `ssid: PepeuNet-6G, bssid: 44:89:6D:61:58:CF, passphrase: xxxxxx, sectype: 4, channel: 6` | credencial decodificada |
| 00:03:19 | `Leaving server socket open to keep mDNS SD functioning` | efeito do `SOCKET_CLOSE_ON_COMPLETION=n` |
| 00:03:20 | `Provisioning completed` | SoftAP derrubado |
| 00:03:22 | `PSM disabled` → `Network connected` | conectou como estação |
| 00:03:22 | `DHCP IP address: 192.168.15.19` | **o endereço obtido** — ver abaixo |
| 00:05:22 | `PSM enabled` | power save volta, 120 s depois |

### A imagem que justifica o certificado inteiro

O log imprime o corpo cru do `POST`, e dá para **ler o SSID e a senha na coluna ASCII**:

```
0a 1b 0a 0b 50 65 70 65  75 4e 65 74 2d 36 47 12 |....Pepe uNet-6G.
06 44 89 6d 61 58 cf 18  01 20 06 28 04 12 0b 47 |.D.maX.. . .(...G
6f 70 69 67 6f 70 69 21  32 31                   |opigopi! 21
```

**Protobuf não criptografa nada** — é serialização, não segurança. Quem protege a senha
no ar é o **TLS por baixo**. Uma imagem só justifica todo o trabalho do certificado.

Repare também que a linha *parseada* censura (`passphrase: xxxxxx`) e a do **corpo cru**
não. Se for projetar o log em sala, é essa linha que precisa ser cortada.

### O "Verify" do app falha — e não é o provisionamento

O último passo do app, **Verify**, deu timeout. **O provisionamento funcionou**: o kit
está na rede e responde. Diagnóstico feito do PC, na mesma rede:

| Teste | Resultado |
|---|---|
| `ping 192.168.15.19` | **responde** |
| `Resolve-DnsName wifiprov.local` | **não resolve** |
| consulta mDNS multicast direta por `wifiprov.local` | **zero respostas** |
| a mesma consulta, aceitando qualquer respondente | **três outros aparelhos respondem** |

**A rede entrega mDNS normalmente; o kit é que não responde depois de virar estação.**
O Verify funciona resolvendo `wifiprov.local` por mDNS, então falha.

O sample até tenta ajudar: ele **desliga o power save de propósito** por
`CONFIG_SOFTAP_WIFI_PROVISION_SAMPLE_PSM_DISABLED_SECONDS` (**120 s** aqui) justamente
para o cliente conseguir confirmar por mDNS — está escrito no `main.c`. Mas mesmo dentro
dessa janela, e com o PSM comprovadamente desligado, o mDNS não respondeu.

> **Risco a verificar antes da aula:** o `scripts/provision.py` tem
> `https://wifiprov.local/prov/networks` **fixo no código**. Se o kit também não responder
> mDNS em modo SoftAP, o script falha pelo mesmo motivo — e o caminho alternativo ao app
> deixa de existir. **Não testado** (exige o PC sair da rede).

### O IP agora sai no log — divergência do curso

O sample original **nunca imprime o endereço obtido**: ele loga só `Network connected`.
Sem o IP, achar o kit na rede depois de provisionado exige caçar o MAC na tabela ARP do
PC. Todos os outros labs que sobem em rede imprimem (7, 9, 11, 12, 13); este era o único
que não.

O curso acrescentou uma assinatura de `NET_EVENT_IPV4_DHCP_BOUND` que imprime
`DHCP IP address: ...`, **o mesmo texto do lab 7**, para os dois logs se lerem igual. É a
única divergência de código deste lab em relação ao SDK, e está marcada no cabeçalho
`ORIGEM:` do `src/main.c`.

> **Se precisar achar o kit sem o log:** `arp -a` filtrando o OUI do nRF7002 (`f4-ce-36`).
> Cuidado com entradas obsoletas — nesta bancada havia um `.11` de um lab anterior
> apontando para o mesmo MAC.

### Um bônus que caiu no colo: a latência do power save

O ping para o kit provisionado voltou com **37–54 ms**, quando uma LAN normal dá 2–5 ms.
Com o power save desligado (dentro da janela de 120 s), **13 ms**. Essa diferença é o
rádio dormindo entre beacons — o **custo** da economia de energia, medido sem instrumento
nenhum. É o gancho direto para o lab 11, que mede o outro lado da mesma moeda.

### Os LEDs neste lab

| LED | Significado |
|---|---|
| **LED0** aceso | SoftAP de provisionamento no ar (`SOFTAP_WIFI_PROVISION_EVT_STARTED`) |
| **LED1** aceso | conectado à rede provisionada (`NET_EVENT_L4_CONNECTED`) |

Os dois juntos contam a história inteira do lab: acende o primeiro, o aluno provisiona,
apaga o primeiro e acende o segundo.

> **Armadilha de numeração:** no código são `DK_LED1` e `DK_LED2`, mas `DK_LED1` é o
> **índice 0** (`dk_buttons_and_leds.h`), e a serigrafia da nRF54LM20-DK começa em
> **LED0**. Então `DK_LED1` acende o LED marcado **LED0** na placa. Já gerou correção
> errada aqui antes.
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
  `nrf54lm20dk/nrf54lm20b/cpuapp` com `-D08a_wifi_provisioning_SHIELD="nrf7002eb2"
  -D08a_wifi_provisioning_SNIPPET=nrf70-wifi`, sem `.conf` de board para a variante B;
  `protoc` 25.3 gerando `common_pb2.py` sem erro
- Medição local, 2026-09-06 — `openssl x509` sobre `certs/server_certificate.pem`:
  `CN=wifiprov.local`, SAN `DNS:wifiprov.local`/`DNS:*.wifiprov.local`, validade
  22/mai/2024–20/mai/2034, chave EC `prime256v1`
- Medição de bancada, 2026-09-06 — nRF54LM20-DK var. B com nRF7002 EB-II: log do
  boot até o SoftAP no ar, `protoc` e módulo `protobuf` do Python conferidos no
  PC
- `zephyr/boards/nordic/nrf54lm20dk/nrf54lm20dk_common.dtsi` e
  `nrf/lib/dk_buttons_and_leds/dk_buttons_and_leds.c` — numeração física dos LEDs
  (`Green LED 0`..`3`) e como os macros `DK_LED1`/`DK_LED2` mapeiam para os
  índices 0/1 dessa lista
