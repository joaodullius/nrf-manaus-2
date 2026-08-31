# Notas para o material — armadilhas do módulo Edge AI

Coisas que **só apareceram no hardware** durante o preparo. Cada uma custou tempo de
depuração; todas viram slide, aviso em roteiro ou nota de rodapé.

Critério para estar aqui: **falha em silêncio** ou **contradiz a intuição**. Erro que
aparece no build não entra — o aluno resolve sozinho.

---

## As que falham em silêncio

### 1. Escala da entrada do modelo · ⭐ a mais importante

O modelo espera a escala do **dataset com que foi treinado**. Alimentar em outra escala
não dá erro: compila, roda, e classifica errado.

Medido no `05_gesture_led` com o modelo de exemplo da Nordic (espera **mili-g**):

| Alimentado com | TAG parada na mesa reporta |
|---|---|
| m/s² (1 g ≈ 9,81) | `Free Fall (65%)` |
| mili-g (1 g ≈ 1000) | `Idle (98%)` |

Faz sentido: 9,8 cai no fundo da faixa conhecida (`INPUT_FEATURES_SCALE_MIN = 6.26`), e o
fundo da faixa **é** queda livre.

A unidade não estava documentada — foi preciso ler os vetores embarcados do sample
(`CLASS_0_PARCEL_IDLE_ACCEL_DATA[] = {1019.23, ...}` → mili-g).

**Slide:** o modelo tem contrato, e escala faz parte do contrato.

**Onde morde no curso:** `03_central_uart` entrega mili-unidades, `04_data_forwarder`
entrega micro (fator 1000). O `01_gesture_recognition` alimenta `imu_data.raw`, que é mili.

### 2. `NCS_SAMPLES_DEFAULTS` mata o log na TAG

`CONFIG_NCS_SAMPLES_DEFAULTS=y` puxa `CONFIG_LOG_MODE_MINIMAL=y`. Em modo mínimo o log
**não tem backends** — vai para o console, e a TAG não tem console.

Sintoma: silêncio absoluto no RTT, com o firmware rodando normalmente. Chega a parecer
crash. Correção: `CONFIG_LOG_MODE_DEFERRED=y`.

### 3. Buffers de log: são **dois**, não um

`CONFIG_LOG_BUFFER_SIZE` e `CONFIG_SEGGER_RTT_BUFFER_SIZE_UP`, ambos 1024 por padrão. A
rajada de boot estoura os dois.

Sintoma: o log corta no meio de uma palavra (`<inf> bt_hci_core: HW Platform: Nordi`) e
tudo depois some — inclusive o `Identity:` com o endereço BLE do tag, que o aluno precisa.

Mexer só no do RTT não resolve: no modo deferred a mensagem morre antes, no ring buffer do
subsistema de log. Os dois para 4096.

> Já era conhecido no `C:\work\nrf-tag` (`tag/01-motion-adv/prj.conf`) — o instrutor tinha
> batido nisso antes. Vale como exemplo de que o problema recorre.

### 4. Tabela de cores maior que o número de classes

Array dimensionado por macro: **menos** entradas que classes compila em silêncio (C
preenche com zero → LED apagado + `nome = NULL` no `%s`). **Mais** entradas já falhava no
build. Assimetria corrigida com `BUILD_ASSERT`.

**Slide:** inicialização parcial de array em C é silenciosa.

---

## As que contradizem a intuição

### 5. MITM só existe no modo HID

`CONFIG_BLE_MITM_AUTH` tem `depends on BLE_MODE_HID`. Em `DATA_COLLECTION_MODE` ele **não é
selecionável**, e o `ble_nus.c` **não chama `bt_conn_set_security()`** — conecta sem parear,
sem confirmação de botão.

Ou seja: "desabilitar o MITM para a coleta" é trabalho desnecessário. Já está desligado.

### 6. No modo HID o tag para de anunciar quando conecta

`ble_hid.c` chama `start_advertising()` no init e **só de novo no `disconnected()`**. Com o
host HID conectado, nenhum outro central entra — mesmo com `CONFIG_BT_MAX_CONN=2`.

Consequência: log por BLE (`LOG_BACKEND_BLE`) é inviável no modo HID. E qualquer central é
forçado a `BT_SECURITY_L4`, sendo desconectado se falhar.

### 7. FPROTECT bloqueia a regravação

Depois do primeiro boot com MCUboot, `nrfutil device program` falha com
*"Memory access error at 0x5004e400"*. Não é cabo, não é firmware corrompido.

Saída: `nrfutil device recover` antes de gravar.

### 8. A TAG precisa estar alimentada para o DEBUG OUT redirecionar

Sem bateria CR2032 ou `VDD SWD0`, o DK **não detecta a TAG** e o debugger fica apontando
para o SoC do próprio DK. Tudo "funciona" — grava, conecta — só que no chip errado.

Diagnóstico rápido: `nrfutil device device-info` deve dizer `nRF54L15`. Se disser
`nRF54LM20B`, a TAG não está sendo vista.

⚠️ Bateria **ou** alimentação externa, nunca as duas.

### 9. `LOG_BACKEND_BLE` e `BT_NUS` colidem de UUID

Os dois registram serviços GATT distintos com os **mesmos** UUIDs (`6E400001/2/3`). Um
cliente que descobre por UUID pode se ligar ao errado.

---

## Bugs de ferramenta (reportar / contornar)

### 10. `samples/data_forwarder` não compila no Windows

```
makedirs("./" + path.dirname(saida))        zcbor.py:2793
OSError: [WinError 123] ... './C:'
```

O `CMakeLists.txt` passa caminhos absolutos; o zcbor concatena `"./"` na frente.
**Reproduzido com o sample intocado** do add-on v2.3.0. Contorno no lab 04: caminhos
relativos + `WORKING_DIRECTORY`.

**Candidato a reportar no DevZone.**

### 11. Data Forwarder Host é **GUI pura**

O README dele: *"The application is a pure GUI — there is no command-line interface."*
Não há modo headless. Se o roteiro previa automação por CLI, não vem daí.

### 12. O script de centralização da Nordic não é CLI

`nordicsemi-neuton/segment-center-signal` — você **edita constantes no fim do .py** e roda.
Abre janelas do matplotlib e bloqueia. `work_axis` e `threshold_coef` são chutes iniciais
que precisam de calibração com dado real. É lento (`df.loc[i] = row` em laço).

---

## Correção de algo que eu afirmei errado

**A ponte de texto do `central_uart` não corrompeu os frames binários.** Eu previ que a
injeção de LF (quando o pedaço termina em `\r`) quebraria o CBOR/COBS. Medi os dois modos:

| Ponte | Frames | CRC ok |
|---|---|---|
| binária | 1011 em 10 s | 100% |
| texto | 6009 em 60 s | 100% |

O risco é **estrutural e dependente do dado** — só dispara quando o último byte de uma
notificação é `0x0D`, o que não aconteceu com este payload. O `binary_bridge.conf` continua
sendo o certo a usar, mas por precaução, não por falha observada.

**Nota de método para o curso:** vale mostrar isso aos alunos. Uma previsão plausível a
partir da leitura do código não substitui a medição.

---

## Números que valem decorar

| | |
|---|---|
| Taxa de amostragem do IMU (01 e 04) | 100 Hz |
| Janela do modelo de gestos | 99 amostras (≈1 s) |
| Sliding shift para inferência | 33 (3 inferências/s) |
| Fundo de escala do 01 | ±4 g / ±1000 dps |
| Fundo de escala do `data_forwarder` | ±2 g / ±500 dps |
| Coleta recomendada (PoC) | 3–5 min por gesto |
| Mínimo do Lab | 2 classes, 20 amostras/classe, alvo começando em 0 |
| Tipos aceitos pelo Lab | INT8, INT16, FLOAT32 |
