# GNSS e Localização de Precisão

Labs de geolocalização outdoor, separados do módulo de comunicação por usarem kits dedicados com fluxos distintos: o **nRF9151** (GNSS integrado ao modem, banda única) e o **u-blox EVK-X20P** (receptor multi-banda de alta precisão).

**Hardware:** nRF9151-SMA-DK × 3, u-blox EVK-X20P × 2, antenas GNSS ativas com visada de céu.

> A pergunta que organiza o módulo não é "como se lê uma posição", é **por que existem tantas técnicas de correção e como se escolhe entre elas**. A resposta é geografia e infraestrutura — e Manaus é o estudo de caso.

## Labs

| Lab | Descrição | Kit | Status |
|-----|-----------|-----|--------|
| [`01_gnss_basic/`](01_gnss_basic/) | **Lab 1** — O fix a frio, sem assistência: rastreio contínuo, precisão em metros, satélites rastreados × usados, sentenças NMEA. É a **única pasta com código-fonte** do módulo (cópia do sample `cellular/gnss` do NCS); os labs 2 e 3 recompilam este mesmo código | nRF9151-SMA-DK | ✅ compila e passa a asserção |
| [`02_gnss_radio/`](02_gnss_radio/) | **Lab 2** — Receita, sem código. Duas partes na mesma execução: a assistência em **três degraus** (nenhuma, mínima, nuvem) e o **rádio compartilhado** — LTE e GNSS disputam o mesmo front-end, e as mensagens de coexistência mostram a disputa | nRF9151-SMA-DK | ✅ quatro variantes compilam e passam |
| [`03_nmea/`](03_nmea/) | **Lab 3** — Receita, sem código. A porta que carrega **só NMEA**: log e AT host desligados, para alimentar o u-center e para gravar log reproduzível. Não ocupa bloco próprio de tempo — é o firmware do primeiro degrau da demo | nRF9151-SMA-DK | ✅ compila e passa a asserção |
| [`04_demo_rtk/`](04_demo_rtk/) | **Demo do instrutor**, sem código: os três degraus no **mesmo ponto físico**, com os dois EVK-X20P, mais as **cinco falhas de RTK** que dá para provocar mexendo só na base — e como diagnosticar cada uma. É onde a teoria de correção encontra número medido | 2 × EVK-X20P + antenas | ✅ roteiro escrito |

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

Um único código-fonte, quatro configurações. `02_gnss_radio/` e `03_nmea/` seguem o molde de [`comms/10_wifi_http_mqtt/`](../comms/10_wifi_http_mqtt/): são pastas de receita que recompilam o `01_gnss_basic` com outras opções. Cada uma traz seu script de asserção de configuração (`verifica_config.sh`, `verifica_variantes.sh`, `verifica_nmea.sh`), que confere o `.config` gerado antes de a placa entrar na história.

## A escada de precisão

> O roteiro completo do instrutor — montagem, Survey-In, mensagens RTCM, as cinco falhas e os diagnósticos — está em [`04_demo_rtk/`](04_demo_rtk/). O que segue é o resumo.

Uma antena fixa marca o ponto de medida. Os receptores se **revezam nela**, com troca de cabo e sempre desenergizados:

| Degrau | Receptor | Correção | Ordem de grandeza |
|---|---|---|---|
| 1 | nRF9151, banda única | nenhuma | metros |
| 2 | EVK-X20P, multibanda | nenhuma | decimétrica |
| 3 | EVK-X20P, multibanda | RTK da **base local** | centimétrica |

Uma segunda antena, alguns metros ao lado, é a **base**. A baseline curta elimina o termo de 1 ppm e faz as duas antenas verem rigorosamente a mesma atmosfera — o que também neutraliza a cintilação ionosférica que seria fatal numa baseline longa. **Manaus fica sob a anomalia equatorial**, então isso não é detalhe: é a razão de a montagem ser essa.

**O laço que fecha o módulo:** a coordenada verdadeira do ponto de medida sai do próprio fix RTK e volta como `CONFIG_GNSS_SAMPLE_REFERENCE_LATITUDE/LONGITUDE` no firmware do nRF9151. A partir daí a placa do aluno não reporta uma posição — reporta **o próprio erro contra uma verdade medida em sala**. O laço fecha no build do lab 1, o do console legível; no build do lab 3 essa linha sujaria o fluxo de NMEA.

**Ressalva que o material carrega:** os três degraus acontecem com minutos de diferença, não no mesmo instante. A comparação se sustenta porque a diferença entre metros e centímetros é enorme perto da deriva de geometria em poucos minutos — mas **não se afirma simultaneidade**.

### Bônus: a estação pública da UEA

A estação **AMUA0**, na Universidade do Estado do Amazonas, é publicada no caster do IBGE e está a distância útil. Testar RTK contra ela é **bônus, não lab**: depende de cadastro gratuito no IBGE e de internet na sala, e nenhuma das duas coisas é pré-requisito do módulo. O caminho garantido é a base própria, que roda offline.

## Ferramentas

| Ferramenta | Papel | Observação |
|---|---|---|
| **u-center 2** | Configurar o X20P, Survey-In, caster, cliente NTRIP, e o mapa de desvio com CEP50/CEP95 | Serve **também para o NMEA do nRF9151** — medido na bancada. Conta u-blox com dois fatores no primeiro uso, **fazer antes do curso** |
| **`gnss/tools/`** | Captura e análise próprias: grava `.nmea` + `.uc2`, desenha o mapa de desvio e o mapa do céu | O CEP bate com o do u-center dentro de 1 % |
| **RTKPLOT** (RTKLIB) | Opcional: as duas trilhas sobrepostas e a diferença | Exige `$GPRMC` e `$GPGGA` — que os dois receptores já emitem de fábrica |

## Tópicos teóricos

- **Constelações, bandas e fontes de erro**, e as técnicas de correção organizadas pelo que cada uma **exige de infraestrutura**: SBAS, RTK, PPP e PPP-RTK. Manaus entra aqui como estudo de caso — cintilação ionosférica e a geografia das estações de referência.
- **O rádio é um só.** LTE e GNSS compartilham o front-end do nRF9151 e são chaveados no tempo. Janela de GNSS, `deadline missed`, e por que a assistência é, antes de tudo, uma forma de encurtar o tempo em que o rádio precisa ficar com o GNSS.
- **Assistência em três degraus:** nenhuma, mínima (almanaque de fábrica + hora da rede + posição por MCC) e A-GNSS por nuvem. O que cada degrau custa em conectividade e o que devolve em tempo até o primeiro fix.
- **RTK por dentro:** base e rover, mensagens RTCM, baseline e o termo de 1 ppm, e por que a base própria é o caminho garantido enquanto o caster de terceiro é bônus.

---

> **Antes do curso:** a seção GNSS do [`PREREQUISITOS.md`](../PREREQUISITOS.md) lista as contas que precisam existir antes (u-blox, e a integração das DKs à nRF Cloud, que é tarefa do instrutor).
