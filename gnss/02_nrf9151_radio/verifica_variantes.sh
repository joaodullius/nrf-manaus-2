#!/bin/sh
# Uso: verifica_variantes.sh <dir de build> <sem|minima|nuvem|periodico>
CFG="$1/01_gnss_basic/zephyr/.config"
case "$2" in
  sem)        esperado="CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=y" ;;
  minima)     esperado="CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y CONFIG_GNSS_SAMPLE_ASSISTANCE_MINIMAL=y" ;;
  nuvem)      esperado="CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y CONFIG_GNSS_SAMPLE_ASSISTANCE_NRF_CLOUD=y" ;;
  periodico)  esperado="CONFIG_GNSS_SAMPLE_MODE_PERIODIC=y CONFIG_GNSS_SAMPLE_LTE_ON_DEMAND=y" ;;
  *) echo "variante desconhecida: $2"; exit 2 ;;
esac
falhou=0
for e in $esperado; do
  grep -qx "$e" "$CFG" || { echo "FALTA: $e"; falhou=1; }
done
[ "$falhou" -eq 0 ] && echo "OK: variante $2 confere"
exit "$falhou"
