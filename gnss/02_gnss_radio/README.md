# GNSS · Lab 2 — o rádio compartilhado

Este lab não tem firmware próprio: ele **recompila o firmware do lab 1**
(`gnss/01_gnss_basic/`) escolhendo outras opções das duas *choices* do `Kconfig` do
sample — o modo de operação do GNSS e o grau de assistência. O `src/` não muda uma
linha; o nome da imagem no sysbuild continua `01_gnss_basic`, igual ao nome da pasta
do lab 1, e é esse prefixo que toda receita de build abaixo reaproveita
(`-D01_gnss_basic_CONFIG_...`). Cada build sai em um diretório próprio **dentro de
`gnss/01_gnss_basic/`** (o `.gitignore` daquele lab, `build*/`, já cobre todos eles);
esta pasta só documenta as receitas e a asserção que confere cada uma.

Duas perguntas, quatro receitas:

- **Quanto de assistência o receptor tem?** — três graus, todos em modo
  *time-to-first-fix* (TTFF): sem assistência, assistência mínima (offline), A-GNSS
  via nRF Cloud.
- **O que muda quando o GNSS roda de olho na bateria, não só de olho no primeiro
  fix?** — modo periódico com assistência mínima, onde LTE e GNSS disputam o mesmo
  rádio.

## Parte A — os três degraus de assistência

O sample tem uma *choice* de assistência (`Kconfig` do lab 1, herdado do SDK) com
padrão `GNSS_SAMPLE_ASSISTANCE_NONE`. As três receitas abaixo giram essa *choice*,
sempre em modo TTFF (`GNSS_SAMPLE_MODE_TTFF_TEST=y`, com `..._COLD_START=y` para
forçar um fix a frio a cada execução — a mesma condição em que a Product
Specification do nRF9151 mede TTFF, ver a tabela abaixo).

| Grau | Receita | O que o receptor usa | Chamada de rede? |
|---|---|---|---|
| **sem** | `build_02_sem` | nada — parte do zero, igual ao lab 1 | não |
| **mínima** | `build_02_min` | almanaque de fábrica embutido no firmware + hora da rede LTE + posição aproximada pelo código do país (MCC) | LTE já precisa estar registrado (para a hora e o MCC), mas **nenhuma chamada de A-GNSS** |
| **nuvem** | `build_02_nuvem` | A-GNSS completo (efemérides, almanaque, hora, posição, dados ionosféricos) baixado da nRF Cloud por CoAP | sim — e exige o dispositivo provisionado com certificado na nRF Cloud |

O grau **mínimo** é o que rende mais aula: ele reduz o TTFF sem custar uma única
chamada de rede além da própria conexão LTE que o lab já precisa para funcionar, e
sem exigir nenhuma integração de nuvem. O preço é a precisão do almanaque: o que vem
embutido no NCS v3.4.0 foi gerado em **2026-06-02** e **envelhece** — quanto mais
tempo passa entre essa data e o dia da bancada, menos precisa é a posição inicial que
ele oferece, e o ganho de TTFF encolhe.

### Receitas

```bash
cd C:\ncs\v3.4.0

# sem assistencia
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_02_sem C:/work/nrf-manaus-2/gnss/01_gnss_basic -- -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_CONTINUOUS=n -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST_COLD_START=y

# assistencia minima (almanaque de fabrica + hora LTE + posicao por MCC)
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_02_min C:/work/nrf-manaus-2/gnss/01_gnss_basic -- -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_CONTINUOUS=n -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST_COLD_START=y -D01_gnss_basic_CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=n -D01_gnss_basic_CONFIG_GNSS_SAMPLE_ASSISTANCE_MINIMAL=y

# assistencia de nuvem (A-GNSS via nRF Cloud)
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_02_nuvem C:/work/nrf-manaus-2/gnss/01_gnss_basic -- -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_CONTINUOUS=n -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST_COLD_START=y -D01_gnss_basic_CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=n -D01_gnss_basic_CONFIG_GNSS_SAMPLE_ASSISTANCE_NRF_CLOUD=y

cd C:/work/nrf-manaus-2
sh gnss/02_gnss_radio/verifica_variantes.sh gnss/01_gnss_basic/build_02_sem sem
sh gnss/02_gnss_radio/verifica_variantes.sh gnss/01_gnss_basic/build_02_min minima
sh gnss/02_gnss_radio/verifica_variantes.sh gnss/01_gnss_basic/build_02_nuvem nuvem
```

`CONFIG_AT_HOST_LIBRARY` continua ligado nas três, como no lab 1 — não é opção deste
lab, é herdada do `prj.conf` do sample.

**O build da variante de nuvem não exige credencial nenhuma para compilar.**
`CONFIG_GNSS_SAMPLE_ASSISTANCE_NRF_CLOUD` só liga a biblioteca cliente
(`NRF_CLOUD_COAP`) no binário; o certificado e o provisionamento do dispositivo na
nRF Cloud são **pré-requisito para rodar o firmware em bancada, não para
compilá-lo** — o build sobe sem eles e só falharia ao tentar buscar dados de
assistência de fato, com o dispositivo ligado. Não confunda um binário que compila
com um lab pronto para gravar: falta o certificado antes de ligar a placa com esta
variante. As três variantes compilaram limpo, `exit 0`.

### FLASH e RAM medidos

Mesma placa (`nrf9151dk/nrf9151/ns`), mesmo `prj.conf` de base — a única variável é
a *choice* de assistência. Tabela da **imagem de aplicação** (o alvo `/ns` também
gera a imagem segura `tfm`, que não muda entre as três: TF-M não sabe nada de GNSS).

| Grau | FLASH | % FLASH (960 KB) | RAM | % RAM (211608 B) |
|---|---|---|---|---|
| sem | 83528 B | 8,50% | 35708 B | 16,87% |
| mínima | 107092 B | 10,89% | 36180 B | 17,10% |
| nuvem | 128108 B | 13,03% | 48764 B | 23,04% |

Cada degrau custa FLASH: **+23564 B** entre sem e mínima (a lógica de assistência
mínima, mais o *backend* de `SETTINGS`/`FCB`/flash que ela liga para gravar o
almanaque), e mais **+21016 B** entre mínima e nuvem (o cliente CoAP da nRF Cloud,
`MODEM_JWT`, `MODEM_INFO`, `DATE_TIME`). RAM sobe pouco entre sem e mínima (+472 B)
e mais entre mínima e nuvem (+12584 B) — o custo de manter o cliente de nuvem vivo é
majoritariamente RAM, não FLASH adicional relevante. **Nenhuma das três muda o
`CMakeLists.txt` nem o `src/`** — a diferença inteira nasce do Kconfig.

### O que o fabricante promete (medido em laboratório, não nesta bancada)

A *Product Specification* do nRF9151 traz uma tabela de desempenho do receptor GPS,
nas condições declaradas: céu aberto, 25 °C, relógio GPS a TCXO, LNA externo com
filtro SAW na entrada da antena; a linha "periódico" usa intervalo de fix de 2
minutos; a linha "A-GPS" inclui os parâmetros do modelo ionosférico NeQuick.

| Grandeza | Valor |
|---|---|
| TTFF a frio | 30,5 s |
| TTFF a quente | 1,3 s |
| TTFF com A-GPS | 1,3 s |
| Precisão 2D CEP50, contínuo | 2,0 m |
| Precisão 2D CEP50, contínuo com A-GPS | 1,8 m |
| Precisão 2D CEP50, periódico | 3,4 m |
| Precisão 2D CEP50, periódico com A-GPS | 3,1 m |

Fonte: *nRF9151 Product Specification*, seção "GPS receiver" → "Electrical
specification". Os **30,5 s a frio contra 1,3 s com A-GPS** são o número que
justifica a existência de A-GNSS: quase 30 segundos de diferença, na mesma placa, só
por ter almanaque e efemérides prontos em vez de baixados do próprio sinal de
satélite a 50 bps.

Esses valores são o que o fabricante promete, nas condições de laboratório dele —
não substituem a medição desta bancada, que aparece abaixo. O aluno compara os dois:
quanto a bancada real bateu com a folha de dados, e por quê, se não bateu (céu
parcialmente obstruído, antena diferente, almanaque envelhecido).

**A constelação é só GPS + QZSS.** O receptor do nRF9151 recebe **GPS L1 C/A** e
**QZSS L1 C/A**, os dois na mesma frequência (1575,42 MHz) — não há Galileo,
GLONASS nem BeiDou nesta série. QZSS é o sistema regional japonês que aumenta a
cobertura sobre a Ásia-Oceania; a antena GNSS ativa desta bancada os recebe pelo
mesmo caminho de RF, sem configuração extra.

### Tempo até o primeiro fix, medido

| Grau | TTFF a frio, mediana | faixa | amostras |
|---|---|---|---|
| sem | **54,0 s** | 30 a 115 s | 11 |
| mínima | 104,8 s ⚠ | 27 a 576 s | 5 |
| nuvem | **60,6 s** | 35 a 269 s | 10 |

Duas rodadas em blocos de 20 min, com a ordem invertida na segunda — assim uma mudança lenta
do céu não vira diferença entre os graus.

**O resultado surpreende: a assistência não ajudou.** A nuvem ficou *pior* que não ter
assistência nenhuma. Antes de concluir que a assistência não serve, olhe a Parte B — o
próprio firmware reporta quanto tempo o LTE tomou o rádio, e descontando isso a conta se
inverte.

⚠ **A linha "mínima" tem poucas amostras porque o firmware trava.** Ela é a única das três
que desliga o LTE (`CONFIG_GNSS_SAMPLE_LTE_ON_DEMAND`) e precisa religá-lo a cada ciclo;
depois do primeiro `Sleeping for 120 s` o ciclo seguinte às vezes nunca começa — nem a linha
`Deleting GNSS data` aparece. Medido: 1 amostra num bloco de 20 min, 4 em outro. Não é a
instrumentação: os outros dois graus, no mesmo script e na mesma porta, produzem
normalmente.

## Parte B — o rádio compartilhado

O nRF9151 tem **um** receptor de rádio para GNSS e modem LTE — os dois disputam o
mesmo hardware por *time multiplexing*. É texto da própria *Product Specification*:

> GPS receiver operation is time multiplexed with the LTE modem, and GPS and QZSS
> position can be received while the LTE modem is in RRC Idle mode, power saving
> mode (PSM), or completely deactivated.

Em rastreio contínuo (lab 1) essa disputa é discreta: o GNSS aproveita as folgas do
modem. Em **modo periódico**, ela aparece no log — porque o GNSS liga e desliga, e
cada janela que ele ganha (ou perde) para o LTE fica registrada.

### Receita

```bash
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_02_per C:/work/nrf-manaus-2/gnss/01_gnss_basic -- -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_CONTINUOUS=n -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_PERIODIC=y -D01_gnss_basic_CONFIG_GNSS_SAMPLE_LTE_ON_DEMAND=y -D01_gnss_basic_CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=n -D01_gnss_basic_CONFIG_GNSS_SAMPLE_ASSISTANCE_MINIMAL=y
cd C:/work/nrf-manaus-2
sh gnss/02_gnss_radio/verifica_variantes.sh gnss/01_gnss_basic/build_02_per periodico
```

Esta variante liga o mesmo grau de assistência **mínima** da Parte A
(`GNSS_SAMPLE_ASSISTANCE_MINIMAL`) — não por acaso: `GNSS_SAMPLE_LTE_ON_DEMAND` só
existe no Kconfig quando alguma assistência está ligada (ver "Pegadinhas" abaixo),
e a mínima é a que não exige certificado nem integração de nuvem, então o lab
continua rodando em qualquer bancada. Isso muda o que o firmware faz com os
downloads agendados de dado de navegação — ver "A disciplina de agenda" a seguir.

FLASH e RAM desta variante ficam próximos da variante **mínima** da Parte A
(106544 B / 10,84% de FLASH, 36060 B / 17,04% de RAM contra 107092 B / 10,89% e
36180 B / 17,10%) — a diferença é só o modo (periódico em vez de TTFF) e o
`GNSS_SAMPLE_LTE_ON_DEMAND`, que não puxa biblioteca nova, só muda a lógica de
`gnss/01_gnss_basic/src/main.c` que liga e desliga o LTE.

### As quatro mensagens, evidência do rádio dividido

A cada PVT, o firmware examina as *flags* que o modem devolve
(`print_flags()`, `gnss/01_gnss_basic/src/main.c`) e imprime uma linha para cada
uma que estiver setada:

| Flag do modem | Linha impressa | O que significa |
|---|---|---|
| `NRF_MODEM_GNSS_PVT_FLAG_DEADLINE_MISSED` | `GNSS operation blocked by LTE` | o LTE tomou o rádio na janela em que o GNSS precisava dele |
| `NRF_MODEM_GNSS_PVT_FLAG_NOT_ENOUGH_WINDOW_TIME` | `Insufficient GNSS time windows` | as folgas que o LTE deixou não foram longas o suficiente |
| `NRF_MODEM_GNSS_PVT_FLAG_SLEEP_BETWEEN_PVT` | `Sleep period(s) between PVT notifications` | o GNSS dormiu entre uma notificação e outra, dentro do próprio intervalo periódico |
| `NRF_MODEM_GNSS_PVT_FLAG_SCHED_DOWNLOAD` | `Scheduled navigation data download` | o GNSS está rodando fora do ciclo normal, baixando dado de navegação da transmissão dos satélites |

Tempo em que o LTE tomou o rádio, por partida a frio, na variante de nuvem:

| TTFF bruto | bloqueado pelo LTE | TTFF líquido |
|---|---|---|
| 34,6 s | 6 s | 28,6 s |
| 50,5 s | 9 s | 41,5 s |
| 57,4 s | 15 s | 42,4 s |
| 57,5 s | 29 s | 28,5 s |
| 59,1 s | 29 s | 30,1 s |
| 62,1 s | 31 s | 31,1 s |
| 63,2 s | 29 s | 34,2 s |
| 158,4 s | 30 s | 128,4 s |
| 232,0 s | 31 s | 201,0 s |
| 269,2 s | 29 s | 240,2 s |
| **mediana 60,6 s** | **mediana 29 s** | **mediana 37,9 s** |

**Aqui a conta se inverte.** A assistência de nuvem tira ~16 s do TTFF — 37,9 s líquidos
contra 54,0 s sem assistência. Mas o rádio compartilhado devolve 29 s, e o saldo fica
negativo.

E o bloqueio não é aleatório: **29 s aparece repetidamente**, quase sempre o mesmo valor.
Ele é o **timer de liberação RRC** da rede — o tempo que a UE fica presa em `RRC_CONNECTED`
depois de terminar a transferência. A própria documentação da Nordic diz que esse timer
"dura de 5 a 60 segundos, é definido pela rede e não é negociável pela UE".

Cruzando o `+CSCON` do log com a corrente medida no PPK2, o tempo bloqueado é **exatamente**
a janela entre `+CSCON: 1` e `+CSCON: 0`, um para um. Os dados de A-GNSS chegam em menos de
um segundo; o resto da janela a UE fica presa sem transferir nada.

**Uma observação de método, para quem for reproduzir:** no modo de teste de TTFF o sample
**não imprime** a mensagem `GNSS operation blocked by LTE` a cada PVT — ele acumula e
reporta uma linha `Time GNSS was blocked by LTE: <n> s` junto do fix. Contar as mensagens
numa build de TTFF dá sempre zero. A grandeza que interessa é o tempo, não a contagem.

**Como encurtar esse tempo.** Desativar o LTE na mão funciona (a variante mínima derruba a
janela de 30 s para 1,6 s e zera o bloqueio), mas **não é prática recomendável**: expõe o
dispositivo como mal comportado e pode render sanção da rede. Os caminhos corretos são o
**AS-RAI**, em que o dispositivo avisa a rede que terminou e pede a liberação antecipada, e o
**ajuste do timer em APN privada**, negociado com a operadora.

### A disciplina de agenda, a assistência e a precisão são a mesma decisão

Em modo periódico, o modem só baixa efemérides e almanaque **da própria
transmissão dos satélites** (50 bps, lento) quando precisa — e, quando decide que
precisa, ele **ignora temporariamente o intervalo e as tentativas configurados** e
roda GNSS continuamente até terminar o download. É o que a *flag*
`SCHED_DOWNLOAD` acima anuncia quando aparece.

Existe um bit que desliga esse comportamento —
`NRF_MODEM_GNSS_USE_CASE_SCHED_DOWNLOAD_DISABLE`, setado em
`gnss/01_gnss_basic/src/main.c` sempre que o modo é periódico **e** algum grau de
assistência está ligado:

```c
if (IS_ENABLED(CONFIG_GNSS_SAMPLE_MODE_PERIODIC) &&
    !IS_ENABLED(CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE)) {
	/* Disable GNSS scheduled downloads when assistance is used. */
	use_case |= NRF_MODEM_GNSS_USE_CASE_SCHED_DOWNLOAD_DISABLE;
}
```

**Esta variante usa assistência mínima, então essa condição é verdadeira**: o bit
é setado, e os downloads agendados ficam desligados. É a recomendação da Nordic —
desligar os downloads agendados **quando há assistência**, porque a assistência já
entrega efemérides e almanaque, e o GNSS não precisa mais parar a agenda para
buscar isso sozinho por conta própria. Na prática, isso quer dizer que a
`Scheduled navigation data download` da tabela acima **não deve aparecer** nesta
variante — o firmware está configurado para evitar exatamente essa interrupção.

O contraponto é a variante **sem** assistência da Parte A: se ela rodasse em modo
periódico (o que este lab não faz, mas o Kconfig deixaria), a condição acima seria
falsa, o bit ficaria desligado, e os downloads agendados continuariam — é o preço
de não ter assistência nenhuma. **Desligar o bit à força sem nenhuma
assistência ligada** — o que não é o caso de nenhuma receita deste lab, mas é a
armadilha que o Kconfig evita ao recusar `GNSS_SAMPLE_LTE_ON_DEMAND` sem
assistência (ver "Pegadinhas" abaixo) — significa que o receptor nunca recebe as
correções ionosféricas: a precisão cai, silenciosamente, sem nenhum erro no log.

Disciplina de agenda (downloads agendados desligados ou não), assistência (dados
prontos ou buscados na hora) e precisão (correção ionosférica presente ou ausente)
não são três decisões independentes — é a mesma decisão, vista de três ângulos. As
outras três mensagens da tabela (`GNSS operation blocked by LTE`,
`Insufficient GNSS time windows`, `Sleep period(s) between PVT notifications`)
continuam possíveis nesta variante: elas vêm da disputa comum do rádio entre LTE e
GNSS a cada janela periódica, não do download agendado — e é a assistência mínima
usando o LTE (para hora de rede e MCC) que dá ao rádio um motivo concreto para
disputar espaço com o GNSS.

## `verifica_variantes.sh`

```
Uso: verifica_variantes.sh <dir de build> <sem|minima|nuvem|periodico>
```

Recebe o **diretório de build** (`gnss/01_gnss_basic/build_02_sem`, por exemplo),
não o caminho do `.config` — o script monta `<dir>/01_gnss_basic/zephyr/.config`
sozinho. É a convenção oposta à de `gnss/01_gnss_basic/verifica_config.sh`, que
recebe o `.config` diretamente: aqui há quatro variantes para conferir com o mesmo
script, então receber só o diretório (e escolher a variante pelo segundo argumento)
evita repetir o caminho completo do `.config` em cada chamada.

## Pegadinhas

- **`CONFIG_GNSS_SAMPLE_LTE_ON_DEMAND` só existe quando há assistência ligada —
  ligar essa opção sem escolher um grau de assistência não faz nada.** Sintoma: se
  a receita da variante periódica passar `-D..._CONFIG_GNSS_SAMPLE_LTE_ON_DEMAND=y`
  sem também escolher um grau de assistência, o build compila normalmente mas o
  CMake avisa `warning: GNSS_SAMPLE_LTE_ON_DEMAND ... was assigned the value 'y'
  but got the value 'n'. Check these unsatisfied dependencies:
  (!GNSS_SAMPLE_ASSISTANCE_NONE) (=n)`, o `.config` sai sem a linha, e
  `verifica_variantes.sh` reporta `FALTA: CONFIG_GNSS_SAMPLE_LTE_ON_DEMAND=y`.
  Causa: no `Kconfig` do lab 1, `GNSS_SAMPLE_LTE_ON_DEMAND` vive dentro de
  `if !GNSS_SAMPLE_ASSISTANCE_NONE` — a opção **nem existe** para ser ligada
  enquanto a *choice* de assistência estiver no padrão do SDK
  (`GNSS_SAMPLE_ASSISTANCE_NONE`). Não é capricho do Kconfig: o próprio texto da
  opção diz "ativa o LTE só quando é preciso buscar dados de A-GNSS" — sem
  nenhuma assistência configurada, não há o que buscar, e "LTE sob demanda" não
  significa nada. Correção: a receita deste lab (acima) já liga
  `CONFIG_GNSS_SAMPLE_ASSISTANCE_MINIMAL=y` junto com `LTE_ON_DEMAND=y`, e
  `verifica_variantes.sh gnss/01_gnss_basic/build_02_per periodico` confere limpo,
  sem aviso do CMake e com `.config` trazendo as três linhas esperadas.
- **`CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=y`, na variante "sem", já é o padrão do
  Kconfig do SDK — a asserção não está testando essa linha da linha de comando,
  porque a linha de comando nem precisa dela.** O que de fato discrimina a
  variante "sem" das outras três é só `CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y` (o
  padrão do SDK é rastreio contínuo). Nas variantes "mínima" e "nuvem" as duas
  linhas checadas (modo e assistência) divergem do padrão — lá a asserção testa as
  duas de verdade.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/cellular/gnss` (`Kconfig`, `src/main.c`)
- *nRF9151 Product Specification* — seção "GPS receiver" ("Electrical
  specification" e a frase sobre *time multiplexing* com o LTE)
- nRF Connect SDK — documentação do `nrf_modem`, seção GNSS ("Periodic
  navigation" e o glossário de *Scheduled downloads*)
- `gnss/01_gnss_basic/` (Task 1 deste módulo) — o firmware que este lab recompila
