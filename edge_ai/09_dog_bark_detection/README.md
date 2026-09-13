# 09 · Outro zip, mesmo molde — detector de latido

O mesmo app do [`08_cough_detection/`](../08_cough_detection/) com **outro zip** do
Edge AI Lab dentro: *Dog Bark Detection* (`sound-event-dog-bark`). A dupla existe
para provar o ponto do contrato padrão — **trocar de modelo não muda o app** — e
para mostrar que cada modelo tem um *temperamento* que o pós-processamento precisa
respeitar.

> **Origem do modelo:** solução pronta do
> [Nordic Edge AI Lab](https://www.nordicsemi.com/Products/Technologies/Edge-AI/Get-Started);
> [`src/nrf_edgeai_generated/`](src/nrf_edgeai_generated/) é cópia literal do zip,
> licença em [LICENSE.txt](LICENSE.txt), guia genérico do Lab em
> [README_edgeai_lab.md](README_edgeai_lab.md). O app (`src/main.c`) é do curso.

## A diferença que importa: a calibração

A anatomia do zip, as 4 chamadas da API e o fluxo do `main.c` são idênticos ao 08 —
leia lá. O que muda aqui é a tabela de pós-processamento:

| | 08 · tosse | 09 · latido |
|---|---|---|
| limiar bruto | 0,50 | **0,90** |
| quadros na janela de 15 | 2 | **5** |

Na bancada, o modelo de latido se mostrou **"gatilho fácil"**: dispara com pico de
92–99 % em qualquer som impulsivo (tosse, miado, até ronco). O de tosse é o oposto —
tímido. Mesma arquitetura, mesmo tamanho (~35 kB), datasets diferentes →
sensibilidades diferentes. **O limiar não é do framework, é de cada modelo** — e
descobrir o do seu é trabalho de bancada, olhando o pico bruto no painel.

## Hardware, build e uso

Idênticos ao 08 (troque `08_cough_detection` por `09_dog_bark_detection` nos
comandos). Para testar, um vídeo de latido no celular perto do mic:

```
=== 09_dog_bark_detection: detector de latido na NPU Axon ===
[latido] pico do ultimo segundo:   3%  (eventos: 0)
>>> LATIDO (pico 99%) — evento 1
```
