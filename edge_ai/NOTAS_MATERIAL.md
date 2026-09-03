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

Medido no `04_classify_led` com o modelo de exemplo da Nordic (espera **mili-g**):

| Alimentado com | TAG parada na mesa reporta |
|---|---|
| m/s² (1 g ≈ 9,81) | `Free Fall (65%)` |
| mili-g (1 g ≈ 1000) | `Idle (98%)` |

Faz sentido: 9,8 cai no fundo da faixa conhecida (`INPUT_FEATURES_SCALE_MIN = 6.26`), e o
fundo da faixa **é** queda livre.

A unidade não estava documentada — foi preciso ler os vetores embarcados do sample
(`CLASS_0_PARCEL_IDLE_ACCEL_DATA[] = {1019.23, ...}` → mili-g).

**Slide:** o modelo tem contrato, e escala faz parte do contrato.

**Onde morde no curso:** `03_central_uart` entrega mili-unidades, `05_data_forwarder`
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

### 4b. A coleta por NUS dilata o tempo — e o detector de perdas é cego para isso · ⭐⭐ a mais grave

Medido na coleta de 2026-09-01, com o `01` em modo de coleta e a ponte do `03`:

| Classe | Taxa medida | Amostras perdidas |
|---|---|---|
| `idle` | 94,3 Hz | **0** |
| `swipe_left` | 84,5 Hz | **0** |
| `unknown` | 81,8 Hz | 46 (0,19%) |
| `swipe_right` | **76,4 Hz** | **0** |

O `imu_config.data_rate_hz` é 100. Zero amostras perdidas com ids contíguos, e ainda
assim 76 Hz. **O dado não sumiu no ar: a TAG produziu menos.**

**Por quê.** O `main.c` amostra e envia na mesma thread:

```
K_TIMER 10 ms → imu_data_ready_cb() → k_sem_give()      [ISR]
                        ↓
        main.c:154  k_sem_take(K_FOREVER)               [thread]
        main.c:156  imu_read()
        main.c:175  send_imu_data() → ble_nus_send()
```

O semáforo é criado com **limite 1** (`main.c:332`). Enquanto a thread está no envio,
o tick do timer chega, encontra o semáforo cheio e é **descartado**, sem contador e sem
log. Quanto mais movimento, pior o link, mais demora o envio, menos amostras — daí a
correlação com a classe.

**Por que o id não pega.** O `id++` do `ble_nus.c:143` incrementa por **chamada de
envio**, não por tick. Tick descartado não vira chamada, não vira id, não vira buraco.
São duas perdas diferentes e o contador só enxerga uma:

| Perda | Visível? |
|---|---|
| tick descartado (semáforo cheio) | **não** — vira só taxa menor |
| `bt_nus_send()` falha por falta de buffer | sim — buraco de id |

O README upstream atribui a perda a *"RF noise or increased distance"* e oferece o id
sequencial + `scripts/check_nus_data.py` como mitigação. Isso cobre o segundo caminho.
O primeiro — o que realmente dominou aqui — passa despercebido pelo detector da
própria Nordic.

**Por que importa.** Na inferência não há NUS e o `k_timer` roda solto a 100 Hz. Um
gesto de 1 s vira ~76 linhas no treino e ~100 na inferência: o modelo treina numa
escala de tempo e infere em outra, com fator diferente por classe. Não há parâmetro de
janela que conserte — o conserto é resampling, que exigiria saber **onde** estão os
buracos, informação que o id não carrega.

**Conserto de duas linhas**, se for para corrigir: incrementar o contador no tick, em
vez de no envio.

```c
static volatile uint32_t sample_tick;

static void imu_data_ready_cb(void)
{
    sample_tick++;              /* conta o tick, tenha ou nao consumidor */
    k_sem_give(&imu_data_ready_sem);
}
```

Não elimina a perda, mas a torna **visível**: buraco de id no lugar exato, e a grade de
100 Hz vira reconstruível. O lado do PC não muda — o `prep_dataset.py` já conta buracos.

**Slide:** o contador de perdas estava no lugar errado por uma função de distância. Um
detector que mede o sintoma errado é pior que nenhum, porque o "0 perdidas" dá
confiança no dado ruim.

---

## As que contradizem a intuição

### 5. Janela maior que o evento · ⭐ vale um slide inteiro

Se o fenômeno dura menos que a janela de inferência, a janela **nunca contém só o
fenômeno** — e a classe correspondente praticamente não é prevista.

Caso concreto e mensurável no `04_classify_led`: a classe **Free Fall nunca aparece**,
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
**Reproduzido com o sample intocado** do add-on v2.3.0. Contorno no lab 05: caminhos
relativos + `WORKING_DIRECTORY`.

**Candidato a reportar no DevZone.**

### 12. Data Forwarder Host é **GUI pura**

O README dele: *"The application is a pure GUI — there is no command-line interface."*
Não há modo headless. Se o roteiro previa automação por CLI, não vem daí.

### 13. O script de centralização da Nordic não é CLI

`nordicsemi-neuton/segment-center-signal` — você **edita constantes no fim do .py** e roda.
Cópia vendorizada em `03_central_uart/tools/segment-center-signal/` (upstream **sem
licença declarada** — ver `ORIGEM.md` da pasta). `work_axis` e `threshold_coef` são chutes
iniciais que precisam de calibração com dado real. É lento (`df.loc[i] = row` em laço).

**Correção:** eu tinha escrito aqui que ele "abre janelas do matplotlib e bloqueia".
Lendo o fonte, é o contrário e é pior: ele chama `plot_segments()` duas vezes mas **nunca
chama `plt.show()`**. Rodando como script, as figuras são criadas e descartadas em
silêncio — o aluno espera os gráficos de calibração e não vê nada. Precisa acrescentar um
`plt.show()` no fim.

**Janela ímpar perde uma linha · falha em silêncio.** O recorte é
`range(centro - int(w/2), centro + int(w/2))`: com `w=99` saem **98** linhas por segmento.
Aí os segmentos não casam mais com a janela do Lab e o alinhamento escorrega 1 linha por
gesto — a centralização inteira é desfeita sem nenhum erro aparecer. Usar valor par.

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

## Trocar o modelo — o procedimento e o que falha nele

O ato 3 do loop 1: o aluno treinou no Edge AI Lab e quer o modelo dele rodando na TAG.
Parece copiar arquivo; tem quatro armadilhas, três delas silenciosas.

### O procedimento, em quatro passos

1. Baixar o zip do Lab e copiar **toda** a pasta `nrf_edgeai_generated/` dele
2. Colar em `01_gesture_recognition/src/nrf_edgeai_generated/nrf54l15tag/<modelo>/`
3. Apontar o `CURSO_MODELO` no `CMakeLists.txt` para essa pasta
4. **Recompilar com `-p`** e gravar

### 14. Recompilar sem `-p` grava o modelo antigo · ⭐ silencioso

O `CURSO_MODELO` mora no `CMakeLists.txt`, e o CMake só relê o arquivo num build
pristine. Sem o `-p`, o build "funciona", o `west flash` grava, e a TAG continua com o
modelo anterior. Nada avisa.

É a armadilha mais provável em sala, porque acontece com quem fez tudo certo.

### 15. Como saber qual modelo está rodando · ⭐ o antídoto, vale um slide

O antídoto já existe no upstream e ninguém repara nele. Cada solução do Edge AI Lab
tem um **solution id** numérico, que aparece em três lugares:

```c
// no header gerado
#ifndef _NRF_EDGEAI_USER_MODEL_95867_H_
nrf_edgeai_t *nrf_edgeai_user_model_95867(void);
#define nrf_edgeai_user_model nrf_edgeai_user_model_95867   // alias que o main.c usa

// e no boot, ja no codigo do sample — src/main.c:145
LOG_INF("nRF Edge AI Lab Solution id: %s", nrf_edgeai_solution_id_str(p_model));
```

No RTT, no boot:

```
<inf> main: nRF Edge AI Lab Solution id: 95867
```

| id | modelo |
|---|---|
| `91278` | de fábrica, do Add-on v2.3.0 |
| `95867` | treinado no curso em 2026-09-01 |

Uma linha de log responde "gravei o certo?" sem abrir arquivo nenhum, e é a defesa
direta contra a armadilha 14. **Ensinar a olhar essa linha vale mais que ensinar o
procedimento**, porque ela também pega o aluno que copiou na pasta errada.

⚠️ **Com uma condição, descoberta no hardware em 2026-09-01:** no build padrão essa
linha **não aparece**. Os buffers de log vêm em 1024 bytes, a rajada de boot estoura os
dois, e tudo que o `main()` loga no início some em silêncio — inclusive o Solution id
(é a armadilha 3, batendo de novo). O antídoto precisa de antídoto: o `prj.conf` da
TAG agora traz `CONFIG_LOG_BUFFER_SIZE=4096` e `CONFIG_SEGGER_RTT_BUFFER_SIZE_UP=4096`
por padrão.

**Slide:** o mecanismo de verificação existia no código desde sempre e era inútil por
falta de 3 kB de buffer. Ninguém percebe, porque a ausência de uma linha de log não
parece um defeito.

O alias `#define nrf_edgeai_user_model nrf_edgeai_user_model_<id>` é o que faz o
`main.c` compilar sem saber o id — e é também por isso que **misturar o `.h` de um
treino com o `.c` de outro dá erro de link**. Essa é a única das quatro que falha alto.

### 16. A pasta gerada tem 5 arquivos, não 2 · silencioso

A doc da Nordic manda *"replace the `nrf_edgeai_generated` folder"*, e está certa. O que
o zip entrega:

```
nrf_edgeai_user_model.c      15.120 B
nrf_edgeai_user_model.h       1.051 B
nrf_edgeai_user_types.h         585 B   <- o esquecido
prj_example.conf                 94 B
README.md                        66 B
```

O `nrf_edgeai_user_types.h` carrega os typedefs do modelo:

```c
typedef int16_t nrf_user_input_t;
typedef flt32_t nrf_user_output_t;
```

Se o aluno escolher outro **Data Type** ou **Output format** no Lab e mantiver o
types.h antigo, **compila e infere errado**. No treino de 2026-09-01 os tipos vieram
iguais aos de fábrica, então o erro não se manifestou — o que é a pior forma de
aprender que ele existe.

O `prj_example.conf` é inerte dentro de `src/` (o `APPLICATION_CONFIG_DIR` aponta para
`configuration/<board>`). Ele sugere `CONFIG_NEWLIB_LIBC=y`, que **não** se deve aplicar:
a app roda com picolibc e funciona.

### 17. Trocar as classes obriga a editar C · silencioso

O modelo devolve um índice. Quem dá nome, cor e tecla a ele é o firmware, em três
lugares: o `enum class_label_t` (`inference_postprocessing.h`), a tabela de nomes e a
de limiares (`inference_postprocessing.c:41` e `:61`), e o mapa gesto→tecla no `main.c`.

Treinar com outro conjunto de classes e não mexer neles não dá erro: o gesto sai com o
nome errado e aperta a tecla errada.

**O truque para não precisar:** treinar com um subconjunto **contíguo começando em 0**
da ordem do enum. Foi o que fizemos — `idle`, `unknown`, `swipe_right`, `swipe_left`
são os rótulos 0-3 — e por isso o modelo do curso entrou sem tocar em uma linha de C.
O `CLASSES` do `prep_dataset.py:50` é uma cópia dessa ordem exatamente para isso.

### O que fica de invariante

Qualquer modelo novo tem que manter três coisas, ou a app quebra:

| Invariante | Onde quebra |
|---|---|
| **6 canais** de entrada | `main.c:42` alimenta 6, cravado; outro número desalinha a janela, em silêncio |
| **Output float32** | `main.c:478` lê `probabilities.p_f32`; saída quantizada vira lixo |
| **Cortex-M33 · Neuton** | LiteRT/Axon não roda na nRF54L15 |

A **janela** pode mudar à vontade: vem do modelo (`INPUT_WINDOW_SIZE`) e a app lê de lá.

---

## Quanto o modelo ocupa

Medido com `rom_report` / `ram_report` do Zephyr, que atribui por arquivo no binario
linkado — não pelo tamanho do `.obj`, que engana com LTO ligado.

```bash
ninja -C <build>/<imagem> rom_report     # gera rom.json + arvore na tela
ninja -C <build>/<imagem> ram_report
```

**O modelo em si** (o `.c` gerado pelo Edge AI Lab):

| Lab | Modelo | Flash | RAM |
|---|---|---:|---:|
| `01_gesture_recognition` | 6 entradas · janela 99 · 8 classes | **3.336 B** | **1.818 B** |
| `04_classify_led` | 1 entrada · janela 50 · 7 classes | **5.794 B** | **760 B** |

**O runtime** (API pública `nrf_edgeai_*`): ~1,1 kB no 01, ~1,0 kB no 04. Praticamente
constante — o runtime é fino, o custo está no modelo.

### A inversão · ⭐ vale um slide

O modelo do 01 tem **6 entradas e janela de 99**, mas ocupa **menos flash** que o do 04,
que tem **1 entrada e janela de 50**. E gasta **mais que o dobro de RAM**. Separando as
duas coisas, faz sentido:

| | O que determina | Dá para prever antes de treinar? |
|---|---|---|
| **RAM** | a janela de entrada: `janela × canais` | **sim** — 99×6 contra 50×1 é ~12× mais dado acumulado |
| **Flash** | a complexidade que o treino encontrou | **não** — só se sabe depois |

Mensagem para o Ato 3, quando o aluno escolhe janela e número de gestos: **RAM você
calcula, flash você descobre.**

### O denominador engana

| | Imagem | Modelo | % |
|---|---:|---:|---:|
| 01 flash | 320.452 B | 3.336 B | **1,0%** |
| 01 RAM | 59.313 B | 1.818 B | 3,1% |
| 04 flash | 87.116 B | 5.794 B | **6,7%** |
| 04 RAM | 19.413 B | 760 B | 3,9% |

O modelo é **~1% do firmware de gestos**. Todo o resto é BLE, MCUboot, HID e criptografia.
No 04, sem nada disso, o mesmo tipo de modelo salta para 6,7% — parece dez vezes maior só
porque o denominador mudou.

### Cuidado ao medir: nem todo símbolo ofuscado é Edge AI

O `rom_report` joga o que não tem caminho de debug num bucket `(no paths)`. No 01 esse
bucket tem **682 símbolos `sym_*` somando 45,7 kB**, que é tentador atribuir ao runtime
proprietário do Neuton.

**Não é.** O 04 tem Edge AI e **zero** símbolos `sym_*`. A diferença entre os dois é BLE e
`nrf_security` — ou seja, os 45,7 kB são **criptografia**. Somar isso ao Edge AI inflaria o
número em 14×.

---

## Loop 2 — o que a bancada ensinou (2026-09-02/03)

Caso: velocidade de um ventilador portátil por vibração, 4 classes, coletado com o
`data_forwarder` + Data Forwarder Host, treinado no Lab com features de frequência,
rodando no `04_classify_led`. Tudo validado; o detalhe está nos READMEs do 05 e do 04.

### 18. A taxa de inferência é parte do contrato · ⭐⭐ silenciosa

`k_msleep(10)` no laço do 04 dava 96,9 Hz (a leitura SPI soma ao sleep): janela de 128
em 1321 ms em vez de 1280. Com FFT, 3 % de taxa é o espectro inteiro deslocado — uma
velocidade acima da real, com 99 % de confiança. Corrigido com k_timer + semáforo, igual
ao forwarder; o boot agora imprime o ritmo das três primeiras janelas e avisa se sair de
2 %. Vale um slide ao lado da armadilha de escala: as duas têm o mesmo perfil.

### 19. O domínio da coleta é o domínio do modelo · ⭐

Ventilador no carregador gira mais devagar que na bateria. Modelo treinado no carregador
→ `vel1` vira `vel2` na bateria. Regravado tudo na bateria. Mesma família da lição da
fixação: muda só a variável que se quer classificar, e colete onde o modelo vai rodar.

### 20. FLOAT32 e micro-unidades: o caminho da Nordic, sem conversão

O CSV do Host sobe no Lab como está (micro-unidades SI, float) e a app alimenta com
`sensor_value_to_micro()`. Zero fatores. INT16 exigiria dividir por 1000 e não cabia
para as colunas do BME688. O loop 2 não precisa casar com o loop 1.

### 21. Remover colunas é no Lab, não no firmware

O sample manda 9 canais; `temp,hum,pres` saem em *Remove variables* no upload. O Host é
validado a 500 frames/s × 10 canais — banda não é argumento para desligar o BME688.

### 22. Features para vibração: frequência e energia; média é orientação

Marcar amplitude spectrum, dominant frequencies, espectrais, RMS, std, mean-crossing
rate. Não marcar mean (gravidade = orientação da TAG, o `acc_mean` do loop 1 de novo).
Feature selection ligado: o Lab ficou com **45 de 495** candidatas. O que o modelo usa
está no `.c` gerado (`timedomain_features_[]`, `freqdomain_features_[]`,
`FEATURES_EXTRACTION_MASK[]`) — não precisa voltar ao Lab para saber.

### 23. Janela 128 é obrigatória com FFT, e "Time Interval" engana

Frequency features exigem potência de 2 entre 128 e 2048. Em *Time Interval*, 128 **ms**
a 100 Hz vira 12 amostras e o Lab recusa; usar *Number of Rows*.

### 24. Três coisas de bancada que parecem falha e não são

- **RTT velho após regravar:** o logger acha o bloco RTT do firmware anterior na RAM e
  mostra um boot que não é o seu. Ler de novo.
- **`Sensor init failed (-19)` ao reencaixar a TAG:** os sensores não recebem reset do
  SoC; tirar da DEBUG OUT, tirar bateria, 5 s, encaixar.
- **Python da Store esconde o log do Host** em `%LOCALAPPDATA%/Packages/...`.

### 25. `proto_send_samples()` retorna 0 sem conexão

Ele só enfileira; o envio falha depois numa work queue (`-22`, `nus_mtu == 0`). Para um
LED de "transmitindo" o estado tem de vir de um `bt_conn_cb`, não do retorno.

## Números que valem decorar

| | |
|---|---|
| Taxa de amostragem do IMU (01 e 04) | 100 Hz |
| Janela do modelo de gestos | 99 amostras (≈1 s) |
| Sliding shift para inferência | 33 (3 inferências/s) |
| Janela do modelo de exemplo (04) | 50 amostras (0,5 s), shift 50 — sem sobreposição |
| Queda livre para preencher 0,5 s | ≈1,23 m |
| Fundo de escala do 01 | ±4 g / ±1000 dps |
| Fundo de escala do `data_forwarder` | ±2 g / ±500 dps |
| Coleta recomendada (PoC) | 3–5 min por gesto |
| Mínimo do Lab | 2 classes, 20 amostras/classe, alvo começando em 0 |
| Tipos aceitos pelo Lab | INT8, INT16, FLOAT32 |
| Modelo de gestos (01) | 3.336 B flash · 1.818 B RAM — 1,0% da imagem |
| Modelo do 04 | 5.794 B flash · 760 B RAM — 6,7% da imagem |
| Janela do modelo do ventilador (04) | 128 amostras (1,28 s), shift de inferência 128 |
| Modelo do ventilador | 39 coeficientes · 45 de 495 features · 11,7 kB NVM (8,8 kB é a FFT) |
| Ritmo aceito pelo 04 | janela de 1280 ms ± 2 % — fora disso, `<wrn>` no boot |
| Runtime `nrf_edgeai_*` | ~1 kB, praticamente constante |
