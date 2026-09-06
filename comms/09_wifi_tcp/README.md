# Wi-Fi · Lab 9 — telemetria por socket TCP

## O que observar

- O intervalo entre amostras de telemetria não é perfeitamente regular: a thread de
  recepção (`thread_recepcao()`, em `src/main.c`) segura o mutex do transporte
  (`transporte_mutex`, em `src/transporte.c`) durante toda a espera por uma linha do
  servidor (`transporte_receber()`, timeout de 1 s), e isso pode atrasar em até esse
  tempo um envio concorrente de telemetria ou do botão. É escolha de projeto — a
  exclusão mútua entre as threads que compartilham o mesmo socket prioriza corretude
  sobre regularidade — não sintoma de problema de rede ou do kit.
