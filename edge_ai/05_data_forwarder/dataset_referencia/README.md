# Dataset de referência do loop 2 — velocidade de um ventilador por vibração

Coleta feita no preparo do curso, em 2026-09-03, com o `05_data_forwarder` **deste
repo** (9 canais, LED de estado, fundo de escala ±4 g / ±1000 dps) e o
**Data Forwarder Host** por BLE direto no PC. Serve para quem não tiver tempo de coletar,
e como gabarito do que o Passo 4 e o Passo 5 do [README](../README.md) produzem.

Uso: TAG presa a um ventilador portátil de 3 velocidades. Quatro classes:

| `class` | label | O que é |
|---:|---|---|
| 0 | `idle` | TAG presa ao ventilador, ventilador desligado |
| 1 | `vel1` | velocidade 1 |
| 2 | `vel2` | velocidade 2 |
| 3 | `vel3` | velocidade 3 |

## Arquivos

- **`dataset_ventilador.csv`** — o que sobe no Lab. Gerado por
  `tools/fwd_to_lab.py merge` a partir de `bruto/`, na ordem idle → vel1 → vel2 → vel3.
  Header `ax,ay,az,gx,gy,gz,temp,hum,pres,class`, 146.523 linhas, valores em
  **micro-unidades SI** float, exatamente como o Host gravou.
- **`bruto/`** — as gravações do Host, uma por classe, intocadas: o `.csv` e o `.txt` de
  metadados que ele escreve ao lado (transporte, timing, canais, erros).

## As gravações

| Arquivo | Classe | Linhas | Duração | Taxa | Perdidas | σ az (m/s²) | σ gx (rad/s) |
|---|---|---:|---:|---:|---:|---:|---:|
| `idle_ble-6dbeaa_…09-46-06` | idle | 36.695 | 367,5 s | 99,84 Hz | 0 | 0,009 | 0,001 |
| `vel1_ble-6dbeaa_…09-52-25` | vel1 | 37.237 | 373,0 s | 99,84 Hz | 0 | 0,054 | 0,003 |
| `vel2_ble-6dbeaa_…09-58-56` | vel2 | 36.120 | 361,8 s | 99,83 Hz | 3 | 0,098 | 0,014 |
| `vel3_ble-6dbeaa_…10-05-07` | vel3 | 36.471 | 365,4 s | 99,80 Hz | 15 | 0,174 | 0,014 |

σ = desvio-padrão do canal, medido pelo `fwd_to_lab.py info`. É a separação "a olho":
a amplitude cresce com a velocidade, mas `vel2` e `vel3` têm o mesmo σ no giroscópio —
o que separa de verdade é o **espectro**, e por isso o treino usa os features de
frequência (janela 128, potência de 2).

As quatro classes foram gravadas em sequência, na mesma sessão BLE (`6dbeaa`), ventilador
**na bateria**, TAG no mesmo lugar do começo ao fim; o `idle` é o ventilador desligado.
As quatro classes diferem só no que se quer classificar.

## Para coletar o seu

**Muda só a variável que se quer classificar.** A fixação do sensor faz parte da classe:
a mesma velocidade com a TAG presa de outro jeito dá outro perfil de vibração, e o modelo
aprende as duas como classes diferentes. Prenda a TAG uma vez e grave todas as classes
sem mexer nela — inclusive `idle`, com o ventilador desligado e a TAG no mesmo lugar.
O `fwd_to_lab.py info` mostra o desvio-padrão de cada gravação; duas gravações da mesma
classe com σ muito diferentes são sinal de que algo além da velocidade mudou.

**E colete nas condições em que o modelo vai rodar.** Um ventilador portátil gira mais
devagar no carregador do que na bateria: um modelo treinado no carregador classifica
`vel1` como `vel2` quando o ventilador está na bateria — com 99% de confiança. O
espectro de vibração é o objeto que o modelo aprende, e a fonte de alimentação do
ventilador faz parte dele. Este dataset foi coletado **na bateria**, que é como o
ventilador anda na aula. Se as duas condições importarem, grave as duas e junte na mesma
classe: o `merge` aceita vários arquivos por classe, e `--session-col` deixa o Lab
validar entre gravações, que é a acurácia que interessa.

## Limitações

**Fundo de escala ±4 g / ±1000 dps**, não o ±2 g / ±500 dps do sample. A app de
inferência tem de configurar o BMI270 igual, senão o modelo vê um sinal que nunca satura
onde o dataset saturava (ou o contrário).

**Taxa real 99,8 Hz**, não 100. É o `device_time_ms` avançando 9/10/11 ms — jitter do
timer do sample, sem perda. As 18 amostras perdidas (3 em `vel2`, 15 em `vel3`, em 12
minutos) são buracos de 20 ms registrados pelo Host no transporte BLE; irrelevante para
o treino.

**Unidades:** micro-unidades SI do Zephyr — m/s² × 10⁶ para o acelerômetro, **rad/s** ×
10⁶ para o giroscópio (não dps), °C / % / kPa × 10⁶ para o BME688. A app alimenta o modelo
com `sensor_value_to_micro()`, sem fator.

## Regenerar

```
cd edge_ai\05_data_forwarder
python tools\fwd_to_lab.py info  dataset_referencia\bruto\*.csv
python tools\fwd_to_lab.py merge dataset_referencia\bruto\idle_*.csv dataset_referencia\bruto\vel1_*.csv dataset_referencia\bruto\vel2_*.csv dataset_referencia\bruto\vel3_*.csv --classes idle,vel1,vel2,vel3 --out dataset_referencia\dataset_ventilador.csv
```

No Lab: target `class`; marcar `temp`, `hum`, `pres` em *Remove variables*; signal
processing com janela **128** e features de frequência.
