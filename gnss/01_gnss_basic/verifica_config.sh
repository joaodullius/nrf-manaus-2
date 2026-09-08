#!/bin/sh
# Verifica que o build do lab 1 saiu com a configuracao que o lab exige.
CFG="$1"
falhou=0
for esperado in \
  "CONFIG_MODEM_ANTENNA_GNSS_EXTERNAL=y" \
  "CONFIG_GNSS_SAMPLE_MODE_CONTINUOUS=y" \
  "CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=y"
do
  if ! grep -qx "$esperado" "$CFG"; then
    echo "FALTA: $esperado"
    falhou=1
  fi
done
[ "$falhou" -eq 0 ] && echo "OK: configuracao do lab 1 confere"
exit "$falhou"
