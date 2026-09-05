# Channel Sounding — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar em `comms/` os cinco labs de Channel Sounding do treinamento (reflector RAS no TAG, initiator RAS no LM20-DK, par IPT, roteiro de segurança, e IQ→PC com IFFT em NumPy + MUSIC), prontos para o aluno compilar do repo sem download externo.

**Architecture:** Cada firmware é uma cópia freestanding de um sample do NCS v3.4.0 (`ras_reflector`, `ras_initiator`, `ipt_reflector`, `ipt_initiator`) com cabeçalho `ORIGEM:` e divergências do curso marcadas por comentário, no padrão de `edge_ai/03_central_uart`. Os initiators ganham filtro por endereço BLE do TAG (Kconfig `LAB_TAG_ADDR_*` + `meu_tag.conf`). O lab 5 despeja o IQ por canal em CSV na serial e o processa no PC com um port em NumPy do `cs_de.c` da Nordic e o `cs_music.py` do projeto `skig/waves` (MIT), vendorizado.

**Tech Stack:** nRF Connect SDK v3.4.0 (`C:/ncs/v3.4.0`), west + sysbuild via `nrfutil sdk-manager toolchain launch`, SoftDevice Controller com CS, biblioteca `cs_de`, Python 3.11 (numpy, pyserial, pytest).

**Spec:** `docs/superpowers/specs/2026-09-05-channel-sounding-design.md`

## Global Constraints

- SDK alvo: **nRF Connect SDK v3.4.0** em `C:/ncs/v3.4.0`. Nunca copiar de outra versão.
- Board targets fixos: TAG = `nrf54l15tag/nrf54l15/cpuapp`; DK = `nrf54lm20dk/nrf54lm20b/cpuapp` (variante **B**).
- Build sempre com `--sysbuild`, rodando de dentro do workspace `C:/ncs/v3.4.0`, pelo toolchain launcher:
  `nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b <board> --sysbuild -d <build_dir> <app_dir> [-- -DEXTRA_CONF_FILE=<frag>]`
  (é a mesma invocação de `edge_ai/hex/build_all.py`, validada na bancada). Caminhos com `/`.
- Diretórios de build: `build_tag` para o TAG, `build_lm20` para a DK (já ignorados pelo `.gitignore` raiz via `build*/`).
- Todo arquivo copiado do SDK leva no topo o bloco `ORIGEM:` no formato exato de `edge_ai/03_central_uart/src/main.c` (SDK, Upstream, Local, Copiado, comando `diff`, lista de DIVERGENCIA DO CURSO). Data de cópia: a data real do dia da execução, formato `AAAA-MM-DD`.
- Toda alteração no código copiado é marcada com comentário começando por `ALTERADO PELO CURSO (nrf-manaus-2)`. Nunca alterar em silêncio.
- Cada pasta de lab tem `LICENSE` = cópia byte a byte de `edge_ai/03_central_uart/LICENSE` (Nordic 5-Clause).
- Código de terceiros não-Nordic (waves) entra com o `LICENSE` original ao lado e um `ORIGEM.md` no formato de `edge_ai/03_central_uart/tools/segment-center-signal/ORIGEM.md`.
- READMEs descrevem **o estado final que o aluno recebe** — regras, comandos, pegadinhas, fontes. Sem histórico de decisões. Em português, sem acentos nos comentários de código C/Kconfig (padrão do repo), com acentos no Markdown.
- Símbolos Kconfig do filtro: exatamente `LAB_TAG_ADDR_VALUE` e `LAB_TAG_ADDR_TYPE`, no `menu "Lab: filtro do tag (nrf-manaus-2)"`.
- `meu_tag.conf` é rastreado no git **com o endereço vazio**; nunca commitar um endereço real.
- Mensagens de commit em português, no formato `<pasta do lab>: <o que mudou>`, terminando com:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
  ```
- Sem DFU/OTA, sem MCUboot, sem lab de step modes (fora de escopo pela spec).

---

## Estrutura de arquivos

```
comms/
  README.md                                   (modificar: tabela de labs + fontes)
  channel_sounding_reflector/                 Lab 1 — ras_reflector no TAG
    CMakeLists.txt  prj.conf  Kconfig.sysbuild  LICENSE  README.md
    src/main.c                                (cópia + ORIGEM, sem divergência)
    boards/nrf54l15tag_nrf54l15_cpuapp.conf   (RTT + buffers de log — curso)
    android_ranging.conf                      (cópia do SDK)
    demo.conf  s26.conf                       (curso — só para a demo do instrutor)
  channel_sounding_initiator/                 Lab 2 — ras_initiator no LM20-DK
    CMakeLists.txt  prj.conf  Kconfig  Kconfig.sysbuild  LICENSE  README.md
    meu_tag.conf  .gitignore
    src/main.c                                (cópia + filtro por endereço + intervalo)
    rtt_only.conf  pbr_only.conf              (variação opcional do README)
  channel_sounding_ipt_reflector/             Lab 3a — ipt_reflector no TAG
    CMakeLists.txt  prj.conf  Kconfig.sysbuild  LICENSE  README.md
    src/main.c  boards/nrf54l15tag_nrf54l15_cpuapp.conf
  channel_sounding_ipt_initiator/             Lab 3b — ipt_initiator no LM20-DK
    CMakeLists.txt  prj.conf  Kconfig  Kconfig.sysbuild  LICENSE  README.md
    meu_tag.conf  .gitignore  src/main.c      (cópia + filtro por endereço)
  channel_sounding_secure/                    Lab 4 — só roteiro
    README.md
  channel_sounding_iq_music/                  Lab 5 — IQ → PC
    CMakeLists.txt  prj.conf  Kconfig  Kconfig.sysbuild  LICENSE  README.md
    meu_tag.conf  .gitignore
    src/main.c                                (lab 2 + despejo CSV)
    tools/
      requirements.txt
      cs_de_numpy.py                          (port do cs_de.c — curso)
      cs_capture.py                           (serial → CSV — curso)
      cs_compare.py                           (CSV → tabela de estimadores — curso)
      music/cs_music.py  music/LICENSE  music/ORIGEM.md   (vendorizado do waves)
      tests/test_cs_de_numpy.py  tests/test_cs_capture.py  tests/test_music_adapter.py
PREREQUISITOS.md                              (modificar: seção comms)
```

Responsabilidades: cada `src/main.c` é o sample da Nordic com o mínimo de divergência; `cs_de_numpy.py` reproduz o firmware (sem MUSIC); `cs_music.py` é intocado, e o adaptador de entrada fica em `cs_compare.py`; `cs_capture.py` só grava, não calcula.

---

### Task 1: Lab 1 — reflector RAS no TAG, com RTT

**Files:**
- Create: `comms/channel_sounding_reflector/CMakeLists.txt`, `prj.conf`, `Kconfig.sysbuild`, `LICENSE`, `README.md`, `src/main.c`, `boards/nrf54l15tag_nrf54l15_cpuapp.conf`, `android_ranging.conf`

**Interfaces:**
- Produces: firmware que anuncia com `CONFIG_BT_DEVICE_NAME="Nordic CS Reflector"` (default do SDK) e o UUID do Ranging Service; log por RTT. Consumido pelos labs 2 e 5 (initiators RAS) e pela demo (Task 2).

- [ ] **Step 1: Copiar o sample e a licença**

```bash
cd /c/work/nrf-manaus-2
mkdir -p comms/channel_sounding_reflector/src comms/channel_sounding_reflector/boards
S=/c/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_reflector
cp $S/CMakeLists.txt $S/prj.conf $S/Kconfig.sysbuild $S/android_ranging.conf comms/channel_sounding_reflector/
cp $S/src/main.c comms/channel_sounding_reflector/src/main.c
cp edge_ai/03_central_uart/LICENSE comms/channel_sounding_reflector/LICENSE
```

- [ ] **Step 2: Cabeçalho `ORIGEM:` em `src/main.c` e `prj.conf`**

Inserir no topo de `src/main.c`, antes do bloco de copyright da Nordic (trocar `AAAA-MM-DD` pela data real):

```c
/*
 * ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
 *   SDK     : nRF Connect SDK v3.4.0
 *   Upstream: nrf/samples/bluetooth/channel_sounding/ras_reflector/src/main.c
 *   Local   : C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_reflector/src/main.c
 *   Copiado : AAAA-MM-DD — curso nrf-manaus-2, modulo comms/channel_sounding_reflector
 *
 * Para conferir se divergiu do SDK:
 *   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_reflector/src/main.c
 *
 * DIVERGENCIA DO CURSO: nenhuma. O reflector roda como a Nordic entregou.
 *   O que o curso acrescenta esta fora deste arquivo: boards/nrf54l15tag_nrf54l15_cpuapp.conf
 *   (log por RTT, porque o TAG nao tem UART) e os fragmentos demo.conf / s26.conf.
 */
```

Inserir no topo de `prj.conf`:

```
#
# ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
#   SDK     : nRF Connect SDK v3.4.0
#   Upstream: nrf/samples/bluetooth/channel_sounding/ras_reflector/prj.conf
#   Local   : C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_reflector/prj.conf
#   Copiado : AAAA-MM-DD — curso nrf-manaus-2, modulo comms/channel_sounding_reflector
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_reflector/prj.conf
#
# DIVERGENCIA DO CURSO: nenhuma. RTT e buffers de log ficam em
#   boards/nrf54l15tag_nrf54l15_cpuapp.conf, aplicado automaticamente para o TAG.
#
```

Inserir no topo de `android_ranging.conf` o mesmo bloco, com `Upstream: .../ras_reflector/android_ranging.conf` e `DIVERGENCIA DO CURSO: nenhuma.`

- [ ] **Step 3: Fragmento de board com RTT (a única saída de log do TAG)**

Criar `comms/channel_sounding_reflector/boards/nrf54l15tag_nrf54l15_cpuapp.conf`:

```
#
# Fragmento do curso (nrf-manaus-2) — aplicado automaticamente pelo Zephyr
# quando o board target e nrf54l15tag/nrf54l15/cpuapp.
#
# O nRF54L15-TAG nao tem UART: o board nao declara zephyr,console nem
# zephyr,shell-uart em nenhum "chosen", e "uart" nao esta na lista supported
# do nrf54l15tag_nrf54l15_cpuapp.yaml. O CONFIG_NCS_SAMPLES_DEFAULTS do sample
# so faz "imply LOG" e nao escolhe backend — sem este arquivo o reflector
# compila limpo e nao imprime NADA em lugar nenhum.
#
# RTT so existe com o TAG encaixado no DEBUG OUT da DK. Na bateria nao ha log:
# a evidencia de vida e o LED e a saida do initiator.
#
CONFIG_USE_SEGGER_RTT=y
CONFIG_LOG_BACKEND_RTT=y
CONFIG_LOG_BACKEND_UART=n
CONFIG_CONSOLE=y
CONFIG_RTT_CONSOLE=y

# Os dois buffers vem em 1024 e a rajada de boot estoura ambos — a linha
# "Identity:" e as de "CS ... enabled" somem. Mesma correcao do edge_ai/03_central_uart.
CONFIG_LOG_BUFFER_SIZE=4096
CONFIG_SEGGER_RTT_BUFFER_SIZE_UP=4096
```

- [ ] **Step 4: Compilar para o TAG**

```bash
cd /c/ncs/v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d /c/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag /c/work/nrf-manaus-2/comms/channel_sounding_reflector
```

Expected: build termina sem erro; existe `build_tag/channel_sounding_reflector/zephyr/zephyr.hex` (ou `build_tag/merged.hex`).

- [ ] **Step 5: Conferir que o RTT entrou no build**

```bash
grep -E "^CONFIG_(LOG_BACKEND_RTT|LOG_BACKEND_UART|USE_SEGGER_RTT|BT_CHANNEL_SOUNDING|BT_RAS_RRSP)=" /c/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag/channel_sounding_reflector/zephyr/.config
```

Expected (exatamente estas linhas, em qualquer ordem):
```
CONFIG_USE_SEGGER_RTT=y
CONFIG_LOG_BACKEND_RTT=y
CONFIG_BT_CHANNEL_SOUNDING=y
CONFIG_BT_RAS_RRSP=y
```
e **nenhuma** linha `CONFIG_LOG_BACKEND_UART=y`.

- [ ] **Step 6: Bancada — gravar e ler o RTT**

TAG encaixado no `DEBUG OUT` da nRF54LM20-DK. Conferir antes que o debugger vê o TAG (`nrfutil device device-info` deve mostrar nRF54L15, não nRF54LM20).

```bash
cd /c/ncs/v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d /c/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag
"/c/Program Files/SEGGER/JLink_V924a/JLinkRTTLogger.exe" -USB 1051898754 -Device NRF54L15_M33 -If SWD -Speed 4000 -RTTChannel 0 /c/Users/joaod/AppData/Local/Temp/claude/rtt_reflector.log
```

Expected no log (após reset): o banner do Zephyr, a linha `<inf> bt_hci_core: Identity: XX:XX:XX:XX:XX:XX (random)` e a mensagem de início do sample. Se o log mostrar conteúdo de um firmware anterior, `nrfutil device reset` e ler de novo (o bloco RTT velho pode ficar na RAM).

- [ ] **Step 7: README do lab**

Criar `comms/channel_sounding_reflector/README.md`:

```markdown
# Channel Sounding · Lab 1 — Reflector no nRF54L15-TAG

O lado simples do Channel Sounding: o TAG anuncia o **Ranging Service**, aceita a
conexão de um initiator, participa dos procedimentos de CS e expõe as suas medidas
cruas por GATT. Ele **não calcula distância** — quem calcula é o initiator (lab 2).

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ras_reflector` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE).
> `src/main.c` e `prj.conf` são idênticos ao SDK; o que o curso acrescenta está em
> `boards/` e nos fragmentos de demo.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54L15-TAG** | roda este firmware; reflector, alimentado pela CR2032 |
| **nRF54LM20-DK** | só grava o TAG (ele encaixa no `DEBUG OUT`) e lê o RTT |

## Gravar

O TAG fica encaixado no `DEBUG OUT` da DK. Enquanto ele está lá, **o debugger da DK
aponta para o TAG, não para o SoC da DK** — é isso que permite gravá-lo, e é isso
que faz "gravar a DK" nessa hora gravar o TAG por engano. Confira com
`nrfutil device device-info`: tem que aparecer nRF54L15.

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag C:/work/nrf-manaus-2/comms/channel_sounding_reflector
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag
```

No VS Code: build configuration com board target `nrf54l15tag/nrf54l15/cpuapp`, sem
fragmentos extras.

## Ler o log — só por RTT, só no `DEBUG OUT`

O TAG **não tem UART**. O board não declara console nenhum, e o sample da Nordic não
escolhe backend de log — compila limpo e fica mudo. O
[`boards/nrf54l15tag_nrf54l15_cpuapp.conf`](boards/nrf54l15tag_nrf54l15_cpuapp.conf)
liga o RTT e aumenta os dois buffers de log (senão a rajada de boot corta o `Identity:`).

```
"C:\Program Files\SEGGER\JLink_V924a\JLinkRTTLogger.exe" -Device NRF54L15_M33 -If SWD -Speed 4000 -RTTChannel 0 rtt.log
```

O que esperar, com um initiator conectando (texto do próprio sample):

```
I: Connected to xx.xx.xx.xx.xx.xx (random) (err 0x00)
I: CS capability exchange completed.
I: CS config creation complete. ID: 0
I: CS security enabled.
I: CS procedures enabled.
```

Assim que o TAG sai do `DEBUG OUT` para a bateria, **o log acaba**. A partir daí a
evidência de vida é o LED 1 (aceso = conectado) e a saída do initiator. É a diferença
entre bancada e campo — e é assim que um reflector de verdade vive.

## O endereço do seu TAG

É o mesmo do Edge AI: o endereço BLE estático vem do próprio chip e não muda com o
firmware. Reaproveite o `meu_tag.conf` do `edge_ai/03_central_uart` nos labs 2, 3 e 5.
Se precisar reler, ele está na linha `Identity:` do boot, no RTT.

## Pegadinhas

- **RTT mostra log velho.** Logo depois de regravar, o bloco RTT do firmware anterior
  pode continuar na RAM. `nrfutil device reset` e ler de novo.
- **Gravou a DK em vez do TAG (ou vice-versa).** Com o TAG encaixado, `west flash`
  grava o TAG; sem ele, grava a DK. Sempre conferir `device-info` antes.
- **Um initiator antigo esquecido numa DK rouba o TAG** (só aceita 1 conexão).
  `nrfutil device recover` na DK esquecida.

## Demo do instrutor com smartphone

Ver [`demo.conf`](demo.conf) e [`s26.conf`](s26.conf). Não faz parte do lab do aluno.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ras_reflector`
- Nordic, *Bluetooth: Channel Sounding Reflector with Ranging Responder* (doc do sample)
- Nordic DevZone, *Introducing the nRF54L15 Tag* — o TAG como reflector e o build para `nrf54l15tag/nrf54l15/cpuapp`
```

- [ ] **Step 8: Commit**

```bash
cd /c/work/nrf-manaus-2
git add comms/channel_sounding_reflector
git commit -F - <<'EOF'
channel_sounding_reflector: reflector RAS no TAG, copia do SDK v3.4.0

Copia do ras_reflector com cabecalho ORIGEM, sem divergencia no codigo.
O TAG nao tem UART e o sample nao escolhe backend de log: o fragmento
boards/nrf54l15tag_nrf54l15_cpuapp.conf liga o RTT e sobe os buffers.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---

### Task 2: Lab 1 — fragmentos da demo com o Galaxy S26

**Files:**
- Create: `comms/channel_sounding_reflector/demo.conf`, `comms/channel_sounding_reflector/s26.conf`
- Modify: `comms/channel_sounding_reflector/README.md` (seção "Demo do instrutor")

**Interfaces:**
- Consumes: o build da Task 1 e o `android_ranging.conf` copiado do SDK.
- Produces: build de demo com nome `"CS Reflector DEMO"` e `CONFIG_BT_CTLR_SDC_MAX_CONN_EVENT_LEN_DEFAULT=1250`.

- [ ] **Step 1: Criar `demo.conf`**

```
#
# Fragmento do curso (nrf-manaus-2) — demo do instrutor com smartphone.
# NAO faz parte do lab do aluno.
#
# Seis TAGs na sala anunciam "Nordic CS Reflector"; o da demo precisa de outro
# nome para ser achado na lista do app.
#
CONFIG_BT_DEVICE_NAME="CS Reflector DEMO"
```

- [ ] **Step 2: Criar `s26.conf`**

```
#
# Fragmento do curso (nrf-manaus-2) — ajuste para o Samsung Galaxy S26.
# NAO faz parte do lab do aluno. Use junto com android_ranging.conf e demo.conf.
#
# Com o ras_reflector pristino o S26 falha no LE CS Procedure Enable com 0x1E
# (INVALID_LMP_OR_LL_PARAMETERS). O telefone negocia os interludios maximos
# (T_IP1 = T_IP2 = 145 us, T_FCS = 150 us), o subevent passa de ~23 ms, e com o
# evento ACL padrao de 7500 us dentro do intervalo de 30 ms do Android o proprio
# SoftDevice Controller rejeita o agendamento. Reduzir o evento ACL resolve o
# lado do TAG; o lado do telefone (min_sub_event_len >= 2250 us) so se resolve
# num app proprio — o nRF Toolbox de prateleira nao expoe esse parametro.
#
# Fonte: Nordic DevZone #128985 ("nRF54L15 DK NCS v3.3.1 Channel Sounding
# procedure enable fails with 0x1e on Galaxy S26 Android 17") e a doc de
# scheduling do SoftDevice Controller (o offset do CS deriva deste valor).
#
CONFIG_BT_CTLR_SDC_MAX_CONN_EVENT_LEN_DEFAULT=1250
```

- [ ] **Step 3: Compilar a variante de demo**

```bash
cd /c/ncs/v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d /c/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag_demo /c/work/nrf-manaus-2/comms/channel_sounding_reflector -- "-DEXTRA_CONF_FILE=android_ranging.conf;demo.conf;s26.conf"
grep -E "^CONFIG_(BT_DEVICE_NAME|BT_CTLR_SDC_MAX_CONN_EVENT_LEN_DEFAULT|BT_BONDABLE|BT_RAS_MAX_ANTENNA_PATHS)=" /c/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag_demo/channel_sounding_reflector/zephyr/.config
```

Expected:
```
CONFIG_BT_DEVICE_NAME="CS Reflector DEMO"
CONFIG_BT_BONDABLE=y
CONFIG_BT_RAS_MAX_ANTENNA_PATHS=2
CONFIG_BT_CTLR_SDC_MAX_CONN_EVENT_LEN_DEFAULT=1250
```

- [ ] **Step 4: Substituir a seção "Demo do instrutor" do README**

Trocar o parágrafo de duas linhas da Task 1 por:

```markdown
## Demo do instrutor com smartphone

Não faz parte do lab do aluno. O telefone é o initiator (Android `RangingManager`), o
TAG é o reflector, e o app mostra a distância na tela.

```
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/channel_sounding_reflector/build_tag_demo C:/work/nrf-manaus-2/comms/channel_sounding_reflector -- "-DEXTRA_CONF_FILE=android_ranging.conf;demo.conf;s26.conf"
```

| Fragmento | O que faz |
|---|---|
| `android_ranging.conf` (do SDK) | bonding + settings em NVS, e 2 caminhos de antena — o que o Android exige |
| `demo.conf` | nome `CS Reflector DEMO`, para achar o TAG certo entre seis iguais |
| `s26.conf` | `MAX_CONN_EVENT_LEN_DEFAULT=1250` — sem isso o Galaxy S26 falha com `0x1E` no *Procedure Enable* |

Suporte documentado pela Nordic hoje: Pixel 9 e 10 (Android 16 QPR2+ / 17), nRF Toolbox
≥ 4.1.4. O S26 exige o `s26.conf` **e** um ajuste do lado do telefone
(`min_sub_event_len` ≥ 2250 µs) que o nRF Toolbox da loja não expõe — precisa de um
build próprio do app (open source, Kotlin). Se não houver telefone compatível no dia, a
demo é o par embarcado (labs 1 + 2) projetado na tela.
```

- [ ] **Step 5: Commit**

```bash
cd /c/work/nrf-manaus-2
git add comms/channel_sounding_reflector
git commit -F - <<'EOF'
channel_sounding_reflector: fragmentos da demo com smartphone (demo.conf, s26.conf)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---
### Task 3: Lab 2 — initiator RAS no LM20-DK com filtro por endereço do TAG

**Files:**
- Create: `comms/channel_sounding_initiator/CMakeLists.txt`, `prj.conf`, `Kconfig`, `Kconfig.sysbuild`, `LICENSE`, `meu_tag.conf`, `.gitignore`, `src/main.c`

**Interfaces:**
- Consumes: reflector da Task 1 anunciando o UUID do Ranging Service.
- Produces: símbolos Kconfig `CONFIG_LAB_TAG_ADDR_VALUE` (string) e `CONFIG_LAB_TAG_ADDR_TYPE` (string); função `static int add_tag_address_filter(uint8_t *filter_mode)` em `src/main.c`. As Tasks 6 e 8 repetem o mesmo padrão.

- [ ] **Step 1: Copiar o sample e a licença**

```bash
cd /c/work/nrf-manaus-2
mkdir -p comms/channel_sounding_initiator/src
S=/c/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_initiator
cp $S/CMakeLists.txt $S/prj.conf $S/Kconfig $S/Kconfig.sysbuild comms/channel_sounding_initiator/
cp $S/src/main.c comms/channel_sounding_initiator/src/main.c
cp edge_ai/03_central_uart/LICENSE comms/channel_sounding_initiator/LICENSE
```

- [ ] **Step 2: `CMakeLists.txt` — falhar cedo sem endereço**

Substituir o conteúdo por (mantendo o copyright da Nordic):

```cmake
#
# Copyright (c) 2024 Nordic Semiconductor
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(channel_sound_ras_initiator)

# ALTERADO PELO CURSO (nrf-manaus-2): falha cedo e com mensagem util, em vez de
# compilar um initiator que conecta no TAG do colega.
if(NOT CONFIG_LAB_TAG_ADDR_VALUE)
  message(FATAL_ERROR
    "CONFIG_LAB_TAG_ADDR_VALUE nao definido.\n"
    "Este initiator so conecta no TAG cujo endereco BLE for informado.\n"
    "E o MESMO endereco do edge_ai/03_central_uart — copie o meu_tag.conf de la,\n"
    "ou leia a linha \"Identity:\" do log RTT do TAG e preencha:\n"
    "  CONFIG_LAB_TAG_ADDR_VALUE=\"EF:12:34:56:78:9A\"\n"
    "  CONFIG_LAB_TAG_ADDR_TYPE=\"random\"\n"
    "e compile com -DEXTRA_CONF_FILE=meu_tag.conf")
endif()

FILE(GLOB app_sources src/*.c)
# NORDIC SDK APP START
target_sources(app PRIVATE
  ${app_sources}
)
# NORDIC SDK APP END
```

- [ ] **Step 3: `Kconfig` — menu do filtro antes do menu do sample**

Substituir o conteúdo por:

```kconfig
#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

# ALTERADO PELO CURSO (nrf-manaus-2): menu abaixo acrescentado. Mesmos simbolos do
# edge_ai/03_central_uart, para o aluno reaproveitar o meu_tag.conf de la.
menu "Lab: filtro do tag (nrf-manaus-2)"

config LAB_TAG_ADDR_VALUE
	string "Endereco BLE do tag deste aluno"
	default ""
	help
	  Endereco BLE do nRF54L15-TAG em que este initiator deve conectar, no
	  formato "EF:12:34:56:78:9A".

	  Sem isto o initiator conectaria em qualquer dispositivo anunciando o
	  Ranging Service — numa sala com varios tags, no do colega. O build
	  falha se ficar vazio.

	  E o mesmo endereco usado no edge_ai/03_central_uart: o endereco estatico
	  vem do proprio chip e nao muda com o firmware. Copie o meu_tag.conf de la.

config LAB_TAG_ADDR_TYPE
	string "Tipo do endereco BLE do tag"
	default "random"
	help
	  "random" ou "public", conforme aparece entre parenteses na linha
	  "Identity:" do log do tag. Os tags da Nordic usam endereco random
	  estatico, entao o default costuma servir.

endmenu

menu "Channel Sounding RAS Initiator sample"

choice SAMPLE_RAS_INITIATOR_STEP_MODE
	prompt "Channel Sounding Step Modes selection"
	default SAMPLE_RAS_INITIATOR_STEP_MODE_2_SUB_MODE_1

config SAMPLE_RAS_INITIATOR_STEP_MODE_2_SUB_MODE_1
	bool "Main: 2, Sub: 1."
	help
	  This option enables CS with main mode 2 and submode 1.
	  Mode 2 steps are used for PBR and mode 1 steps are used for RTT.

config SAMPLE_RAS_INITIATOR_STEP_MODE_1
	bool "Main: 1, Sub: unused."
	help
	  This option enables CS with main mode 1 and submode unused.
	  Mode 1 steps are used for RTT.

config SAMPLE_RAS_INITIATOR_STEP_MODE_2
	bool "Main: 2, Sub: unused."
	help
	  This option enables CS with main mode 2 and submode unused.
	  Mode 2 steps are used for PBR.

config SAMPLE_RAS_INITIATOR_STEP_MODE_3
	bool "Main: 3, Sub: unused."
	select BT_RAS_MODE_3_SUPPORTED
	select BT_CTLR_SDC_CS_STEP_MODE3
	help
	  This option enables CS with main mode 3 and submode unused.
	  Mode 3 steps are used for PBR and RTT.

endchoice

endmenu

source "Kconfig.zephyr"
```

- [ ] **Step 4: `prj.conf` — cabeçalho `ORIGEM:` e o contador de filtros de endereço**

Inserir no topo (trocar a data):

```
#
# ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
#   SDK     : nRF Connect SDK v3.4.0
#   Upstream: nrf/samples/bluetooth/channel_sounding/ras_initiator/prj.conf
#   Local   : C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_initiator/prj.conf
#   Copiado : AAAA-MM-DD — curso nrf-manaus-2, modulo comms/channel_sounding_initiator
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_initiator/prj.conf
#
# DIVERGENCIA DO CURSO (unica): CONFIG_BT_SCAN_ADDRESS_CNT=1 no bloco de scan.
#   O filtro em si e configurado por fragmento (CONFIG_LAB_TAG_ADDR_VALUE), nao aqui.
#
```

E logo após a linha `CONFIG_BT_SCAN_UUID_CNT=1` acrescentar:

```
# ALTERADO PELO CURSO (nrf-manaus-2): um slot de filtro por endereco, para o
# add_tag_address_filter() de src/main.c.
CONFIG_BT_SCAN_ADDRESS_CNT=1
```

- [ ] **Step 5: `src/main.c` — cabeçalho `ORIGEM:` e o filtro por endereço**

Inserir no topo (trocar a data):

```c
/*
 * ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
 *   SDK     : nRF Connect SDK v3.4.0
 *   Upstream: nrf/samples/bluetooth/channel_sounding/ras_initiator/src/main.c
 *   Local   : C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_initiator/src/main.c
 *   Copiado : AAAA-MM-DD — curso nrf-manaus-2, modulo comms/channel_sounding_initiator
 *
 * Para conferir se divergiu do SDK:
 *   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_initiator/src/main.c
 *
 * DIVERGENCIA DO CURSO (unica): scan_init() e add_tag_address_filter().
 *   O upstream filtra so pelo UUID do Ranging Service, em modo OR. Aqui entra um
 *   filtro pelo endereco de CONFIG_LAB_TAG_ADDR_VALUE e o modo passa a AND —
 *   cada aluno conecta no seu proprio TAG.
 */
```

Substituir a função `scan_init()` inteira (a que faz `bt_scan_filter_add(BT_SCAN_FILTER_TYPE_UUID, ...)` e `bt_scan_filter_enable(BT_SCAN_UUID_FILTER, false)`) por:

```c
/* ALTERADO PELO CURSO (nrf-manaus-2).
 *
 * Upstream: so o filtro de UUID do Ranging Service, em modo OR
 * (bt_scan_filter_enable(..., false)) — o initiator conectava em QUALQUER
 * reflector anunciando RAS. Numa sala com seis TAGs iguais isso cruza as
 * estacoes. Aqui entra o filtro pelo endereco de CONFIG_LAB_TAG_ADDR_VALUE e o
 * modo passa a AND (match_all = true): precisa ser um reflector RAS E ser o
 * meu TAG. Mesmo padrao do edge_ai/03_central_uart.
 */
static int add_tag_address_filter(uint8_t *filter_mode)
{
	bt_addr_le_t tag_addr;
	int err;

	err = bt_addr_le_from_str(CONFIG_LAB_TAG_ADDR_VALUE, CONFIG_LAB_TAG_ADDR_TYPE,
				  &tag_addr);
	if (err) {
		LOG_ERR("CONFIG_LAB_TAG_ADDR invalido: \"%s (%s)\" (err %d)",
			CONFIG_LAB_TAG_ADDR_VALUE, CONFIG_LAB_TAG_ADDR_TYPE, err);
		return err;
	}

	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_ADDR, &tag_addr);
	if (err) {
		LOG_ERR("Address filter cannot be added (err %d)", err);
		return err;
	}

	*filter_mode |= BT_SCAN_ADDR_FILTER;
	LOG_INF("Filtrando pelo tag %s (%s)", CONFIG_LAB_TAG_ADDR_VALUE,
		CONFIG_LAB_TAG_ADDR_TYPE);

	return 0;
}

static int scan_init(struct bt_scan_init_param *p_param)
{
	int err;
	uint8_t filter_mode = BT_SCAN_UUID_FILTER;

	bt_scan_init(p_param);
	bt_scan_cb_register(&scan_cb);

	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_UUID, BT_UUID_RANGING_SERVICE);
	if (err) {
		LOG_ERR("Scanning filters cannot be set (err %d)", err);
		return err;
	}

	err = add_tag_address_filter(&filter_mode);
	if (err) {
		return err;
	}

	/* match_all = true: UUID do RAS E endereco do meu TAG. */
	err = bt_scan_filter_enable(filter_mode, true);
	if (err) {
		LOG_ERR("Filters cannot be turned on (err %d)", err);
		return err;
	}

	return 0;
}
```

- [ ] **Step 6: `meu_tag.conf` e `.gitignore`**

Criar `comms/channel_sounding_initiator/meu_tag.conf`:

```
#
# Fragmento do aluno — endereco BLE do SEU tag.
#
# Uso:
#   west build ... -- -DEXTRA_CONF_FILE=meu_tag.conf
#
# E o MESMO endereco do edge_ai/03_central_uart: o endereco estatico vem do
# proprio chip e nao muda com o firmware. Copie o meu_tag.conf de la, ou leia a
# linha "Identity:" do boot do TAG no RTT:
#
#   <inf> bt_hci_core: Identity: EC:EF:40:2D:5E:46 (random)
#                                ^^^^^^^^^^^^^^^^^  ^^^^^^
#                                VALUE              TYPE
#
# Deixar vazio faz o build falhar de proposito: um initiator sem endereco
# conectaria no tag do colega.
#
CONFIG_LAB_TAG_ADDR_VALUE=""
CONFIG_LAB_TAG_ADDR_TYPE="random"
```

Criar `comms/channel_sounding_initiator/.gitignore`:

```
# NOTA: meu_tag.conf NAO entra aqui de proposito. Ele e rastreado e vem no repo
# com o endereco vazio — e o template que cada aluno preenche, e o CMakeLists.txt
# falha de proposito quando esta vazio, com a mensagem de onde achar o endereco.
# So nao commite o SEU endereco: 'git checkout comms/channel_sounding_initiator/meu_tag.conf'
# antes do commit, ou deixe-o fora do 'git add'.
```

- [ ] **Step 7: Verificar que o build sem endereço falha com a mensagem certa**

```bash
cd /c/ncs/v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d /c/work/nrf-manaus-2/comms/channel_sounding_initiator/build_lm20 /c/work/nrf-manaus-2/comms/channel_sounding_initiator 2>&1 | grep -A3 "CONFIG_LAB_TAG_ADDR_VALUE nao definido"
```

Expected: a mensagem `CONFIG_LAB_TAG_ADDR_VALUE nao definido.` seguida de `Este initiator so conecta no TAG ...`, e o build termina com erro.

- [ ] **Step 8: Verificar que o build com endereço passa**

Preencher `meu_tag.conf` com o endereço do TAG da bancada (lido no RTT na Task 1, Step 6) e:

```bash
cd /c/ncs/v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d /c/work/nrf-manaus-2/comms/channel_sounding_initiator/build_lm20 /c/work/nrf-manaus-2/comms/channel_sounding_initiator -- -DEXTRA_CONF_FILE=meu_tag.conf
grep -E "^CONFIG_(LAB_TAG_ADDR_VALUE|BT_SCAN_ADDRESS_CNT|SAMPLE_RAS_INITIATOR_STEP_MODE_2_SUB_MODE_1|BT_CS_DE)=" /c/work/nrf-manaus-2/comms/channel_sounding_initiator/build_lm20/channel_sounding_initiator/zephyr/.config
```

Expected: build sem erro e as quatro linhas:
```
CONFIG_LAB_TAG_ADDR_VALUE="<endereco da bancada>"
CONFIG_BT_SCAN_ADDRESS_CNT=1
CONFIG_SAMPLE_RAS_INITIATOR_STEP_MODE_2_SUB_MODE_1=y
CONFIG_BT_CS_DE=y
```

- [ ] **Step 9: Bancada — o par medindo, três colunas**

TAG **fora** do `DEBUG OUT`, na bateria, com o firmware da Task 1. Conferir com `nrfutil device device-info` que o debugger agora vê o nRF54LM20. Então:

```bash
cd /c/ncs/v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d /c/work/nrf-manaus-2/comms/channel_sounding_initiator/build_lm20
```

Abrir a serial USB da DK (115200 8N1; a DK enumera duas COM — na bancada o log sai na **vcom1**, COM22; se ficar muda, tentar a outra).

Expected, em sequência: `Filtrando pelo tag <endereco> (random)`, `Connected`, e depois, repetidas vezes:
```
Latest distance estimates on antenna path 0: ifft: X.XX, phase_slope: Y.YY, rtt: Z.ZZ meters
```
com três números da ordem da distância real entre TAG e DK. Anotar no relato da task os valores a ~1 m para o README (Task 4).

- [ ] **Step 10: Limpar o endereço e commitar**

```bash
cd /c/work/nrf-manaus-2
sed -i 's/^CONFIG_LAB_TAG_ADDR_VALUE=.*/CONFIG_LAB_TAG_ADDR_VALUE=""/' comms/channel_sounding_initiator/meu_tag.conf
grep -q 'CONFIG_LAB_TAG_ADDR_VALUE=""' comms/channel_sounding_initiator/meu_tag.conf && echo "meu_tag.conf limpo"
git add comms/channel_sounding_initiator
git commit -F - <<'EOF'
channel_sounding_initiator: initiator RAS no LM20-DK com filtro pelo TAG do aluno

Copia do ras_initiator do SDK v3.4.0. Divergencia unica em src/main.c:
add_tag_address_filter() e scan em modo AND (UUID do RAS E endereco de
CONFIG_LAB_TAG_ADDR_VALUE), mesmos simbolos do edge_ai/03_central_uart para
o aluno reaproveitar o meu_tag.conf. Build falha de proposito sem endereco.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

Expected da primeira linha: `meu_tag.conf limpo`.

---

### Task 4: Lab 2 — intervalo de procedure por estação, variações só-RTT/só-PBR e README

**Files:**
- Modify: `comms/channel_sounding_initiator/Kconfig`, `comms/channel_sounding_initiator/src/main.c`
- Create: `comms/channel_sounding_initiator/rtt_only.conf`, `pbr_only.conf`, `README.md`

**Interfaces:**
- Produces: `CONFIG_LAB_PROCEDURE_INTERVAL` (int, default 0 = valor do sample). A Task 8 copia este `main.c` já com esta divergência.

- [ ] **Step 1: `Kconfig` — símbolo do intervalo dentro do menu do curso**

Dentro do `menu "Lab: filtro do tag (nrf-manaus-2)"`, após `LAB_TAG_ADDR_TYPE` e antes do `endmenu`, acrescentar:

```kconfig
config LAB_PROCEDURE_INTERVAL
	int "Intervalo entre procedures de CS (em intervalos de conexao; 0 = valor do sample)"
	default 0
	range 0 255
	help
	  Quantos intervalos de conexao ACL (20 ms neste sample) separam dois
	  procedures de Channel Sounding. 0 mantem a escolha do sample da Nordic:
	  5 com ranging data em tempo real, 10 caso contrario (100 ou 200 ms).

	  Seis estacoes medindo ao mesmo tempo na mesma sala nao e uma condicao
	  que a Nordic documenta. Se as medidas degradarem, escalone: estacao n
	  (0 a 5) usa 50 + n*12 (1000 a 2200 ms), passado por fragmento ou
	  -DCONFIG_LAB_PROCEDURE_INTERVAL=<n>.
```

- [ ] **Step 2: `src/main.c` — aplicar o override**

Localizar em `main()`:

```c
	uint16_t desired_procedure_interval = realtime_rd ? 5 : 10;
```

e substituir por:

```c
	uint16_t desired_procedure_interval = realtime_rd ? 5 : 10;

	/* ALTERADO PELO CURSO (nrf-manaus-2): intervalo escalonavel por estacao,
	 * para varias bancadas medindo na mesma sala. 0 = valor do sample.
	 */
	if (CONFIG_LAB_PROCEDURE_INTERVAL > 0) {
		desired_procedure_interval = CONFIG_LAB_PROCEDURE_INTERVAL;
		LOG_INF("Intervalo de procedure: %u intervalos de conexao",
			desired_procedure_interval);
	}
```

Atualizar o cabeçalho `ORIGEM:` do arquivo: `DIVERGENCIA DO CURSO (unica)` vira `DIVERGENCIA DO CURSO (duas)` e acrescentar a linha:

```
 *   2. main(): CONFIG_LAB_PROCEDURE_INTERVAL sobrescreve o intervalo de procedure
 *      quando diferente de 0 (escalonamento entre bancadas).
```

- [ ] **Step 3: Fragmentos de variação**

Criar `rtt_only.conf`:

```
#
# Variacao opcional do lab 2 (nrf-manaus-2): so RTT (step mode 1).
# Uso: -DEXTRA_CONF_FILE="meu_tag.conf;rtt_only.conf"
# Rebuild so da DK; o reflector nao muda.
#
CONFIG_SAMPLE_RAS_INITIATOR_STEP_MODE_1=y
```

Criar `pbr_only.conf`:

```
#
# Variacao opcional do lab 2 (nrf-manaus-2): so PBR (step mode 2).
# Uso: -DEXTRA_CONF_FILE="meu_tag.conf;pbr_only.conf"
# Rebuild so da DK; o reflector nao muda.
#
CONFIG_SAMPLE_RAS_INITIATOR_STEP_MODE_2=y
```

- [ ] **Step 4: Verificar os três builds**

Preencher `meu_tag.conf` com o endereço da bancada e:

```bash
cd /c/ncs/v3.4.0
A=/c/work/nrf-manaus-2/comms/channel_sounding_initiator
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d $A/build_lm20 $A -- -DEXTRA_CONF_FILE=meu_tag.conf -DCONFIG_LAB_PROCEDURE_INTERVAL=62
grep -E "^CONFIG_(LAB_PROCEDURE_INTERVAL|SAMPLE_RAS_INITIATOR_STEP_MODE_2_SUB_MODE_1)=" $A/build_lm20/channel_sounding_initiator/zephyr/.config
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d $A/build_lm20_pbr $A -- "-DEXTRA_CONF_FILE=meu_tag.conf;pbr_only.conf"
grep -E "^CONFIG_SAMPLE_RAS_INITIATOR_STEP_MODE_2=" $A/build_lm20_pbr/channel_sounding_initiator/zephyr/.config
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d $A/build_lm20_rtt $A -- "-DEXTRA_CONF_FILE=meu_tag.conf;rtt_only.conf"
grep -E "^CONFIG_SAMPLE_RAS_INITIATOR_STEP_MODE_1=" $A/build_lm20_rtt/channel_sounding_initiator/zephyr/.config
```

Expected: `CONFIG_LAB_PROCEDURE_INTERVAL=62` e `CONFIG_SAMPLE_RAS_INITIATOR_STEP_MODE_2_SUB_MODE_1=y` no primeiro; `CONFIG_SAMPLE_RAS_INITIATOR_STEP_MODE_2=y` no segundo; `CONFIG_SAMPLE_RAS_INITIATOR_STEP_MODE_1=y` no terceiro.

- [ ] **Step 5: Bancada — as variações imprimem o que o código promete**

Gravar `build_lm20_pbr` e conferir na serial a linha `Latest distance estimates on antenna path 0: ifft: X, phase_slope: Y meters` (sem `rtt`). Gravar `build_lm20_rtt` e conferir `Latest distance estimate rtt: Z meters`. Voltar a gravar `build_lm20` (default, com intervalo 62) e conferir `Intervalo de procedure: 62 intervalos de conexao` e a cadência das linhas de ~1,2 s.

- [ ] **Step 6: README do lab**

Criar `comms/channel_sounding_initiator/README.md`:

```markdown
# Channel Sounding · Lab 2 — Initiator no nRF54LM20-DK: RTT e PBR lado a lado

Fecha o par com o TAG do lab 1 e imprime distância no terminal. É **aqui** que os dois
princípios físicos do Channel Sounding aparecem na prática — a cada procedure, o sample
imprime **três estimativas da mesma distância**:

```
Latest distance estimates on antenna path 0: ifft: 2.31, phase_slope: 2.44, rtt: 2.70 meters
```

| Coluna | Princípio | Como estima (`include/bluetooth/cs_de.h`) |
|---|---|---|
| `ifft` | **PBR** — fase | transformada inversa de Fourier sobre a fase por canal; o pico é o caminho mais curto |
| `phase_slope` | **PBR** — fase | inclinação média da fase em função da frequência |
| `rtt` | **RTT** — tempo | tempo de ida e volta médio dos steps de mode 1 |

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ras_initiator` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE). As duas
> divergências do curso estão marcadas no cabeçalho de `src/main.c`.

> **Precisão.** A própria Nordic classifica o algoritmo deste sample (`cs_de`, marcado
> `[EXPERIMENTAL]`) como referência: "*the accuracy is not representative for Channel
> Sounding and should be replaced if accuracy is important*". Os números que você vai
> ver são o que **um algoritmo simples** tira dos dados — não o teto da tecnologia. O
> lab 5 mostra o que muda com um algoritmo melhor.

## Hardware

| Peça | Papel |
|---|---|
| **nRF54L15-TAG** | reflector do lab 1, **na bateria, fora do `DEBUG OUT`** |
| **nRF54LM20-DK** | roda este firmware; initiator, calcula e imprime |

## Passo 1 — o endereço do seu TAG

É o **mesmo do Edge AI**. O endereço BLE estático vem do próprio chip e não muda com
o firmware, então o `meu_tag.conf` que você preencheu no `edge_ai/03_central_uart`
serve aqui sem alteração:

```
copy ..\..\edge_ai\03_central_uart\meu_tag.conf meu_tag.conf
```

Se precisar reler: é a linha `Identity:` do boot do TAG, no RTT (lab 1).

## Passo 2 — compilar e gravar a DK

TAG **fora** do `DEBUG OUT` (senão o debugger grava o TAG). Confira com
`nrfutil device device-info`: tem que aparecer nRF54LM20.

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/channel_sounding_initiator/build_lm20 C:/work/nrf-manaus-2/comms/channel_sounding_initiator -- -DEXTRA_CONF_FILE=meu_tag.conf
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/channel_sounding_initiator/build_lm20
```

No VS Code: board target `nrf54lm20dk/nrf54lm20b/cpuapp` com `meu_tag.conf` em
*Kconfig fragments*.

Deixar o endereço vazio **falha o build de propósito** (`CMakeLists.txt`). Um initiator
sem filtro conectaria no TAG do colega: os seis TAGs da sala anunciam o mesmo UUID.

## Passo 3 — ler

Serial USB da DK, **115200 8N1**. A DK enumera duas portas COM; o log sai numa delas
(na bancada, a segunda). Sequência esperada:

```
Filtrando pelo tag EC:EF:40:2D:5E:46 (random)
Connected ...
CS capability exchange completed.
CS config creation complete. ID: 0
CS security enabled.
CS procedures enabled.
Latest distance estimates on antenna path 0: ifft: 1.02, phase_slope: 1.11, rtt: 1.35 meters
Latest distance estimates on antenna path 0: ifft: 0.98, phase_slope: 1.09, rtt: 0.90 meters
```

## Passo 4 — o experimento: RTT × PBR

Sem recompilar nada. Trena na mão.

**A. Distâncias conhecidas.** TAG a 1 m, 3 m e 5 m da DK, linha de visada. Para cada
uma, anote dez linhas. Perguntas:

- Qual coluna acompanha a trena? Qual tem o menor espalhamento?
- `ifft` e `phase_slope` medem a **mesma fase** por métodos diferentes — quanto
  divergem entre si?
- `rtt` mede **tempo**. Um erro de 1 ns em tempo de voo são 30 cm. Qual a resolução
  que você vê nele?

**B. Obstrução e multipath.** TAG a 3 m: (1) corpo entre TAG e DK; (2) TAG encostado
numa superfície metálica. O que a física prevê: os estimadores de **fase** reagem ao
multipath (o sinal refletido soma-se ao direto e distorce a fase), o de **tempo** é
mais grosseiro mas não "salta". Confira se é isso que aparece — e anote onde não é.

**C. Registre.** Média e desvio das três colunas por condição. É o dado que o lab 5
vai revisitar com outro algoritmo.

## Variações (opcional)

O sample tem um `choice` de Kconfig para o step mode. Dois fragmentos deixam isolar
um princípio de cada vez — rebuild **só da DK**, o TAG não muda:

```
-- -DEXTRA_CONF_FILE="meu_tag.conf;pbr_only.conf"   # so mode 2: ifft e phase_slope
-- -DEXTRA_CONF_FILE="meu_tag.conf;rtt_only.conf"   # so mode 1: rtt
```

## Várias bancadas na mesma sala

Seis pares medindo ao mesmo tempo não é condição documentada pela Nordic. Se as medidas
degradarem, escalone o intervalo de procedure por estação:

```
-- -DEXTRA_CONF_FILE=meu_tag.conf -DCONFIG_LAB_PROCEDURE_INTERVAL=<50 + n*12>
```

com `n` = número da estação (0 a 5). O valor está em intervalos de conexão de 20 ms:
50 = 1 s. Zero (default) mantém a escolha do sample (100–200 ms).

## As duas divergências do curso

1. **`src/main.c` — filtro por endereço.** O upstream filtra só pelo UUID do Ranging
   Service em modo OR. Aqui `add_tag_address_filter()` acrescenta o endereço de
   `CONFIG_LAB_TAG_ADDR_VALUE` e `bt_scan_filter_enable()` passa a `match_all = true`.
   Mesmo código do `edge_ai/03_central_uart`.
2. **`src/main.c` — intervalo de procedure.** `CONFIG_LAB_PROCEDURE_INTERVAL`, quando
   diferente de 0, sobrescreve o intervalo escolhido pelo sample.

E `prj.conf` ganha `CONFIG_BT_SCAN_ADDRESS_CNT=1`, o slot do filtro.

## Pegadinhas

- **Gravou o TAG achando que era a DK.** Com o TAG no `DEBUG OUT`, o `west flash` vai
  para o TAG. Tire-o antes.
- **Não conecta.** O endereço em `meu_tag.conf` é o do **seu** TAG? A linha
  `Filtrando pelo tag ...` mostra o que o firmware está usando.
- **Conectou e não mede.** Um segundo initiator (outra DK, um telefone) já pegou o
  TAG — ele só aceita uma conexão. Desligue o outro; `nrfutil device recover` numa DK
  esquecida com firmware antigo.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ras_initiator` e
  `subsys/bluetooth/cs_de/cs_de.c` (os três estimadores, em fonte)
- Nordic, *Bluetooth Channel Sounding Distance Estimation* (doc da biblioteca `cs_de`)
- Nordic, release notes do nRF Connect SDK v2.9.0 — a nota sobre a precisão do sample
- Nordic, webinar *Bluetooth Channel Sounding: From theory to practice on the nRF54L Series and Android*
```

- [ ] **Step 7: Limpar o endereço e commitar**

```bash
cd /c/work/nrf-manaus-2
sed -i 's/^CONFIG_LAB_TAG_ADDR_VALUE=.*/CONFIG_LAB_TAG_ADDR_VALUE=""/' comms/channel_sounding_initiator/meu_tag.conf
git add comms/channel_sounding_initiator
git commit -F - <<'EOF'
channel_sounding_initiator: intervalo por estacao, variacoes so-RTT/so-PBR e README

RTT e PBR aparecem lado a lado no build default (ifft, phase_slope, rtt);
o README traz o experimento com trena e obstrucao. CONFIG_LAB_PROCEDURE_INTERVAL
escalona as bancadas se a sala degradar. rtt_only.conf e pbr_only.conf isolam
um principio de cada vez, rebuild so da DK.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---
### Task 5: Lab 3a — reflector IPT no TAG

**Files:**
- Create: `comms/channel_sounding_ipt_reflector/CMakeLists.txt`, `prj.conf`, `Kconfig.sysbuild`, `LICENSE`, `README.md`, `src/main.c`, `boards/nrf54l15tag_nrf54l15_cpuapp.conf`

**Interfaces:**
- Produces: firmware que anuncia com o nome `"Nordic CS IPT Reflector"` (default do SDK, é o que o `ipt_initiator` procura). Consumido pela Task 6.

- [ ] **Step 1: Copiar o sample, a licença e o fragmento de board**

```bash
cd /c/work/nrf-manaus-2
mkdir -p comms/channel_sounding_ipt_reflector/src comms/channel_sounding_ipt_reflector/boards
S=/c/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ipt_reflector
cp $S/CMakeLists.txt $S/prj.conf $S/Kconfig.sysbuild comms/channel_sounding_ipt_reflector/
cp $S/src/main.c comms/channel_sounding_ipt_reflector/src/main.c
cp edge_ai/03_central_uart/LICENSE comms/channel_sounding_ipt_reflector/LICENSE
cp comms/channel_sounding_reflector/boards/nrf54l15tag_nrf54l15_cpuapp.conf comms/channel_sounding_ipt_reflector/boards/
```

- [ ] **Step 2: Cabeçalhos `ORIGEM:`**

No topo de `src/main.c` e de `prj.conf`, o mesmo bloco da Task 1 com `Upstream`/`Local` apontando para `.../channel_sounding/ipt_reflector/...`, `modulo comms/channel_sounding_ipt_reflector`, e:

```
 * DIVERGENCIA DO CURSO: nenhuma. O reflector IPT roda como a Nordic entregou.
 *   O que o curso acrescenta esta em boards/nrf54l15tag_nrf54l15_cpuapp.conf
 *   (log por RTT, porque o TAG nao tem UART).
```

No `boards/nrf54l15tag_nrf54l15_cpuapp.conf`, trocar a referência "Mesma correcao do edge_ai/03_central_uart." por "Mesmo fragmento do comms/channel_sounding_reflector."

- [ ] **Step 3: Compilar para o TAG — o item que a Nordic não documenta**

```bash
cd /c/ncs/v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d /c/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector/build_tag /c/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector
grep -E "^CONFIG_(LOG_BACKEND_RTT|BT_DEVICE_NAME|BT_CTLR_SDC_CS_ROLE_REFLECTOR_ONLY|BT_CTLR_EXTENDED_FEAT_SET)=" /c/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector/build_tag/channel_sounding_ipt_reflector/zephyr/.config
```

Expected: build sem erro e
```
CONFIG_LOG_BACKEND_RTT=y
CONFIG_BT_DEVICE_NAME="Nordic CS IPT Reflector"
CONFIG_BT_CTLR_SDC_CS_ROLE_REFLECTOR_ONLY=y
CONFIG_BT_CTLR_EXTENDED_FEAT_SET=y
```

Se o build falhar por RAM/flash no `nrf54l15tag` (o TAG não está no `platform_allow` deste sample), registrar o erro exato no relato da task e **parar** — é decisão de design, não de execução.

- [ ] **Step 4: Bancada — gravar e ver o boot no RTT**

TAG no `DEBUG OUT` (conferir `device-info` = nRF54L15):

```bash
cd /c/ncs/v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d /c/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector/build_tag
"/c/Program Files/SEGGER/JLink_V924a/JLinkRTTLogger.exe" -USB 1051898754 -Device NRF54L15_M33 -If SWD -Speed 4000 -RTTChannel 0 /c/Users/joaod/AppData/Local/Temp/claude/rtt_ipt_reflector.log
```

Expected: banner do Zephyr, `Identity:` (o **mesmo** endereço do lab 1 — anotar, é a prova para o README) e a mensagem de início do sample IPT.

- [ ] **Step 5: README**

Criar `comms/channel_sounding_ipt_reflector/README.md`:

```markdown
# Channel Sounding · Lab 3a — Reflector IPT no nRF54L15-TAG

O reflector do lab 3. Mesmo papel do lab 1 — anunciar, aceitar conexão, participar
dos procedures — com uma diferença que não aparece no código dele: **ele não expõe
dado nenhum por GATT**. Com o IPT (Inline Phase Correction Term Transfer) ligado pelo
initiator na configuração de CS, o reflector ajusta a fase do tom que devolve para
casar com a que acabou de receber. A contribuição dele viaja **dentro do tom de
rádio**, não pela conexão.

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ipt_reflector` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE).
> `src/main.c` e `prj.conf` são idênticos ao SDK; o curso acrescenta só o `boards/`
> com o RTT. O TAG não está na lista de boards do sample — o build foi validado na
> bancada do curso.

## Gravar

TAG no `DEBUG OUT` da DK (o debugger passa a apontar para o TAG; confira
`nrfutil device device-info` = nRF54L15). O mesmo TAG do lab 1 — o endereço BLE
continua o mesmo, o firmware não muda isso.

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54l15tag/nrf54l15/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector/build_tag C:/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/channel_sounding_ipt_reflector/build_tag
```

## Log — RTT, só no `DEBUG OUT`

Igual ao lab 1: o TAG não tem UART, o
[`boards/nrf54l15tag_nrf54l15_cpuapp.conf`](boards/nrf54l15tag_nrf54l15_cpuapp.conf)
manda o log para o RTT, e na bateria não há log.

```
"C:\Program Files\SEGGER\JLink_V924a\JLinkRTTLogger.exe" -Device NRF54L15_M33 -If SWD -Speed 4000 -RTTChannel 0 rtt.log
```

Depois de gravar, **tire o TAG** do `DEBUG OUT`: o próximo passo (lab 3b) grava a DK.

## Nome, não UUID

O `ipt_initiator` da Nordic procura o reflector pelo **nome** `Nordic CS IPT Reflector`
— não há Ranging Service para anunciar. Seis TAGs na sala terão o mesmo nome; por isso
o initiator do curso filtra também pelo endereço (lab 3b).

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ipt_reflector`
- Nordic, *Bluetooth: Channel Sounding Reflector with Inline PCT Transfer* (doc do sample — "How CS IPT works")
- Nordic, changelog do SoftDevice Controller, nRF Connect SDK v3.3.1 — suporte a IPT (DRGN-26911)
```

- [ ] **Step 6: Commit**

```bash
cd /c/work/nrf-manaus-2
git add comms/channel_sounding_ipt_reflector
git commit -F - <<'EOF'
channel_sounding_ipt_reflector: reflector IPT no TAG, copia do SDK v3.4.0

Sem divergencia no codigo; RTT pelo mesmo fragmento de board do lab 1.
Build para nrf54l15tag validado na bancada (o TAG nao esta no platform_allow
do sample).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---

### Task 6: Lab 3b — initiator IPT no LM20-DK com filtro por endereço

**Files:**
- Create: `comms/channel_sounding_ipt_initiator/CMakeLists.txt`, `prj.conf`, `Kconfig`, `Kconfig.sysbuild`, `LICENSE`, `meu_tag.conf`, `.gitignore`, `README.md`, `src/main.c`

**Interfaces:**
- Consumes: reflector da Task 5 anunciando `"Nordic CS IPT Reflector"`; os mesmos símbolos `CONFIG_LAB_TAG_ADDR_*` da Task 3.
- Produces: log `Distance estimates: median: X.XXm, update: Y.YYm, time_delta: Nms` (texto do sample) — comparado com o lab 2 no README.

- [ ] **Step 1: Copiar o sample e a licença**

```bash
cd /c/work/nrf-manaus-2
mkdir -p comms/channel_sounding_ipt_initiator/src
S=/c/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ipt_initiator
cp $S/CMakeLists.txt $S/prj.conf $S/Kconfig.sysbuild comms/channel_sounding_ipt_initiator/
cp $S/src/main.c comms/channel_sounding_ipt_initiator/src/main.c
cp edge_ai/03_central_uart/LICENSE comms/channel_sounding_ipt_initiator/LICENSE
cp comms/channel_sounding_initiator/meu_tag.conf comms/channel_sounding_ipt_initiator/meu_tag.conf
sed 's#comms/channel_sounding_initiator/#comms/channel_sounding_ipt_initiator/#' comms/channel_sounding_initiator/.gitignore > comms/channel_sounding_ipt_initiator/.gitignore
```

(O `ipt_initiator` do SDK não tem `Kconfig` próprio; o do curso é criado no Step 3.)

- [ ] **Step 2: `CMakeLists.txt` com o `FATAL_ERROR`**

Substituir por:

```cmake
#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(channel_sound_ipt_initiator)

# ALTERADO PELO CURSO (nrf-manaus-2): falha cedo e com mensagem util, em vez de
# compilar um initiator que conecta no TAG do colega.
if(NOT CONFIG_LAB_TAG_ADDR_VALUE)
  message(FATAL_ERROR
    "CONFIG_LAB_TAG_ADDR_VALUE nao definido.\n"
    "Este initiator so conecta no TAG cujo endereco BLE for informado.\n"
    "E o MESMO endereco do edge_ai/03_central_uart e do lab 2 — copie o meu_tag.conf,\n"
    "ou leia a linha \"Identity:\" do log RTT do TAG e preencha:\n"
    "  CONFIG_LAB_TAG_ADDR_VALUE=\"EF:12:34:56:78:9A\"\n"
    "  CONFIG_LAB_TAG_ADDR_TYPE=\"random\"\n"
    "e compile com -DEXTRA_CONF_FILE=meu_tag.conf")
endif()

# NORDIC SDK APP START
target_sources(app PRIVATE src/main.c)
# NORDIC SDK APP END
```

- [ ] **Step 3: `Kconfig` novo (o sample não tem)**

Criar `comms/channel_sounding_ipt_initiator/Kconfig`:

```kconfig
#
# Kconfig do curso (nrf-manaus-2). O ipt_initiator do SDK nao tem Kconfig proprio;
# este arquivo existe so para o filtro do tag, com os mesmos simbolos do
# edge_ai/03_central_uart e do comms/channel_sounding_initiator.
#

menu "Lab: filtro do tag (nrf-manaus-2)"

config LAB_TAG_ADDR_VALUE
	string "Endereco BLE do tag deste aluno"
	default ""
	help
	  Endereco BLE do nRF54L15-TAG em que este initiator deve conectar, no
	  formato "EF:12:34:56:78:9A".

	  O initiator IPT da Nordic procura o reflector pelo NOME
	  ("Nordic CS IPT Reflector"), que e igual em todos os TAGs da sala. Sem
	  isto ele conectaria no do colega. O build falha se ficar vazio.

	  E o mesmo endereco do edge_ai/03_central_uart e do lab 2.

config LAB_TAG_ADDR_TYPE
	string "Tipo do endereco BLE do tag"
	default "random"
	help
	  "random" ou "public", conforme aparece entre parenteses na linha
	  "Identity:" do log do tag.

endmenu

source "Kconfig.zephyr"
```

- [ ] **Step 4: `prj.conf` — cabeçalho `ORIGEM:` e o slot de endereço**

Inserir no topo o bloco `ORIGEM:` da Task 3 com os caminhos de `ipt_initiator` e `modulo comms/channel_sounding_ipt_initiator`, `DIVERGENCIA DO CURSO (unica): CONFIG_BT_SCAN_ADDRESS_CNT=1`. Após `CONFIG_BT_SCAN_NAME_CNT=1` acrescentar:

```
# ALTERADO PELO CURSO (nrf-manaus-2): um slot de filtro por endereco, para o
# add_tag_address_filter() de src/main.c.
CONFIG_BT_SCAN_ADDRESS_CNT=1
```

- [ ] **Step 5: `src/main.c` — cabeçalho e filtro**

Inserir no topo o bloco `ORIGEM:` da Task 3 (caminhos de `ipt_initiator`, módulo `comms/channel_sounding_ipt_initiator`) com:

```
 * DIVERGENCIA DO CURSO (unica): scan_init() e add_tag_address_filter().
 *   O upstream filtra so pelo NOME "Nordic CS IPT Reflector", em modo OR — e
 *   todos os TAGs da sala tem esse nome. Aqui entra o filtro pelo endereco de
 *   CONFIG_LAB_TAG_ADDR_VALUE e o modo passa a AND.
```

Substituir a função `scan_init()` (a que faz `bt_scan_filter_add(BT_SCAN_FILTER_TYPE_NAME, REFLECTOR_NAME)` e `bt_scan_filter_enable(BT_SCAN_NAME_FILTER, false)`) por:

```c
/* ALTERADO PELO CURSO (nrf-manaus-2).
 *
 * Upstream: so o filtro de NOME, em modo OR (bt_scan_filter_enable(..., false)).
 * Seis TAGs na sala anunciam "Nordic CS IPT Reflector" — o initiator conectava
 * no primeiro que aparecesse. Aqui entra o filtro pelo endereco de
 * CONFIG_LAB_TAG_ADDR_VALUE e o modo passa a AND (match_all = true): precisa ter
 * o nome E ser o meu TAG. Mesmo padrao do edge_ai/03_central_uart.
 */
static int add_tag_address_filter(uint8_t *filter_mode)
{
	bt_addr_le_t tag_addr;
	int err;

	err = bt_addr_le_from_str(CONFIG_LAB_TAG_ADDR_VALUE, CONFIG_LAB_TAG_ADDR_TYPE,
				  &tag_addr);
	if (err) {
		LOG_ERR("CONFIG_LAB_TAG_ADDR invalido: \"%s (%s)\" (err %d)",
			CONFIG_LAB_TAG_ADDR_VALUE, CONFIG_LAB_TAG_ADDR_TYPE, err);
		return err;
	}

	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_ADDR, &tag_addr);
	if (err) {
		LOG_ERR("Address filter cannot be added (err %d)", err);
		return err;
	}

	*filter_mode |= BT_SCAN_ADDR_FILTER;
	LOG_INF("Filtrando pelo tag %s (%s)", CONFIG_LAB_TAG_ADDR_VALUE,
		CONFIG_LAB_TAG_ADDR_TYPE);

	return 0;
}

static int scan_init(struct bt_scan_init_param *p_param)
{
	int err;
	uint8_t filter_mode = BT_SCAN_NAME_FILTER;

	bt_scan_init(p_param);
	bt_scan_cb_register(&scan_cb);

	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_NAME, REFLECTOR_NAME);
	if (err) {
		LOG_ERR("Scanning filters cannot be set (err %d)", err);
		return err;
	}

	err = add_tag_address_filter(&filter_mode);
	if (err) {
		return err;
	}

	/* match_all = true: nome do reflector IPT E endereco do meu TAG. */
	err = bt_scan_filter_enable(filter_mode, true);
	if (err) {
		LOG_ERR("Filters cannot be turned on (err %d)", err);
		return err;
	}

	return 0;
}
```

- [ ] **Step 6: Build sem endereço falha; com endereço passa**

```bash
cd /c/ncs/v3.4.0
A=/c/work/nrf-manaus-2/comms/channel_sounding_ipt_initiator
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d $A/build_lm20 $A 2>&1 | grep -c "CONFIG_LAB_TAG_ADDR_VALUE nao definido"
```
Expected: `1`.

Preencher `meu_tag.conf` com o endereço da bancada e:

```bash
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d $A/build_lm20 $A -- -DEXTRA_CONF_FILE=meu_tag.conf
grep -E "^CONFIG_(BT_SCAN_ADDRESS_CNT|BT_SCAN_NAME_CNT|BT_CS_DE_1024_NFFT)=" $A/build_lm20/channel_sounding_ipt_initiator/zephyr/.config
```
Expected: build sem erro; `CONFIG_BT_SCAN_ADDRESS_CNT=1`, `CONFIG_BT_SCAN_NAME_CNT=1`, `CONFIG_BT_CS_DE_1024_NFFT=y`.

- [ ] **Step 7: Bancada — o par IPT medindo, e a coluna que sumiu**

TAG (com o firmware da Task 5) **fora** do `DEBUG OUT`. Gravar a DK:

```bash
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d $A/build_lm20
```

Expected na serial (115200): `Filtrando pelo tag ...`, conexão, e depois repetidas:
```
Distance estimates: median: X.XXm, update: Y.YYm, time_delta: Nms
```
Anotar `time_delta` típico e a distância a ~1 m para o README. Não há coluna `rtt`.

- [ ] **Step 8: README**

Criar `comms/channel_sounding_ipt_initiator/README.md`:

```markdown
# Channel Sounding · Lab 3b — Initiator IPT: a mesma distância por outro caminho

Mesmo par do lab 2, mesma distância — o que muda é **por onde viaja** a contribuição
do reflector. No lab 2 (RAS) ela vem por GATT, pela conexão; aqui (IPT) ela vem
codificada na **fase do tom** que o reflector devolve. O initiator calcula sozinho,
dos seus próprios eventos de subevent, e nunca recebe medida crua do outro lado.

> **Origem:** cópia de `nrf/samples/bluetooth/channel_sounding/ipt_initiator` do
> **nRF Connect SDK v3.4.0**. Licença Nordic preservada em [LICENSE](LICENSE). A
> divergência única do curso está marcada no cabeçalho de `src/main.c`.

## IPT não é step mode

Step mode é *o que se mede* num step (1 = RTT, 2 = PBR, 3 = os dois). IPT é uma
**flag ligada na criação da configuração de CS** — `CS configuration creation with
CS IPT enabled`, é o initiator quem liga — e atua sobre os tons de PBR (mode 2 e a
parte PBR do mode 3). Os dois eixos são independentes.

## O que comparar com o lab 2

| | Lab 2 — RAS | Lab 3 — IPT |
|---|---|---|
| Setup antes da 1ª medida | descoberta do Ranging Service + assinaturas | nenhum |
| Dado do reflector | por GATT (ACL) | dentro da fase do tom |
| O que o log imprime | `ifft`, `phase_slope`, **`rtt`** | `median`, `update`, `time_delta` |
| Abrange | RTT + PBR | **só PBR** |

A coluna `rtt` **sumiu**. Não é omissão do log: o IPT só existe no mundo do PBR. Se
você quiser RTT, precisa do RAS (ou equivalente) para trazer o tempo de volta pela
conexão. E `time_delta` é a latência entre estimativas, medida pelo próprio sample —
compare com a cadência do lab 2.

## Passo 1 — o TAG com o reflector IPT

Lab 3a: TAG no `DEBUG OUT`, grava, tira. É o mesmo TAG, o endereço não muda.

## Passo 2 — o endereço

O mesmo `meu_tag.conf` do lab 2 (e do Edge AI):

```
copy ..\channel_sounding_initiator\meu_tag.conf meu_tag.conf
```

## Passo 3 — compilar e gravar a DK

TAG fora do `DEBUG OUT`.

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/channel_sounding_ipt_initiator/build_lm20 C:/work/nrf-manaus-2/comms/channel_sounding_ipt_initiator -- -DEXTRA_CONF_FILE=meu_tag.conf
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/channel_sounding_ipt_initiator/build_lm20
```

## Passo 4 — ler e comparar

Serial USB da DK, 115200 8N1:

```
Filtrando pelo tag EC:EF:40:2D:5E:46 (random)
...
Distance estimates: median: 1.05m, update: 1.02m, time_delta: 44ms
```

Repita o experimento A do lab 2 (1 m, 3 m, 5 m) e anote `median` e `time_delta`. O
que ganhou (latência, setup) e o que perdeu (RTT) é o assunto do lab 4.

## A divergência do curso

**`src/main.c` — filtro por endereço.** O upstream filtra só pelo nome
`Nordic CS IPT Reflector` em modo OR — e todos os TAGs da sala têm esse nome. Aqui
`add_tag_address_filter()` acrescenta o endereço de `CONFIG_LAB_TAG_ADDR_VALUE` e
`bt_scan_filter_enable()` passa a `match_all = true`. `prj.conf` ganha
`CONFIG_BT_SCAN_ADDRESS_CNT=1`.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/bluetooth/channel_sounding/ipt_initiator`
- Nordic, *Bluetooth: Channel Sounding Initiator with Inline PCT Transfer* — "How CS IPT works", "Benefits", "Drawbacks"
- Nordic, *LE Channel Sounding* (doc do SoftDevice Controller) — T_IP2_IPT e T_SW_IPT
```

- [ ] **Step 9: Limpar o endereço e commitar**

```bash
cd /c/work/nrf-manaus-2
sed -i 's/^CONFIG_LAB_TAG_ADDR_VALUE=.*/CONFIG_LAB_TAG_ADDR_VALUE=""/' comms/channel_sounding_ipt_initiator/meu_tag.conf
git add comms/channel_sounding_ipt_initiator
git commit -F - <<'EOF'
channel_sounding_ipt_initiator: initiator IPT no LM20-DK com filtro pelo TAG do aluno

Copia do ipt_initiator do SDK v3.4.0. O upstream filtra so pelo nome, igual em
todos os TAGs; entra o filtro por endereco em modo AND, mesmos simbolos do
lab 2. README compara com o RAS: a coluna rtt some, time_delta cai.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---

### Task 7: Lab 4 — roteiro de segurança (sem firmware)

**Files:**
- Create: `comms/channel_sounding_secure/README.md`

**Interfaces:**
- Consumes: os logs dos labs 2 e 3 e o `s26.conf` da Task 2. Nenhum código novo.

- [ ] **Step 1: Confirmar no código o que o roteiro vai pedir para o aluno observar**

```bash
grep -n "security" /c/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_initiator/src/main.c | head
grep -n "security" /c/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_reflector/src/main.c | head
grep -n "rtt_type\|BT_CONN_LE_CS_RTT_TYPE" /c/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_initiator/src/main.c
```

Expected: pelo menos uma linha por arquivo com `bt_le_cs_security_enable` ou `security_enable_cb`, e a linha `.rtt_type = BT_CONN_LE_CS_RTT_TYPE_AA_ONLY,` em `cs_config_get()`. Anotar os textos exatos das mensagens de log de segurança que aparecem nos `grep` — são eles que vão no README.

- [ ] **Step 2: Escrever o roteiro**

Criar `comms/channel_sounding_secure/README.md` (ajustar as mensagens de log às encontradas no Step 1):

```markdown
# Channel Sounding · Lab 4 — Segurança: o que o rádio garante e o que o chip suporta

Sem firmware novo. O TAG volta ao reflector RAS (lab 1) e o par do lab 2 é
reexaminado com outros olhos: **por que Channel Sounding resiste a um ataque de relé
onde RSSI não resiste**, e onde o lab 3 abriu mão disso.

## 1. O que já aconteceu antes da primeira medida

Releia o log do lab 2, na ordem:

```
Connected ...
CS capability exchange completed.
CS config creation complete. ID: 0
CS security enabled.
CS procedures enabled.
```

Três coisas para notar:

- **A conexão é cifrada antes de tudo.** O `main()` do initiator chama
  `bt_conn_set_security(connection, BT_SECURITY_L2)` e espera — sem ACL cifrada não
  há CS. O pareamento não é burocracia: é de onde saem as chaves do passo seguinte.
- **`CS security enabled`** é o `bt_le_cs_security_enable()`: initiator e reflector
  derivam da chave da conexão os segredos que embaralham a sequência de canais e o
  conteúdo dos pacotes de RTT. Um terceiro que só escuta não sabe qual canal vem
  depois nem o que vai dentro do pacote.
- **`.rtt_type = BT_CONN_LE_CS_RTT_TYPE_AA_ONLY`** em `cs_config_get()`: o RTT deste
  sample carimba o tempo no *access address* do pacote. O SoftDevice Controller também
  suporta RTT com payload aleatório de 32, 64, 96 ou 128 bits — quanto mais bits
  imprevisíveis, mais difícil para um atacante responder "antes da hora".

## 2. Por que RSSI é fácil de enganar e CS não

Com RSSI, "perto" significa "sinal forte". Um relé — dois rádios que repetem o sinal
entre a chave e a fechadura — faz o sinal chegar forte de longe. É o ataque clássico
contra chave de carro.

Com **RTT**, distância é **tempo de voo**. Um relé pode amplificar, mas não pode
fazer o sinal chegar **antes** do que a luz permite: ele só acrescenta atraso. O RTT
dá um **limite inferior físico** para a distância. Com o payload aleatório e a
sequência de canais secreta, o atacante também não consegue pré-computar a resposta.

Com **PBR** sozinho, a história é outra: a fase é periódica. Um atacante que consiga
manipular a fase pode fazer "longe" parecer "perto". Por isso a combinação
**mode 1 + mode 2** (RTT + PBR, o default do `ras_initiator`) é o arranjo robusto: o
PBR dá precisão, o RTT dá o limite que o PBR sozinho não dá.

## 3. O que o lab 3 abriu mão

O `ipt_initiator` roda **só mode 2**. A própria Nordic escreve, em "Drawbacks of CS
IPT": *"Reduced security level. This sample only runs CS mode 2 steps, so it cannot
provide the same level of protection against ranging attacks as a RAS-based setup
that combines mode 1 (RTT) and mode 2 (PBR) steps."*

É o trade-off do bloco: o IPT compra latência, taxa de atualização e economia de
RAM pagando em segurança. Nenhum dos dois é "o certo" — depende do que o produto
protege.

## 4. O que o SoftDevice Controller **não** faz (v3.4.0)

Da tabela de capacidades da doc do SDC — para o aluno não sair achando que tudo da
spec está no chip:

| Recurso da spec | SDC v3.4.0 |
|---|---|
| RTT with AA-only | suportado |
| RTT with Random Payload (32/64/96/128 bits) | suportado |
| **RTT with Sounding Sequence** | **não** |
| **Normalized Attack Detection Metric** | **não** |
| **CS AM Attack Resilience** | **não** |
| Channel Selection Algorithm #3b | suportado (#3c não) |

Segurança em CS é uma **combinação** do que o rádio faz, do que o algoritmo faz com os
dois tipos de medida, e do que a aplicação decide com o resultado. O chip entrega os
dois primeiros até onde a tabela diz; o terceiro é seu.

## 5. Exercício (10 min)

1. No lab 2, troque `.rtt_type` em `cs_config_get()` de `BT_CONN_LE_CS_RTT_TYPE_AA_ONLY`
   para `BT_CONN_LE_CS_RTT_TYPE_32_BIT_RANDOM` (o reflector precisa suportar — ele
   suporta; confira `CS capability exchange completed`). Recompile a DK. A distância
   mudou? O que mudou foi o que um atacante teria de adivinhar.
2. Compare os logs: a coluna `rtt` do lab 2 e a ausência dela no lab 3. Que produto
   você faria com cada um?

Gancho para o módulo de Segurança Embarcada (dia 5): as chaves que o `CS security
enable` usa vêm do pareamento BLE — e é lá que a história continua.

## Fontes

- nRF Connect SDK v3.4.0 — `ras_initiator/src/main.c` (`bt_conn_set_security`, `bt_le_cs_security_enable`, `cs_config_get`)
- Nordic, *LE Channel Sounding* — tabela "CS feature support for the SoftDevice Controller"
- Nordic, *Bluetooth: Channel Sounding Initiator with Inline PCT Transfer* — "Drawbacks of CS IPT"
- Bluetooth SIG, *Bluetooth Channel Sounding* (página de tecnologia) — segurança e o ataque de relé
```

- [ ] **Step 3: Verificar que o exercício compila**

No lab 2, aplicar a troca do exercício num build descartável e voltar:

```bash
cd /c/work/nrf-manaus-2
grep -n "BT_CONN_LE_CS_RTT_TYPE_32_BIT_RANDOM" /c/ncs/v3.4.0/zephyr/include/zephyr/bluetooth/conn.h
sed -i 's/BT_CONN_LE_CS_RTT_TYPE_AA_ONLY/BT_CONN_LE_CS_RTT_TYPE_32_BIT_RANDOM/' comms/channel_sounding_initiator/src/main.c
cd /c/ncs/v3.4.0
A=/c/work/nrf-manaus-2/comms/channel_sounding_initiator
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d $A/build_lm20_ex $A -- -DCONFIG_LAB_TAG_ADDR_VALUE=\"00:11:22:33:44:55\"
cd /c/work/nrf-manaus-2 && git checkout comms/channel_sounding_initiator/src/main.c
```

Expected: o `grep` acha o enum; o build passa; o `git checkout` deixa o lab 2 limpo (`git status` sem mudança em `src/main.c`). Se o enum tiver outro nome em `cs.h`, corrigir o README para o nome real.

- [ ] **Step 4: Commit**

```bash
cd /c/work/nrf-manaus-2
git add comms/channel_sounding_secure
git commit -F - <<'EOF'
channel_sounding_secure: roteiro de seguranca do CS (lab 4, sem firmware)

ACL cifrada e CS security enable no log do lab 2; RTT como limite fisico
contra rele; o que o IPT do lab 3 abre mao; e a tabela do que o SDC v3.4.0
nao suporta (sounding sequence, NADM, AM attack resilience).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---
### Task 8: Lab 5 — firmware: initiator RAS que despeja o IQ em CSV na serial

**Files:**
- Create: `comms/channel_sounding_iq_music/CMakeLists.txt`, `prj.conf`, `Kconfig`, `Kconfig.sysbuild`, `LICENSE`, `meu_tag.conf`, `.gitignore`, `src/main.c`

**Interfaces:**
- Consumes: `comms/channel_sounding_initiator/` como está após a Task 4 (filtro + intervalo já aplicados).
- Produces: na serial USB da DK (115200 8N1), por procedure, 75 linhas `IQ,...` e uma linha `CS,...`, neste formato exato (consumido pelas Tasks 10–13):

```
IQ,<ranging_counter>,<ap>,<canal 2..76>,<i_local>,<q_local>,<i_remote>,<q_remote>
CS,<ranging_counter>,<ap>,<tone_quality 1=OK 0=BAD>,<ifft_m>,<phase_slope_m>,<rtt_m>,<rtt_count>,<rtt_accumulated_half_ns>
```
Floats com `%.1f` nas linhas `IQ` e `%.3f` nas `CS`; `NAN` sai como `nan`. O log do sample continua existindo, mas vai para o **RTT** — a serial fica só com o CSV.

- [ ] **Step 1: Copiar o lab 2 (não o SDK) e limpar o que não vem**

```bash
cd /c/work/nrf-manaus-2
mkdir -p comms/channel_sounding_iq_music
cp -r comms/channel_sounding_initiator/{CMakeLists.txt,prj.conf,Kconfig,Kconfig.sysbuild,LICENSE,meu_tag.conf,.gitignore,src} comms/channel_sounding_iq_music/
sed -i 's/^CONFIG_LAB_TAG_ADDR_VALUE=.*/CONFIG_LAB_TAG_ADDR_VALUE=""/' comms/channel_sounding_iq_music/meu_tag.conf
sed -i 's#comms/channel_sounding_initiator/#comms/channel_sounding_iq_music/#' comms/channel_sounding_iq_music/.gitignore
sed -i 's/^project(channel_sound_ras_initiator)/project(channel_sounding_iq_music)/' comms/channel_sounding_iq_music/CMakeLists.txt
ls comms/channel_sounding_iq_music
```

Expected: `CMakeLists.txt  Kconfig  Kconfig.sysbuild  LICENSE  meu_tag.conf  prj.conf  src` (mais o `.gitignore`). Sem `rtt_only.conf`, `pbr_only.conf`, `README.md` nem `build_*`.

- [ ] **Step 2: Cabeçalho `ORIGEM:` de `src/main.c` — três divergências**

Substituir o bloco `ORIGEM:` do topo por (data real):

```c
/*
 * ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
 *   SDK     : nRF Connect SDK v3.4.0
 *   Upstream: nrf/samples/bluetooth/channel_sounding/ras_initiator/src/main.c
 *   Local   : C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_initiator/src/main.c
 *   Copiado : AAAA-MM-DD — curso nrf-manaus-2, modulo comms/channel_sounding_iq_music
 *             (via comms/channel_sounding_initiator, que ja traz as divergencias 1 e 2)
 *
 * Para conferir se divergiu do SDK:
 *   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/bluetooth/channel_sounding/ras_initiator/src/main.c
 *
 * DIVERGENCIA DO CURSO (tres):
 *   1. scan_init() e add_tag_address_filter(): filtro pelo endereco do TAG do aluno,
 *      modo AND. Mesmo codigo do comms/channel_sounding_initiator.
 *   2. main(): CONFIG_LAB_PROCEDURE_INTERVAL sobrescreve o intervalo de procedure.
 *   3. csv_dump_report(), chamada em ranging_data_cb() logo apos cs_de_calc():
 *      despeja o IQ por canal e as estimativas do cs_de em CSV na serial (printk),
 *      para o processamento no PC (tools/). O log do sample vai para o RTT.
 */
```

- [ ] **Step 3: `src/main.c` — a função de despejo e a chamada**

Inserir **antes** de `static void ranging_data_cb(struct bt_conn *conn, uint16_t ranging_counter, int err)`:

```c
/* ALTERADO PELO CURSO (nrf-manaus-2): despejo do IQ em CSV na serial.
 *
 * Uma linha IQ por canal (75: canais 2..76; 23..25 sao reservados e saem zerados,
 * como o cs_de os ve) e uma linha CS com as estimativas do proprio firmware, para
 * o PC reproduzir o cs_de e comparar com o MUSIC. Sai por printk, que com
 * CONFIG_LOG_PRINTK=n vai direto para a UART console; o log do sample vai para o
 * RTT (prj.conf), entao a serial fica so com o CSV.
 */
static void csv_dump_report(uint16_t ranging_counter, const cs_de_report_t *r)
{
	for (uint8_t ap = 0; ap < r->n_ap; ap++) {
		const cs_de_iq_tones_t *t = &r->iq_tones[ap];

		for (uint8_t ch = 0; ch < CS_DE_NUM_CHANNELS; ch++) {
			printk("IQ,%u,%u,%u,%.1f,%.1f,%.1f,%.1f\n", ranging_counter, ap,
			       ch + CHANNEL_INDEX_OFFSET, (double)t->i_local[ch],
			       (double)t->q_local[ch], (double)t->i_remote[ch],
			       (double)t->q_remote[ch]);
		}

		const cs_de_dist_estimates_t *d = &r->distance_estimates[ap];

		printk("CS,%u,%u,%u,%.3f,%.3f,%.3f,%u,%d\n", ranging_counter, ap,
		       r->tone_quality[ap] == CS_DE_TONE_QUALITY_OK ? 1 : 0, (double)d->ifft,
		       (double)d->phase_slope, (double)d->rtt, r->rtt_count,
		       r->rtt_accumulated_half_ns);
	}
}
```

Em `ranging_data_cb()`, localizar:

```c
	cs_de_quality_t quality = cs_de_calc(&m_cs_de_report);
```

e acrescentar logo abaixo:

```c
	/* ALTERADO PELO CURSO (nrf-manaus-2): ver csv_dump_report(). */
	csv_dump_report(ranging_counter, &m_cs_de_report);
```

- [ ] **Step 4: `prj.conf` — log para o RTT, serial só para o CSV**

Atualizar o cabeçalho `ORIGEM:` (`DIVERGENCIA DO CURSO (duas): CONFIG_BT_SCAN_ADDRESS_CNT=1 e o bloco "Log por RTT" no fim`). Acrescentar no **fim** do arquivo:

```
#
# --- Log por RTT, serial so para o CSV (adicionado pelo curso, nao esta no sample) ---
#
# O despejo de IQ sai por printk na UART console (uart20 da DK). Se o log do
# sample fosse para a mesma UART, as linhas se intercalariam no meio do CSV.
# Mesma solucao do edge_ai/03_central_uart: log no RTT, printk fora do log.
#
CONFIG_LOG=y
CONFIG_USE_SEGGER_RTT=y
CONFIG_LOG_BACKEND_RTT=y
CONFIG_LOG_BACKEND_UART=n
CONFIG_LOG_PRINTK=n
CONFIG_LOG_BUFFER_SIZE=4096
CONFIG_SEGGER_RTT_BUFFER_SIZE_UP=4096
```

- [ ] **Step 5: Compilar**

Preencher `meu_tag.conf` com o endereço da bancada e:

```bash
cd /c/ncs/v3.4.0
A=/c/work/nrf-manaus-2/comms/channel_sounding_iq_music
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d $A/build_lm20 $A -- -DEXTRA_CONF_FILE=meu_tag.conf
grep -E "^CONFIG_(LOG_BACKEND_RTT|LOG_PRINTK|CBPRINTF_FP_SUPPORT|UART_CONSOLE)=" $A/build_lm20/channel_sounding_iq_music/zephyr/.config
```

Expected: build sem erro; `CONFIG_LOG_BACKEND_RTT=y`, `CONFIG_CBPRINTF_FP_SUPPORT=y`, `CONFIG_UART_CONSOLE=y`, e **nenhuma** linha `CONFIG_LOG_PRINTK=y`.

- [ ] **Step 6: Bancada — o CSV íntegro na serial**

TAG com o reflector RAS (lab 1), na bateria. Gravar a DK (`west flash -d $A/build_lm20`). Capturar ~10 s da serial (115200) para um arquivo — com qualquer terminal, ou:

```bash
python -c "import serial,sys,time; s=serial.Serial(sys.argv[1],115200,timeout=1); t=time.time()+10; f=open('/c/Users/joaod/AppData/Local/Temp/claude/iq_raw.txt','wb')
while time.time()<t: f.write(s.read(4096))" COM22
grep -c "^IQ," /c/Users/joaod/AppData/Local/Temp/claude/iq_raw.txt
grep -c "^CS," /c/Users/joaod/AppData/Local/Temp/claude/iq_raw.txt
grep "^CS," /c/Users/joaod/AppData/Local/Temp/claude/iq_raw.txt | head -3
```

Expected: contagem de `IQ,` = 75 × contagem de `CS,` (linhas completas, sem log intercalado); as linhas `CS,` com `ifft`/`phase_slope`/`rtt` da ordem da distância real e `tone_quality` = 1 na maioria. Se aparecer qualquer linha `<inf>` ou `I:` no meio, o `CONFIG_LOG_BACKEND_UART=n` não entrou — voltar ao Step 4.

- [ ] **Step 7: Limpar o endereço e commitar**

```bash
cd /c/work/nrf-manaus-2
sed -i 's/^CONFIG_LAB_TAG_ADDR_VALUE=.*/CONFIG_LAB_TAG_ADDR_VALUE=""/' comms/channel_sounding_iq_music/meu_tag.conf
git add comms/channel_sounding_iq_music
git commit -F - <<'EOF'
channel_sounding_iq_music: initiator RAS que despeja o IQ por canal em CSV na serial

Lab 5, firmware: o lab 2 mais csv_dump_report() apos o cs_de_calc(). Uma
linha IQ por canal com I/Q local e remoto, e uma linha CS com as tres
estimativas do proprio firmware. Log vai para o RTT; a serial fica so
com o CSV (CONFIG_LOG_PRINTK=n).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---

### Task 9: Lab 5 — `cs_de_numpy.py`: port do `cs_de.c` da Nordic, com testes

**Files:**
- Create: `comms/channel_sounding_iq_music/tools/cs_de_numpy.py`, `tools/tests/conftest.py`, `tools/tests/test_cs_de_numpy.py`, `tools/requirements.txt`

**Interfaces:**
- Produces (todas com `numpy` e `NCH = 75`, `C = 299792458.0`, `DF = 1e6`):
  - `combine(i_local, q_local, i_remote, q_remote) -> np.ndarray[complex]` (75)
  - `rtt_m(rtt_accumulated_half_ns: int, rtt_count: int) -> float` (NaN se `rtt_count == 0`)
  - `phase_slope_m(comb) -> float` (NaN se negativa)
  - `ifft_mag(comb, nfft=512) -> np.ndarray` (nfft magnitudes)
  - `ifft_m(comb, nfft=512) -> float` (NaN se sem pico válido)
  - `estimates(comb, rtt_half_ns, rtt_count, nfft=512) -> dict` com chaves `ifft`, `phase_slope`, `rtt`
  - em `conftest.py`: `synthetic_comb(d_m, amp=1000.0) -> np.ndarray` (75, zeros nos índices 21–23)

- [ ] **Step 1: `requirements.txt` e o gerador sintético dos testes**

Criar `comms/channel_sounding_iq_music/tools/requirements.txt`:

```
numpy>=1.24
pyserial>=3.5
pytest>=7
```

Criar `comms/channel_sounding_iq_music/tools/tests/conftest.py`:

```python
# -*- coding: utf-8 -*-
"""Fixtures dos testes do lab 5.

synthetic_comb(d): IQ combinado (local x remoto) de um unico caminho a d metros,
sem ruido. Fase por canal: -4*pi*DF*d/c * n, que e o que o cs_de_phase_slope()
do cs_de.c inverte (dist = -c*atan2(...)/(4*pi*DF)). Os canais 23..25 (indices
21..23) sao reservados para advertising e saem zerados, como no firmware.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

C = 299792458.0
DF = 1e6
NCH = 75
GAPS = (21, 22, 23)


def synthetic_comb(d_m: float, amp: float = 1000.0) -> np.ndarray:
    n = np.arange(NCH)
    comb = amp * np.exp(-1j * 4 * np.pi * DF * d_m / C * n)
    comb[list(GAPS)] = 0
    return comb


@pytest.fixture
def comb_3m():
    return synthetic_comb(3.0)
```

- [ ] **Step 2: Testes que falham**

Criar `comms/channel_sounding_iq_music/tools/tests/test_cs_de_numpy.py`:

```python
# -*- coding: utf-8 -*-
import math

import numpy as np
import pytest

from conftest import synthetic_comb
import cs_de_numpy as de


def test_combine_is_complex_product():
    i_l, q_l, i_r, q_r = (np.array([1.0]), np.array([2.0]), np.array([3.0]), np.array([4.0]))
    comb = de.combine(i_l, q_l, i_r, q_r)
    # (1 + 2j) * (3 + 4j) = (3 - 8) + (4 + 6)j  — a mesma conta do cs_de_combined_iq_calculate()
    assert comb[0] == pytest.approx(-5 + 10j)


def test_rtt_formula_matches_cs_de_rtt():
    # 40 meias-ns acumuladas em 1 medida = 20 ns de ida e volta = 10 ns de voo = 2.998 m
    assert de.rtt_m(40, 1) == pytest.approx(2.99792458, abs=1e-6)
    assert de.rtt_m(-40, 1) == 0.0            # fmaxf(..., 0)
    assert math.isnan(de.rtt_m(0, 0))         # rtt_count == 0


def test_phase_slope_recovers_distance():
    assert de.phase_slope_m(synthetic_comb(3.0)) == pytest.approx(3.0, abs=0.01)
    assert de.phase_slope_m(synthetic_comb(0.5)) == pytest.approx(0.5, abs=0.01)


def test_phase_slope_negative_is_nan():
    comb = np.conj(synthetic_comb(3.0))       # inclinacao invertida => distancia negativa
    assert math.isnan(de.phase_slope_m(comb))


def test_ifft_recovers_distance_512():
    assert de.ifft_m(synthetic_comb(3.0), nfft=512) == pytest.approx(3.0, abs=0.15)
    assert de.ifft_m(synthetic_comb(8.0), nfft=512) == pytest.approx(8.0, abs=0.15)


def test_ifft_1024_is_finer():
    err512 = abs(de.ifft_m(synthetic_comb(5.0), nfft=512) - 5.0)
    err1024 = abs(de.ifft_m(synthetic_comb(5.0), nfft=1024) - 5.0)
    assert err1024 <= err512 + 0.01


def test_estimates_dict(comb_3m):
    e = de.estimates(comb_3m, rtt_half_ns=40, rtt_count=1)
    assert set(e) == {"ifft", "phase_slope", "rtt"}
    assert e["phase_slope"] == pytest.approx(3.0, abs=0.01)
```

- [ ] **Step 3: Rodar e ver falhar**

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools
python -m pip install -r requirements.txt
python -m pytest tests/test_cs_de_numpy.py -q
```

Expected: `ModuleNotFoundError: No module named 'cs_de_numpy'` (ou falha equivalente de import).

- [ ] **Step 4: O port**

Criar `comms/channel_sounding_iq_music/tools/cs_de_numpy.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Port em NumPy da biblioteca cs_de da Nordic — codigo do curso (nrf-manaus-2).

Reproduz, funcao a funcao, o que o firmware do initiator faz com o IQ:

    cs_de_combined_iq_calculate()  -> combine()
    cs_de_rtt()                    -> rtt_m()
    cs_de_phase_slope()            -> phase_slope_m()
    cs_de_ifft()                   -> ifft_m()   (calculate_ifft_mag + find_ifft_peak_index
                                                  + calculate_ifft_peak_index_to_distance)

Fonte portada: nRF Connect SDK v3.4.0, nrf/subsys/bluetooth/cs_de/cs_de.c
(licenca LicenseRef-Nordic-5-Clause; este arquivo e uma reimplementacao, nao
uma copia — os nomes das funcoes originais estao nos comentarios para o aluno
ler os dois lado a lado). Constantes de cs_de.c: SPEED_OF_LIGHT_M_PER_S,
CHANNEL_SPACING_HZ = 1e6, NORMAL_PEAK_TO_NULL = (NFFT + 75 - 1) // 75.

O firmware calcula em float32 (CMSIS-DSP); aqui e float64. Diferencas na 2a-3a
casa decimal sao esperadas — o cs_compare.py mede quanto.

Requisitos: numpy.
"""
from __future__ import annotations

import math

import numpy as np

C = 299792458.0        # SPEED_OF_LIGHT_M_PER_S
DF = 1e6               # CHANNEL_SPACING_HZ
NCH = 75               # CS_DE_NUM_CHANNELS


def combine(i_local, q_local, i_remote, q_remote) -> np.ndarray:
    """cs_de_combined_iq_calculate(): produto complexo local x remoto, por canal."""
    return (np.asarray(i_local, float) + 1j * np.asarray(q_local, float)) * (
        np.asarray(i_remote, float) + 1j * np.asarray(q_remote, float))


def rtt_m(rtt_accumulated_half_ns: int, rtt_count: int) -> float:
    """cs_de_rtt(): media das meias-ns acumuladas, metade e o tempo de voo."""
    if rtt_count <= 0:
        return math.nan
    rtt_avg_ns = (rtt_accumulated_half_ns * 0.5) / rtt_count
    tof_ns = rtt_avg_ns / 2.0
    return max(tof_ns * (C / 1e9), 0.0)


def phase_slope_m(comb: np.ndarray) -> float:
    """cs_de_phase_slope(): soma de comb[n] * conj(comb[n-1]); atan2 da soma."""
    comb = np.asarray(comb, complex)
    s = np.sum(comb[1:] * np.conj(comb[:-1]))
    dist = -(C * math.atan2(s.imag, s.real)) / (4.0 * math.pi * DF)
    return dist if dist >= 0 else math.nan


def ifft_mag(comb: np.ndarray, nfft: int = 512) -> np.ndarray:
    """calculate_ifft_mag(): conj -> FFT -> |.| / nfft (a IFFT via FFT do conjugado)."""
    buf = np.zeros(nfft, complex)
    buf[:NCH] = np.conj(np.asarray(comb, complex)[:NCH])
    return np.abs(np.fft.fft(buf)) / nfft


def _find_left_null(peak: int, mag: np.ndarray, nfft: int) -> int:
    """calculate_ifft_find_left_null(): heuristica de nulo a esquerda do pico."""
    ln = peak
    while True:
        nxt = nfft - 1 if ln == 0 else ln - 1
        if ((mag[ln] * 2 > mag[peak] or mag[ln] > 1.10 * mag[nxt])
                and mag[ln] * 10 > mag[peak] and nxt != peak):
            ln = nxt
        else:
            return ln


def _dist_to_left_null(peak: int, ln: int, nfft: int) -> int:
    """calculate_distance_to_left_null()."""
    return (nfft + peak - ln) if ln > peak else (peak - ln)


def _left_null_compensation(peak: int, mag: np.ndarray, nfft: int) -> int:
    """calculate_left_null_compensation_of_peak()."""
    normal_peak_to_null = (nfft + NCH - 1) // NCH
    ln = _find_left_null(peak, mag, nfft)
    if _dist_to_left_null(peak, ln, nfft) > normal_peak_to_null:
        if ln > peak:
            v = ln + normal_peak_to_null - nfft
            return v if v > 0 else peak
        return ln + normal_peak_to_null
    return peak


def _find_peak_index(mag: np.ndarray, nfft: int) -> int:
    """find_ifft_peak_index(): maximo, busca por pico mais curto, compensacao."""
    max_idx = int(np.argmax(mag))
    max_val = mag[max_idx]

    nw, nw_next = nfft - 2, nfft - 1
    shortest = max_idx
    short_found = False
    first_rise = False
    while nw != max_idx and not short_found:
        if mag[nw_next] < mag[nw]:
            if 2.5 * mag[nw] > max_val and first_rise:
                shortest = nw
                short_found = True
        else:
            first_rise = True
        nw = nw_next
        nw_next = (nw_next + 1) % nfft

    comp = shortest
    if comp < nfft - 2:
        comp = _left_null_compensation(shortest, mag, nfft)
    return comp


def _peak_to_distance(k: int, mag: np.ndarray, nfft: int) -> float:
    """calculate_ifft_peak_index_to_distance(): interpolacao parabolica do pico."""
    prompt = mag[k]
    early = mag[k - 1] if k != 0 else mag[nfft - 1]
    late = mag[k + 1] if k != nfft - 1 else mag[0]
    if prompt >= early and prompt >= late:
        t_hat = (late - early) / (4 * prompt - 2 * (early + late))
    else:
        t_hat = 0.0
    dist = ((k + t_hat) * C) / (2.0 * nfft * DF)
    if k >= nfft - 2 or dist < 0.0:
        return math.nan
    return dist


def ifft_m(comb: np.ndarray, nfft: int = 512) -> float:
    """cs_de_ifft(): magnitude da IFFT -> indice do pico -> distancia."""
    mag = ifft_mag(comb, nfft)
    return _peak_to_distance(_find_peak_index(mag, nfft), mag, nfft)


def estimates(comb: np.ndarray, rtt_half_ns: int, rtt_count: int, nfft: int = 512) -> dict:
    """O que cs_de_calc() preenche em distance_estimates (sem o 'best')."""
    return {
        "ifft": ifft_m(comb, nfft),
        "phase_slope": phase_slope_m(comb),
        "rtt": rtt_m(rtt_half_ns, rtt_count),
    }
```

- [ ] **Step 5: Rodar e ver passar**

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools
python -m pytest tests/test_cs_de_numpy.py -q
```

Expected: `7 passed`.

- [ ] **Step 6: Commit**

```bash
cd /c/work/nrf-manaus-2
git add comms/channel_sounding_iq_music/tools
git commit -F - <<'EOF'
channel_sounding_iq_music: port em NumPy do cs_de.c (ifft, phase_slope, rtt) com testes

Reimplementa funcao a funcao o cs_de da Nordic (SDK v3.4.0), inclusive a
busca de pico e a compensacao pelo nulo a esquerda do IFFT, para o aluno
reproduzir no PC o numero que o firmware imprime. Testes com IQ sintetico.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---

### Task 10: Lab 5 — `cs_csv.py`: o formato do firmware, lido de volta

**Files:**
- Create: `comms/channel_sounding_iq_music/tools/cs_csv.py`, `tools/tests/test_cs_csv.py`

**Interfaces:**
- Consumes: as linhas `IQ,`/`CS,` da Task 8.
- Produces:
  - `parse_line(line: str) -> tuple | None` — `("IQ", counter, ap, ch, i_l, q_l, i_r, q_r)` ou `("CS", counter, ap, tq, ifft, phase_slope, rtt, rtt_count, rtt_half_ns)`; `None` para qualquer outra linha.
  - `class Procedure` com atributos `counter: int`, `ap: int`, `i_local, q_local, i_remote, q_remote: np.ndarray` (75, índice = canal − 2), `tone_quality_ok: bool`, `fw: dict` (`ifft`, `phase_slope`, `rtt`), `rtt_count: int`, `rtt_half_ns: int`, e método `comb() -> np.ndarray`.
  - `read_procedures(path) -> list[Procedure]` — só procedures completas (75 `IQ` + 1 `CS` do mesmo `counter`/`ap`), em ordem.
  - `format_iq(...)`/`format_cs(...)` — inversos exatos do `printk` do firmware (usados pelos testes e fixtures).

- [ ] **Step 1: Testes que falham**

Acrescentar ao fim de `tools/tests/conftest.py` (o gerador de arquivo de captura sintético, usado também na Task 13):

```python
def write_procedure(f, counter, comb, tq=1, rtt_half_ns=40, rtt_count=1,
                    fw=(3.0, 3.0, 2.998)):
    """Escreve uma procedure completa no formato do firmware: 75 linhas IQ com
    local = comb e remoto = 1+0j (entao comb() == local), e a linha CS."""
    import cs_csv
    for idx in range(NCH):
        f.write(cs_csv.format_iq(counter, 0, idx + 2, comb[idx].real, comb[idx].imag, 1.0, 0.0))
    f.write(cs_csv.format_cs(counter, 0, tq, fw[0], fw[1], fw[2], rtt_count, rtt_half_ns))
```

Criar `comms/channel_sounding_iq_music/tools/tests/test_cs_csv.py`:

```python
# -*- coding: utf-8 -*-
import math

import numpy as np

from conftest import synthetic_comb, write_procedure
import cs_csv


def test_parse_iq_line():
    assert cs_csv.parse_line("IQ,17,0,2,-123.0,456.0,7.0,-8.0\n") == (
        "IQ", 17, 0, 2, -123.0, 456.0, 7.0, -8.0)


def test_parse_cs_line_with_nan():
    got = cs_csv.parse_line("CS,17,0,1,2.310,nan,2.700,12,-345\n")
    assert got[:5] == ("CS", 17, 0, 1, 2.31)
    assert math.isnan(got[5])
    assert got[6:] == (2.7, 12, -345)


def test_parse_ignores_noise():
    assert cs_csv.parse_line("*** Booting nRF Connect SDK ***\n") is None
    assert cs_csv.parse_line("IQ,garbage\n") is None
    assert cs_csv.parse_line("") is None


def test_read_procedures_roundtrip(tmp_path):
    p = tmp_path / "cap.csv"
    with open(p, "w") as f:
        f.write("*** Booting ***\n")
        write_procedure(f, 5, synthetic_comb(3.0))
        f.write("IQ,6,0,2,1.0,1.0,1.0,0.0\n")          # procedure 6 incompleta
        write_procedure(f, 7, synthetic_comb(1.0), tq=0)
    procs = cs_csv.read_procedures(p)
    assert [q.counter for q in procs] == [5, 7]
    assert procs[0].tone_quality_ok and not procs[1].tone_quality_ok
    assert procs[0].fw == {"ifft": 3.0, "phase_slope": 3.0, "rtt": 2.998}
    assert procs[0].rtt_half_ns == 40 and procs[0].rtt_count == 1
    # comb() == local * remoto; remoto = 1+0j no fixture, entao comb == local
    np.testing.assert_allclose(procs[0].comb(), synthetic_comb(3.0), atol=0.1)


def test_format_is_firmware_format():
    assert cs_csv.format_iq(3, 0, 2, 1.26, -2.0, 3.0, 4.0) == "IQ,3,0,2,1.3,-2.0,3.0,4.0\n"
    assert cs_csv.format_cs(3, 0, 1, 1.0, float("nan"), 2.0, 5, -7) == "CS,3,0,1,1.000,nan,2.000,5,-7\n"
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools && python -m pytest tests/test_cs_csv.py -q
```
Expected: falha de import de `cs_csv`.

- [ ] **Step 3: Implementar**

Criar `comms/channel_sounding_iq_music/tools/cs_csv.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formato CSV do firmware do lab 5 (channel_sounding_iq_music) — codigo do curso.

O que a serial entrega, por procedure de Channel Sounding (csv_dump_report() em
src/main.c):

    IQ,<counter>,<ap>,<canal 2..76>,<i_local>,<q_local>,<i_remote>,<q_remote>   x75
    CS,<counter>,<ap>,<tone_quality 1/0>,<ifft>,<phase_slope>,<rtt>,<rtt_count>,<rtt_half_ns>

Este modulo so le e escreve esse formato. Quem calcula e cs_de_numpy.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

NCH = 75
CH_OFFSET = 2          # CHANNEL_INDEX_OFFSET do firmware: indice 0 = canal 2


def _f(s: str) -> float:
    return float(s)    # aceita "nan", "inf", "-1.500"


def parse_line(line: str):
    parts = line.strip().split(",")
    try:
        if parts[0] == "IQ" and len(parts) == 8:
            return ("IQ", int(parts[1]), int(parts[2]), int(parts[3]),
                    _f(parts[4]), _f(parts[5]), _f(parts[6]), _f(parts[7]))
        if parts[0] == "CS" and len(parts) == 9:
            return ("CS", int(parts[1]), int(parts[2]), int(parts[3]),
                    _f(parts[4]), _f(parts[5]), _f(parts[6]), int(parts[7]), int(parts[8]))
    except ValueError:
        return None
    return None


def format_iq(counter, ap, ch, i_l, q_l, i_r, q_r) -> str:
    return f"IQ,{counter},{ap},{ch},{i_l:.1f},{q_l:.1f},{i_r:.1f},{q_r:.1f}\n"


def format_cs(counter, ap, tq, ifft, phase_slope, rtt, rtt_count, rtt_half_ns) -> str:
    return (f"CS,{counter},{ap},{tq},{ifft:.3f},{phase_slope:.3f},{rtt:.3f},"
            f"{rtt_count},{rtt_half_ns}\n")


@dataclass
class Procedure:
    counter: int
    ap: int
    i_local: np.ndarray = field(default_factory=lambda: np.zeros(NCH))
    q_local: np.ndarray = field(default_factory=lambda: np.zeros(NCH))
    i_remote: np.ndarray = field(default_factory=lambda: np.zeros(NCH))
    q_remote: np.ndarray = field(default_factory=lambda: np.zeros(NCH))
    seen: set = field(default_factory=set)
    tone_quality_ok: bool = False
    fw: dict = field(default_factory=dict)
    rtt_count: int = 0
    rtt_half_ns: int = 0
    complete: bool = False

    def comb(self) -> np.ndarray:
        return (self.i_local + 1j * self.q_local) * (self.i_remote + 1j * self.q_remote)


def read_procedures(path) -> list[Procedure]:
    """Le o arquivo capturado e devolve so as procedures completas, em ordem."""
    pending: dict[tuple[int, int], Procedure] = {}
    done: list[Procedure] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            rec = parse_line(raw)
            if rec is None:
                continue
            key = (rec[1], rec[2])
            proc = pending.setdefault(key, Procedure(counter=rec[1], ap=rec[2]))
            if rec[0] == "IQ":
                idx = rec[3] - CH_OFFSET
                if 0 <= idx < NCH:
                    proc.i_local[idx], proc.q_local[idx] = rec[4], rec[5]
                    proc.i_remote[idx], proc.q_remote[idx] = rec[6], rec[7]
                    proc.seen.add(idx)
            else:
                proc.tone_quality_ok = rec[3] == 1
                proc.fw = {"ifft": rec[4], "phase_slope": rec[5], "rtt": rec[6]}
                proc.rtt_count, proc.rtt_half_ns = rec[7], rec[8]
                if len(proc.seen) == NCH:
                    proc.complete = True
                    done.append(proc)
                del pending[key]
    return done
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools && python -m pytest tests/test_cs_csv.py -q
```
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
cd /c/work/nrf-manaus-2
git add comms/channel_sounding_iq_music/tools
git commit -F - <<'EOF'
channel_sounding_iq_music: cs_csv.py le e escreve o formato do firmware, com testes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---
### Task 11: Lab 5 — `cs_capture.py`: serial → arquivo

**Files:**
- Create: `comms/channel_sounding_iq_music/tools/cs_capture.py`, `tools/tests/test_cs_capture.py`

**Interfaces:**
- Consumes: `cs_csv.parse_line`.
- Produces: CLI `python cs_capture.py [--port COMx] [--seconds N] --out capturas/<nome>.csv`; função pura `filter_lines(lines) -> iterator[str]` (só linhas que `parse_line` aceita) e `looks_like_ours(lines) -> bool` (≥ 2 linhas válidas).

- [ ] **Step 1: Testes que falham**

Criar `tools/tests/test_cs_capture.py`:

```python
# -*- coding: utf-8 -*-
import cs_capture


LINES = [
    "*** Booting nRF Connect SDK v3.4.0 ***\n",
    "IQ,1,0,2,1.0,2.0,3.0,4.0\n",
    "lixo\n",
    "CS,1,0,1,3.000,3.000,2.998,1,40\n",
]


def test_filter_lines_keeps_only_valid():
    assert list(cs_capture.filter_lines(LINES)) == [LINES[1], LINES[3]]


def test_looks_like_ours():
    assert cs_capture.looks_like_ours(LINES)
    assert not cs_capture.looks_like_ours(["87799 67,9602,535,1,-3,0\n"] * 10)   # CSV do lab 03 do Edge AI
    assert not cs_capture.looks_like_ours([])
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools && python -m pytest tests/test_cs_capture.py -q
```
Expected: falha de import de `cs_capture`.

- [ ] **Step 3: Implementar**

Criar `tools/cs_capture.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grava o CSV de IQ do firmware do lab 5 direto da serial — codigo do curso.

    python cs_capture.py --seconds 30 --out capturas/1m.csv
    python cs_capture.py --port COM22 --seconds 30 --out capturas/3m.csv

Sem --port, procura a porta que esta enviando linhas IQ,/CS, (a DK enumera duas
COM; o CSV sai numa delas — na bancada do curso, a segunda). Guarda so as linhas
que o cs_csv.parse_line() aceita; o banner de boot fica de fora. Conta
procedures completas (75 IQ + 1 CS) e mostra a taxa.

Requisitos: pyserial (ja vem no toolchain do nRF Connect).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cs_csv

BAUD = 115200


def filter_lines(lines):
    for line in lines:
        if cs_csv.parse_line(line) is not None:
            yield line if line.endswith("\n") else line + "\n"


def looks_like_ours(lines) -> bool:
    return sum(1 for _ in filter_lines(lines)) >= 2


def morrer(msg: str) -> None:
    print(f"erro: {msg}", file=sys.stderr)
    sys.exit(1)


def autodetect(espera: float = 3.0) -> str:
    from serial import Serial, SerialException
    from serial.tools import list_ports

    candidatas = [p.device for p in list_ports.comports()]
    if not candidatas:
        morrer("nenhuma porta serial encontrada")
    print(f"procurando a porta com dados ({', '.join(candidatas)}) ...")
    for porta in candidatas:
        try:
            with Serial(porta, BAUD, timeout=0.3) as s:
                fim = time.time() + espera
                vistas = []
                while time.time() < fim:
                    vistas.append(s.readline().decode("utf-8", "replace"))
                    if looks_like_ours(vistas):
                        print(f"porta encontrada: {porta}")
                        return porta
        except (SerialException, OSError):
            continue
    morrer("nenhuma porta esta enviando linhas IQ,/CS,.\n"
           "       confira: a DK esta gravada com o channel_sounding_iq_music? o TAG esta\n"
           "       ligado com o reflector do lab 1? o endereco em meu_tag.conf esta certo?")


def capturar(porta: str, segundos: float, saida: Path) -> None:
    from serial import Serial

    saida.parent.mkdir(parents=True, exist_ok=True)
    n_iq = n_cs = 0
    inicio = time.time()
    with Serial(porta, BAUD, timeout=1) as s, open(saida, "w", encoding="utf-8") as f:
        while time.time() - inicio < segundos:
            line = s.readline().decode("utf-8", "replace")
            rec = cs_csv.parse_line(line)
            if rec is None:
                continue
            f.write(line if line.endswith("\n") else line + "\n")
            if rec[0] == "IQ":
                n_iq += 1
            else:
                n_cs += 1
                dt = time.time() - inicio
                print(f"\r{n_cs} procedures, {n_cs / dt:.1f}/s, ultima: ifft={rec[4]:.2f} "
                      f"phase_slope={rec[5]:.2f} rtt={rec[6]:.2f} m", end="")
    print()
    procs = cs_csv.read_procedures(saida)
    print(f"gravado em {saida}: {n_cs} linhas CS, {n_iq} linhas IQ, "
          f"{len(procs)} procedures completas")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="COMx (default: procura sozinho)")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    porta = args.port or autodetect()
    capturar(porta, args.seconds, args.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools && python -m pytest tests/test_cs_capture.py -q
```
Expected: `2 passed`.

- [ ] **Step 5: Bancada — capturar 20 s**

Com a DK gravada (Task 8) e o TAG na bateria:

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools
python cs_capture.py --seconds 20 --out ../capturas/teste.csv
```

Expected: acha a porta sozinho, imprime a taxa (~5 procedures/s no default do sample) e termina com `N procedures completas`, N ≥ 50.

- [ ] **Step 6: `.gitignore` das capturas e commit**

Acrescentar ao `comms/channel_sounding_iq_music/.gitignore`:

```
# Capturas do aluno — nao versionadas
capturas/
```

```bash
cd /c/work/nrf-manaus-2
git add comms/channel_sounding_iq_music
git commit -F - <<'EOF'
channel_sounding_iq_music: cs_capture.py grava o CSV da serial, achando a porta sozinho

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---

### Task 12: Lab 5 — vendorizar o MUSIC do `skig/waves` e escrever o adaptador

**Files:**
- Create: `tools/music/__init__.py`, `tools/music/cs_music.py` (cópia), `tools/music/constants.py` (cópia), `tools/music/LICENSE` (cópia), `tools/music/ORIGEM.md`, `tools/music_adapter.py`, `tools/tests/test_music_adapter.py`

**Interfaces:**
- Consumes: `cs_music.py` do waves — na leitura do repositório, expõe `compute_music_spectrum(phase_data, amplitude_data)` e `calculate_distance_from_music(phase_data, amplitude_data) -> float` (metros), com `phase_data: Dict[int, float]` (rad) e `amplitude_data: Dict[int, float]` (dB) indexados por canal, mínimo 4 canais. **Confirmar os nomes no arquivo copiado** (Step 2) e ajustar o adaptador se divergirem.
- Produces: `music_adapter.music_m(comb: np.ndarray, ch_offset: int = 2) -> float` (metros, NaN se < 4 canais válidos).

- [ ] **Step 1: Clonar e copiar, registrando o commit**

```bash
W=/c/Users/joaod/AppData/Local/Temp/claude/waves
rm -rf $W && git clone --depth 1 https://github.com/skig/waves $W
cd $W && git rev-parse HEAD && git log -1 --format=%cd --date=short
cd /c/work/nrf-manaus-2
mkdir -p comms/channel_sounding_iq_music/tools/music
cp $W/toolset/processing/cs_music.py comms/channel_sounding_iq_music/tools/music/cs_music.py
cp $W/toolset/constants.py comms/channel_sounding_iq_music/tools/music/constants.py
cp $W/LICENSE comms/channel_sounding_iq_music/tools/music/LICENSE
head -3 comms/channel_sounding_iq_music/tools/music/LICENSE
grep -n "^def \|^from \|^import \|^_[A-Z_]* = " comms/channel_sounding_iq_music/tools/music/cs_music.py
```

Expected: o hash e a data do commit (anotar para o `ORIGEM.md`); `LICENSE` começando por `MIT License`; o `grep` listando os `def` (esperados `compute_music_spectrum` e `calculate_distance_from_music`), a linha `from toolset.constants import SPEED_OF_LIGHT, BLE_CS_STEP_1MHZ` e as constantes `_N_SIGNALS`, `_SUBARRAY_LEN`, `_MAX_DELAY_NS`.

- [ ] **Step 2: A única alteração no arquivo copiado — o import**

Em `tools/music/cs_music.py`, trocar a linha

```python
from toolset.constants import SPEED_OF_LIGHT, BLE_CS_STEP_1MHZ
```

por

```python
# ALTERADO PELO CURSO (nrf-manaus-2): o upstream importa de toolset.constants;
# aqui o constants.py vem copiado ao lado (ver ORIGEM.md).
from .constants import SPEED_OF_LIGHT, BLE_CS_STEP_1MHZ
```

Criar `tools/music/__init__.py` vazio. Se o `grep` do Step 1 tiver mostrado outros imports de `toolset.`, copiar o módulo correspondente do clone para `music/` e tratar do mesmo jeito, registrando no `ORIGEM.md`.

- [ ] **Step 3: `ORIGEM.md`**

Criar `tools/music/ORIGEM.md` (preencher hash e datas):

```markdown
# Origem e uso — `music/`

Cópia do estimador MUSIC do projeto **waves**, uma ferramenta open source de análise
de Channel Sounding para o nRF54L15 DK.

| | |
|---|---|
| Upstream | https://github.com/skig/waves |
| Arquivos | `toolset/processing/cs_music.py`, `toolset/constants.py`, `LICENSE` |
| Branch / commit | `main` · `<hash>` (<data do commit>) |
| Copiado em | <AAAA-MM-DD> |
| Licença | MIT (arquivo `LICENSE` ao lado, do upstream) |
| Alteração local | Em `cs_music.py`: só a linha de import (`toolset.constants` → `.constants`), marcada. O algoritmo está intocado. |

## Para que serve

`cs_de_numpy.py` reproduz o que o firmware da Nordic faz: IFFT sobre os tons, pico =
caminho mais curto. A resolução bruta do IFFT sobre 75 MHz de banda é de ~2 m por
bin, e a interpolação do pico é o que a leva a decímetros. **MUSIC** (MUltiple SIgnal
Classification) é o método clássico de super-resolução: em vez de procurar o pico da
transformada, decompõe a matriz de covariância dos tons em subespaço de sinal e de
ruído e varre os atrasos possíveis procurando onde o vetor de direção é ortogonal ao
ruído. Resolve caminhos mais próximos entre si do que o IFFT consegue.

## O que o arquivo faz (lido do fonte)

- Entrada: dois dicionários indexados por canal — fase (rad) e amplitude (dB).
  Mínimo de 4 canais.
- Monta o vetor complexo `10**(amp/20) * exp(j*fase)` por canal.
- Covariância por *spatial smoothing* (subarrays sobrepostos, tamanho `N // 2`).
- Autodecomposição; subespaço de ruído = todos menos `_N_SIGNALS = 1` autovetores.
- Pseudo-espectro `1 / |a(τ)ᴴ Eₙ|²` numa grade de 512 atrasos entre 0 e
  `_MAX_DELAY_NS = 500`.
- Devolve a distância do pico.

## O que o curso acrescenta em volta (`../music_adapter.py`)

O IQ que o nosso firmware entrega é o **produto** local × remoto — a fase acumulada
na **ida e na volta**. O `waves` foi escrito para outra fonte de dados; o adaptador
converte o IQ combinado em fase/amplitude por canal e ajusta a convenção de
ida-e-volta. O teste `tests/test_music_adapter.py` com IQ sintético a 3 m é o que
fixa essa convenção — se o resultado sair 6 m, o adaptador divide por 2; se sair
espelhado, conjuga. Nada disso toca o `cs_music.py`.

## Limites conhecidos

- `_N_SIGNALS = 1`: assume um caminho dominante. Em multipath forte o pico pode
  cair no caminho refletido.
- Sem calibração de fase entre initiator e reflector — o `cs_de` também não faz.
- Antena única: o TAG tem duas, mas o firmware do lab usa um caminho.
```

- [ ] **Step 4: Teste do adaptador que falha**

Criar `tools/tests/test_music_adapter.py`:

```python
# -*- coding: utf-8 -*-
import math

import numpy as np
import pytest

from conftest import synthetic_comb
import music_adapter


@pytest.mark.parametrize("d", [1.0, 3.0, 7.5])
def test_music_recovers_distance(d):
    assert music_adapter.music_m(synthetic_comb(d)) == pytest.approx(d, abs=0.2)


def test_music_needs_four_channels():
    comb = np.zeros(75, complex)
    comb[:3] = 1.0
    assert math.isnan(music_adapter.music_m(comb))
```

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools && python -m pytest tests/test_music_adapter.py -q
```
Expected: falha de import de `music_adapter`.

- [ ] **Step 5: O adaptador**

Criar `tools/music_adapter.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapta o IQ combinado do firmware ao MUSIC do waves — codigo do curso.

music/cs_music.py (MIT, ver music/ORIGEM.md) quer fase e amplitude por canal. O
nosso IQ e o produto local x remoto: a fase da IDA E DA VOLTA. Por isso a distancia
que o MUSIC devolve para esse dado corresponde ao caminho de ida e volta e e
dividida por ROUND_TRIP_DIVISOR. CONJUGATE espelha o sinal da fase se a convencao
de atraso do waves for a oposta a do cs_de. Os dois valores sao fixados pelo
tests/test_music_adapter.py com IQ sintetico — nao por inspecao.
"""
from __future__ import annotations

import math

import numpy as np

from music.cs_music import calculate_distance_from_music

CH_OFFSET = 2
ROUND_TRIP_DIVISOR = 2.0
CONJUGATE = False
MIN_CHANNELS = 4


def music_m(comb: np.ndarray, ch_offset: int = CH_OFFSET) -> float:
    comb = np.asarray(comb, complex)
    if CONJUGATE:
        comb = np.conj(comb)
    phase, amp = {}, {}
    for idx, z in enumerate(comb):
        if z == 0:
            continue                      # canais reservados (23..25) saem zerados
        phase[idx + ch_offset] = float(np.angle(z))
        amp[idx + ch_offset] = float(20.0 * np.log10(abs(z)))
    if len(phase) < MIN_CHANNELS:
        return math.nan
    d = calculate_distance_from_music(phase, amp)
    if d is None or not math.isfinite(d):
        return math.nan
    return float(d) / ROUND_TRIP_DIVISOR
```

- [ ] **Step 6: Rodar; fixar a convenção pelo resultado**

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools && python -m pytest tests/test_music_adapter.py -q
```

Decisão pelo que o teste de 3 m imprimir (ver `pytest -q -k "3.0"` com `--tb=short`):

Com os defaults do adaptador (`ROUND_TRIP_DIVISOR = 2.0`, `CONJUGATE = False`):

| Resultado do caso 3 m | Significado | Ajuste em `music_adapter.py` |
|---|---|---|
| ≈ 3.0 | o waves devolve ida-e-volta (6 m) e o adaptador divide por 2 | nada — `4 passed` |
| ≈ 1.5 | o waves já devolve a distância de ida | `ROUND_TRIP_DIVISOR = 1.0` |
| ≈ 0, ou ≈ `_MAX_DELAY_NS·c/2` = 75 m (pico na borda da grade) | convenção de sinal do atraso é a oposta | `CONJUGATE = True`, repetir a tabela |
| `TypeError`/`AttributeError`/`ImportError` | nomes ou assinaturas do arquivo copiado divergem da leitura | ajustar a chamada no adaptador ao que o `grep` do Step 1 mostrou (nunca o `cs_music.py`) |

Repetir até `4 passed`. Registrar no `ORIGEM.md` (linha "O que o curso acrescenta em volta") os valores finais de `ROUND_TRIP_DIVISOR` e `CONJUGATE`.

- [ ] **Step 7: Commit**

```bash
cd /c/work/nrf-manaus-2
git add comms/channel_sounding_iq_music/tools
git commit -F - <<'EOF'
channel_sounding_iq_music: MUSIC do skig/waves vendorizado (MIT) e adaptador para o IQ combinado

cs_music.py e constants.py copiados com LICENSE e ORIGEM.md (commit
registrado); unica alteracao e o import. music_adapter.py converte o IQ
local x remoto em fase/amplitude por canal e fixa a convencao de ida e
volta pelo teste com IQ sintetico.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---

### Task 13: Lab 5 — `cs_compare.py`: a tabela dos quatro estimadores

**Files:**
- Create: `tools/cs_compare.py`, `tools/tests/test_cs_compare.py`

**Interfaces:**
- Consumes: `cs_csv.read_procedures`, `cs_de_numpy.estimates`, `music_adapter.music_m`.
- Produces: `summarize(procs, nfft=512) -> list[dict]` (uma linha por procedure com `counter`, `tq`, `ifft_fw`, `ifft_np`, `d_ifft`, `ps_fw`, `ps_np`, `rtt_fw`, `rtt_np`, `music`); `stats(rows) -> dict[str, tuple[mean, std, n]]` para `ifft_fw`, `ps_fw`, `rtt_fw`, `music` sobre linhas com `tq == 1`; CLI `python cs_compare.py capturas/1m.csv [--nfft 512] [--csv saida.csv]`.

- [ ] **Step 1: Teste que falha**

Criar `tools/tests/test_cs_compare.py`:

```python
# -*- coding: utf-8 -*-
import numpy as np
import pytest

from conftest import synthetic_comb, write_procedure
import cs_csv
import cs_de_numpy as de
import cs_compare


@pytest.fixture
def captura_3m(tmp_path):
    p = tmp_path / "3m.csv"
    comb = synthetic_comb(3.0)
    fw = (de.ifft_m(comb), de.phase_slope_m(comb), de.rtt_m(40, 1))
    with open(p, "w") as f:
        for k in range(3):
            write_procedure(f, 10 + k, comb, fw=fw)
        write_procedure(f, 13, synthetic_comb(0.7), tq=0, fw=fw)   # tone quality BAD: fora das estatisticas
    return p


def test_summarize_reproduces_firmware(captura_3m):
    rows = cs_compare.summarize(cs_csv.read_procedures(captura_3m))
    assert [r["counter"] for r in rows] == [10, 11, 12, 13]
    for r in rows[:3]:
        assert abs(r["d_ifft"]) < 0.02            # NumPy == firmware (o CSV tem 3 casas)
        assert r["ps_np"] == pytest.approx(3.0, abs=0.01)
        assert r["rtt_np"] == pytest.approx(2.998, abs=0.001)
        assert r["music"] == pytest.approx(3.0, abs=0.2)


def test_stats_skip_bad_tone_quality(captura_3m):
    rows = cs_compare.summarize(cs_csv.read_procedures(captura_3m))
    st = cs_compare.stats(rows)
    assert st["music"][2] == 3                    # n = so as tres com tq == 1
    assert st["music"][0] == pytest.approx(3.0, abs=0.2)
    assert st["ifft_fw"][1] == pytest.approx(0.0, abs=1e-9)
```

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools && python -m pytest tests/test_cs_compare.py -q
```
Expected: falha de import de `cs_compare`.

- [ ] **Step 2: Implementar**

Criar `tools/cs_compare.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quatro estimadores sobre o mesmo IQ — codigo do curso (nrf-manaus-2).

    python cs_compare.py capturas/1m.csv
    python cs_compare.py capturas/3m.csv --nfft 512 --csv saida_3m.csv

Para cada procedure completa do arquivo (cs_capture.py):
  - ifft_fw / ps_fw / rtt_fw : o que o FIRMWARE imprimiu (cs_de da Nordic, float32)
  - ifft_np / ps_np / rtt_np : o mesmo algoritmo reimplementado em NumPy (cs_de_numpy.py)
  - d_ifft                   : ifft_np - ifft_fw  (se nao for ~0, o port nao reproduz o chip)
  - music                    : MUSIC do waves sobre o MESMO IQ (music_adapter.py)

No fim, media, desvio e n por estimador, so das procedures com tone quality OK.
--nfft deve ser o CONFIG_BT_CS_DE_NFFT_SIZE do firmware (512 no lab).
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

import cs_csv
import cs_de_numpy as de
import music_adapter

COLS = ["counter", "tq", "ifft_fw", "ifft_np", "d_ifft", "ps_fw", "ps_np",
        "rtt_fw", "rtt_np", "music"]
STAT_COLS = ["ifft_fw", "ps_fw", "rtt_fw", "music"]


def summarize(procs, nfft: int = 512) -> list[dict]:
    rows = []
    for p in procs:
        comb = p.comb()
        e = de.estimates(comb, p.rtt_half_ns, p.rtt_count, nfft)
        rows.append({
            "counter": p.counter,
            "tq": 1 if p.tone_quality_ok else 0,
            "ifft_fw": p.fw["ifft"], "ifft_np": e["ifft"],
            "d_ifft": e["ifft"] - p.fw["ifft"],
            "ps_fw": p.fw["phase_slope"], "ps_np": e["phase_slope"],
            "rtt_fw": p.fw["rtt"], "rtt_np": e["rtt"],
            "music": music_adapter.music_m(comb),
        })
    return rows


def stats(rows) -> dict:
    out = {}
    for c in STAT_COLS:
        v = np.array([r[c] for r in rows if r["tq"] == 1 and math.isfinite(r[c])])
        out[c] = (float(v.mean()), float(v.std()), int(v.size)) if v.size else (math.nan, math.nan, 0)
    return out


def imprimir(rows, st) -> None:
    fmt = "{:>7} {:>2} " + " ".join(["{:>8}"] * 8)
    print(fmt.format(*COLS))
    for r in rows:
        print(fmt.format(r["counter"], r["tq"], *[f"{r[c]:.3f}" for c in COLS[2:]]))
    print()
    print("{:>10} {:>8} {:>8} {:>4}".format("estimador", "media", "desvio", "n"))
    for c in STAT_COLS:
        m, s, n = st[c]
        print(f"{c:>10} {m:8.3f} {s:8.3f} {n:4d}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("captura", type=Path)
    ap.add_argument("--nfft", type=int, default=512, choices=[512, 1024, 2048])
    ap.add_argument("--csv", type=Path, help="tambem grava a tabela por procedure neste arquivo")
    args = ap.parse_args()

    procs = cs_csv.read_procedures(args.captura)
    if not procs:
        raise SystemExit(f"nenhuma procedure completa em {args.captura}")
    rows = summarize(procs, args.nfft)
    imprimir(rows, stats(rows))
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            w.writerows(rows)
        print(f"tabela gravada em {args.csv}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Rodar e ver passar — a suíte inteira**

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools && python -m pytest -q
```
Expected: `20 passed` (7 + 5 + 2 + 4 + 2).

- [ ] **Step 4: Bancada — o port reproduz o chip?**

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools
python cs_compare.py ../capturas/teste.csv | tail -8
```

Expected: `d_ifft` com módulo < 0.05 m na maioria das procedures (float32 do chip vs float64; se for sistematicamente maior, o port tem um erro — comparar passo a passo com `cs_de.c`); `ps_np ≈ ps_fw` e `rtt_np == rtt_fw` a 3 casas; coluna `music` da ordem da distância real. Anotar as quatro médias.

- [ ] **Step 5: Commit**

```bash
cd /c/work/nrf-manaus-2
git add comms/channel_sounding_iq_music/tools
git commit -F - <<'EOF'
channel_sounding_iq_music: cs_compare.py poe os quatro estimadores lado a lado, com testes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---

### Task 14: Lab 5 — medição de referência e README

**Files:**
- Create: `comms/channel_sounding_iq_music/README.md`
- Modify: nada

**Interfaces:**
- Consumes: tudo das Tasks 8–13.

- [ ] **Step 1: Bancada — três distâncias com trena, 30 s cada**

TAG (reflector RAS) na bateria, DK com o firmware do lab 5, linha de visada, trena:

```bash
cd /c/work/nrf-manaus-2/comms/channel_sounding_iq_music/tools
python cs_capture.py --seconds 30 --out ../capturas/ref_1m.csv
python cs_capture.py --seconds 30 --out ../capturas/ref_3m.csv
python cs_capture.py --seconds 30 --out ../capturas/ref_5m.csv
for d in 1 3 5; do echo "== ${d} m =="; python cs_compare.py ../capturas/ref_${d}m.csv | tail -5; done
```

Anotar, por distância, média e desvio de `ifft_fw`, `ps_fw`, `rtt_fw`, `music` e `n`. Esses números vão para o README como **medição de referência da bancada, com data** — não como promessa.

- [ ] **Step 2: README**

Criar `comms/channel_sounding_iq_music/README.md` (preencher a tabela com o medido no Step 1 e a data):

```markdown
# Channel Sounding · Lab 5 — O IQ no PC: reproduzir o chip e tentar um algoritmo melhor

A Nordic diz, com todas as letras, que o algoritmo do `ras_initiator` é referência:
*"provided just as reference algorithms — we recommend you to work with a third party
algorithm partner if you require more sophisticated algorithms."* O que ela **não** diz é
que o algoritmo vem em fonte — `subsys/bluetooth/cs_de/cs_de.c`, 328 linhas — e que o
IQ cru está numa estrutura que o próprio sample monta. Este lab tira o IQ do chip e
faz duas coisas com ele no PC:

1. **Reproduz o número do firmware** com o mesmo algoritmo, em NumPy. *Entendi o que o
   chip faz?*
2. **Roda um algoritmo de super-resolução** (MUSIC) sobre o mesmo IQ. *O que muda?*

O ganho é **medido, não prometido**. Veja a tabela no fim.

> **Origem.** Firmware: cópia do `ras_initiator` do **nRF Connect SDK v3.4.0** via o
> lab 2, com uma divergência a mais (`csv_dump_report()`), marcada em `src/main.c`.
> Python: `tools/cs_de_numpy.py` é reimplementação do `cs_de.c` da Nordic (código do
> curso); `tools/music/` é cópia do projeto **skig/waves** (MIT) — ver
> [`tools/music/ORIGEM.md`](tools/music/ORIGEM.md).

## Hardware

| Peça | Papel |
|---|---|
| **nRF54L15-TAG** | reflector RAS do lab 1, na bateria |
| **nRF54LM20-DK** | initiator que, além de medir, despeja o IQ na serial USB |
| **PC** | Python 3.11 com `numpy`, `pyserial`, `pytest` |

## Passo 1 — o firmware

O mesmo `meu_tag.conf` dos labs 2 e 3. TAG fora do `DEBUG OUT`.

```
copy ..\channel_sounding_initiator\meu_tag.conf meu_tag.conf
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/channel_sounding_iq_music/build_lm20 C:/work/nrf-manaus-2/comms/channel_sounding_iq_music -- -DEXTRA_CONF_FILE=meu_tag.conf
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/channel_sounding_iq_music/build_lm20
```

O que sai na serial (115200 8N1), por procedure — 75 linhas `IQ` e uma `CS`:

```
IQ,42,0,2,-812.0,455.0,301.0,-903.0
IQ,42,0,3,-799.0,480.0,318.0,-897.0
...
CS,42,0,1,1.023,1.087,1.349,12,180
   │  │ │   │     │     │    │  └─ rtt acumulado (meias-ns), como o cs_de recebe
   │  │ │   │     │     │    └──── quantos steps de RTT entraram
   │  │ │   │     │     └───────── rtt (m)          ┐
   │  │ │   │     └─────────────── phase_slope (m)  ├ o que o FIRMWARE calculou
   │  │ │   └───────────────────── ifft (m)         ┘
   │  │ └───────────────────────── tone quality (1 = OK)
   │  └─────────────────────────── antenna path
   └────────────────────────────── ranging counter
```

O log do sample (`Filtrando pelo tag`, `CS procedures enabled`, ...) vai para o
**RTT**, não para a serial — senão intercalaria com o CSV. Se precisar dele,
`JLinkRTTLogger -Device CORTEX-M33 -RTTSearchRanges "0x20000000 0x80000" -USB <serial da DK>`.

## Passo 2 — o ambiente Python

```
cd tools
python -m pip install -r requirements.txt
python -m pytest -q          # 20 passed: o port e o adaptador batem com IQ sintetico
```

## Passo 3 — capturar

```
python cs_capture.py --seconds 30 --out ../capturas/1m.csv
```

Acha a porta sozinho, mostra a taxa e a última estimativa, e guarda só as linhas
válidas. Repita para 3 m e 5 m, com trena. `capturas/` não é versionada.

## Passo 4 — comparar

```
python cs_compare.py ../capturas/1m.csv
```

```
counter tq  ifft_fw  ifft_np   d_ifft    ps_fw    ps_np   rtt_fw   rtt_np    music
     42  1    1.023    1.021   -0.002    1.087    1.087    1.349    1.349    0.98x
...
 estimador    media   desvio    n
   ifft_fw    x.xxx    x.xxx   nn
     ps_fw    x.xxx    x.xxx   nn
    rtt_fw    x.xxx    x.xxx   nn
     music    x.xxx    x.xxx   nn
```

Três colunas para olhar primeiro:

- **`d_ifft`** — NumPy menos firmware. Tem que ser ~0 (o chip calcula em float32).
  Se não for, o port não reproduz o chip, e nada do resto vale.
- **`rtt_np` = `rtt_fw`** a três casas: é uma média, não há o que divergir.
- **`music`** — o mesmo IQ, outro algoritmo. Compare média **e desvio** com `ifft_fw`.

## Passo 5 — ler o algoritmo

Abra `tools/cs_de_numpy.py` e `C:\ncs\v3.4.0\nrf\subsys\bluetooth\cs_de\cs_de.c`
lado a lado. Cada função do Python tem no docstring o nome da função C que reproduz:

| C (`cs_de.c`) | Python | O que faz |
|---|---|---|
| `cs_de_combined_iq_calculate` | `combine` | produto complexo local × remoto: soma as fases da ida e da volta |
| `cs_de_rtt` | `rtt_m` | média das meias-ns, metade é o voo, × c |
| `cs_de_phase_slope` | `phase_slope_m` | fase entre canais adjacentes → inclinação → distância |
| `calculate_ifft_mag` | `ifft_mag` | IFFT via FFT do conjugado |
| `find_ifft_peak_index` | `_find_peak_index` | maior pico; depois procura um **mais curto** que seja ≥ 40 % dele |
| `calculate_left_null_compensation_of_peak` | `_left_null_compensation` | se o nulo à esquerda está longe demais, o pico foi alargado por multipath — recua |
| `calculate_ifft_peak_index_to_distance` | `_peak_to_distance` | interpolação parabólica do pico |

Duas perguntas para discutir: por que a busca por um pico "mais curto" (o que
acontece numa reflexão forte)? E por que a compensação pelo nulo (o que o multipath
faz com a largura do pico)?

## Medição de referência da bancada (<data>)

Linha de visada, 30 s por distância, `n` procedures com tone quality OK. Média ± desvio
em metros:

| Trena | `ifft_fw` | `phase_slope` | `rtt` | `music` | n |
|---|---|---|---|---|---|
| 1,0 m | | | | | |
| 3,0 m | | | | | |
| 5,0 m | | | | | |

O que ler nela: o **desvio** de cada estimador é a sua repetibilidade; a diferença da
média para a trena é o **viés**. O `rtt` é o mais grosseiro; o `phase_slope` é o mais
simples; o `ifft` é o que a Nordic escolhe como `best`; o `music` é o que este lab
acrescenta. Nenhum deles é "o teto da tecnologia" — são quatro algoritmos sobre um
caminho de antena, sem calibração.

## Onde ir a partir daqui

- `--nfft 1024` no `cs_compare.py` **não** melhora a resolução — só a interpolação
  (zero-padding). Confira.
- `music/cs_music.py` assume **um** caminho (`_N_SIGNALS = 1`). Com dois, o que muda
  na obstrução do lab 2?
- O TAG tem **duas antenas**. `CONFIG_BT_RAS_MAX_ANTENNA_PATHS=2` no par abre um
  segundo `ap` no CSV — o `cs_compare.py` já itera por `ap`.
- Parceiros de algoritmo da Nordic (Metirionic e outros) é o caminho de produto.

## A divergência a mais deste lab

**`src/main.c` — `csv_dump_report()`**, chamada em `ranging_data_cb()` logo após
`cs_de_calc()`. Despeja `m_cs_de_report` — a estrutura que o próprio sample monta — em
CSV por `printk`. `prj.conf` manda o log para o RTT (`CONFIG_LOG_BACKEND_UART=n`,
`CONFIG_LOG_PRINTK=n`) para a serial ficar só com o CSV.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/subsys/bluetooth/cs_de/cs_de.c`, `nrf/include/bluetooth/cs_de.h`
- Nordic, *Bluetooth Channel Sounding Distance Estimation* (doc da biblioteca `cs_de`)
- Nordic, webinar *Bluetooth Channel Sounding: From theory to practice on the nRF54L Series and Android* (a posição sobre algoritmos de referência e parceiros)
- Nordic DevZone #128575, *Channel Sounding ranging algorithm* — `cs_de` é experimental
- skig/waves — https://github.com/skig/waves (MIT): `toolset/processing/cs_music.py`
- Bluetooth SIG, *Bluetooth Channel Sounding: A step towards 10-cm ranging accuracy...* — super-resolução vs IFFT (não verificado por nós; é o que a tabela acima mede)
```

- [ ] **Step 3: Limpar e commitar**

```bash
cd /c/work/nrf-manaus-2
sed -i 's/^CONFIG_LAB_TAG_ADDR_VALUE=.*/CONFIG_LAB_TAG_ADDR_VALUE=""/' comms/channel_sounding_iq_music/meu_tag.conf
git status --short comms/channel_sounding_iq_music
git add comms/channel_sounding_iq_music
git commit -F - <<'EOF'
channel_sounding_iq_music: README com a medicao de referencia da bancada

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

Expected do `git status`: nenhum arquivo em `capturas/` nem `build_*` listado.

---

### Task 15: Índice do módulo e pré-requisitos

**Files:**
- Modify: `comms/README.md`, `PREREQUISITOS.md` (seção "Módulo Comunicação (`comms/`)")

- [ ] **Step 1: `comms/README.md` — tabela de labs**

Substituir a tabela "Labs planejados" e o título por:

```markdown
## Labs

| Lab | Descrição | Kit | Status |
|-----|-----------|-----|--------|
| [`channel_sounding_reflector/`](channel_sounding_reflector/) | **CS 1** — Reflector RAS no TAG, CS default da Nordic. Log por RTT (o TAG não tem UART). Fragmentos da demo com smartphone | nRF54L15-TAG | ✅ |
| [`channel_sounding_initiator/`](channel_sounding_initiator/) | **CS 2** — Initiator RAS no LM20-DK: `ifft`, `phase_slope` e `rtt` lado a lado. Filtra pelo endereço do TAG do aluno (mesmo `meu_tag.conf` do Edge AI). Experimento com trena e obstrução | nRF54LM20-DK | ✅ |
| [`channel_sounding_ipt_reflector/`](channel_sounding_ipt_reflector/) + [`channel_sounding_ipt_initiator/`](channel_sounding_ipt_initiator/) | **CS 3** — O mesmo par com IPT: a contribuição do reflector viaja na fase do tom, não por GATT. A coluna `rtt` some; `time_delta` cai | TAG + LM20-DK | ✅ |
| [`channel_sounding_secure/`](channel_sounding_secure/) | **CS 4** — Roteiro: ACL cifrada, CS Security Enable, RTT como limite físico contra relé, o que o IPT abre mão, o que o SDC não suporta | par do CS 2 | ✅ (conforme o tempo) |
| [`channel_sounding_iq_music/`](channel_sounding_iq_music/) | **CS 5** — IQ para o PC: port do `cs_de` em NumPy reproduz o chip; MUSIC (skig/waves, MIT) sobre o mesmo IQ; medição de referência com trena | LM20-DK + PC | ✅ (conforme o tempo) |
| `wifi_provisioning/` | Provisionamento de dispositivo Wi-Fi 6+ com circuito companion | nRF54LM20-DK + nRF7002-EBII | planejado |
| `wifi_tcp_client/` | Envio de dados via socket TCP/IP sobre Wi-Fi | nRF54LM20-DK + nRF7002-EBII | planejado |
| `ntn_nbiot/` | Comunicação NB-IoT via satélite (NTN) — teste ao vivo dependente de janela de passada | nRF9151-SMA-DK | planejado |

### Channel Sounding — ordem de ensino

```
CS 1  reflector no TAG            "o dispositivo simples"        grava por fio, RTT
CS 2  initiator no DK             "RTT e PBR lado a lado"        trena, obstrucao
CS 3  o mesmo par com IPT         "por onde viaja o dado"        a coluna que some
CS 4  seguranca                   "o que o radio garante"        conforme o tempo
CS 5  o IQ no PC                  "o algoritmo e da aplicacao"   conforme o tempo
```

O TAG é gravado por fio, encaixado no `DEBUG OUT` da DK, duas vezes (reflector RAS
no CS 1, reflector IPT no CS 3). Enquanto ele está encaixado, o debugger da DK aponta
para ele — gravar "a DK" nessa hora grava o TAG. Sem DFU/OTA neste módulo.

Os seis TAGs da sala anunciam o mesmo UUID e o mesmo nome: todo initiator do módulo
filtra pelo endereço BLE do TAG do aluno, que é o **mesmo do Edge AI** (vem do chip,
não do firmware). Um `meu_tag.conf` serve para os três initiators.
```

E na seção "Tópicos teóricos", trocar a primeira linha por:

```markdown
- BLE 6.0 e Channel Sounding: RTT × PBR, initiator/reflector/subevent, Ranging Service, RAS × IPT como trade-off, segurança, e "o algoritmo é camada de aplicação"
```

- [ ] **Step 2: `PREREQUISITOS.md` — seção comms**

Substituir a linha `- **nRF Toolbox** no smartphone — opcionalmente Pixel 10 como Channel Sounding initiator.` por:

```markdown
- **Python 3.11** com `numpy`, `pyserial` e `pytest` para o lab CS 5 (`pip install -r comms/channel_sounding_iq_music/tools/requirements.txt`). O mesmo ambiente do Edge AI serve.
- **Trena** (≥ 5 m) por bancada, para os labs CS 2 e CS 5.
- **SEGGER J-Link** (vem com o toolchain) — o log do TAG só sai por RTT.
- Smartphone com Channel Sounding (Pixel 9/10 com Android 16 QPR2+, nRF Toolbox ≥ 4.1.4) é **opcional** e só para a demo do instrutor; o Galaxy S26 exige ajustes dos dois lados (ver `comms/channel_sounding_reflector/s26.conf`).
```

- [ ] **Step 3: Conferir os links do índice**

```bash
cd /c/work/nrf-manaus-2
for d in channel_sounding_reflector channel_sounding_initiator channel_sounding_ipt_reflector channel_sounding_ipt_initiator channel_sounding_secure channel_sounding_iq_music; do test -f comms/$d/README.md && echo "ok $d" || echo "FALTA $d"; done
grep -c "channel_sounding" README.md
```

Expected: seis `ok`; o README raiz já cita `comms/channel_sounding_initiator` no exemplo de build (≥ 1).

- [ ] **Step 4: Commit**

```bash
cd /c/work/nrf-manaus-2
git add comms/README.md PREREQUISITOS.md
git commit -F - <<'EOF'
comms: indice dos cinco labs de Channel Sounding e pre-requisitos do modulo

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LurGbU8nMm9xZDvXheodHb
EOF
```

---

## Fora deste plano

- `edge_ai/hex/build_all.py` não cobre `comms/`; um `comms/hex/` com os `.hex` prontos por lab é trabalho à parte.
- Deck `doc/comms/M2-01_Channel_Sounding.pptx` e figuras (§8 da spec) — material, não código; plano próprio.
- Fork do nRF Toolbox para o S26 (§7 da spec) — só com o telefone em mãos.
