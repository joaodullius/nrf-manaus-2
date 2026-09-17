# GNSS e Localização de Precisão

Labs de geolocalização outdoor, separados do módulo de comunicação por usarem kits dedicados com fluxos distintos: o **nRF9151** (GNSS integrado ao modem, banda única) e o **u-blox EVK-X20P** (receptor multi-banda de alta precisão).

**Hardware:** nRF9151-SMA-DK × 3, u-blox EVK-X20P × 2, antenas GNSS ativas com visada de céu.

> A pergunta que organiza o módulo não é "como se lê uma posição", é **por que existem tantas técnicas de correção e como se escolhe entre elas**. A resposta é geografia e infraestrutura — e Manaus é o estudo de caso.

## Labs

| Lab | Descrição | Kit | Status |
|-----|-----------|-----|--------|
| [`01_nrf9151_basic/`](01_nrf9151_basic/) | **Lab 1** — O fix a frio, sem assistência: rastreio contínuo, precisão em metros, satélites rastreados × usados, sentenças NMEA. É a **única pasta com código-fonte** do módulo (cópia do sample `cellular/gnss` do NCS); os labs 2 e 3 recompilam este mesmo código | nRF9151-SMA-DK | ✅ compila e passa a asserção |
| [`02_nrf9151_radio/`](02_nrf9151_radio/) | **Lab 2** — Receita, sem código. Duas partes na mesma execução: a assistência em **três degraus** (nenhuma, mínima, nuvem) e o **rádio compartilhado** — LTE e GNSS disputam o mesmo front-end, e as mensagens de coexistência mostram a disputa | nRF9151-SMA-DK | ✅ quatro variantes compilam e passam |
| [`03_nrf9151_nmea/`](03_nrf9151_nmea/) | **Lab 3** — Receita, sem código. A porta que carrega **só NMEA**: log e AT host desligados, para alimentar o u-center e para gravar log reproduzível. Não ocupa bloco próprio de tempo — é o firmware do primeiro degrau da demo | nRF9151-SMA-DK | ✅ compila e passa a asserção |
| [`04_x20p_demo_rtk/`](04_x20p_demo_rtk/) | **Demo do instrutor**, sem código: os três degraus no **mesmo ponto físico**, com os dois EVK-X20P, mais as **cinco falhas de RTK** que dá para provocar mexendo só na base — e como diagnosticar cada uma. É onde a teoria de correção encontra número medido | 2 × EVK-X20P + antenas | ✅ roteiro escrito |

**O que há em cada pasta.** Só `01_nrf9151_basic/` tem código-fonte. `02_nrf9151_radio/` e
`03_nrf9151_nmea/` têm o README (a receita e os resultados), um `build.cmd` que executa a linha de
`west build` sobre o fonte do lab 1 com o binário saindo na própria pasta, e o
`verifica_*.sh` que confere o `.config` gerado antes de gravar. `04_x20p_demo_rtk/` tem só o
roteiro: a demo roda nos EVK-X20P pelo u-center 2 e usa o hex do lab 3 no nRF9151.
As ferramentas de PC (captura, mapa de desvio, NTRIP, base RTK) ficam em `tools/`.

Os números de bancada dos três labs estão **medidos e nos READMEs**, colhidos na bancada de
Porto Alegre em 2026-09-08/09: antena numa janela entre dois prédios, com vista de céu
parcial. São números de um sítio obstruído — é isso que os torna úteis em aula, porque é a
condição em que o aluno vai trabalhar, e não a de céu aberto do datasheet.

### Ordem de ensino

```
Lab 1  o fix a frio              "quanto custa uma posicao"     precisao em metros, ceu aberto
Lab 2  assistencia + coexistencia "o radio e um so"             tres degraus de TTFF
Lab 3  NMEA limpo                "porta de dados x depuracao"   entra no u-center
Demo   a escada de precisao      "metros, decimetros, centimetros" mesmo ponto, tres degraus
```

Um único código-fonte, quatro configurações. `02_nrf9151_radio/` e `03_nrf9151_nmea/` seguem o molde de [`comms/10_wifi_http_mqtt/`](../comms/10_wifi_http_mqtt/): são pastas de receita que recompilam o `01_nrf9151_basic` com outras opções. Cada uma traz seu script de asserção de configuração (`verifica_config.sh`, `verifica_variantes.sh`, `verifica_nmea.sh`), que confere o `.config` gerado antes de a placa entrar na história.

## Sequência de testes — o que cada build exige

Todos os builds do módulo compartilham o mesmo esqueleto, e é isso que precisa estar claro
antes de qualquer passo:

- **Fonte único, alvo único:** `gnss/01_nrf9151_basic`, `nrf9151dk/nrf9151/ns`, sempre com
  `--sysbuild`. As opções de cada variante levam o prefixo `01_nrf9151_basic_`, o nome da
  imagem de aplicação.
- **O hex é o `merged_nrf9151dk_nrf9151_ns.hex` do sysbuild** (`SB_CONFIG_MERGED_HEX_FILES=y`
  no `sysbuild.conf` do lab): TF-M e aplicação num arquivo só, o mesmo conteúdo do
  `tfm_merged.hex` que o `west flash` grava. O `zephyr.hex` sozinho não roda no alvo `/ns`.
  Gravar com `nrfutil device program --options chip_erase_mode=ERASE_ALL`.
- **Antena ativa no J2, com céu.** A SMA-DK não tem antena nem LNA de bordo
  (`CONFIG_MODEM_ANTENNA_GNSS_EXTERNAL=y` em todos os builds). Uma antena por receptor;
  troca de cabo sempre com o receptor desenergizado.
- **Console** na VCOM da DK a 115200. Modem `mfw_nrf91x1_2.0.4` (sai por `AT+CGMR` no
  console do lab 1). LTE-M forçado no `prj.conf`.
- **Antes de gravar, o `verifica_*.sh` do lab confere o `.config` do build.** O
  `hex/build_all.py` faz a mesma asserção antes de copiar cada hex.
- **As linhas completas** de `west build`, `west flash` e conferência dos seis builds, e as de
  gravação dos hex prontos, estão em [`comandos_west.txt`](comandos_west.txt), para copiar e colar.

| # | Lab | Firmware: hex pronto · pasta de build | Opções além do padrão | Exige para rodar | O que se observa | Confere com |
|---|---|---|---|---|---|---|
| 1 | Lab 1 | `01_nrf9151_basic.hex` · `01_nrf9151_basic/build_9151` | nenhuma: contínuo, sem assistência, log e AT host | antena + céu. **Não usa LTE**: SIM dispensável | fix a frio (dezenas de segundos a ~2 min na janela; 30,5 s no datasheet), satélites rastreados × usados, PVT a 1 Hz | `verifica_config.sh` |
| 2 | Lab 2 · sem | `02_nrf9151_ttff_sem.hex` · `02_nrf9151_radio/build_sem` | `MODE_TTFF_TEST=y`, `TTFF_TEST_COLD_START=y` | antena + céu. Sem LTE | TTFF por ciclo, partida a frio forçada, 120 s de sono entre ciclos | `verifica_variantes.sh … sem` |
| 3 | Lab 2 · mínima | `02_nrf9151_ttff_minima.hex` · `02_nrf9151_radio/build_minima` | + `ASSISTANCE_MINIMAL=y` (seleciona `LTE_ON_DEMAND`) | antena + **SIM com cobertura LTE-M** (hora da rede e posição por MCC) | TTFF; o LTE liga só para buscar a assistência. Pode travar depois de `Sleeping for 120 s` | `verifica_variantes.sh … minima` |
| 4 | Lab 2 · nuvem | `02_nrf9151_ttff_nuvem.hex` · `02_nrf9151_radio/build_nuvem` | + `ASSISTANCE_NRF_CLOUD=y` | antena + SIM LTE-M + **DK provisionada na nRF Cloud** (certificado; tarefa do instrutor) | A-GNSS em menos de 1 s e ~30 s presos em RRC conectado (`+CSCON`); `Time GNSS was blocked by LTE` | `verifica_variantes.sh … nuvem` |
| 5 | Lab 2 · periódica | sem hex · `02_nrf9151_radio/build_periodico` (receita do README) | `MODE_PERIODIC=y`, `LTE_ON_DEMAND=y`, `ASSISTANCE_MINIMAL=y` | antena + SIM LTE-M | as quatro mensagens do rádio compartilhado; LTE ligado e desligado a cada ciclo | `verifica_variantes.sh … periodico` |
| 6 | Lab 3 | `03_nrf9151_nmea.hex` · `03_nrf9151_nmea/build` | `NMEA_ONLY=y`, `LOG=n`, `AT_HOST_LIBRARY=n` | antena + céu. Sem LTE. No PC, u-center 2 **ou** `tools/nmea_captura.py` (a porta é exclusiva) | só linhas `$` na porta; mapa de desvio com CEP50 e CEP95 | `verifica_nmea.sh` |
| 7 | Demo | hex do lab 3 no nRF9151; 2 × EVK-X20P em HPG 2.11 | — | três antenas na mesma altura; u-center 2 (Survey-In na base, caster local, NTRIP no rover); sem internet | a escada metros → decímetros → centímetros; as cinco falhas de RTK | roteiro em `04_x20p_demo_rtk/` |

Só o passo 4 depende de infraestrutura fora da sala (rede LTE-M **e** nRF Cloud); os passos
3 e 5 dependem só da rede. Sem SIM ou sem cobertura, os passos 1, 2, 6 e a demo rodam
inteiros.

## A escada de precisão

> O roteiro completo do instrutor — montagem, Survey-In, mensagens RTCM, as cinco falhas e os diagnósticos — está em [`04_x20p_demo_rtk/`](04_x20p_demo_rtk/). O que segue é o resumo.

Cada receptor tem a **própria antena** ANN-MB2, sobre plano de terra de ø12 cm, todas na mesma altura e separadas por ~1,5 m. O nRF9151 e o rover gravam **ao mesmo tempo**:

| Degrau | Receptor | Correção | Ordem de grandeza |
|---|---|---|---|
| 1 | nRF9151, banda única | nenhuma | metros |
| 2 | EVK-X20P, multibanda | nenhuma | decimétrica |
| 3 | EVK-X20P, multibanda | RTK da **base local** | centimétrica |

A terceira antena, alguns metros ao lado, é a **base**. A baseline curta elimina o termo de 1 ppm e faz as antenas verem rigorosamente a mesma atmosfera, o que também neutraliza a cintilação ionosférica que seria fatal numa baseline longa.

**O laço que fecha o módulo:** a coordenada verdadeira do ponto de medida sai do próprio fix RTK e volta como `CONFIG_GNSS_SAMPLE_REFERENCE_LATITUDE/LONGITUDE` no firmware do nRF9151. A partir daí a placa do aluno não reporta uma posição — reporta **o próprio erro contra uma verdade medida em sala**. O laço fecha no build do lab 1, o do console legível; no build do lab 3 essa linha sujaria o fluxo de NMEA.

**Ressalva que o material carrega:** as antenas do nRF9151 e do rover não estão no mesmo ponto. Os degraus comparam **dispersão** (CEP de cada receptor contra a própria média), não a posição absoluta de um contra o outro.

### Bônus: a estação pública da UEA

A estação **AMUA0**, na Universidade do Estado do Amazonas, é publicada no caster do IBGE e está a distância útil. Testar RTK contra ela é **bônus, não lab**: depende de cadastro gratuito no IBGE e de internet na sala, e nenhuma das duas coisas é pré-requisito do módulo. O caminho garantido é a base própria, que roda offline.

### PointPerfect (PPP-RTK): medido em Porto Alegre, fora da demo de Manaus

O terceiro tipo de correção que o material mede é o **PointPerfect** da u-blox, um serviço de
PPP-RTK: em vez das observações brutas de uma base (OSR), o rover recebe um modelo de estado
(SSR: órbita, relógio, vieses e atmosfera regional). A entrega é por IP, em SPARTN via MQTT ou
como RTCM de uma **base virtual** gerada na posição do rover e servida por NTRIP, ou por L-band,
com um receptor NEO-D9S ao lado do X20P (L-band fica só como conceito neste curso). Em Porto
Alegre o acesso foi por NTRIP, pela Nordian (`services.nordian.com`, mountpoint
`NEAR-RTCM-VRS`): o rover envia o GGA e recebe 1005 e MSM4 da base virtual, então a baseline
efetiva é ~0 (a 1032 do fluxo aponta uma estação física a 16,4 km, mas a correção não vem dela).
Medido: em céu aberto, RTK fixo em 197 s num bloco e dois blocos de três sem fixar, CEP50 de
2 cm no bloco fixo; no cânion, CEP50 de 12 cm, por multicaminho. **Em Manaus não há cobertura
do PointPerfect na data do curso**: a comparação PPP-RTK × RTK entra no material com os dados de
Porto Alegre, e a demo usa a base própria e, como bônus, a AMUA0.

## Hex de referência

[`hex/`](hex/) tem um binário pronto de cada uma das cinco configurações do módulo (lab 1, as
três variantes de TTFF do lab 2 e o NMEA limpo do lab 3), para gravar sem compilar com
`nrfutil device program`. Todos são públicos: nenhum carrega credencial nem coordenada.
`hex/build_all.py` regenera os cinco e confere o `.config` de cada um antes de copiar.

## Ferramentas

| Ferramenta | Papel | Observação |
|---|---|---|
| **u-center 2** | Configurar o X20P, Survey-In, caster, cliente NTRIP, e o mapa de desvio com CEP50/CEP95 | Serve **também para o NMEA do nRF9151** — medido na bancada. Conta u-blox com dois fatores no primeiro uso, **fazer antes do curso** |
| **`gnss/tools/`** | Captura e análise próprias: grava `.nmea` + `.uc2`, desenha o mapa de desvio e o mapa do céu | O CEP bate com o do u-center dentro de 1 % |
| **RTKPLOT** (RTKLIB) | Opcional: as duas trilhas sobrepostas e a diferença | Exige `$GPRMC` e `$GPGGA` — que os dois receptores já emitem de fábrica |

## Tópicos teóricos

- **Constelações, bandas e fontes de erro**, e as técnicas de correção organizadas pelo que cada uma **exige de infraestrutura**: SBAS, RTK, PPP e PPP-RTK (o PPP-RTK medido é o PointPerfect da u-blox). Manaus entra aqui como estudo de caso — cintilação ionosférica e a geografia das estações de referência.
- **O rádio é um só.** LTE e GNSS compartilham o front-end do nRF9151 e são chaveados no tempo. Janela de GNSS, `deadline missed`, e por que a assistência é, antes de tudo, uma forma de encurtar o tempo em que o rádio precisa ficar com o GNSS.
- **Assistência em três degraus:** nenhuma, mínima (almanaque de fábrica + hora da rede + posição por MCC) e A-GNSS por nuvem. O que cada degrau custa em conectividade e o que devolve em tempo até o primeiro fix.
- **RTK por dentro:** base e rover, mensagens RTCM, baseline e o termo de 1 ppm. A base própria é o caminho garantido; as duas fontes externas são de tipos diferentes: a estação física de um caster (AMUA0, no caster do IBGE: bônus em Manaus) e o PPP-RTK entregue por NTRIP como base virtual (PointPerfect via Nordian: medido em Porto Alegre, sem cobertura em Manaus).

---

> **Antes do curso:** a seção GNSS do [`PREREQUISITOS.md`](../PREREQUISITOS.md) lista as contas que precisam existir antes (u-blox, e a integração das DKs à nRF Cloud, que é tarefa do instrutor).
