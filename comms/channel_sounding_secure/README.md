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
