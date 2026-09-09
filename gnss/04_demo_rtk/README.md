# GNSS · Demo — a escada de precisão e as falhas de RTK

**Esta pasta não tem código, e não é lab de aluno.** É o roteiro do instrutor para os ~25
minutos de demonstração com os dois **u-blox EVK-X20P**, e é onde a taxonomia de correção do
bloco teórico encontra número medido.

O primeiro degrau da escada usa o firmware do [`../03_nmea/`](../03_nmea/), gravado numa
nRF9151-SMA-DK.

> **O que é feito na montagem e o que é feito em aula.** O Survey-In da base roda **uma vez, na
> montagem**, e nunca em aula — leva minutos e não tem nada para ver. Em aula a base sobe pronta
> em segundos, já em modo fixo.

---

## 1. Antes da aula — a montagem e a base

### As duas antenas

Duas antenas com visada de céu, separadas por alguns metros:

| Antena | Papel |
|---|---|
| **Ponto de medida** | Onde os três receptores se revezam. **Tem de ser a multibanda** (ANN-MB2, do kit da u-blox), porque ela serve ao nRF9151 **e** ao X20P — a que vem com a SMA-DK provavelmente cobre só L1 |
| **Base** | Alguns metros ao lado, ligada ao EVK que faz de base |

A baseline curta é escolha, não limitação: ela elimina o termo de 1 ppm e faz as duas antenas
verem rigorosamente a mesma atmosfera — o que neutraliza a cintilação ionosférica que seria
fatal numa baseline longa. Em Manaus isso não é detalhe.

⚠️ **Troca de cabo sempre com o receptor desenergizado**, e nunca dois receptores no mesmo
cabo: o J2 da SMA-DK entrega 3 V e o EVK entrega 3,3 V para a antena ativa.

### O Survey-In, uma vez só

1. Rodar o **Survey-In** no EVK da base. O guia sugere começar com **5000 mm** de precisão alvo
   e **60 s**. Acompanhar por `UBX-NAV-SVIN`.
2. **Anotar a coordenada.** Ela é a referência de verdade do módulo inteiro.
3. Gravar a base em **`CFG-TMODE-MODE = FIXED`**, com os campos de alta precisão.
4. **Salvar na flash**, com o botão Save do u-center 2.

**Por que não deixar em Survey-In gravado.** Nesse modo a base **refaz o levantamento a cada
boot** e entrega uma coordenada um pouco diferente toda vez. O manual é explícito: qualquer erro
na posição da base **se traduz diretamente em erro no rover**. Gravada como fixa, a base sobe
pronta em segundos e a coordenada é idêntica entre sessões.

> A mensagem **1005** só começa a sair **depois** que o Survey-In conclui. Base recém-ligada em
> Survey-In não emite posição — e um rover esperando por ela fica em float sem explicação
> aparente.

**Memória:** o que está na flash sobrevive ao ciclo de energia, mas o kit **não tem bateria de
backup**. Efemérides, almanaque e última posição se perdem, então **todo boot do X20P é partida
a frio**, cerca de 25 s. O botão RST força o mesmo.

---

## 2. As mensagens e o caster

O caster NTRIP roda **dentro do u-center 2**, na máquina da base; o rover se conecta ao IP que o
próprio u-center 2 mostra no rodapé da janela. Isso é **rede local** — Wi-Fi da sala, cabo entre
os notebooks, ou um deles como ponto de acesso. **O RTK entre os kits não toca a internet.**

### A lista recomendada para base estacionária

| Mensagem | O que carrega |
|---|---|
| **1005** | Posição da antena da base |
| **1006** | O mesmo, com altura da antena |
| **1074** | Observáveis GPS (MSM4) |
| **1084** | Observáveis GLONASS (MSM4) |
| **1094** | Observáveis Galileo (MSM4) |
| **1124** | Observáveis BeiDou (MSM4) |
| **1230** | Viés de código GLONASS |

São sete, e são **MSM4, não MSM7**. A saída do X20P tem 12 mensagens ao todo (1005, 1006, MSM4
e MSM7 das quatro constelações, 1230 e 4072.0); não há MSM5 na saída, nem nada legado.

### Três regras que decidem se fixa

1. **Não misturar MSM4 e MSM7.** O manual avisa que isso pode setar errado o bit de múltiplas
   mensagens. Todas as constelações usam o mesmo tipo. Todas as observações vão no **mesmo
   rate** — os rates em Hz não são especificados pela u-blox.
2. **1230 é obrigatório na prática**, ou **1033** no lugar dele. Sem um dos dois, as ambiguidades
   de GLONASS ficam **em float mesmo com o rover em fixo**. É a Falha C.
3. **Desmarcar "Get configuration automatically"** no u-center 2. O padrão transmite tudo e
   causa latência.

### Duas armadilhas de infraestrutura

- ⚠️ **A porta do caster precisa estar liberada no firewall.** Na primeira execução o Windows
  pergunta, e uma **negativa distraída** faz o rover não conectar — sem nenhum sintoma que
  aponte para a causa. Se o rover não acha o caster, este é o primeiro lugar a olhar.
- **1006 e 4072.0 na saída exigem firmware HPG 2.10.** Num EVK com HPG 2.02 a base só emite
  **1005** — e isso **basta**, porque o rover aceita 1005 **ou** 1006. Conferir a versão dos dois
  EVK na montagem, não em aula.

---

## 3. A escada — os três degraus, no mesmo ponto

Os três receptores se revezam na **mesma antena do ponto de medida**, com troca de cabo sempre
desenergizada.

| Degrau | Receptor | Correção | O que se vê |
|---|---|---|---|
| 1 | nRF9151, banda única | nenhuma | dispersão de **metros** |
| 2 | EVK-X20P, multibanda | nenhuma | dispersão **decimétrica** |
| 3 | EVK-X20P, multibanda | **RTK da base local** | dispersão **centimétrica**, e `carrSoln` = 2 |

- **Degrau 1** — a SMA-DK com o firmware de [`../03_nmea/`](../03_nmea/), aberta no **u-center
  clássico**. A dispersão do u-center 2 depende de `UBX-NAV-PVT` e fica vazia com NMEA; por isso
  o degrau 1 usa o clássico e os degraus 2 e 3 usam o 2.
- **Degrau 2** — o rover sozinho, sem correção. É o degrau que mostra o que a **multibanda** faz
  sozinha, antes de qualquer correção entrar na conta.
- **Degrau 3** — o mesmo rover, agora com a correção da base. A sequência de estados
  **3D → 3D/DGNSS → Float → Fixed** acontece na tela e vale ser narrada enquanto acontece.

### O laço que fecha o módulo

A coordenada verdadeira do ponto de medida sai do **próprio fix RTK** do degrau 3 e volta como
`CONFIG_GNSS_SAMPLE_REFERENCE_LATITUDE` / `..._LONGITUDE` no firmware do nRF9151. A partir daí a
placa do aluno **não reporta uma posição — reporta o próprio erro contra uma verdade medida em
sala**.

O laço fecha no build do **lab 1** (o do console legível). No build do lab 3 essa linha sairia no
meio do fluxo de NMEA e o sujaria.

### A ressalva metodológica, que é obrigatória

Os três degraus acontecem **com minutos de diferença, não no mesmo instante**. A u-blox recomenda
comparação em paralelo, por divisor, e testes de 24 h. A comparação se sustenta porque a
diferença entre metros e centímetros é enorme perto da deriva de geometria em poucos minutos —
**mas o material não pode afirmar simultaneidade.** Dizer isso em voz alta na demo é parte do
roteiro.

---

## 4. As cinco falhas de RTK

Todas se montam **mexendo na configuração da base**, sem caster externo, e todas são
**documentadas e determinísticas** — é por isso que são estas cinco, e não outras.

### Falha A — a base não diz onde está

**Como provocar:** base emitindo só as MSM, **sem 1005 nem 1006**.

**O que o manual garante:** o rover exige observação **e** posição da base. Sem a mensagem de
estação de referência ele **não computa posição**. É falha total e limpa — nada de meio-termo.

**Assinatura na tela:** chegam correções de MSM e **nenhuma** de 1005 ou 1006.

### Falha B — o rover está ouvindo outra estação

**Como provocar:** ID de estação de referência da base **diferente** do filtro do rover.

**O que o manual garante:** o ID precisa bater com o das mensagens MSM; se não bater, o rover
**não computa a posição RTK fixa**.

**Assinatura na tela:** chega MSM com `msgUsed` em **"recebida mas não usada"**, e o
`correctionId` que não bate. É o caso em que tudo parece certo e nada fixa.

### Falha C — a degradação silenciosa

**Como provocar:** GLONASS ligado na base, **sem 1230 nem 1033**.

**O que o manual garante:** as ambiguidades de GLONASS ficam **em float mesmo em modo fixo**, com
desempenho degradado.

**Por que é a mais didática:** não há mensagem de erro. O sistema "funciona", só que pior — é o
modo de falha que mais aparece em campo e o mais difícil de diagnosticar sem olhar o
`carrSoln`.

### Falha D — a correção envelhece

**Como provocar:** **interromper o stream** do caster.

**O que o manual garante:** o rover descarta correção com mais de **60 s** e cai para 3D ou
3D/DGNSS. **Reversível** — religar o stream traz o fixo de volta.

**Assinatura na tela:** os `RXM-COR` simplesmente **param**. É a mais visual das cinco, e a única
que dá para fazer ida e volta na frente da turma.

### Falha E — precisão não é acurácia

**Como provocar:** base em modo fixo com coordenada errada em **mais de ~50 m**.

**O que o manual garante:** o receptor emite `UBX-INF-WARNING` com *"base station position seems
incorrect"*.

**O ponto de aula:** o rover continua fixando, com dispersão centimétrica — **e centrado no lugar
errado**. É a separação entre **precisão relativa** e **acurácia absoluta**, e é a razão de o
Survey-In da §1 ser feito com cuidado.

> **Não usar a variante "base emite só GLONASS".** O manual não descreve o comportamento quando
> falta a observação de uma constelação inteira, então a demo **não seria determinística**.

**Roteiro sugerido, se o tempo apertar:** **A** (falha dura) → **C** (degradação silenciosa) →
**D** (timeout) → **E** (precisão contra acurácia).

---

## 5. Mostrar **por que** não fixou, não só que não fixou

`UBX-RXM-COR` é emitido ao parsear com sucesso **cada** correção de entrada — **mesmo quando a
mensagem não é suportada ou não é usada**. É o que separa "chegou e foi descartada" de "chegou e
serviu".

| Campo | Uso didático |
|---|---|
| `msgUsed` | **1 = recebida mas não usada**, 2 = usada |
| `correctionId` | O ID de estação da mensagem — é o que denuncia a **Falha B** |
| `msgType` | O número da mensagem. **A ausência** de um tipo significa que ele não chegou — a assinatura da **Falha A** |
| `msgInputHandle` | Se o receptor tem suporte de entrada para aquela mensagem |
| `errStatus` | Livre de erro contra errônea |

Complementos, por satélite e por sinal:

- **`UBX-NAV-SAT`** — quais satélites têm dado válido, e em quais a correção foi **de fato
  aplicada**.
- **`UBX-NAV-PVT`** — o campo `carrSoln`: **1 para float, 2 para fixo**.
- **No NMEA**, a qualidade do `GGA` é **4 para fixo e 5 para float** — o que aparece também no
  u-center clássico, e é o que permite diagnosticar o degrau 3 sem sair do NMEA.

A sequência **3D → 3D/DGNSS → Float → Fixed** é a espinha do diagnóstico: saber em qual dos
quatro estados o rover parou já diz qual das cinco falhas está acontecendo.

---

## 6. Bônus — RTK contra a estação pública da UEA

**É bônus, não lab.** Nenhuma das condições está sob controle total do instrutor, e **se não
rodar, nada do módulo cai**.

A estação **AMUA0** fica na Escola Superior de Tecnologia da UEA e é publicada no caster do IBGE.
O curso é na SIDIA Amazon Tower, **Avenida Darcy Vargas, 654**; a estação fica na **mesma
avenida, número 1200**. A baseline é da ordem de **1 km** — a distância exata **é medida em
aula**, porque a coordenada da base chega na mensagem de posição assim que o rover conecta.

### As quatro condições

1. **Cadastro no serviço do IBGE** — gratuito, mas com prazo de liberação não confirmado (entre
   imediato e cerca de um dia útil). **Fazer com antecedência.**
2. **Internet na sala.** O RTK da base própria não precisa; este precisa.
3. **A baseline** — resolvida, e a favor: ~1 km, bem dentro da faixa confortável, com o termo de
   1 ppm contribuindo cerca de 1 mm.
4. **Cintilação** — é fenômeno pós-pôr-do-sol, então aula diurna joga a favor.

### O que ele entrega: um experimento controlado

Duas soluções RTK **no mesmo rover, no mesmo ponto, na mesma hora**:

| Fonte de correção | Baseline | Constelações |
|---|---|---|
| Base própria | metros | GPS, GLONASS, Galileo e BeiDou |
| AMUA0, na UEA | ~1 km | **apenas** GPS e GLONASS |

Como as **duas baselines são curtas**, a distância deixa de ser a variável e o que resta é o
**número de constelações** disponíveis para resolver ambiguidade. O aluno vê o efeito de duas
contra quatro constelações **isolado**, sem confundir com o efeito da distância.

Detalhe que fecha o caso: a AMUA0 satisfaz o requisito de viés de GLONASS por **1033**, não por
1230 — o manual aceita uma **ou** outra. As demais mensagens que ela emite (1008, 1013, 1019,
1020) não estão na tabela de entrada do X20P e serão ignoradas; isso não atrapalha, e ainda rende
demonstração — elas aparecem no status de correção **sem suporte de entrada**, que é o campo
`msgInputHandle` da §5.

---

## `verifica_roteiro.sh`

```
sh gnss/04_demo_rtk/verifica_roteiro.sh
```

Esperado: `OK: roteiro cobre os itens obrigatorios`. O script não julga o texto — confere que
este roteiro não perdeu nenhum dos quinze itens que o spec exige: as sete mensagens RTCM da lista
recomendada, as cinco falhas rotuladas, e os três diagnósticos. É a rede de segurança contra uma
reescrita que apague um item sem querer.

## Fontes

- Spec do módulo — `docs/superpowers/specs/2026-09-08-gnss-design.md`, §3.1 a §3.5 e §7.2
- [`../03_nmea/`](../03_nmea/) — o firmware do primeiro degrau
- Checklist de bancada do módulo (não versionado) — a ordem em que montar e o que anotar
