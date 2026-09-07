# Tempos — frente de Wi-Fi 6+ (`comms/06` a `comms/13`)

## O que este documento é, e o que não é

Nenhum dos oito labs foi cronometrado com aluno. O que existe é **tempo de bancada**,
medido pelo instrutor sozinho, do reset do kit até um evento observável (IP obtido,
SoftAP no ar, coordenada resolvida) — isso é **tempo de máquina**, não tempo de aula.
Tempo de aula inclui ler o README, montar hardware, digitar comandos, errar e
corrigir; tempo de máquina não inclui nada disso. Os dois números não são
intercambiáveis, e este documento não finge que são.

A duração de cada lab **em sala** está pendente de cronometragem com turma real —
ver a tabela na seção correspondente. Não há número inventado nela.

## Tempo de compilação — o fator que mais atrapalha se ninguém avisar

Um build limpo de Wi-Fi nesta máquina leva **de 7 a 12 minutos**. Isso já é grande o
bastante para dominar o tempo de qualquer lab que peça mais de uma compilação. Pior:
o build **pode ser morto por falta de memória** durante a etapa de link/empacotamento
— sintoma comum em máquinas com pouca RAM livre enquanto o VS Code e o toolchain
também estão de pé. A saída, testada nesta bancada:

```
west build ... -o=-j2
```

Isso reduz o paralelismo do build (menos jobs simultâneos, menos pico de memória), ao
custo de um build mais lento. Vale avisar a turma **antes** do primeiro build de
Wi-Fi do dia, não depois que alguém travar a máquina.

**Quantos builds cada lab pede** (isso multiplica o custo de compilação por lab):

| Lab | Builds | Observação |
|---|---|---|
| 06 shell | 1 | |
| 07 sta | 1 | |
| 08 provisionamento | 1 | + `protoc` uma vez, no PC |
| 09 TCP | 1 | |
| 10 HTTP/MQTT | **3** | TCP, HTTP e MQTT são três binários separados (`build_TCP`, `build_HTTP`, `build_MQTT`) |
| 11 energia | 0 ou 1 | Parte A reaproveita o binário do lab 6 (0 builds novos); Parte B (TWT) precisa de 1 build próprio |
| 12 coexistência | **2** | `build_on` e `build_off` — a troca de regime é decidida em tempo de compilação, não em runtime |
| 13 locationing | 1 | |

Um lab com três builds (10) ou dois builds (12) não é "um build mais um pouco" — é
duas ou três vezes o custo de compilação de um lab de build único, e nesta máquina
isso pode significar de 14 a 36 minutos só de `west build`, antes de qualquer
interação com o kit.

## Tempo de bancada medido (tempo de máquina, não de aula)

Só três labs têm medida de tempo de execução do zero, feita pelo instrutor:

| Lab | O que foi medido | Tempo de máquina | Onde mais esse número aparece |
|---|---|---|---|
| 07 sta | do reset ao IP obtido por DHCP | ~7 s (dos quais ~4 s de varredura/associação) | só aqui — medido pelo instrutor fora do README do lab. O `comms/07_wifi_sta/README.md` (Passo 2) ainda marca a checklist de bancada como "a confirmar"; o número é real, só não foi propagado para lá ainda |
| 08 provisionamento | do boot até o SoftAP no ar | ~5,6 s | só aqui — mesmo caso do lab 7: medido pelo instrutor, mas o `comms/08_wifi_provisioning/README.md` (Passo 3) ainda marca o fluxo completo como "a confirmar" |
| 13 locationing | do reset à coordenada resolvida | ~15 s (dos quais ~5,5 s de varredura) | também em `comms/13_wifi_location/README.md`, seção "Ciclo completo, validado com hardware" — as duas fontes batem |

**Os números de 07 e 08 não são inventados nem contraditórios com os READMEs
daqueles labs** — são reais, medidos pelo instrutor, só ainda não propagados para lá.
A atualização dos dois READMEs (para que a checklist de bancada pare de dizer "a
confirmar" quando o tempo já foi medido) é responsabilidade de quem mantém cada lab,
não deste documento.

Os labs 06, 09, 10, 11 e 12 não têm esse tipo de medida (reset→evento) registrada
aqui — não porque sejam mais lentos ou mais rápidos, só porque o instrumento
(cronômetro na bancada) não foi aplicado a eles nesta rodada. Os labs 09 e 10 têm,
nos seus próprios READMEs, evidência de bancada de outro tipo (sequência de eventos,
reconexão) que não é um tempo do reset a um evento único, e por isso não entra nesta
tabela.

## Duração de cada lab em sala — pendente de cronometragem

**Nenhum número abaixo foi inventado.** É o dado que falta para decidir corte de
conteúdo, e chutar seria pior que deixar em branco.

| Lab | Duração em sala |
|---|---|
| 06 shell | pendente — a cronometrar |
| 07 sta | pendente — a cronometrar |
| 08 provisionamento | pendente — a cronometrar |
| 09 TCP | pendente — a cronometrar |
| 10 HTTP/MQTT | pendente — a cronometrar |
| 11 energia | pendente — a cronometrar |
| 12 coexistência | pendente — a cronometrar |
| 13 locationing | pendente — a cronometrar |

## Se só couberem 3h

A decisão de corte é do instrutor. Sem duração de aula medida, o argumento aqui não
pode ser "qual lab é mais rápido" — é **o que já se sabe**: quantos builds cada lab
exige (seção acima, o maior custo de tempo confirmado) e quais dependências externas
podem travar o andamento independente de quanto tempo sobrar.

| Lab | Argumento medido | Sugestão |
|---|---|---|
| 06 shell | 1 build; sem dependência externa; abre a frente (console, `wifi scan`/`connect`) | manter |
| 07 sta | 1 build; só precisa de `minha_rede.conf` | manter |
| 08 provisionamento | 1 build; único que mostra a DK escaneando por conta própria e HTTPS/protobuf | manter |
| 09 TCP | 1 build; lab central, o payload que os labs 10 e 13 reaproveitam | manter |
| 10 HTTP/MQTT | **3 builds** (até ~36 min só de compilação) + broker mosquitto no PC | **virar demo** se o tempo apertar: o instrutor grava as três variantes antes da aula e mostra a tabela de bytes/FLASH/RAM já medida, sem recompilar ao vivo |
| 11 energia | Parte A não pede build novo (reusa o lab 6) e é só shell + `ping`; Parte B (TWT) pede 1 build **e** depende de um AP com TWT (EX3000) confirmado na sala | Parte A mantém sempre; Parte B só entra em modo laboratório se o EX3000 estiver confirmado — senão vira demo com os números da Nordic citados como ordem de grandeza |
| 12 coexistência | **2 builds**; exige um segundo dispositivo BLE dedicado (par de throughput) e `iperf` 2.0.5 no PC; maior uso de RAM da frente (71,49%) | **virar demo**: é o lab com mais pré-requisitos de bancada simultâneos (dois builds, dois dispositivos, ferramenta de PC específica) |
| 13 locationing | 1 build, mas depende de conta e token (OAT) do nRF Cloud já configurados **antes** da aula, e cada varredura é uma chamada paga | manter **se** a conta/OAT estiver pronta com antecedência; senão **demo**, para não gastar chamadas pagas testando credencial na hora |

Resumo do argumento: os labs 06–09 e 13 (com conta pronta) têm custo de bancada
baixo e dependência externa mínima ou controlável antecipadamente — são os
candidatos naturais a ficarem hands-on num corte de 3h. Os labs 10 e 12 concentram o
maior custo de compilação e de montagem de bancada (múltiplos builds, hardware ou
ferramenta extra) — são os primeiros candidatos a virar demonstração do instrutor,
com os números já medidos neste repositório em vez de recompilação ao vivo. A
Parte B do lab 11 é condicional a um AP específico, independente de quanto tempo
sobrar.
