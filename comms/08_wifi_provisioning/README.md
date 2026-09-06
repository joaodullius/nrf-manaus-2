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
> `CMakeLists.txt` e `src/main.c` levam o cabeçalho `ORIGEM:` do curso; nenhum dos
> três diverge do SDK. O `README.rst` original do sample não foi trazido — este
> `README.md` substitui.

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

LEDs: LED1 acende quando a DK entra em modo AP (provisionamento em andamento); LED2
acende quando a DK conecta na rede provisionada.

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

> **A confirmar na bancada.**

Checklist para a rodada de bancada, na UART correta (aviso no topo deste README —
primeira VCOM com o shield acoplado):

- [ ] Gravar o firmware e abrir o console. Confirmar `Provisioning started` e o
      servidor DHCP subindo (a DK já está em modo AP, com o SSID `nrf-wifiprov`).
- [ ] No notebook, conectar na rede Wi-Fi `nrf-wifiprov`.
- [ ] Rodar `python provision.py --certificate ../certs/server_certificate.pem`.
- [ ] Conferir que o script **lista as redes que a DK viu** (SSID, RSSI, banda,
      canal, tipo de autenticação) — não uma lista digitada pelo usuário.
- [ ] Escolher a rede da sala na lista e digitar a senha (rede WPA2-PSK, sem WPA3).
- [ ] Confirmar no console da DK que ela recebeu a credencial, saiu do modo AP e
      associou na rede da sala (LED2 acende; `net_mgmt` reporta a conexão).

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
