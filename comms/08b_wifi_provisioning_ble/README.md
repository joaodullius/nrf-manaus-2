# Wi-Fi · Lab 8b — Provisionamento por Bluetooth LE

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

Este é o segundo caminho de provisionamento da frente de Wi-Fi. O lab 8a monta um
**Access Point** na própria DK e recebe a credencial por HTTPS de um PC que entrou
nessa rede temporária. Aqui o transporte é outro: a DK **anuncia por Bluetooth LE**,
o celular se conecta a ela por GATT e entrega a credencial de Wi-Fi por esse link.
O mesmo par de rádios do kit — nRF54LM20 (BLE) + nRF7002 (Wi-Fi) — trabalha junto na
mesma imagem.

A diferença prática entre os dois: no 8a o cliente precisa **sair** da sua rede para
entrar no AP da DK e depois voltar; no 8b o celular nunca perde a rede em que já
está, porque a conversa vai por BLE. Em compensação, o 8b exige o app oficial da
Nordic (**nRF Wi-Fi Provisioner**) — não há cliente de linha de comando equivalente
ao `provision.py` do lab 8a.

> **Origem.** Cópia integral de `nrf/samples/wifi/provisioning/ble` do **nRF Connect
> SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE). `prj.conf`,
> `CMakeLists.txt` e `src/main.c` levam o cabeçalho `ORIGEM:` do curso; nenhum dos
> três diverge do SDK. O `README.rst` original do sample não foi trazido — este
> `README.md` substitui. Os diretórios `sysbuild/` (`b0n`, `ipc_radio`, `mcuboot`) e
> `boards/thingy53_*` vieram junto por fidelidade à cópia, mas não são usados nesta
> board: eles servem aos alvos de dois núcleos (nRF5340/Thingy53), e a nRF54LM20 é de
> núcleo único.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54LM20-DK** (variante B, `nrf54lm20b`) | roda o firmware; anuncia por BLE e associa por Wi-Fi |
| **nRF7002 EB-II** | shield companion Wi-Fi 6, encaixado no header de expansão |
| **Celular Android/iOS** com **nRF Wi-Fi Provisioner** | o configurador: acha a DK por BLE, escaneia por ela e envia a credencial |
| **PC / notebook** | terminal serial (VCOM) para acompanhar o log |

Com o shield acoplado, `sw3` some do overlay (ele não existe mais): sobram `sw0`–`sw2`
e os quatro LEDs. Diferente do lab 8a, este sample **não usa botão nenhum**: não há
como resetar o provisionamento apertando `sw0`. O apagamento da credencial é feito
pelo próprio app (ou por `west flash --erase`, que limpa a partição de `settings`).

## Passo 1 — compilar e gravar

Shield é escopado pela imagem — que o sysbuild nomeia `08b_wifi_provisioning_ble`,
igual ao nome da pasta:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/08b_wifi_provisioning_ble/build_lm20 C:/work/nrf-manaus-2/comms/08b_wifi_provisioning_ble -- -D08b_wifi_provisioning_ble_SHIELD="nrf7002eb2"
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/08b_wifi_provisioning_ble/build_lm20
```

Build limpo, `exit 0`, imagem única (o nRF7002 é um companion por SPI, não um
segundo SoC; sem partition manager — `SB_CONFIG_PARTITION_MANAGER=n` no
`sysbuild.conf` do sample). Resumo de memória:

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 678024 B | 2036 KB | 32,52% |
| RAM | 320304 B | 511 KB | 61,21% |

### O snippet `nrf70-wifi` **não** entra aqui

Os labs 6, 7, 8a, 9–13 deste módulo passam `-D<imagem>_SNIPPET=nrf70-wifi` junto com
o shield. Neste lab a linha acima **não passa o snippet**, e é o que o `sample.yaml`
do SDK também faz: a entrada `sample.54lm20dk.nrf7002eb2.ble-wifi-provision` tem
apenas `extra_args: ble_SHIELD="nrf7002eb2"`, enquanto a entrada irmã para a
nRF54L15 (`sample.nrf7002eb2.nrf54l15.ble-wifi-provision`) traz o snippet.

O motivo está no próprio snippet: `nrf/snippets/nrf70-wifi/snippet.yml` só tem seções
`boards:` para `nrf54h20dk/nrf54h20/cpuapp`, `nrf54h20dk/nrf54h20/cpurad` e
`nrf54l15dk/nrf54l15/cpuapp`. **Não há seção para `nrf54lm20dk`** — e o snippet não
tem parte comum a todas as boards. Aplicado à nRF54LM20 ele é um no-op: não acrescenta
`.conf` nem overlay nenhum.

Conferido nesta bancada: as duas linhas de build (com e sem
`-D08b_wifi_provisioning_ble_SNIPPET=nrf70-wifi`) terminam em `exit 0` e produzem
**exatamente os mesmos números de FLASH e RAM**. Ou seja, passar o snippet aqui não
quebra nada — só não faz diferença. Por isso a linha canônica deste lab é a curta,
igual à do `sample.yaml`.

## O que este sample faz

O `src/main.c` é curto e o essencial está em três blocos:

1. **Nome do dispositivo derivado do MAC.** Ele monta o nome BLE como `PVxxxxxx`,
   onde os seis dígitos hexadecimais são os três últimos bytes do endereço MAC da
   interface Wi-Fi (`update_dev_name()`). Cada kit da sala anuncia um nome diferente
   sem que ninguém precise editar `.conf` nenhum — é a solução para o problema que o
   lab 8a resolve na mão com o `meu_softap.conf`.

2. **Serviço de provisionamento no advertising.** O pacote anunciado carrega o UUID
   de 128 bits do Wi-Fi Provisioning Service e quatro bytes de *service data*:

   | Byte 1 | Byte 2 | Byte 3 | Byte 4 |
   |---|---|---|---|
   | versão | flags (LSB) | flags (MSB) | RSSI |

   Bit 0 das flags = "já está provisionado"; bit 1 = "Wi-Fi conectado"; o RSSI só vale
   quando o bit 1 está ligado. Uma tarefa periódica (`update_adv_data_task`,
   `CONFIG_WIFI_PROV_ADV_DATA_UPDATE_INTERVAL`, 5 s por padrão) reescreve esses bytes.
   O app mostra o estado do kit **sem precisar se conectar** a ele.

3. **Intervalo de anúncio que muda com o estado.** Não provisionado, a DK anuncia
   rápido (`BT_GAP_ADV_FAST_INT_*_2`, na casa dos 100 ms) para ser achada logo;
   já provisionada, cai para o intervalo lento (na casa de 1 s) para economizar.

Depois do `bt_le_adv_start()`, o `main()` termina com
`net_mgmt(NET_REQUEST_WIFI_CONNECT_STORED, ...)`: se já existe credencial em flash
(`CONFIG_WIFI_CREDENTIALS` sobre `NVS`/`settings`), o kit reconecta sozinho no boot
seguinte. O provisionamento é feito uma vez e persiste.

A entrega da credencial em si não está neste arquivo: quem implementa o serviço GATT
e o protocolo (protobuf, o mesmo schema do lab 8a) são as bibliotecas
`nrf/subsys/bluetooth/services/wifi_prov` e `nrf/subsys/net/lib/wifi_prov_core`,
ligadas pelo `target_link_libraries(app PRIVATE wifi_prov_ble)` do `CMakeLists.txt`.

### BLE e Wi-Fi no mesmo kit — o que o `prj.conf` já prevê

Vale ler três linhas do `prj.conf` do sample, porque elas são o resumo do custo de ter
dois rádios na mesma imagem:

- `CONFIG_NRF70_SR_COEX=y` e `CONFIG_NRF70_SR_COEX_RF_SWITCH=y` — o árbitro de
  coexistência entre o rádio de curto alcance (BLE) e o Wi-Fi. É o mesmo assunto do
  **lab 12**, aqui ligado por padrão.
- `CONFIG_BT_RX_STACK_SIZE=22000` — a pilha da workqueue de RX do Bluetooth sobe para
  22 KB porque, durante o provisionamento, as operações de BLE e de Wi-Fi rodam na
  **mesma** thread. O comentário está no próprio arquivo.
- `CONFIG_BT_PERIPHERAL_PREF_TIMEOUT=75` (750 ms) — o supervision timeout do link BLE
  é esticado para a conexão não cair enquanto o árbitro entrega o rádio ao Wi-Fi
  durante uma varredura.

Esses três valores são a razão de este lab ser **mais pesado de RAM que o 8a**
(320304 B contra 271813 B, ~61% contra ~52% dos 511 KB) — enquanto ocupa **menos
FLASH** que ele (678024 B contra 728140 B). Os dois números são medidos, nesta board,
nas linhas de build documentadas em cada README.

> **Um aviso esperado no build.** O `prj.conf` do sample pede
> `CONFIG_NRF70_SR_COEX_RF_SWITCH=y`, e o Kconfig responde que a opção *"was assigned
> the value 'y' but got the value 'n'"*. Não é erro. Essa opção depende de o nó
> `nrf70` do devicetree ter a propriedade `srrf-switch-gpios`
> (`zephyr/drivers/wifi/nrf_wifi/Kconfig.nrfwifi`, linha 229), e o overlay da EB-II
> nesta board não a declara — não há GPIO de chave de RF a controlar aqui. O árbitro
> de coexistência (`CONFIG_NRF70_SR_COEX`) continua ligado; só o controle da chave de
> antena é que cai.

## O que observar no console

Ordem esperada no log, com a primeira VCOM aberta a 115200:

```
Bluetooth initialized.
Wi-Fi provisioning service starts successfully.
BT Advertising successfully started.
```

Com o app conectado e pareando:

```
BT Connected: <endereco BLE do celular>
BT Security changed: <endereco> level <n>.
BT pairing completed: <endereco>, bonded: 0
```

Depois da credencial enviada e aceita, aparecem as mensagens do supplicant, as mesmas
dos labs 7 e 8a:

```
wpa_supp: wlan0: CTRL-EVENT-CONNECTED - Connection to <MAC do AP> completed
```

Note o `bonded: 0`: o `prj.conf` traz `CONFIG_BT_BONDABLE=n`, então o pareamento é
por sessão e não fica salvo. A credencial de **Wi-Fi**, essa sim, persiste em flash —
o que persiste e o que não persiste são coisas diferentes aqui.

> **Bancada pendente.** O build deste lab foi validado (números de FLASH/RAM acima);
> o fluxo com o celular ainda não foi cronometrado nesta bancada. Os trechos de log
> desta seção vêm do `README.rst` do sample e do `src/main.c` (as strings de `printk`
> são literais do código), não de uma captura local.

## Pegadinhas

- **A VCOM muda com o shield — não é sempre a mesma porta.** Ver o aviso no topo
  deste README.
- **`sw3` não existe mais.** O overlay do shield remove o botão e o alias junto.
- **Não passe o snippet aqui.** Não que quebre — mas a linha canônica deste lab é a
  do `sample.yaml`, sem `nrf70-wifi`. Ver a seção do snippet acima. É a única linha
  de build do módulo que difere nesse ponto.
- **Sem cliente de PC.** Este lab depende do app **nRF Wi-Fi Provisioner** no celular.
  Quem quiser provisionar por script fica no lab 8a (`provision.py` sobre HTTPS).
- **O nome BLE é `PVxxxxxx` e não é configurável por `.conf`.** Ele sai do MAC da
  interface Wi-Fi em tempo de execução. Numa sala com vários kits, cada um aparece com
  um nome diferente — mas para saber qual é o *seu*, leia o log do console (o
  `bt_set_name()` acontece antes do primeiro anúncio).
- **`protoc` é pré-requisito do PC que compila**, igual ao lab 8a: o build gera código
  nanopb a partir dos `.proto` do SDK. Sem `protoc` no PATH, o build falha — não é um
  problema da DK.
- **`CONFIG_NRF70_SR_COEX_RF_SWITCH` sai do build sozinho.** O aviso do Kconfig
  aparece em todo build deste lab e é esperado — ver a caixa na seção "BLE e Wi-Fi no
  mesmo kit" acima.
- **`sysbuild/` e `boards/thingy53_*` não valem para esta board.** Estão na pasta por
  fidelidade à cópia do SDK; quem for procurar por que o `ipc_radio` não aparece no
  build desta DK vai encontrar a resposta aqui: a nRF54LM20 é de núcleo único.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/wifi/provisioning/ble` (código, `prj.conf`,
  `sample.yaml` e o `README.rst` que este arquivo substitui)
- nRF Connect SDK v3.4.0 — `nrf/subsys/bluetooth/services/wifi_prov` e
  `nrf/subsys/net/lib/wifi_prov_core` (serviço GATT e protocolo protobuf)
- nRF Connect SDK v3.4.0 — `nrf/snippets/nrf70-wifi/snippet.yml` (as três boards com
  seção própria; nenhuma delas é a nRF54LM20)
- nRF Connect SDK v3.4.0 — `zephyr/boards/shields/nrf7002eb2` (overlay do console:
  desabilita `uart20`, habilita `uart30`, remove `sw3`)
- Medição local, 2026-09-07 — nRF54LM20-DK var. B: build limpo para
  `nrf54lm20dk/nrf54lm20b/cpuapp` com `-D08b_wifi_provisioning_ble_SHIELD="nrf7002eb2"`,
  sem `.conf` de board para a variante B e sem snippet; segundo build com
  `-D08b_wifi_provisioning_ble_SNIPPET=nrf70-wifi` para conferir que os números não
  mudam
- [`../08a_wifi_provisioning/README.md`](../08a_wifi_provisioning/README.md) — o outro
  caminho de provisionamento (SoftAP + HTTPS), com a discussão de por que nenhum dos
  dois é um formulário web
