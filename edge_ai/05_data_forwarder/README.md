# 05 · Coleta pelo caminho oficial (Data Forwarder)

**Alternativa ao [`03_central_uart`](../03_central_uart/), não continuação dele.** Os dois
levam amostras do IMU da TAG para o PC; mudam o firmware, o protocolo e a ferramenta.

> **Origem:** cópia de `samples/data_forwarder` do **Edge AI Add-on v2.3.0**, copiada em
> 2026-08-30. Licença Nordic preservada em [LICENSE](LICENSE). Divergências do curso
> marcadas nos cabeçalhos.

## Quando usar qual

| | `03_central_uart` | `05_data_forwarder` (este) |
|---|---|---|
| Firmware na TAG | **o mesmo do 01**, com um fragmento | outro firmware |
| Protocolo | texto: `"<id> ax,...,gz\r\n"` | **CBOR + COBS + CRC-16** |
| Ferramenta no PC | `prep_dataset.py` (terminal) | **Data Forwarder Host** (GUI) |
| Segunda placa | nRF54LM20-DK obrigatória | opcional (o PC conecta por BLE) |
| Unidades | mili | **micro** (`INT32_VALUES=y`) |
| Vantagem | continuidade com o Ato 1, unidades já casam | GUI com plot ao vivo, ferramenta oficial |

Para o **loop 1** use o 03: as unidades já batem com o que a app de gestos alimenta na
inferência. Para o **loop 2**, onde o aluno escreve a própria app, use este — a app
é escrita para casar com o que foi capturado, então a diferença de unidades deixa de ser
um problema.

## Build

```
west build -p -b nrf54l15tag/nrf54l15/cpuapp ^
  -d C:\work\nrf-manaus-2\edge_ai\05_data_forwarder\build_tag ^
  C:\work\nrf-manaus-2\edge_ai\05_data_forwarder
```

Sem fragmento: é o sample como a Nordic documenta, **9 canais** — 6 do BMI270
(`ax..gz`) mais temperatura, umidade e pressão do BME688 (`temp,hum,pres`). O modelo de
gesto usa 6; as três colunas ambientais são removidas **no Lab**, na hora do upload
(seção *Remove variables*), não no firmware. Ver o Passo 5 do roteiro.

Desligar o BME688 por Kconfig (`CONFIG_DATA_FWD_EXTRA_SENSOR_BME688=n`) não vale a pena:
o Data Forwarder Host é validado pela Nordic a **500 frames/s com 10 canais**, e aqui são
100 Hz com 9. Banda não é argumento, e remover colunas no Lab é um passo de dados que o
aluno deve ver.

## ⚠️ Bug do zcbor no Windows (contornado aqui)

O sample **não compila no Windows** como vem do add-on:

```python
makedirs("./" + path.dirname(saida))        # zcbor.py:2793
OSError: [WinError 123] ... './C:'
```

O `CMakeLists.txt` passa `--output-c`/`--output-h` **absolutos**, e o zcbor concatena
`"./"` na frente — num caminho `C:\...` isso vira `./C:`, que é inválido.

**Reproduzido com o sample intocado**, direto de
`C:/ncs/sdk-edge-ai/edge-ai/samples/data_forwarder`, num build dir limpo. Não é efeito da
cópia — é bug do add-on v2.3.0 com o zcbor do toolchain.

O contorno está no [`CMakeLists.txt`](CMakeLists.txt): passar os caminhos **relativos**,
com `WORKING_DIRECTORY ${PROJECT_BINARY_DIR}`. Em Linux/macOS o upstream funciona e o
contorno também.

## Roteiro do loop 2 — coleta com o forwarder, treino no Lab, inferência no 04

Espelho do roteiro do loop 1 (Passos 1–6 do [`03_central_uart`](../03_central_uart/README.md)),
agora pelo caminho oficial. O aluno coleta com o Data Forwarder Host, treina no Edge AI
Lab e coloca o modelo na **própria app**, o [`04_classify_led`](../04_classify_led/).

Todos os passos foram executados no hardware do curso (`✅`), com o caso do ventilador
descrito no fim desta seção.

### Antes de começar: três decisões

**1. Fundo de escala.** O sample crava ±2 g / ±500 dps em `src/sensor/bmi270.c:85` e
`:102`. O 04 usa ±4 g / ±1000 dps. Alinhar o 05 antes de coletar: um sinal que satura a
±2 g na captura não satura na inferência, e o modelo aprende algo que a app nunca vai ver.

**2. Como receber.** Opção A: PC direto por BLE (Data Forwarder Host, fonte *BLE NUS*).
Opção B: nRF54LM20-DK como ponte binária, Host com fonte *UART*. Tentar A; se o BLE do
Windows não conectar ou perder frames, B. A doc da Nordic segue essa mesma ordem.

**3. O que classificar.** 3 a 5 classes (limite prático do LED RGB, ver README do 04).
O caso do curso é **vibração**: a velocidade de um ventilador, 4 classes (`idle`, `vel1`,
`vel2`, `vel3`) — contínuo, sem centralização, e o que separa as classes é o espectro.
Janela **128** (potência de 2, exigida pelos features de frequência). Gestos discretos
também funcionam por este caminho, mas voltam a exigir a centralização do loop 1.

### Escala e tipo: o loop 2 vai em FLOAT32, micro-unidades

O CSV do Host vai para o Lab **como está** — micro-unidades SI do Zephyr, escritas como
float — e o Lab detecta FLOAT32. É o caminho que a Nordic documenta: o Host "exporta CSV
compatível com o Edge AI Lab", e o `prj.conf` do sample liga `INT32_VALUES=y` "for use
with Edge AI Lab". O loop 2 não precisa casar com a escala do loop 1.

A doc de requisitos do Lab
([dataset_requirements](https://docs.nordicsemi.com/r/bundle/edge-ai-lab/page/model_creating_pipeline/dataset_requirements.html/requirements-for-training-datasets))
aceita **INT8, INT16 e FLOAT32**. Micro-unidades em int32 não cabem em INT16, então
INT16 exigiria dividir por 1000 (mili, o caminho do loop 1). Em FLOAT32 não há conversão
nenhuma, e a lição de escala fica mais limpa — **a app alimenta o modelo com
`sensor_value_to_micro()`, exatamente o número que está no CSV.**

### Passo 1 — limpar o central antigo da DK ✅

A DK do aluno ainda roda o `03_central_uart` do loop 1, filtrando o tag dele. Se ficar
ligado, ele conecta primeiro e o PC nunca vê a TAG (ela aceita um central por vez). Com a
TAG **fora** do `DEBUG OUT`:

```
nrfutil device recover --serial-number <serial da DK>
```

Só faz falta na opção A; na B a DK é regravada de qualquer jeito.

*Validado 2026-09-02:* LM20-DK `1051898754`, `exit 0`, `device-info` reporta
`nRF54LM20B_xxAA_ENGB`.

### Passo 2 — gravar o forwarder na TAG ✅

TAG encaixada no `DEBUG OUT` da LM20-DK.

**Fundo de escala — o aluno edita, o repo fica como o sample.** O repo mantém os
literais do sample (±2 g / ±500 dps) e o aluno muda para casar com o 04 (±4 g / ±1000
dps). É um exercício de leitura de código, e vale um slide: dois literais em
`src/sensor/bmi270.c`, sem Kconfig.

```c
/* src/sensor/bmi270.c:85 — acelerômetro */
full_scale.val1 = 2; /* G */        →   full_scale.val1 = 4; /* G */

/* src/sensor/bmi270.c:102 — giroscópio */
full_scale.val1 = 500; /* dps */    →   full_scale.val1 = 1000; /* dps */
```

Não muda a unidade (continua micro-unidade em int32), só o teto antes de saturar. A
mesma escala tem de ser configurada no `imu_init()` do 04 (Passo 7).

**LED de estado — a única divergência de código do curso.** O sample não usa LED, e na
aula a TAG roda na bateria, sem RTT. Acrescentado em `src/main.c` (marcado no cabeçalho)
com `CONFIG_GPIO=y` no `prj.conf`:

| LED | Significa |
|---|---|
| **azul**, um flash curto por segundo | anunciando, sem central conectado |
| **verde**, piscando a 2 Hz | central conectado e laço de coleta rodando |
| nenhum | travou antes do laço (sensor, BLE) — olhar o RTT |

O verde é um heartbeat do próprio laço de amostragem, condicionado a haver conexão. O
estado da conexão vem de um `bt_conn_cb` registrado no `main.c` com `BT_CONN_CB_DEFINE`,
sem tocar no transporte. Detalhe que engana quem for estender isso:
`proto_send_samples()` **retorna 0 mesmo sem conexão** — ele só enfileira, e o envio real
falha depois, numa work queue (`-22`, `nus_mtu == 0`). Não dá para usar o retorno dele
como "enviou".

*Validado 2026-09-02 nos dois estados:* azul piscando com a TAG anunciando (RTT com os
`-22`), verde a 2 Hz assim que o Host conectou e começou a gravar. Custo: ~800 B de flash.

```
west build -p -b nrf54l15tag/nrf54l15/cpuapp -d C:\work\nrf-manaus-2\edge_ai\05_data_forwarder\build_tag C:\work\nrf-manaus-2\edge_ai\05_data_forwarder
west flash -d C:\work\nrf-manaus-2\edge_ai\05_data_forwarder\build_tag --dev-id <serial da DK>
```

A TAG passa a anunciar como `nRF DataFwd`, 9 canais a 100 Hz. Log por RTT (o
`JLinkRTTLogger` fica em `C:\Program Files\SEGGER\JLink_Vxxx\`):

```
JLinkRTTLogger -Device NRF54L15_M33 -If SWD -Speed 4000 -USB <serial da DK> -RTTChannel 0 tag_rtt.log
```

Sem central conectado o log repete, a cada 5 s:

```
<wrn> protocol: Skipped 499 messages
<wrn> protocol: Samples send failed: -22
<wrn> protocol: Session send failed: -22
```

É o esperado: `-22` (`-EINVAL`) sai de `ble_send_cb()` porque `nus_mtu == 0` — ainda não
houve troca de MTU, logo não há conexão — e a fila de 500 amostras (5 s) é descartada. Some
quando o Host conecta.

⚠️ **RTT velho depois de regravar.** Na primeira leitura logo após o `west flash`, o
logger mostrou o boot do firmware **anterior** (o 01 em modo de coleta, com `Solution id`
e prompt `tag:~$`). A RAM não é apagada na gravação e o bloco de controle RTT do firmware
antigo continua lá com a assinatura `SEGGER RTT`; o logger achou esse primeiro. Rodar de
novo (ou power-cycle da TAG) resolve. Se o log não bate com o firmware que você acabou de
gravar, desconfie disso antes de desconfiar do `west flash`.

⚠️ **`Sensor init failed (err -19)` depois de reencaixar a TAG.** Aconteceu na bancada
ao tirar a TAG do `DEBUG OUT` e recolocar: o boot parava em `-ENODEV` (BMI270 ou BME688
não "ready"), o `main()` retornava e o LED ficava apagado. **Reset do SoC não resolve**
(`nrfutil device reset` repetiu o erro): os sensores são alimentados pela placa, não pelo
SoC, e continuam no estado em que ficaram. O sinal precursor foi `ADXL367 failed
self-test` no boot anterior — o ADXL367 divide o TWI com o BME688. **Correção: tirar a
TAG do `DEBUG OUT`, tirar a bateria se houver, esperar 5 s e encaixar de novo.** É o
power-on-reset dos sensores. Depois disso: `ADXL367 passed self-test`, `Data forwarder
started`, azul piscando.

*Validado 2026-09-02:* build com o fundo de escala já em 4 / 1000 e o LED de estado,
**202.380 B** flash / **47.304 B** RAM (o LED custou ~800 B); `.config` com
`EXTRA_SENSOR_BME688=y`, `MAX_CHANNELS=9`, `INT32_VALUES=y`, nome `nRF DataFwd`;
`west flash --dev-id 1051898754` com verify OK; `device-info` com a TAG encaixada reporta
`nRF54L15_xxAA_REV2` (o debugger da DK aponta para a TAG); RTT com os avisos acima.

### Passo 3 — instalar e abrir o Data Forwarder Host ✅

**Onde fica.** A ferramenta vem **dentro do Edge AI Add-on**, não é download separado:

```
C:\ncs\sdk-edge-ai\edge-ai\tools\data_forwarder_host\
```

(`C:\ncs\sdk-edge-ai` é o workspace west do add-on; `edge-ai\` é o próprio add-on v2.3.0.)
É um pacote Python com GUI em Qt. Requisitos: Python ≥ 3.12 e, para a opção A, um
adaptador Bluetooth no PC.

**Instalar (uma vez) e abrir:**

```
cd C:\ncs\sdk-edge-ai\edge-ai\tools\data_forwarder_host
pip install -r requirements.txt
python main.py
```

O `pip install` puxa PySide6 (Qt 6, ~150 MB), `cobs`, `bleak` e `pyserial`. *Validado
2026-09-02 com Python 3.12.10:* PySide6 6.11.2 e `data-forwarder-host` 0.1.0. Depois de
instalado, `python -m data_forwarder_host` ou o script `data-forwarder-host` também
abrem. **Não há CLI** — o README da ferramenta diz textualmente
*"there is no command-line interface"*.

**Onde a ferramenta guarda as coisas** (Windows):

| O quê | Onde |
|---|---|
| Gravações (CSV + `.txt`) | pasta escolhida na aba; sem escolher, `recordings\` dentro do pacote |
| Log da aplicação | `%LOCALAPPDATA%\Nordic Semiconductor\data_forwarder\Logs\data_forwarder_host.log` |
| Configurações | `%LOCALAPPDATA%\Nordic Semiconductor\data_forwarder\settings.json` |

O log registra cada clique como `USER ACTION` e cada evento BLE. Quando algo der errado
em sala, é ali que se olha. Ele também vai para o terminal de onde a GUI foi aberta.

⚠️ **Python da Microsoft Store esconde o log.** Se o `python` for o da Store (o caso
desta bancada: `...\WindowsApps\PythonSoftwareFoundation.Python.3.12_...`), o Windows
**virtualiza** o `%LOCALAPPDATA%` e a pasta acima não existe. O log real fica em

```
%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\Local\Nordic Semiconductor\data_forwarder\Logs\
```

Descoberto em 2026-09-02 procurando o log no caminho que o `utils/paths.py` imprime e não
achando nada.

**Criar a sessão.** `Session → New session…`:

| Campo | Valor |
|---|---|
| Session tag | um nome sem espaço/acento; entra no nome do CSV |
| Plot window | 10 s (padrão) |
| Kind | `ble` |
| Dispositivo | `nRF DataFwd` — conferir que o endereço é o **seu** tag |
| Frames carry CRC-16 trailer | **marcado** (o firmware tem `DATA_FWD_PROTO_CRC=y`) |

Clique **Connect** e **espere**. No Windows a negociação leva **10 a 15 s** e o popup
parece travado. Quando o status fica verde, o `Create session` habilita. O streaming
começa sozinho; o plot mostra 9 canais — os três do BME688 em escada, porque o sensor é
lento e o sample repete a última leitura. Na opção A a TAG pode ficar no `DEBUG OUT` ou na
bateria.

⚠️ **Não clique Cancel no popup.** O Connect leva ~10 s e o popup não dá sinal de vida
nesse tempo. Cancelar derruba a conexão, inclusive uma que acabou de completar. Vale
dizer em sala antes do clique.

*Validado 2026-09-02:* Windows 11, adaptador Bluetooth interno do notebook, `bleak`.
`BLE NUS link negotiated ATT MTU = 247 bytes`, conectado a `EC:EF:40:2D:5E:46`.

**Passo 3-B — se o BLE do PC falhar.** Tirar a TAG do `DEBUG OUT` (bateria). Conferir o
endereço em `meu_tag.conf`. Gravar a ponte binária na DK:

```
west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp -d C:\work\nrf-manaus-2\edge_ai\03_central_uart\build_lm20_bin C:\work\nrf-manaus-2\edge_ai\03_central_uart -- -DEXTRA_CONF_FILE="meu_tag.conf;binary_bridge.conf"
west flash -d C:\work\nrf-manaus-2\edge_ai\03_central_uart\build_lm20_bin --dev-id <serial da DK>
```

No Host, sessão com fonte **UART**, a **vcom1** da DK, 115200 8N1. Se ficar muda, a outra.

### Passo 4 — gravar uma classe por vez ✅

Na aba da sessão: **label** (`vel1`), pasta de saída, `Record`, uns 5 minutos na
condição da classe, `Stop`. Repetir por classe **sem mexer na TAG** entre uma e outra.
Cada gravação gera `{label}_{sessão}_{utc}.csv` com header

```
device_time_ms,ax,ay,az,gx,gy,gz,temp,hum,pres,label
```

e um `.txt` de metadados ao lado (host, transporte, timing, canais, erros). Sem pasta, cai
em `recordings/` dentro do pacote do Host.

**As unidades, lidas do CSV real.** São **micro-unidades SI do Zephyr**, não micro-g:

| Canal | Valor típico (TAG parada) | Significa |
|---|---|---|
| `az` | `10011659` | 10,01 m/s² × 10⁶ — gravidade |
| `gx` | `-2663` | −0,0027 rad/s × 10⁶ — o giroscópio do Zephyr é **rad/s**, não dps |
| `temp` | `24030000` | 24,03 °C × 10⁶ |
| `hum` | `48718000` | 48,7 % × 10⁶ |
| `pres` | `101618000` | 101,6 kPa × 10⁶ |

Os valores vêm com `.0` no fim: o Host escreve float, e é assim que vão para o Lab. A
app de inferência alimenta o modelo na mesma escala com `sensor_value_to_micro()`. (O
loop 1 trabalha em mili — `sensor_value_to_double() * 1000` — e isso **não** importa aqui:
o modelo do loop 2 é treinado em micro e alimentado em micro.)

*Validado 2026-09-03, BLE direto no PC (Bluetooth interno de um notebook Windows):* as
4 gravações de [`dataset_referencia/`](dataset_referencia/), 24 min no total, com **18
amostras perdidas em 146 mil** (`device_time_ms` avança 9/10/11 ms; `producer_drop_count
= 0` nos sidecars). A ponte na DK segue como plano B para quem não tiver adaptador ou
não conseguir conectar, não por falta de banda.

### Passo 5 — converter para o Lab (`tools/fwd_to_lab.py`) ✅

O `prep_dataset.py` do 03 lê o texto da serial, **não** este CSV. O conversor deste lab é
[`tools/fwd_to_lab.py`](tools/fwd_to_lab.py), só stdlib:

```
python tools/fwd_to_lab.py info  <pasta>\*.csv
python tools/fwd_to_lab.py merge <pasta>\*.csv --classes idle,vel1,vel2,vel3 --out dataset.csv
```

`info` mostra taxa, amostras perdidas e o espalhamento de cada gravação — serve para
pegar uma gravação ruim antes de treinar. `merge` **não mexe nos valores**:

- descarta `device_time_ms`;
- troca o `label` texto pelo inteiro na ordem de `--classes` — **essa ordem é o
  dicionário de classes**; o script a imprime no fim e a app precisa dela;
- concatena na ordem dos arquivos, sem embaralhar; vários arquivos da mesma classe
  entram na mesma classe; recusa arquivos com canais diferentes entre si;
- valida as regras do Lab (≥ 2 classes, ≥ 20 amostras por classe, classe 0, nada vazio)
  e sai com código 1 sem deixar arquivo se falhar.

Os nomes dos canais ficam os do Host (`ax..gz,temp,hum,pres`), e os valores ficam
verbatim, em micro-unidades float. As três colunas do BME688 **ficam** e o aluno as
remove no Lab, em *Remove variables* no upload — o modelo gerado sai com 6 entradas.
Quem preferir tirá-las antes usa `--drop-env`. `--session-col` acrescenta `session` =
índice do arquivo, que o Lab aceita como *Session ID* para separar treino e validação
por gravação.

Gestos discretos (swipes) ainda precisam de centralização depois disso, como no loop 1
(`center_gestures.py` do 03). Vibração, `idle` e `unknown` não.

*Validado 2026-09-03 com o caso do ventilador (abaixo):* 4 gravações → 4 classes,
146.523 linhas, `ax,ay,az,gx,gy,gz,temp,hum,pres,class`; recusas exercitadas (classe
listada sem arquivo, uma classe só — nada gravado, `exit 1`).

### O caso de uso do loop 2 na bancada: velocidade de um ventilador por vibração

**A coleta completa está no repo:** [`dataset_referencia/`](dataset_referencia/), com as
4 gravações brutas do Host (`bruto/`), o `dataset_ventilador.csv` pronto para o Lab e um
README com as regras de coleta e as limitações. É a rede de segurança da aula, como o do
03 para o loop 1.

Em vez de gestos, um ventilador portátil de 3 velocidades com a TAG presa nele:
classes `idle`, `vel1`, `vel2`, `vel3`. É um caso melhor para o loop 2 do que repetir
os swipes: não precisa centralizar, o dado é contínuo, e o que separa as classes é o
**perfil de vibração** — amplitude e frequência —, que é o que o Lab extrai com signal
processing.

O `info` já mostra a separação, pelo desvio-padrão:

| Gravação | az (m/s²) | gx (rad/s) |
|---|---:|---:|
| idle (TAG presa, ventilador desligado) | 0,009 | 0,001 |
| vel1 | 0,054 | 0,003 |
| vel2 | 0,098 | 0,014 |
| vel3 | 0,174 | 0,014 |

Três coisas para o material:

- **Muda só a variável que se quer classificar.** A fixação do sensor faz parte da
  classe: a mesma velocidade com a TAG presa de outro jeito dá outro perfil. Prender uma
  vez e gravar todas as classes sem mexer, `idle` incluído. O `info` do `fwd_to_lab.py`
  mostra o desvio-padrão por gravação e denuncia quando algo além da velocidade mudou.
- **Colete na condição em que o modelo vai rodar.** O ventilador gira mais devagar no
  carregador que na bateria; um modelo treinado no carregador classifica `vel1` como
  `vel2` na bateria, com 99 % de confiança. O dataset de referência é da bateria, que é
  como o ventilador anda na aula.
- **Features de frequência exigem janela potência de 2.** Para vibração, os features
  no domínio da frequência são os que importam, e o Lab só os aceita com janela de
  **128 a 2048 amostras, potência de 2**
  ([DevZone, "How to create a custom Neuton model"](https://devzone.nordicsemi.com/nordic/nordic-blog/b/blog/posts/introducing-custom-neuton-models)).
  A 100 Hz, 128 amostras = 1,28 s por inferência. É diferente da janela 99/33 dos
  gestos, e o `USER_WINDOW_SIZE` do 04 tem de acompanhar.

### Passo 6 — treinar no Lab ✅

Arrastar o CSV em `ai.lab.nordicsemi.com`. A receita, tela a tela:

| Tela | O que marcar |
|---|---|
| Dataset options | target = `class`; `temp`, `hum`, `pres` em **Remove variables** |
| Signal processing · Windowing | **Number of Rows**, não Time Interval (em ms, 128 vira 12 amostras a 100 Hz e o Lab recusa). Window **128**, shift de treino **32**, shift de inferência **64** |
| Feature extraction | ver tabela abaixo; **Feature selection ligado** |
| Input data | FLOAT32 (detectado sozinho), Normalization AutoSelect, Accuracy |
| Model settings | Neuton, pesos float32, saída float32, **Arm Cortex-M33** |

**Features para vibração.** O que separa velocidades de um ventilador é frequência e
energia; a média é orientação. Com o *Feature selection* ligado marcar a mais não custa
acurácia — o Lab descarta o que não contribui — só footprint no que sobrar.

| Marcar | Por quê |
|---|---|
| **Amplitude spectrum** | o espectro em si; é o feature mais importante do modelo do curso |
| **Dominant frequencies**, Spectral centroid / spread / crest / RMS | a doc do Lab lista "vibration analysis" e "motor condition monitoring" como o caso deles |
| Root mean square, Standard deviation | energia da vibração, cresce com a velocidade; o `info` já mostra que separam |
| Range (ou Max / Min) | amplitude de pico, complementa o RMS |
| Mean-crossing rate ou Zero-crossing rate | frequência grosseira sem FFT, quase de graça |

| Deixar de fora | Por quê |
|---|---|
| Mean, Absolute mean | no acelerômetro a média é a **gravidade** — orientação da TAG, não vibração. Presa um pouco diferente, é o primeiro feature a trair (o mesmo vício do `acc_mean` no loop 1) |
| Linear regression slope / intercept | tendência dentro da janela; sinal estacionário não tem |
| Skewness, Kurtosis, Hjorth, Autocorrelation, Percentage over … | impulsividade e falha de rolamento, não velocidade; só somam código |

Frequency features exigem janela **potência de 2 entre 128 e 2048**. A 100 Hz, 128 = 1,28 s
e bins de 0,78 Hz; se `vel2` e `vel3` se confundirem, 256 dobra a resolução espectral
(e o `USER_WINDOW_SIZE` do 04 acompanha).

Baixar o zip e anotar o **solution id**.

### Passo 7 — o modelo na app do aluno (`04_classify_led`) ✅

TAG de volta no `DEBUG OUT`.

O 04 vem ligado no **modelo de exemplo da Nordic** (estados de transporte de uma
encomenda), para a fiação rodar antes de existir modelo próprio. O do ventilador já está
no repo em `src/nrf_edgeai_generated/ventilador_95922/`; para o seu, o caminho é o mesmo:

1. Copiar a pasta `nrf_edgeai_generated/` do zip para uma subpasta nova de
   `src/nrf_edgeai_generated/` — **os três arquivos**, inclusive `nrf_edgeai_user_types.h`
   — e apontar `CURSO_MODELO` no `CMakeLists.txt` para ela.
2. No topo de `src/main.c`: `USER_WINDOW_SIZE` = janela do Lab, `USER_UNIQ_INPUTS_NUM` = 6,
   `USER_MODELS_CLASS_NUM` = número de classes. Os valores reais estão no `.c` gerado
   (para o ventilador, o bloco já está lá comentado).
3. `CLASS_COLORS` com exatamente uma linha por classe, na ordem do dicionário que o
   `merge` imprimiu (o `BUILD_ASSERT` pega o número errado; a do ventilador está lá,
   comentada).
4. A leitura dos 6 eixos em **micro-unidades** (`sensor_value_to_micro()`, ordem
   `ax,ay,az,gx,gy,gz` do CSV) já está no `main.c`. Conferir só `IMU_ACCEL_FS_G` e
   `IMU_GYRO_FS_DPS`: o mesmo fundo de escala deixado no `bmi270.c` antes de coletar.

```
west build -p -b nrf54l15tag/nrf54l15/cpuapp -d C:\work\nrf-manaus-2\edge_ai\04_classify_led\build_tag C:\work\nrf-manaus-2\edge_ai\04_classify_led
west flash -d C:\work\nrf-manaus-2\edge_ai\04_classify_led\build_tag --dev-id <serial da DK>
```

O `-p` não é opcional. No RTT: conferir o `Solution id`, as três linhas
`janela em ... ms (esperado 1280)` do boot, e que a TAG parada dá `idle` com confiança
alta. Outra classe parada = escala errada; janela fora de 2 % = ritmo errado (as duas
armadilhas estão no README do 04).

*Validado 2026-09-03 com o dataset do ventilador (coleta na bateria):* Lab com janela
128 / shift de treino 32 / features de frequência, FLOAT32, Cortex-M33 → **acurácia
1,000** nas janelas de validação (20 % do dataset), **39 coeficientes**, 5,2 kB SRAM /
11,7 kB NVM estimados (8,8 kB são o signal processing — a FFT; o modelo em si tem 253 B).
Feature Importance: `ax` e `gz` amplitude spectrum e `az` / `ay` dominant frequencies no
topo — frequência decide; o `idle` quase não aparece nas barras porque qualquer feature
de energia o separa com folga, e as espectrais existem para separar as três velocidades
entre si. Na TAG: `Solution id: 95922`, `janela 128 · entradas 6 · classes 4`,
`janela em 1282 ms (esperado 1280)`; 89.384 B flash / 24.016 B RAM. Telas do Lab em
`doc/edge_ai/img/lab_loop2/`.
