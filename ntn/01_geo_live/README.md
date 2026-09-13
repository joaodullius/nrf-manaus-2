# Demo GEO ao vivo — Skylo NTN NB-IoT

Roteiro e ferramentas da demonstração ao vivo com o satélite GEO da Skylo:
um nRF9151-SMA-DK conectado por serial ao PC do instrutor, o roteiro de
comandos AT executado por `skylo_test.py`, e um receptor UDP simples
(`udp_server.py`) rodando no mesmo PC para mostrar o datagrama chegando.

## Kit e firmware

| Componente | Detalhe |
|---|---|
| Kit | nRF9151-SMA-DK |
| SIM | Skylo eminify, APN `em` |
| Antena | Antena NTN externa, com visada de céu |
| App core | `serial_modem_v1.0.0_nrf9151dk_normal.hex` (Serial Modem add-on v1.0.0) |
| Firmware de modem | `mfw_nrf9151-ntn_1.0.1` |
| Serial | 115200 8N1 |

Onde obter e gravar os dois arquivos: [`../hex/README.md`](../hex/README.md).

## Antes de ligar

1. Confirmar que o SIM instalado é o Skylo eminify e que o APN configurado é `em`.
2. Posicionar a antena NTN com visada de céu (sem telhado, parede ou vidro entre
   a antena e o horizonte na direção do satélite).
3. Identificar a porta COM do kit (Gerenciador de Dispositivos no Windows, ou
   `ls /dev/tty*` no Linux/macOS).
4. Instalar as dependências Python do módulo, a partir desta pasta:

   ```bash
   pip install -r ../tools/requirements.txt
   ```

5. **Servidor UDP.** O kit fala com o servidor através do núcleo da Skylo, pela
   Internet pública — um laptop atrás do NAT/Wi-Fi da sala não recebe o
   datagrama. A demo usa o servidor do instrutor, `64.181.168.22:5005` (padrão
   de `--server`; é o mesmo do `prj.conf` do firmware LEO), onde roda o
   `udp_server.py` deste diretório. Para ver o datagrama chegar em sala,
   abrir uma sessão nesse servidor e deixar o `udp_server.py` em primeiro
   plano; a URC `#XSENDNTF` no kit prova a entrega mesmo sem essa sessão.

6. **Posição.** O fix é feito no dia, no local da demo (o lab de GNSS dá lat,
   lon e altitude). Referência do prédio, para conferir a ordem de grandeza:
   Sidia Amazon Tower, Av. Darcy Vargas 654 — **−3,0930, −60,0207**
   (OpenStreetMap). Não vai como padrão no script.

## A sequência

`skylo_test.py` roda a sequência de `skylo_at_commands.txt` em cinco blocos,
decodifica as URCs na tela e abre um shell interativo no final:

```bash
python skylo_test.py --port COM26 --lat <LAT> --lon <LON>   # --server 64.181.168.22:5005 e o padrao
```

`--lat`/`--lon` são obrigatórios (sem padrão de Manaus/SIDIA embutido no
script); `--alt` tem padrão `50`; `--apn` tem padrão `em`; `--server` tem padrão
`64.181.168.22:5005` e, se passado malformado (sem porta), é rejeitado antes de
abrir a porta serial.

A tabela abaixo segue a ordem real em que `skylo_test.py` envia os comandos
(a ordem de `build_config_commands`, não uma reorganização temática — por
isso `AT+CGDCONT` vem depois do par `%LOCATION`, não antes).
`skylo_at_commands.txt` é essa mesma sequência escrita em AT puro, para
leitura fora do script; o script não lê nem faz parsing desse arquivo, os
comandos são gerados em Python.

| Bloco | Comandos | O que aparece na tela | Lâmina |
|---|---|---|---|
| 1. Identificação e modo | `AT#XSMVER`, `AT+CGMM`, `AT%HWVERSION`, `AT+CGMR`, `AT+CFUN=4`, `AT%XSYSTEMMODE=0,0,0,0,1`, `AT%XBANDLOCK=2,,"255,256"`, `AT%XBANDLOCK?` | Versão de firmware do SLM e do modem; confirmação do bandlock NTN (255/256) | deck do módulo NTN (a montar) |
| 2. Posição | `AT%LOCATION=2,"<lat>","<lon>","<alt>",0,0`, `AT%LOCATION=1`, `AT+CGDCONT=0,"ip","em"` | `OK` para as três; a posição informada não aparece ecoada | deck do módulo NTN (a montar) |
| 3. URCs e ativação | `AT%CESQ=1` ... `AT+CSCON=3`, depois `AT+CFUN=1` | `+CEREG: 2` → `+CSCON: 1` → `+CEREG: 5,...,14`; sem satélite à vista, `+CEREG` volta a 4/91 ("no suitable cell") em ~30 s e o modem tenta de novo a cada 2 s | deck do módulo NTN (a montar) |
| 3b. Leitura pós-registro | `AT%SIBREQ=32`, `AT+COPS?`, `AT%XMONITOR` | `%SIBREQ: 32,...` se o SIB32 for transmitido e `%SIBREQ: 0,<status>` (0 concluído, 1 célula perdida, 2 abortado); operadora e AcT (14 = NTN NB-IoT); banda, EARFCN, PCI e RSRP da célula | deck do módulo NTN (a montar) |
| 4. Dado | opção `1` (socket + connect), opção `2` (`AT#XSEND=<handle>,0,8192,"..."`), opção `3` (`AT#XRECVFROM`) | `#XSOCKET: <handle>,2,17`; `#XSEND: <handle>,<tipo>,<tamanho>` seguido da URC `#XSENDNTF: <handle>,<status>,<tamanho>` quando a rede confirma; o datagrama chega no terminal do `udp_server.py` (se o PC estiver alcançável) | deck do módulo NTN (a montar) |
| 5. Encerramento | opção `4` (`AT#XCLOSE`), depois `AT+CFUN=4` e `AT+CFUN=0` digitados diretamente no shell | Socket fechado; RF desligado (nunca `AT+CFUN=45`) | deck do módulo NTN (a montar) |

O shell interativo aceita atalhos numéricos (`1`=abrir socket e conectar,
`2`=enviar mensagem com contador automático, `3`=receber, `4`=fechar socket)
e qualquer outro comando AT digitado diretamente — inclusive os `AT+CFUN=4`/
`AT+CFUN=0` do bloco 5, que não têm atalho e são digitados como comando cru.
Se a opção `1` falhar em abrir o socket, ou a opção `2` for usada antes da
`1`, o shell avisa "socket nao aberto: PDN ativo? rode a opcao 1" em vez de
mandar um `AT#XCONNECT`/`AT#XSEND` com handle vazio. `GNSS_TIMEOUT` e
`run_gnss_fix`/`--gnss` continuam no script, mas **a demo não os usa**: NTN
e GNSS são mutuamente exclusivos no modem, e uma fixação GNSS a frio leva
minutos que a demo ao vivo não tem.

## Números a registrar na demo

Preencher durante a aula:

| Medida | Valor |
|---|---|
| Banda (`%XMONITOR`) | |
| EARFCN (`%XMONITOR`) | |
| PCI (`%XMONITOR`) | |
| Tempo de `AT+CFUN=1` até `+CEREG: 5` | |
| Tempo de `AT#XSEND` até `#XSENDNTF` | |
| Tempo de `AT#XSEND` até a chegada no `udp_server.py` | |

## Falhas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `+CEREG: 4` por mais de 60 s | Sem visada de céu, ou canal/banda errados | Checar a antena e a linha de visada; conferir `AT%XBANDLOCK?` (deve ser `255,256`) |
| `+CNEC_EMM` com causa | Sem landing rights na região, ou problema de assinatura do SIM | Reportar a causa exata; não há como contornar em campo |
| `AT#XSOCKET` retorna `ERROR` | PDN não está ativo (registro ainda não completou) | Esperar `+CEREG: 5` antes de abrir o socket; conferir `AT+CGDCONT?` |
| `AT%LOCATION=2` retorna `ERROR 513` | Posição não aceita pelo modem | Conferir formato de `--lat`/`--lon` (graus decimais, como string) e a faixa de valores |

Não há plano B: se o satélite Skylo não estiver visível na janela da aula, a
demo GEO não roda ao vivo.
