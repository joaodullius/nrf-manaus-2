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
`sw0`, e o LED comandado pelo servidor é o `led1` (alias do devicetree — **LED 2** na
serigrafia da placa).

## Configuração — duas credenciais, dois fragmentos

Além de `minha_rede.conf` (SSID/senha da rede da sala, mesma convenção do lab 7), este
lab precisa saber o IP do PC que roda o servidor: `CONFIG_LAB_SERVIDOR_IP`. Vazio faz o
`CMakeLists.txt` falhar de propósito na configuração, antes de compilar qualquer coisa
— um kit sem IP de destino não teria para onde mandar a telemetria. Descubra o IP do PC
na rede da sala (`ipconfig`) e passe os dois na linha de build.

**Nunca commitar SSID, senha ou IP reais** — `minha_rede.conf` fica vazio no
repositório; o IP do servidor vai só na linha de comando, nunca em um arquivo
versionado.

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

Aceita uma conexão por vez, imprime cada amostra numa linha alinhada, e lê o teclado:
`l` liga o LED 2, `d` apaga, `q` sai. A classe `Servidor` (`porta`, `ao_receber`) é o
que os testes exercitam sem hardware: `porta=0` deixa o SO escolher uma porta livre e
`porta_real` devolve a efetiva, o que torna o teste determinístico; `ao_receber` é
chamado com o dicionário de cada amostra válida (linhas que `payload_ref.parse()`
rejeita são descartadas, sem derrubar a conexão). `enviar_comando(texto)` manda
`texto + "\n"` para o cliente conectado — vira um no-op silencioso se não houver
cliente no momento.

## Os três gestos do lab

1. **O botão.** Apertar o `sw0` manda uma amostra imediata, fora do intervalo
   periódico, com `"botao":true` — dá para ver no servidor sem esperar o próximo tick.
2. **O comando de LED.** Teclar `l` no servidor manda a linha `LED 1`; o firmware
   (`thread_recepcao()`) lê essa linha do transporte e acende o **LED 2**. `d` manda
   `LED 0` e apaga.
3. **A queda de conexão.** Afastar o kit até a conexão cair (e voltar) mostra o
   `seq` pulando — um buraco na sequência — porque as amostras enviadas durante a
   queda se perdem; o firmware reconecta sozinho com espera crescente
   (`abrir_com_backoff()`, em `src/main.c`) e a telemetria retoma sem intervenção. É o
   ponto do lab: a queda é esperada e tratada, não um bug.

## Passo 1 — compilar e gravar

Com `minha_rede.conf` preenchido e o IP do PC em mãos:

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild -d C:/work/nrf-manaus-2/comms/09_wifi_tcp/build_lm20 C:/work/nrf-manaus-2/comms/09_wifi_tcp -- -D09_wifi_tcp_SHIELD="nrf7002eb2" -D09_wifi_tcp_SNIPPET=nrf70-wifi -D09_wifi_tcp_EXTRA_CONF_FILE=minha_rede.conf -D09_wifi_tcp_CONFIG_LAB_SERVIDOR_IP=\"<ip-do-pc>\"
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/comms/09_wifi_tcp/build_lm20
```

Resumo de memória:

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 385256 B | 2036 KB | 18,48% |
| RAM | 111264 B | 511 KB | 21,26% |

## Testes automáticos (PC, sem hardware)

```bash
cd comms/09_wifi_tcp/tools
python -m pytest -q
```

`16 passed, 8 skipped` nesta bancada: os 8 pulados são a travessia C↔Python
(`tests/test_payload_c.py`), por falta de compilador de host utilizável — ver
`tools/README.md` para a ordem de busca e a mensagem de skip. Os testes de
`wifi_server.py` (`tests/test_server.py`) sobem um `Servidor(porta=0)` de verdade e
conversam com ele por um socket local, cobrindo o caminho feliz e os casos ruins:
linha partida em dois pedaços, duas amostras no mesmo pacote, linha malformada e
cliente que desconecta no meio.

## Roteiro de bancada

1. `python wifi_server.py --porta 9000` no PC.
2. Gravar a DK com o IP do PC (Passo 1).
3. Conferir: amostras chegando a cada `CONFIG_LAB_INTERVALO_MS` (padrão 2 s), `seq`
   incrementando.
4. Apertar o **botão 1** (`sw0`) → amostra imediata, com `"botao":true`.
5. Teclar `l` no servidor → **LED 2** acende; `d` → apaga.
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

## Plano B — sem rede utilizável na sala, ou com isolamento de cliente

Se a sala não tiver uma rede Wi-Fi utilizável (sem AP, sem credencial disponível,
etc.), o remédio é o mesmo dos dois casos abaixo: subir um hotspot (celular do
instrutor, ou compartilhamento de conexão do próprio PC) e apontar `minha_rede.conf`
e `CONFIG_LAB_SERVIDOR_IP` para ele. Não muda uma linha de firmware nem do servidor —
só a rede à qual os dois se associam.

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
