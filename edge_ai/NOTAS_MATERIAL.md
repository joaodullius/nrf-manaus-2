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

Medido no `05_classify_led` com o modelo de exemplo da Nordic (espera **mili-g**):

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

### 5. Janela maior que o evento · ⭐ vale um slide inteiro

Se o fenômeno dura menos que a janela de inferência, a janela **nunca contém só o
fenômeno** — e a classe correspondente praticamente não é prevista.

Caso concreto e mensurável no `05_classify_led`: a classe **Free Fall nunca aparece**,
por mais que se derrube a TAG.

O modelo tem `INPUT_WINDOW_SIZE = 50` e `INPUT_WINDOW_SHIFT = 50` — janelas de 0,5 s
**sem sobreposição**. O vetor de treino da classe mostra o que ela espera:

```c
CLASS_3_PARCEL_FREE_FALL_ACCEL_DATA[] = {36.87, 32.60, 29.46, 32.69, ...}
```

~25 a 80 mili-g **sustentados pela janela inteira**. Ou seja, 0,5 s completos em queda:

```
s = ½ · g · t² = ½ · 9,81 · 0,25 ≈ 1,23 m
```

De altura de mesa (~75 cm) a queda dura 0,39 s — nem preenche uma janela. E como as
janelas são disjuntas e não sincronizam com o movimento, mesmo 1,2 m só cai inteiro numa
janela por sorte.

**A regra:** escolha a janela pela duração do fenômeno.

| Fenômeno | Janela |
|---|---|
| gesto de ~1 s | 99 amostras a 100 Hz (o que o lab 01 usa) |
| impacto de ~50 ms | muito menor, senão dilui no resto |
| queda livre de mesa | inalcançável a 0,5 s |

**É o mesmo problema da centralização de gestos discretos** (item 13): evento curto dentro
de janela longa. Lá a solução é centralizar o sinal; aqui, seria encurtar a janela.

**Para a aula:** dá para exercitar `Idle`, `Shaking`, `Carrying` e provavelmente `Placed`
com a TAG na mão. `Free Fall`, `Impact` e `in Car` não — e explicar *por que* vale mais
que a demo funcionar.

### 6. MITM só existe no modo HID

`CONFIG_BLE_MITM_AUTH` tem `depends on BLE_MODE_HID`. Em `DATA_COLLECTION_MODE` ele **não é
selecionável**, e o `ble_nus.c` **não chama `bt_conn_set_security()`** — conecta sem parear,
sem confirmação de botão.

Ou seja: "desabilitar o MITM para a coleta" é trabalho desnecessário. Já está desligado.

### 7. No modo HID o tag para de anunciar quando conecta

`ble_hid.c` chama `start_advertising()` no init e **só de novo no `disconnected()`**. Com o
host HID conectado, nenhum outro central entra — mesmo com `CONFIG_BT_MAX_CONN=2`.

Consequência: log por BLE (`LOG_BACKEND_BLE`) é inviável no modo HID. E qualquer central é
forçado a `BT_SECURITY_L4`, sendo desconectado se falhar.

### 8. FPROTECT bloqueia a regravação

Depois do primeiro boot com MCUboot, `nrfutil device program` falha com
*"Memory access error at 0x5004e400"*. Não é cabo, não é firmware corrompido.

Saída: `nrfutil device recover` antes de gravar.

### 9. A TAG precisa estar alimentada para o DEBUG OUT redirecionar

Sem bateria CR2032 ou `VDD SWD0`, o DK **não detecta a TAG** e o debugger fica apontando
para o SoC do próprio DK. Tudo "funciona" — grava, conecta — só que no chip errado.

Diagnóstico rápido: `nrfutil device device-info` deve dizer `nRF54L15`. Se disser
`nRF54LM20B`, a TAG não está sendo vista.

⚠️ Bateria **ou** alimentação externa, nunca as duas.

### 10. `LOG_BACKEND_BLE` e `BT_NUS` colidem de UUID

Os dois registram serviços GATT distintos com os **mesmos** UUIDs (`6E400001/2/3`). Um
cliente que descobre por UUID pode se ligar ao errado.

---

## Bugs de ferramenta (reportar / contornar)

### 11. `samples/data_forwarder` não compila no Windows

```
makedirs("./" + path.dirname(saida))        zcbor.py:2793
OSError: [WinError 123] ... './C:'
```

O `CMakeLists.txt` passa caminhos absolutos; o zcbor concatena `"./"` na frente.
**Reproduzido com o sample intocado** do add-on v2.3.0. Contorno no lab 04: caminhos
relativos + `WORKING_DIRECTORY`.

**Candidato a reportar no DevZone.**

### 12. Data Forwarder Host é **GUI pura**

O README dele: *"The application is a pure GUI — there is no command-line interface."*
Não há modo headless. Se o roteiro previa automação por CLI, não vem daí.

### 13. O script de centralização da Nordic não é CLI

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
| Janela do modelo de exemplo (05) | 50 amostras (0,5 s), shift 50 — sem sobreposição |
| Queda livre para preencher 0,5 s | ≈1,23 m |
| Fundo de escala do 01 | ±4 g / ±1000 dps |
| Fundo de escala do `data_forwarder` | ±2 g / ±500 dps |
| Coleta recomendada (PoC) | 3–5 min por gesto |
| Mínimo do Lab | 2 classes, 20 amostras/classe, alvo começando em 0 |
| Tipos aceitos pelo Lab | INT8, INT16, FLOAT32 |
