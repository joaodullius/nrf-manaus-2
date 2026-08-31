# 04 · Coleta pelo caminho oficial (Data Forwarder)

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
| Segunda placa | nRF54L15-DK obrigatória | opcional (o PC conecta por BLE) |
| Unidades | mili | **micro** (`INT32_VALUES=y`) |
| Vantagem | continuidade com o Ato 1, unidades já casam | GUI com plot ao vivo, ferramenta oficial |

Para o **loop 1** use o 03: as unidades já batem com o que a app de gestos alimenta na
inferência. Para o **loop 2**, onde o aluno escreve a própria app, o 04 é melhor — a app
é escrita para casar com o que foi capturado, então a diferença de unidades deixa de ser
um problema.

## Build

```
west build -p -b nrf54l15tag/nrf54l15/cpuapp ^
  -d C:\work\nrf-manaus-2\edge_ai\05_data_forwarder\build_tag ^
  C:\work\nrf-manaus-2\edge_ai\05_data_forwarder ^
  -- -DEXTRA_CONF_FILE=gesture_compat.conf
```

O [`gesture_compat.conf`](gesture_compat.conf) desliga o BME688, voltando de **9 para 6
canais** — o que o modelo de gesto usa, e metade da banda.

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

## Receber os dados

**Opção A — PC direto por BLE.** Instale o Data Forwarder Host (`tools/data_forwarder_host`
no add-on, ou o executável pronto). É **GUI pura** — o README dele diz textualmente
*"there is no command-line interface"*.

**Opção B — ponte pela nRF54L15-DK.** É o que a doc da Nordic manda quando o BLE do PC não
conecta. Use o `03_central_uart` **em modo binário**:

```
west build -p -b nrf54l15dk/nrf54l15/cpuapp ^
  -d ...\03_central_uart\build_dk_bin ^
  ...\03_central_uart ^
  -- -DEXTRA_CONF_FILE="meu_tag.conf;binary_bridge.conf"
```

O [`binary_bridge.conf`](../03_central_uart/binary_bridge.conf) faz duas coisas: repassa os
bytes intactos (o modo texto acrescenta LF quando o pedaço termina em CR) e sobe o MTU
para 247, que é o que o tag negocia.

O **endereço BLE do tag não muda** entre o 01 e o 04 — é o endereço estático derivado do
FICR. O mesmo `meu_tag.conf` serve.

## Validado no hardware

TAG com o 04 → nRF54L15-DK com o 03 em modo binário → serial, decodificando COBS + CRC-16
com o mesmo algoritmo do host tool (`protocol/framing.py`):

```
janela             10.1 s
frames delimitados 1011
  CRC ok           1011   (100.0/s)
  CRC ruim         0
  COBS falhou      0
  malformados      0
tamanhos de payload {48: 1, 50: 91, 52: 917, 79: 2}
```

100 frames/s batendo com os 100 Hz; os de 79 bytes são os metadados de sessão, reenviados
a cada 5 s (`DATA_FWD_PROTO_META_RESEND_S`), 2 em 10 s.

### Uma correção honesta

A justificativa original do modo binário era que a ponte de texto **corromperia** os
frames. Medi os dois: **não reproduzi a corrupção**. Com a ponte de texto, 6009 frames em
60 s, todos com CRC válido.

A injeção de LF só dispara quando o último byte de uma notificação NUS é `0x0D`, e com
este payload isso não aconteceu na janela medida. O risco é **estrutural e dependente do
dado** — outro sensor, outra escala ou os 9 canais podem perfeitamente produzir `0x0D`
nessa posição. O fragmento continua sendo o certo a usar, mas por precaução, não por falha
observada.

## O que falta

- Rodar o **Data Forwarder Host** de verdade (nunca executado aqui) e conferir o CSV que
  ele gera: `device_time_ms, <canais>, label` — precisa de conversão para o Lab, porque o
  `label` é texto e o Lab quer inteiro começando em 0
- **Fundo de escala:** o sample crava ±2 g / ±500 dps em `src/sensor/bmi270.c:85` e `:102`,
  literais. O `01_gesture_recognition` usa ±4 g / ±1000 dps. Não muda unidade, mas a ±2 g
  um gesto vigoroso satura. Alinhar exige editar o `bmi270.c`
