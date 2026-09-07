# Wi-Fi · Lab 13 — locationing por varredura de Wi-Fi

> **Antes de tudo: o console troca de VCOM.** Com a nRF7002-EB II acoplada, o overlay
> do shield move o console (e o `shell-uart`) da `uart20` para a `uart30` — e isso
> troca também a porta serial do PC: sem shield, o log sai na **segunda** VCOM da DK;
> com o shield (como neste lab), sai na **primeira**. É a mesma troca medida e
> confirmada no lab 6 (`comms/06_wifi_shell/README.md`, Passo 2) — este lab usa o
> mesmo shield e o mesmo overlay, então o comportamento é idêntico. Na dúvida, abra as
> duas portas seriais da DK e veja qual responde.

Este é o lab de fechamento do módulo de GNSS pelo lado de dentro do prédio: onde
satélite não chega, um kit sem GPS ainda consegue se localizar — desde que veja pelo
menos dois pontos de acesso Wi-Fi que já estejam num banco de dados de mapeamento.
Firmware original do curso (não vem do SDK) que conecta na rede da sala (esqueleto do
lab 7/9), varre as redes Wi-Fi ao redor e manda a lista para o PC por um socket TCP
simples. Uma ferramenta em Python no PC (`tools/wifi_locate.py`) recebe essa lista e
resolve a posição consultando os Location Services (Wi-Fi) do nRF Cloud.

## O princípio: a posição não está no kit

O kit **nunca sabe onde está** — ele só enxerga os vizinhos (BSSID e força de sinal de
cada ponto de acesso ao redor). Quem resolve a posição é o banco de dados de
mapeamento de APs do nRF Cloud, do lado do servidor: alguém (não este curso) já
percorreu o mundo registrando "este BSSID fica nesta coordenada", e o serviço combina
os APs vistos agora com esse mapa para estimar onde o dispositivo está. É o mesmo
princípio por trás do "Localizar minha rede" de qualquer smartphone sem GPS ligado —
aqui, feito manualmente, kit e ferramenta de PC separados, para o mecanismo ficar
visível.

## O fluxo

```
DK (scan Wi-Fi) --TCP, "AP,<bssid>,<rssi>,<freq>,<ssid>"--> PC (wifi_locate.py)
                                                                  |
                                                                  | HTTPS, Organization
                                                                  | Auth Token (OAT)
                                                                  v
                                                    nRF Cloud (Location Services / Wi-Fi)
                                                                  |
                                                                  v
                                                    lat, lon, uncertainty (metros)
```

1. O kit conecta na rede da sala, pede um scan (`NET_REQUEST_WIFI_SCAN`) e acumula os
   resultados.
2. Ao terminar, abre uma conexão TCP nova com o PC e manda uma linha
   `AP,<bssid>,<rssi>,<frequência em MHz>,<ssid>` por ponto de acesso visto, seguida de
   `FIM`.
3. `tools/wifi_locate.py` recebe essa lista, descarta linhas inválidas e BSSIDs
   localmente administrados (ver abaixo), e — havendo pelo menos dois pontos de acesso
   válidos — consulta o nRF Cloud.
4. O nRF Cloud devolve `lat`, `lon` e `uncertainty` (o raio de incerteza, em metros);
   a ferramenta imprime as duas metades: a lista de APs recebida e a coordenada.

## O que é preciso

- **Uma chave OAT** (Organization Auth Token) do nRF Cloud, exportada como
  `NRFCLOUD_OAT` no ambiente do PC — nunca num arquivo do repositório. É diferente da
  API key comum: a API key devolve `401 Auth token is malformed` neste endpoint. Ver
  "Como obter o OAT", abaixo.
- **Internet no PC** — é o PC que fala com `api.nrfcloud.com`, não o kit. O kit só
  precisa da rede da sala, para chegar até o PC.
- **Pelo menos dois pontos de acesso** por varredura — é o mínimo que o serviço de
  localização exige para triangular. Uma varredura com um só AP (ou nenhum) é
  descartada antes de gastar a chamada, que é um serviço **cobrado**.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54LM20-DK** (variante B, `nrf54lm20b`) | roda o firmware; host do Wi-Fi |
| **nRF7002 EB-II** | shield companion Wi-Fi 6, encaixado no header de expansão |
| **PC** | roda `tools/wifi_locate.py`; precisa de internet e da rede Wi-Fi da sala |

Com o shield acoplado, `sw3` some do overlay nesta versão do SDK: o botão do lab é o
`sw0` — cada aperto dispara uma nova varredura.

## Configuração

Além de `minha_rede.conf` (SSID/senha da rede da sala, mesma convenção dos labs 7 e
9), este lab precisa saber o IP do PC que roda `tools/wifi_locate.py`:
`CONFIG_LAB_SERVIDOR_IP`. Vazio faz o `CMakeLists.txt` falhar de propósito na
configuração — um kit sem IP de destino não teria para onde mandar a lista de pontos
de acesso.

**Nunca commitar SSID, senha ou IP reais** — `minha_rede.conf` fica vazio no
repositório; o IP do servidor vai só na linha de comando, nunca em um arquivo
versionado.

## Passo 1 — compilar e gravar

Com `minha_rede.conf` preenchido e o IP do PC em mãos:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/13_wifi_location/build_lm20 C:/work/nrf-manaus-2/comms/13_wifi_location -- -D13_wifi_location_SHIELD="nrf7002eb2" -D13_wifi_location_SNIPPET=nrf70-wifi -D13_wifi_location_EXTRA_CONF_FILE=minha_rede.conf -D13_wifi_location_CONFIG_LAB_SERVIDOR_IP=\"<ip-do-pc>\"
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/13_wifi_location/build_lm20
```

Se o build for morto por falta de memória nesta máquina, acrescente `-o=-j2` na
chamada do `west build`.

Resumo de memória (build real desta bancada, credencial de teste só na linha de
comando — não gravada em `minha_rede.conf`):

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 553520 B | 2036 KB | 26,55% |
| RAM | 187256 B | 511 KB | 35,79% |

## A ferramenta de PC (`tools/wifi_locate.py`)

### Como obter o OAT

1. Interface web do nRF Cloud → **Project Settings** (do projeto que vai receber a
   consulta de localização).
2. Gere um **Organization Auth Token** (OAT) — não confundir com a API key comum da
   conta, que serve para outros endpoints mas **não** para o Location Services (a API
   devolve `401 Auth token is malformed` se você tentar).
3. Exporte no ambiente do PC, nunca em arquivo:

   ```
   set NRFCLOUD_OAT=oat_...
   ```

Os demais valores desta conta (`organizationSlug`, `projectSlug`, `tenantId`) já vêm
como padrão no código — não são segredo, só identificam a conta e o projeto. Uma
conta diferente sobrescreve por linha de comando (`--org`, `--proj`, `--tenant-id`)
ou pelas variáveis `NRF_CLOUD_ORG_SLUG` / `NRF_CLOUD_PROJECT_SLUG` /
`NRF_CLOUD_TENANT_ID`. Esses valores aparecem em **Project Settings → General**, nos
campos **Organization Slug** e **Project Slug**.

### Rodando

```bash
cd comms/13_wifi_location/tools
pip install -r requirements.txt
set NRFCLOUD_OAT=oat_...
python wifi_locate.py --porta 9000 --org <orgSlug> --proj <projSlug>
```

Fica ouvindo a porta TCP, esperando a conexão do kit. A cada varredura recebida,
imprime as duas metades: a lista de pontos de acesso (BSSID, RSSI, frequência, SSID)
e, se houver pelo menos dois válidos, a posição resolvida (`lat`, `lon`,
`incerteza`). Uma varredura com menos de dois APs válidos (por exemplo, todos
localmente administrados — ver abaixo) é reportada e pulada, sem gastar a chamada.

### MAC localmente administrado

O `bit` de "endereço administrado localmente" (`0x02` no primeiro octeto) marca um
MAC aleatório — normalmente aleatorização de privacidade do lado cliente, não o
endereço gravado de fábrica de um ponto de acesso real. O Location Services do nRF
Cloud rejeita esses BSSIDs, porque não correspondem a nada no banco de dados de
mapeamento. `wifi_locate.py` descarta essas linhas antes de montar a requisição —
evita gastar a chamada paga só para receber esse erro de volta.

## Testes automáticos (PC, sem hardware, sem chamar a API de verdade)

```bash
cd comms/13_wifi_location/tools
python -m pytest -q
```

`11 passed` nesta bancada. Localização é um serviço **cobrado** — os testes
automáticos nunca chamam `api.nrfcloud.com` de verdade; `resolver()` é exercitado com
`requests.post` trocado por uma resposta gravada (`monkeypatch`), cobrindo o caminho
feliz e os casos ruins: menos de dois pontos de acesso (antes mesmo de montar a
requisição), lista vazia, erro HTTP (por exemplo o `401` real de token malformado,
visto na investigação desta task), resposta sem `lat`/`lon`, MAC localmente
administrado, e linha de scan malformada. `test_receber_scan_junta_linhas_e_para_no_fim`
sobe um par de sockets local (`socket.socketpair()`) para exercitar o protocolo TCP
kit→PC (acumular bytes, cortar por `\n`, parar em `FIM`, descartar linha inválida e
MAC local no meio do fluxo) sem precisar de hardware.

## Roteiro de bancada

1. `python wifi_locate.py --porta 9000 --org <orgSlug> --proj <projSlug>` no PC, com
   `NRFCLOUD_OAT` exportado.
2. Gravar a DK com o IP do PC (Passo 1).
3. Ao conectar, o kit varre automaticamente e manda o resultado — conferir no PC a
   lista de pontos de acesso vista.
4. Conferir a posição resolvida (`lat`, `lon`, `incerteza`).
5. Apertar o **botão 1** (`sw0`) → nova varredura, novo envio.
6. Se a resposta indicar erro de MAC local (não deveria acontecer — `wifi_locate.py`
   já descarta esses BSSIDs antes de montar a requisição —, mas vale conferir se
   algum passou), comparar com a nota da Nordic sobre endereços localmente
   administrados.

> **A confirmar na bancada:**
> - A lista real de pontos de acesso vista pelo kit na sala do treinamento.
> - A posição resolvida (`lat`, `lon`, `incerteza`) e o erro medido contra a posição
>   real da sala (distância entre a coordenada devolvida e a posição real, em metros).
>   Uma chamada com cinco pontos de acesso desta bancada devolveu incerteza de cerca
>   de 14 metros — mas esse número veio direto da ferramenta de PC, sem passar pelo
>   firmware; o fluxo completo (kit → TCP → `wifi_locate.py` → nRF Cloud) ainda está
>   por confirmar.

## Pegadinhas

- **O firewall do Windows bloqueia o servidor sem avisar ninguém**, mesmo sendo esta
  ferramenta quem só recebe a conexão do kit (não fala com a internet na porta que o
  kit usa). Ver a seção "Pegadinhas" de `comms/09_wifi_tcp/README.md` para o sintoma e
  o comando de liberação (`New-NetFirewallRule`), trocando a porta para a deste lab.
- **API key comum não serve para Location Services** — só o Organization Auth Token
  (OAT). Uma API key aqui devolve `401 Auth token is malformed`, não `403` nem
  qualquer outro erro que sugira "chave errada" — é fácil gastar tempo achando que é
  outro problema.

## O caminho de produção: `wifi/nrf_cloud`

Este lab resolve a posição **fora** do dispositivo, de propósito: o kit manda a lista
de APs para um script Python no PC, que fala com a conta de organização/projeto do
nRF Cloud usando um token de organização — não há TF-M, não há onboarding de
dispositivo, e a chave nunca sobe para o firmware. É a forma mais direta de mostrar o
mecanismo, mas não é como um produto real embarcaria isso.

O caminho de produção é o sample `nrf/samples/wifi/nrf_cloud` do SDK: o **próprio
dispositivo** se conecta ao nRF Cloud (via CoAP ou MQTT), autenticado por certificado
provisionado com **TF-M** (Trust Zone), depois de um fluxo de **onboarding** que
associa aquele dispositivo físico à conta na nuvem. O rastreamento de localização por
Wi-Fi é uma das features desse sample (via a biblioteca `lib_location`), rodando
continuamente no dispositivo — sem um script de PC no meio.
