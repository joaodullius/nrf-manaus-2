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
  fix?** — modo periódico, sem assistência, onde LTE e GNSS disputam o mesmo rádio.

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
nRF Cloud são passos de **runtime**, não de build — o firmware sobe sem eles e só
falha ao tentar buscar dados de assistência de fato, em bancada. As três variantes
compilaram limpo, `exit 0`.

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

| Grau | TTFF a frio |
|---|---|
| sem | <!-- BANCADA: preencher --> |
| mínima | <!-- BANCADA: preencher --> |
| nuvem | <!-- BANCADA: preencher --> |

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
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_02_per C:/work/nrf-manaus-2/gnss/01_gnss_basic -- -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_CONTINUOUS=n -D01_gnss_basic_CONFIG_GNSS_SAMPLE_MODE_PERIODIC=y -D01_gnss_basic_CONFIG_GNSS_SAMPLE_LTE_ON_DEMAND=y
cd C:/work/nrf-manaus-2
sh gnss/02_gnss_radio/verifica_variantes.sh gnss/01_gnss_basic/build_02_per periodico
```

Esta variante **não** liga nenhum grau de assistência — herda o padrão
`GNSS_SAMPLE_ASSISTANCE_NONE` do Kconfig, igual ao lab 1. É deliberado: sem
assistência é a condição em que o rádio compartilhado mais aparece (ver "A
disciplina de agenda" abaixo).

FLASH e RAM desta variante ficam praticamente iguais ao lab 1 (82920 B / 8,44% de
FLASH, 33044 B / 15,62% de RAM) — trocar de contínuo para periódico não muda
biblioteca nenhuma, só o intervalo com que `nrf_modem_gnss_start()` é chamado.

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

Contagem de `GNSS operation blocked by LTE` (prazos perdidos) numa sessão de
bancada:

<!-- BANCADA: preencher -->

### A disciplina de agenda, a assistência e a precisão são a mesma decisão

Em modo periódico, o modem só baixa efemérides e almanaque **da própria
transmissão dos satélites** (50 bps, lento) quando precisa — e, quando decide que
precisa, ele **ignora temporariamente o intervalo e as tentativas configurados** e
roda GNSS continuamente até terminar o download. É o que a *flag*
`SCHED_DOWNLOAD` acima está anunciando quando aparece.

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

A recomendação da Nordic é exatamente essa condição: desligar os downloads
agendados **quando há assistência**, porque a assistência já entrega efemérides,
almanaque e (no caso da nRF Cloud) os parâmetros do modelo ionosférico NeQuick — o
GNSS não precisa mais parar a agenda para buscar isso sozinho. **Desligar esse bit
sem nenhuma assistência ligada** — o que aconteceria se este lab usasse
`GNSS_SAMPLE_ASSISTANCE_NONE` com o bit forçado desativado — significa que o
receptor nunca recebe as correções ionosféricas: a precisão cai, silenciosamente,
sem nenhum erro no log. Por isso esta variante (sem assistência) **mantém** os
downloads agendados ligados: é o preço de não ter assistência, e é isso que as
quatro mensagens acima tornam visível.

Disciplina de agenda (intervalo e retry respeitados ou não), assistência (dados
prontos ou buscados na hora) e precisão (correção ionosférica presente ou ausente)
não são três decisões independentes — é a mesma decisão, vista de três ângulos.

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

- **A receita da variante periódica não liga `CONFIG_GNSS_SAMPLE_LTE_ON_DEMAND`,
  mesmo passando `=y` na linha de build.** Sintoma:
  `sh verifica_variantes.sh gnss/01_gnss_basic/build_02_per periodico` imprime
  `FALTA: CONFIG_GNSS_SAMPLE_LTE_ON_DEMAND=y` e sai com código 1, embora o build em
  si tenha compilado limpo. Causa: no `Kconfig` do lab 1,
  `GNSS_SAMPLE_LTE_ON_DEMAND` só existe dentro de `if !GNSS_SAMPLE_ASSISTANCE_NONE`
  — e esta receita não liga nenhuma assistência, então a *choice* de assistência
  fica no padrão do SDK (`GNSS_SAMPLE_ASSISTANCE_NONE`), a dependência não é
  satisfeita, e o CMake avisa (`warning: ... was assigned the value 'y' but got the
  value 'n'`) e descarta o `=y`. **Isso não quebra a demonstração da Parte B**: o
  objetivo desta variante é justamente mostrar o rádio disputado **sem**
  assistência, e é exatamente essa combinação (periódico + `ASSISTANCE_NONE`) que
  mantém os downloads agendados ligados e as quatro mensagens visíveis. Se algum dia
  esta receita precisar mesmo de LTE-on-demand funcionando, é preciso também ligar
  um grau de assistência (por exemplo `..._ASSISTANCE_MINIMAL=y`) — o que muda o
  experimento, então não foi feito aqui.
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
