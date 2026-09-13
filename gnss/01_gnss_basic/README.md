# GNSS · Lab 1 — o fix a frio, sem assistência

Este é o lab base do módulo de GNSS: cópia do sample `nrf/samples/cellular/gnss` do
**nRF Connect SDK v3.4.0**, compilado com o modo padrão do SDK (rastreio contínuo) e
sem nenhuma assistência (nem nRF Cloud A-GNSS, nem SUPL, nem almanaque de fábrica). É
o firmware que os labs 2 e 3 deste módulo recompilam com outras opções — aqui está o
código-fonte; lá são só receitas de build diferentes sobre este mesmo `gnss/
01_gnss_basic`.

> **Origem.** Cópia de `nrf/samples/cellular/gnss` do **nRF Connect SDK v3.4.0**
> (`src/`, `Kconfig`, `prj.conf`, `CMakeLists.txt` e o overlay de placa). Cada arquivo
> copiado leva o cabeçalho `ORIGEM:` do curso. A única divergência do SDK é
> `CONFIG_MODEM_ANTENNA_GNSS_EXTERNAL=y` em `prj.conf` — ver "Pegadinhas" abaixo.

## Hardware

| Peça | Papel |
|---|---|
| **nRF9151 SMA DK** (PCA10201) | roda o firmware; modem LTE-M/NB-IoT/GNSS |
| **Antena GNSS ativa** | conectada ao conector **J2** por cabo SMA |
| **PC** | terminal serial (VCOM) |

A nRF9151 SMA DK não tem antena de bordo nem LNA de GNSS — ao contrário da nRF9151 DK
comum, ela depende inteiramente da antena externa. Monte a antena ativa no **J2** antes
de ligar a placa; sem ela o receptor não recebe nada.

## Passo 1 — compilar e gravar

```
cd C:\ncs\v3.4.0
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_9151 C:/work/nrf-manaus-2/gnss/01_gnss_basic
nrfutil sdk-manager toolchain launch --ncs-version v3.4.0 -- west flash -d C:/work/nrf-manaus-2/gnss/01_gnss_basic/build_9151
```

O nome da imagem no sysbuild é `01_gnss_basic`, igual ao nome da pasta — é o prefixo
que as receitas de build dos labs 2 e 3 reaproveitam. O `.config` da imagem de
aplicação sai em `build_9151/01_gnss_basic/zephyr/.config`.

Build limpo. O alvo `/ns` traz TF-M: o sysbuild gera a imagem segura (`tfm`) e a
imagem de aplicação não seguro (`01_gnss_basic`) — a tabela abaixo é da **imagem de
aplicação**, a que importa para este lab:

| Região | Usado | Região total | % usado |
|---|---|---|---|
| FLASH | 83052 B | 960 KB | 8,45% |
| RAM | 33044 B | 211608 B | 15,62% |

## `verifica_config.sh`

```
sh gnss/01_gnss_basic/verifica_config.sh gnss/01_gnss_basic/build_9151
```

Esperado: `OK: configuracao do lab 1 confere`. O script confere as três opções que definem
este lab no `.config` da imagem de aplicação: a antena externa, o modo contínuo e a
ausência de assistência. As três scripts do módulo recebem o **diretório de build**, não o
`.config` — vale para `verifica_variantes.sh` e `verifica_nmea.sh` também.

## Passo 2 — abrir o console

Abra a porta serial (VCOM) da DK a 115200 bps. O firmware liga
`CONFIG_AT_HOST_LIBRARY=y`, herdado do sample: além do log do sample, o console aceita
comandos AT diretos — é como se lê a versão do firmware do modem (`AT+CGMR`) numa
placa nRF91, já que o `nrfutil` não lê isso.

## Passo 3 — esperar o fix a frio

Este lab não usa nenhuma assistência (`CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=y`, o padrão
do Kconfig do sample): o modem parte sem almanaque, sem hora de rede e sem posição
aproximada. O primeiro fix é um **fix a frio** — pode demorar, e só acontece com a
antena vendo céu aberto (não funciona perto de janela com muita obstrução, nem
dentro de prédio).

Tempo até o primeiro fix nesta bancada:

| partida | tempo até o fix |
|---|---|
| 1 | 99,9 s |
| 2 | 25,8 s |
| 3 | 35,3 s |

Três partidas do mesmo firmware, no mesmo ponto, no mesmo dia, com a mesma antena. **A
dispersão é o resultado**, não a média: sem assistência o modem tem de decodificar as
efemérides direto do sinal, e quanto tempo isso leva depende de quais satélites estão
visíveis na hora em que ele liga. A especificação do nRF9151 dá 30,5 s de partida a frio em
céu aberto — duas das três partidas caem em volta desse número, e a terceira mostra o que a
vista de céu parcial cobra.

Um detalhe que surpreende: **resetar a placa não encurta o tempo**. Depois do reset o tempo
GPS volta a `000000` e a data a `060180` — o modem perdeu hora e posição. Não existe
"partida quente" por reset aqui: toda partida deste lab é fria. É exatamente esse custo que
o lab 2 vai atacar com assistência.

## Passo 4 — ler a saída

A cada atualização de PVT (*Position, Velocity, Time*), o sample imprime três blocos:

1. **A precisão em metros** — a linha `Accuracy: <N> m`, dentro do bloco de dados do
   fix (latitude, longitude, altitude, velocidade, DOPs).
2. **Satélites rastreados contra usados** — a linha `Tracking: <N> Using: <N>
   Unhealthy: <N>`. "Tracking" é quanto o modem enxerga; "Using" é quanto entrou de
   fato no cálculo da posição.
3. **As sentenças NMEA** — depois do bloco de dados, sob o cabeçalho `NMEA strings:`,
   uma sequência de sentenças `$GPRMC`, `$GPGGA`, `$GPGLL`, `$GPGSA` e `$GPGSV` (mais
   os satélites QZSS habilitados no NMEA por `nrf_modem_gnss_qzss_nmea_mode_set`).

Antes do primeiro fix, essas três linhas não aparecem — só o log de conexão com a
rede LTE e, se aplicável, `Assistance data needed: ...` (irrelevante aqui, porque a
assistência está desligada).

## O que observar

- `CONFIG_GNSS_SAMPLE_MODE_CONTINUOUS=y` e `CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=y` são
  os **padrões** do `Kconfig` do sample — este lab não precisa selecioná-los à mão,
  só herda o que já vem escolhido. A única linha que o curso acrescenta é a da antena
  externa.
- `CONFIG_AT_HOST_LIBRARY=y` fica ligado neste lab (é como se lê `AT+CGMR` para saber
  a versão do firmware do modem). O lab 3 é quem desliga essa opção.
- O `.gitignore` do lab (`build*/`) cobre qualquer diretório de build criado aqui
  dentro, incluindo o `build_9151` usado nos comandos acima.

## Pegadinhas

- **Antena ativa é obrigatória.** A nRF9151 SMA DK não tem antena de bordo nem LNA de
  GNSS — sem a antena externa plugada no J2, a placa não recebe nada.
- **Numa nRF9151 DK comum, a mesma opção piora o desempenho.** Essa placa tem antena
  de bordo com LNA embutido. Ligar `CONFIG_MODEM_ANTENNA_GNSS_EXTERNAL=y` nela
  desabilita o LNA de bordo — o firmware deste lab é pensado para a SMA DK, não para
  a DK comum.
- **Fix a frio sem assistência pode demorar, e exige céu aberto.** Sem almanaque, sem
  hora de rede e sem posição aproximada, o modem tem que resolver tudo do zero; a
  antena precisa de visada de céu, não funciona perto de obstrução.
- **Nunca plugar a mesma antena em dois receptores ao mesmo tempo.** O J2 da SMA DK
  entrega 3 V e o EVK entrega 3,3 V para a antena ativa — com os dois plugados juntos,
  um regulador empurra corrente para dentro do outro. Troque a antena sempre com o
  receptor desenergizado.

## Fontes

- nRF Connect SDK v3.4.0 — `nrf/samples/cellular/gnss`
- Bancada `nrf-manaus-2` — nRF9151 SMA DK (PCA10201) + antena GNSS ativa no J2
