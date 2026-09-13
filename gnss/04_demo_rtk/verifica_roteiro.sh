#!/bin/sh
# Confere que o roteiro da demo cobre os itens obrigatorios (mensagens RTCM, falhas, diagnosticos).
# Rodar da raiz do repo: sh gnss/04_demo_rtk/verifica_roteiro.sh
R="gnss/04_demo_rtk/README.md"
falhou=0
# As sete mensagens RTCM da lista recomendada para base estacionaria
for m in 1005 1006 1074 1084 1094 1124 1230; do
  grep -q "$m" "$R" || { echo "FALTA mensagem RTCM $m"; falhou=1; }
done
# As cinco falhas demonstraveis
for f in "Falha A" "Falha B" "Falha C" "Falha D" "Falha E"; do
  grep -q "$f" "$R" || { echo "FALTA $f"; falhou=1; }
done
# Os diagnosticos
for d in "RXM-COR" "msgUsed" "carrSoln"; do
  grep -q "$d" "$R" || { echo "FALTA diagnostico $d"; falhou=1; }
done
[ "$falhou" -eq 0 ] && echo "OK: roteiro cobre os itens obrigatorios"
exit "$falhou"
