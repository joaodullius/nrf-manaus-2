# Wi-Fi · Lab 9 — telemetria por socket TCP

> **Antes de tudo: o console troca de VCOM.** Com a nRF7002-EB II acoplada, o overlay
> do shield move o console (e o `shell-uart`) da `uart20` para a `uart30` — e isso
> troca também a porta serial do PC: sem shield, o log sai na **segunda** VCOM da DK;
> com o shield (como neste lab), sai na **primeira**. É a mesma troca medida e
> confirmada no lab 6 (`comms/06_wifi_shell/README.md`, Passo 2) — este lab usa o
> mesmo shield e o mesmo overlay, então o comportamento é idêntico. Na dúvida, abra as
> duas portas seriais da DK e veja qual responde.

Este é o lab central da frente de Wi-Fi: firmware original do curso (não vem do SDK)
que conecta na rede da sala (a mesma associação do lab 7), monta uma amostra de
telemetria a cada `CONFIG_LAB_INTERVALO_MS` e manda pelo transporte de `src/
transporte.h` — aqui, TCP puro. Um servidor em Python (`tools/wifi_server.py`) roda no
PC, recebe as amostras e manda comandos de LED de volta pela mesma conexão. A tese do
lab é a travessia: o mesmo formato de payload (`src/payload.c` no firmware,
`tools/payload_ref.py` no PC) tem que bater dos dois lados — é o que o roteiro de
bancada abaixo fecha manualmente, porque o teste automático que provaria isso
(`tools/tests/test_payload_c.py`) fica pulado nesta bancada por falta de compilador de
host (ver `tools/README.md`).

## Hardware

| Peça | Papel |
|---|---|
| **nRF54LM20-DK** (variante B, `nrf54lm20b`) | roda o firmware; host do Wi-Fi |
| **nRF7002 EB-II** | shield companion Wi-Fi 6, encaixado no header de expansão |
| **PC** | roda `tools/wifi_server.py` e a rede Wi-Fi da sala |

Com o shield acoplado, `sw3` some do overlay nesta versão do SDK: o botão do lab é o
`sw0`, e o LED comandado pelo servidor é o `led1` (alias do devicetree — **LED1** na
serigrafia da placa; a nRF54LM20-DK numera os LEDs a partir de 0, igual à devicetree,
sem deslocamento).

## Rede da sala e servidor — digitados no terminal, gravados em settings

O binário não carrega credencial nem IP. No primeiro boot, o firmware pede tudo na
console (115200 8N1; com a EB II acoplada é a **primeira** VCOM), nesta ordem:

```
=== Rede Wi-Fi ===
SSID da rede:
Senha (Enter vazio = rede aberta):
IP do servidor no PC (ex.: 192.168.0.100):
Porta do servidor (Enter = 9000):
```

A senha é ecoada em claro (WPA2: 8 a 63 caracteres). O IP é validado como IPv4; a
porta padrão é `CONFIG_LAB_PORTA` (9000 neste lab). Uma entrada inválida repete só
aquele campo; não há prompt periódico. Descubra o IP do PC na rede da sala com
`ipconfig` antes de ligar o kit.

SSID e senha vão para a biblioteca `wifi_credentials` (backend settings, ZMS na
`storage_partition`); IP e porta ficam nas chaves `lab_rede/ip` e `lab_rede/porta`. A
conexão segue por `NET_REQUEST_WIFI_CONNECT_STORED`, como no sample da Nordic. Nos
boots seguintes o firmware mostra o que tem gravado e espera uma tecla:

```
Rede gravada: "<ssid>" (com senha), servidor <ip>:<porta>
Enter (ou nada em 5 s) usa essa; qualquer outra tecla troca:
```

Um `west flash` ou `nrfutil device program` normal **não apaga** a `storage_partition`:
rede e servidor sobrevivem à regravação. `nrfutil device recover` (ou `west flash
--erase`) apaga tudo, e o prompt volta no boot seguinte.

O código é `src/lab_rede.c` e `src/lab_rede.h` (arquivos do curso, copiados iguais nos
labs 7, 9, 11, 12 e 13): `main()` chama `lab_rede_ler(true, CONFIG_LAB_PORTA)` antes de
qualquer outra coisa, e `src/transporte.c` lê `lab_rede_ip()` e `lab_rede_porta()`.

## Atenção: o coredump despeja a senha da rede em texto claro

`CONFIG_DEBUG_COREDUMP` fica ligado de propósito — se o firmware travar, o despejo da
RAM sai inteiro pela serial, e isso inclui o SSID e a senha da rede em texto claro: o
`wifi_credentials` com backend settings guarda a credencial sem cifrar, tanto na RAM
quanto na `storage_partition`. Na prática: nunca colar um log de coredump inteiro num
ticket, chat ou repositório sem apagar essa parte antes. Num produto de verdade a
escolha seria outra — desligar `CONFIG_DEBUG_COREDUMP` ou usar um backend que não vá
para a serial.

## O payload, campo a campo

Uma linha JSON por amostra, terminada em `\n` (formato em `tools/payload_ref.py`,
espelhado em `src/payload.c`):

```
{"seq":7,"uptime_ms":1234,"temp_c":25.37,"rssi_dbm":-52,"botao":false}
```

| Campo | Tipo | Significado |
|---|---|---|
| `seq` | inteiro | contador da amostra, incrementado a cada envio (telemetria periódica ou botão) |
| `uptime_ms` | inteiro | `k_uptime_get()` no instante da leitura |
| `temp_c` | número | temperatura do die, em grau. O firmware manda em centésimos de grau (`temp_cc`, inteiro) para não precisar de ponto flutuante na serialização embarcada; `payload_ref.montar()` converte para grau com duas casas |
| `rssi_dbm` | inteiro | RSSI da associação Wi-Fi atual |
| `botao` | booleano | `true` só na amostra disparada pelo `sw0`; `false` nas periódicas |

> **O intervalo real bate com o configurado — mas só desde 2026-09-07.** Até essa data a
> thread de recepção segurava o mutex do transporte durante o segundo inteiro do `poll`,
> e a de telemetria esperava por ele: com `CONFIG_LAB_INTERVALO_MS=2000` o ciclo medido
> era de **3000 ms**. O `poll` passou a ser feito em fatias de 50 ms, soltando o mutex
> entre elas, e o ciclo caiu para **2050 ms** (o mesmo defeito existia no transporte MQTT
> do lab 10: 3002 → 2053 ms). Só apareceu porque os três transportes foram medidos lado a
> lado — o HTTP não tinha o problema, porque dorme fora da região crítica, e parecia
> "mais rápido".

Duas sentinelas de `src/main.c` valem saber ao ler os dados na bancada: `temp_cc =
INT16_MIN` (aparece como `-327,68` em `temp_c`) significa sensor de temperatura
indisponível; `rssi_dbm = -128` significa falha ao consultar o status do Wi-Fi. Nenhum
dos dois é uma leitura real — são o firmware sinalizando que não conseguiu ler.

## O servidor (`tools/wifi_server.py`)

```bash
cd comms/09_wifi_tcp/tools
pip install -r requirements.txt   # só pytest, para os testes
python wifi_server.py --porta 9000
```

Imprime cada amostra numa linha alinhada e lê o teclado: `l` liga o LED1, `d` apaga,
`q` sai. A classe `Servidor` (`porta`, `ao_receber`) é o que os testes exercitam sem
hardware: `porta=0` deixa o SO escolher uma porta livre e `porta_real` devolve a
efetiva, o que torna o teste determinístico; `ao_receber` é chamado com o dicionário de
cada amostra válida (linhas que `payload_ref.parse()` rejeita são descartadas, sem
derrubar a conexão). `enviar_comando(texto)` manda `texto + "\n"` para a conexão aceita
mais recentemente — vira um no-op silencioso se não houver cliente no momento.

O servidor aceita mais de uma conexão ao mesmo tempo de propósito: uma queda de
associação Wi-Fi não fecha a conexão de forma limpa (sem `FIN`, às vezes sem nem um
`RST`), e o firmware reconecta sozinho antes que o servidor tenha qualquer chance de
perceber que a conexão antiga morreu. `aceitar_para_sempre()` só aceita e delega cada
conexão para uma thread própria — nunca espera uma conexão terminar para aceitar a
próxima — e cada conexão tem um limite de leitura (`--tempo-limite-leitura`, 90 s por
padrão) sem receber nada antes de ser dada como morta e fechada.

**Esse limite tem que ficar acima de `CONFIG_LAB_INTERVALO_MS`** (o intervalo de
telemetria do firmware, Kconfig do lab, até 60 s de intervalo permitido): quem
aumentar um dos dois precisa olhar o outro, senão o servidor derruba uma conexão
saudável só porque está mais espaçada que o limite de leitura.

## Os três gestos do lab

1. **O botão.** Apertar o `sw0` manda uma amostra imediata, fora do intervalo
   periódico, com `"botao":true` — dá para ver no servidor sem esperar o próximo tick.
   **Validado na bancada em 2026-09-07**, e o `uptime_ms` é a prova: as periódicas caíram
   em 180058 e 182060 ms, e a do botão em **181399** — no meio do intervalo, não é uma
   periódica marcada.

   Detalhe que rende em aula: o `rssi_dbm` cai de −48 para **−55** exatamente nas amostras
   `BOTAO`. É a mão do operador perto da antena — RSSI demonstrado sem instrumento nenhum.
2. **O comando de LED.** Teclar `l` no servidor manda a linha `LED 1`; o firmware
   (`thread_recepcao()`) lê essa linha do transporte e acende o **LED1**. `d` manda
   `LED 0` e apaga. Validado na bancada — no console do kit saem
   `LED1 aceso (comando do servidor)` e `LED1 apagado (comando do servidor)`.

   > **A tecla é `l` minúsculo, a letra ele de "liga" — não o algarismo `1`.** O menu do
   > servidor imprime `l liga o LED1`, onde a letra e o número ficam lado a lado e são
   > quase idênticos em fonte de terminal. Teclas não reconhecidas são **descartadas em
   > silêncio**. E há um agravante medido: se o LED já estiver apagado, o `d` funciona sem
   > nada mudar na placa — o mecanismo parece quebrado quando está certo. Na dúvida, ligue
   > antes de desligar.
3. **A queda de conexão.** Afastar o kit até a conexão cair (e voltar) mostra o
   `seq` pulando — um buraco na sequência — porque as amostras enviadas durante a
   queda se perdem; o firmware reconecta sozinho com espera crescente
   (`abrir_com_backoff()`, em `src/main.c`) e a telemetria retoma sem intervenção. É o
   ponto do lab: a queda é esperada e tratada, não um bug.

## Arquitetura do software — os blocos e o fluxo

Esta seção descreve o firmware bloco a bloco. Serve de base para o diagrama do material.

### Os blocos

```
                       +---------------------------------------+
                       |               main()                  |
                       |  orquestra a partida e larga 3 threads |
                       +---------------------------------------+
                                        |
       +----------------+---------------+---------------+
       |                |                               |
+--------------+  +--------------+              +----------------+
| thread_      |  | thread_botao |              | thread_        |
| telemetria   |  |              |              | recepcao       |
| a cada       |  | espera o     |              | le do servidor |
| INTERVALO_MS |  | semaforo     |              | e move o LED1  |
+--------------+  +--------------+              +----------------+
       |                |                               |
       +--------+-------+                               |
                v                                       |
       +------------------+                             |
       | montar_e_enviar()|                             |
       +------------------+                             |
                |                                       |
       +--------+--------+                              |
       v                 v                              |
+-------------+   +--------------+                      |
| sensores    |   | payload.c    |                      |
| temp / RSSI |   | monta o JSON |                      |
+-------------+   +--------------+                      |
                          |                             |
                          v                             v
                 +-----------------------------------------+
                 |          transporte.h  (a interface)     |
                 |  abrir / enviar / receber / fechar       |
                 +-----------------------------------------+
                                    |
                 +------------------+------------------+
                 |                  |                  |
           +-----------+     +-----------+     +-----------+
           |   TCP     |     |   HTTP    |     |   MQTT    |
           +-----------+     +-----------+     +-----------+
              (so UMA entra no binario, escolhida no Kconfig)
                                    |
                                    v
                    pilha de rede do Zephyr -> Wi-Fi -> PC
```

| Bloco | Arquivo | Papel |
|---|---|---|
| Orquestrador | `src/main.c`, `main()` | registra callbacks, configura GPIO, espera rede, abre transporte, **inicia as três threads** |
| Telemetria | `thread_telemetria()` | dorme `CONFIG_LAB_INTERVALO_MS` e chama `montar_e_enviar(false)` |
| Botão | `thread_botao()` | bloqueia no semáforo `botao_apertado`; ao ser liberado chama `montar_e_enviar(true)` |
| Recepção | `thread_recepcao()` | lê linhas do transporte e acende/apaga o **LED1** |
| Montagem | `montar_e_enviar()` | lê os sensores, incrementa `seq`, chama `payload_montar()` e `transporte_enviar()` |
| Serialização | `src/payload.c` | **só** transforma a struct em linha JSON — não sabe o que é rede |
| Transporte | `src/transporte.h` + `transporte.c` | uma interface, **três** implementações |

As três threads têm a mesma prioridade (7) e pilha de 3072 B, e são criadas paradas
(`K_THREAD_DEFINE(..., -1)`): quem as inicia é o `main()`, **depois** de a rede estar de pé.
É por isso que nenhuma amostra é montada antes de haver para onde mandar.

### O fluxo de partida (e as linhas de log que ele produz)

| # | O que `main()` faz | Log |
|---|---|---|
| 0 | `lab_rede_ler()`: lê rede e servidor do settings ou pede no terminal | `=== Rede Wi-Fi ===` |
| 1 | registra os callbacks de `NET_EVENT_WIFI_CONNECT_RESULT` e `NET_EVENT_IPV4_DHCP_BOUND` | — |
| 2 | configura `sw0` (interrupção) e `led1` (saída, apagado) | — |
| 3 | espera o **supplicant** ficar pronto (`CONFIG_WIFI_READY_LIB`, até 10 s) | `Aguardando o supplicant do Wi-Fi ficar pronto...` |
| 4 | pede a conexão com a credencial armazenada (`NET_REQUEST_WIFI_CONNECT_STORED`) | `Conexao Wi-Fi solicitada` |
| 5 | bloqueia no semáforo `ip_pronto` | `Aguardando IP por DHCP...` |
| 6 | (callback) associação concluída | `Conectado ao Wi-Fi` |
| 7 | (callback) DHCP entregou endereço → libera o semáforo | `IP obtido por DHCP: <ip>` |
| 8 | abre o transporte com espera crescente | `Conectado em <ip>:<porta>` |
| 9 | inicia as três threads | (começam as amostras) |

O passo 3 existe por um achado de bancada: pedir conexão antes de o `wpa_supplicant` ficar
pronto falha com `-ENOTSUP` (−134). Não aparecia no build nem na revisão de código.

### Os três caminhos em operação

**Telemetria (periódico).** `thread_telemetria` → `montar_e_enviar(false)` → lê temperatura
do die e RSSI → `payload_montar()` → `transporte_enviar()` → dorme `INTERVALO_MS`.

**Botão (assíncrono).** A interrupção do `sw0` **não** monta amostra nenhuma: o handler só
faz `k_sem_give(&botao_apertado)` e retorna. Quem monta é `thread_botao`, já fora do
contexto de interrupção. É o padrão de sempre — trabalho pesado (ler sensor, serializar,
mandar pela rede) nunca acontece dentro de uma ISR. As duas threads chamam **a mesma**
`montar_e_enviar()`, só mudando o campo `botao`; por isso a amostra do botão fura o ritmo
sem desalinhar o contador (`seq` é `atomic_t`).

**Recepção (servidor → kit).** `thread_recepcao` fica em `transporte_receber()` com espera
de 1 s, e trata cada retorno segundo o **contrato de erro** que os três transportes
respeitam:

| Retorno | Significa | O que a thread faz |
|---|---|---|
| `> 0` | chegou uma linha | interpreta `LED 1` / `LED 0` |
| `0` | nada chegou em 1 s | **não é erro** — conexão presumida viva, tenta de novo |
| `-ECONNRESET` | o outro lado fechou | reconecta |
| `-EBADMSG` | erro de **aplicação**, não de conexão (só o HTTP produz) | loga e segue — reabrir não resolveria |
| outro `< 0` | erro de rede | reconecta |

Esse contrato é o que permite ao `main.c` ignorar qual transporte está compilado.

### Reconexão: por que existe um mutex

`abrir_com_backoff()` nunca desiste — espera crescente (4 s → 8 s → 16 s → 30 s de teto).
Como **duas** threads podem detectar a queda ao mesmo tempo (a de envio e a de recepção),
`reconectar_transporte()` é protegida por `reconexao_mutex`.

E há um caso sutil, achado na bancada: `transporte_receber()` pode devolver `-ENOTCONN`
porque **outra** thread já está no meio de abrir a conexão nova. Reconectar aí abriria uma
**segunda** conexão por cima da que está nascendo — foi exatamente isso que fazia o comando
de LED ir parar numa conexão abandonada. Por isso esse caso espera 100 ms e tenta de novo,
em vez de reconectar.

### A travessia — o ponto do lab

O formato do payload existe **duas vezes**: `src/payload.c` no firmware e
`tools/payload_ref.py` no PC. Não há geração de código nem schema compartilhado — os dois
são escritos à mão e têm de concordar. É isso que o roteiro de bancada verifica na prática
e o que `tools/tests/` cobre automaticamente.

## Passo 1 — compilar e gravar

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/09_wifi_tcp/build_lm20 C:/work/nrf-manaus-2/comms/09_wifi_tcp -- -D09_wifi_tcp_SHIELD="nrf7002eb2" -D09_wifi_tcp_SNIPPET=nrf70-wifi
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/09_wifi_tcp/build_lm20
```

Sem compilar: `comms/hex/09_wifi_tcp_lm20.hex` é este build, pronto para gravar (não
carrega credencial — a rede e o servidor entram pelo terminal, seção anterior).

As duas opções levam o prefixo `09_wifi_tcp_` — o nome da imagem no sysbuild. Para
`SHIELD` e `SNIPPET` o prefixo é **obrigatório**: sem ele, os dois valeriam para
**todas** as imagens do sysbuild, o que pode quebrar as que não usam esse shield. Para
qualquer `CONFIG_*` (como o `CONFIG_LAB_PORTA` do lab 10) o prefixo é **opcional** — sem
ele a opção já vale para a aplicação principal, de propósito, para o mesmo comando
funcionar com ou sem sysbuild.

O curso escreve sempre com prefixo, em todas as linhas de build da frente. Não é exigência
da ferramenta: é para o aluno ler uma linha só e saber, sem decorar exceção, a qual
imagem cada opção se aplica.

Resumo de memória:

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 566772 B | 2036 KB | 27,19% |
| RAM | 192200 B | 511 KB | 36,73% |

## Testes automáticos (PC, sem hardware)

```bash
cd comms/09_wifi_tcp/tools
python -m pytest -q
```

`19 passed, 8 skipped` nesta bancada: os 8 pulados são a travessia C↔Python
(`tests/test_payload_c.py`), por falta de compilador de host utilizável — ver
`tools/README.md` para a ordem de busca e a mensagem de skip. Os testes de
`wifi_server.py` (`tests/test_server.py`) sobem um `Servidor(porta=0)` de verdade e
conversam com ele por um socket local, cobrindo o caminho feliz e os casos ruins:
linha partida em dois pedaços, duas amostras no mesmo pacote, linha malformada, cliente
que desconecta de forma limpa no meio, cliente derrubado com `RST` abrupto (via
`SO_LINGER` zero, sem hardware — o caso realista de uma queda de Wi-Fi), conferindo que
o servidor continua aceitando conexões novas depois, mesmo com a conexão derrubada
ainda não coletada, e conexão silenciosa (nem `FIN` nem `RST`) derrubada depois do
tempo limite de leitura, com um limite pequeno passado só para o teste.

## Roteiro de bancada

1. `python wifi_server.py --porta 9000` no PC.
2. Gravar a DK (Passo 1) e, no primeiro boot, digitar SSID, senha, o IP do PC e a
   porta 9000 no terminal.
3. Conferir: amostras chegando a cada `CONFIG_LAB_INTERVALO_MS` (padrão 2 s), `seq`
   incrementando.
4. Apertar o **botão 1** (`sw0`) → amostra imediata, com `"botao":true`. **Validado em
   2026-09-07** — ver "Os três gestos do lab".
5. Teclar `l` no servidor → **LED1** acende; `d` → apaga.
6. Andar com o kit até a conexão cair e voltar → **buraco no `seq`**, o ponto do lab.
7. Encostar o dedo no chip → `temp_c` sobe.
8. **Fechar a travessia C↔Python na mão** (o teste automático que provaria isso está
   pulado nesta bancada): copiar uma linha real impressa pelo servidor no passo 3 e
   rodar

   ```bash
   cd comms/09_wifi_tcp/tools
   python - <<'PY'
   import json
   import payload_ref

   linha = input("Cole aqui uma linha real vinda do dispositivo: ")
   amostra = payload_ref.parse(linha)
   assert amostra is not None, "a linha nao passou no parser -- formato quebrado"

   vetores = json.loads(open("tests/vetores_payload.json", encoding="utf-8").read())
   campos_do_contrato = set(vetores["casos"][0]["esperado"].keys())
   assert set(amostra.keys()) == campos_do_contrato, "campos nao batem com o contrato"
   print("OK, formato bate com o contrato:", amostra)
   PY
   ```

   Passa (`OK, ...`) ou falha alto (`AssertionError`) — não é uma inspeção visual, é
   uma checagem que quebra se o firmware e o servidor divergirem no formato.

## A escada do backoff — provoque de propósito

O jeito mais barato de mostrar a reconexão é **gravar o kit antes de subir o servidor**.
Foi o que aconteceu por acidente nesta bancada, e rendeu melhor que provocar a queda:

```
<err> lab_transporte: Falha ao conectar em 192.168.15.15:9000 (-116)
<wrn> lab_wifi_tcp: Falha ao abrir o transporte (-116); nova tentativa em 4000 ms
                                                  ... nova tentativa em 8000 ms
                                                  ... nova tentativa em 16000 ms
<err> lab_wifi_tcp: Sem conseguir conectar depois de 5 tentativas -- confira
      o IP e a porta digitados no boot, se o PC e o kit estao na mesma rede,
      e se o firewall do PC deixa o servidor receber conexao nessa porta
                                                  ... nova tentativa em 30000 ms
[servidor sobe aqui]
<inf> lab_transporte: Conectado em 192.168.15.15:9000
```

O `-116` é `ETIMEDOUT`. A espera dobra até o teto de 30 s (`abrir_com_backoff()`), e na
quinta tentativa o firmware imprime **a lista do que conferir** — inclusive o firewall,
que é a causa mais comum. Quando o servidor sobe, o kit entra sozinho no ciclo seguinte,
**sem reset**.

### O log é mudo no sucesso

Depois que a conexão funciona, **o console não imprime mais nada** — só falha gera linha.
A prova de que está funcionando é a *ausência* de erro, mais as linhas de LED quando se
manda um comando. Todo o resto da evidência está do lado do servidor. Vale avisar, senão
o aluno fica olhando um terminal parado achando que travou.


## Plano B — sem rede utilizável na sala, ou com isolamento de cliente

Se a sala não tiver uma rede Wi-Fi utilizável (sem AP, sem credencial disponível,
etc.), o remédio é o mesmo dos dois casos abaixo: subir um hotspot (celular do
instrutor, ou compartilhamento de conexão do próprio PC), resetar o kit e, na janela
de 5 s do boot, digitar o SSID e a senha do hotspot e o IP do PC nessa rede. Não muda
uma linha de firmware nem do servidor, e não precisa recompilar — só a rede à qual os
dois se associam.

O outro caso é mais traiçoeiro: o AP da sala isola clientes entre si (client
isolation) e o PC não alcança o kit mesmo os dois com IP na mesma sub-rede. O sintoma
engana porque os dois lados parecem certos — a DK associa, pega IP por DHCP, `wifi
status` (lab 6/7) não acusa nada de errado — e mesmo assim a conexão TCP nunca fecha,
porque o isolamento acontece na camada 2, dentro do próprio AP, não em nada que o kit
ou o servidor consigam ver. Não dá para diagnosticar isso pelo lado do firmware; a
saída é a mesma: hotspot alternativo, PC e DK os dois nele.

## O que observar

- O intervalo entre amostras de telemetria não é perfeitamente regular: a thread de
  recepção (`thread_recepcao()`, em `src/main.c`) segura o mutex do transporte
  (`transporte_mutex`, em `src/transporte.c`) durante toda a espera por uma linha do
  servidor (`transporte_receber()`, timeout de 1 s), e isso pode atrasar em até esse
  tempo um envio concorrente de telemetria ou do botão. É escolha de projeto — a
  exclusão mútua entre as threads que compartilham o mesmo socket prioriza corretude
  sobre regularidade — não sintoma de problema de rede ou do kit.

## Os LEDs e o botão neste lab

| Sinal | O que significa |
|---|---|
| **LED1** aceso | o servidor mandou `LED 1` — é o **downlink** chegando, o ponto do lab |
| **LED1** apagado | o servidor mandou `LED 0`, ou o firmware acabou de iniciar |
| **botão `sw0`** | manda uma amostra **extra e imediata**, com `"botao":true` |

O LED1 é o único indicador visual, e ele **não diz nada sobre a conexão** — um kit
desconectado fica com o LED exatamente como estava. Para saber o estado do enlace, o
lugar é o console.

**Por que o LED1 e não o LED0:** o alias do devicetree é `led1`, e a serigrafia da
nRF54LM20-DK numera a partir de **LED0** — aqui os dois batem, e o `led1` é mesmo o LED
marcado **LED1** na placa. (No lab 8a, que usa a `dk_buttons_and_leds`, a numeração é
deslocada e `DK_LED1` acende o **LED0**. São bibliotecas diferentes.)

**O que o botão prova:** a amostra dele **fura o ritmo** do envio periódico. No log do
servidor ela aparece entre duas periódicas, com `uptime_ms` fora da cadência — é assim
que se demonstra que o transporte não está apenas repetindo um relógio.
## Pegadinhas

- **O firewall do Windows bloqueia o servidor sem avisar ninguém — e uma regra de
  bloqueio por programa vence qualquer permissão por porta.** Achado na bancada: com
  o IP e a porta digitados no boot corretos, a conexão ainda falha com `-116`
  (`ETIMEDOUT`) porque o Windows tem uma regra de bloqueio de entrada para o Python
  no perfil de rede Private. O sintoma engana dos dois lados: no PC, `wifi_server.py`
  fica ouvindo e nada chega, sem nenhum erro; no kit, o log do firmware aponta para o
  IP e a porta digitados no boot (a mensagem que aparece depois de 5 tentativas), que
  já estavam certos. **Se o aluno já clicou em
  "Cancelar" num daqueles diálogos de rede do Windows para o Python, alguma vez**,
  fica registrada uma regra de bloqueio por programa (`Block`, perfil Private) — e
  essa regra vence qualquer permissão criada só por porta; liberar a porta sozinho
  não resolve nesse caso. Conserto completo, em PowerShell como administrador, em
  dois comandos:

  ```powershell
  # 1. remove as regras de bloqueio do Python (o "Cancelar" de alguma vez)
  Get-NetFirewallRule -Action Block | Where-Object {
      (Get-NetFirewallApplicationFilter -AssociatedNetFirewallRule $_).Program -like "*python*"
  } | Remove-NetFirewallRule

  # 2. libera a porta do lab, entrada, perfil Private
  New-NetFirewallRule -DisplayName "Lab 9 Wi-Fi TCP (curso nrf-manaus-2)" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9000 -Profile Private
  ```

  Os labs 10, 12 e 13 sofrem do mesmo bloqueio, cada um na sua porta: o primeiro
  comando (remover o bloqueio do Python) só precisa rodar uma vez por PC; o segundo
  (liberar a porta) se repete para cada porta nova.
