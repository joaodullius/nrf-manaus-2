# 02 · Detecção de anomalia (Neuton na CPU)

Segundo exemplo do módulo: um modelo de anomalia monitora **vibração de engrenagem**
em 2 eixos e devolve um **score de desvio do normal**. Sem sensor e sem BLE — dois
vetores de teste embarcados (engrenagem saudável e com falha) mostram o conceito da
terceira tarefa da engine em minutos de bancada.

> **Origem:** cópia literal de `samples/nrf_edgeai/anomaly` do
> **Edge AI Add-on for nRF Connect SDK v2.3.0** (tag `v2.3.0`, commit `1c24f3a`),
> copiada em 2026-08-29. `src/main.c` e `prj.conf` carregam o caminho upstream no
> cabeçalho; licença Nordic preservada em [LICENSE](LICENSE).

## O que ele demonstra

- **Entrada**: 2 canais de vibração (eixos X e Y), `float32`, intercalados —
  janela de **128 = shift** (potência de 2: o descritor liga o **domínio da
  frequência**, então a FFT entra no binário — contraste direto com o `01_gesture`,
  que é só domínio do tempo).
- **Alimentação em lote**: a janela inteira num único `feed_inputs()`
  (`uniq × window_size` valores) → `SUCCESS` na primeira chamada. É o modo
  "em blocos" do slide 13 do M1-03.
- **Saída**: um único `float` — `decoded_output.anomaly.score`. Não há classes.
- **Veredito**: `score >= threshold` → anomalia. O limiar do sample é `0.000025f`.

## O conceito que vale a aula

O modelo de anomalia **treina só com dados normais**: ele não sabe o que é uma
falha, só mede o quanto o sinal desvia do normal aprendido. Consequências:

1. **O limiar é decisão da aplicação**, nunca do modelo. Escalas variam por caso:
   engrenagens/rolamentos vivem em ~0,00005 (normal) a ~0,00025 (falha); outras
   aplicações vão de 0 a 1000.
2. **Calibração faz parte do trabalho**: simule falhas após o deploy ou use o
   EdgeAI Inference Runner (ferramenta desktop do Edge AI Lab) com dados anormais.
3. É a escolha certa quando **não há como coletar exemplos da falha** — o oposto
   da classificação, que exige exemplos de cada classe.

## Build

De dentro de `C:\ncs\sdk-edge-ai` (toolchain v3.4.0 ativo):

```bash
west build -p -b nrf54lm20dk/nrf54lm20a/cpuapp --sysbuild -d C:\work\nrf-manaus-2\build\02_anomaly C:\work\nrf-manaus-2\edge_ai\02_anomaly
```

```bash
west flash -d C:\work\nrf-manaus-2\build\02_anomaly
```

Build de referência: **FLASH 62.812 B (3,0 %)** · **RAM 8.960 B (1,7 %)** —
engine + FFT + modelo em ~63 kB.

> Alvo `nrf54lm20a` de propósito: é a variante do LM20 **sem** Axon — nem por
> hardware este exemplo sai da CPU. O sample também compila para nRF52/53/54L/54H
> (não para a nRF54L15-TAG, que não está na lista de targets dele).

## Saída esperada na serial

```
--- Testing GOOD gear vibration data ---
Anomaly score for GOOD gear data: 0.0000xx
Verdict: NORMAL (score < threshold)
--- Testing ANOMALOUS gear vibration data ---
Anomaly score for ANOMALOUS gear data: 0.000xxx
Verdict: ANOMALY (score >= threshold)
```

## Classificação + anomalia

Anomalia não nomeia a falha; classificação não reconhece o nunca-visto. Três
padrões para compor (slide "três padrões" do M1-03):

1. **Classe UNKNOWN** no classificador (o `01_gesture` faz) — só pega o que parece
   com o "resto" treinado.
2. **Limiar de confiança** no pós-processamento — grátis, mas confiança não é
   familiaridade.
3. **Dois modelos no mesmo firmware** — a anomalia decidindo quando o classificador roda.
   A engine suporta: cada modelo gerado exporta símbolos com sufixo do solution-id
   (`nrf_edgeai_user_model_<id>()`), então N modelos convivem; alimente a mesma
   janela nos dois e só aceite a classe quando o score estiver abaixo do limiar.
