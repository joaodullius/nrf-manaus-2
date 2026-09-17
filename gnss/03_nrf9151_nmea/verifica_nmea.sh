#!/bin/sh
# Uso: verifica_nmea.sh <dir de build>
# Confere que o build entrega NMEA limpo: a sentenca ligada, e os dois
# concorrentes do mesmo UART desligados.
CFG="$1/01_gnss_basic/zephyr/.config"
falhou=0
grep -qx "CONFIG_GNSS_SAMPLE_NMEA_ONLY=y" "$CFG" || { echo "FALTA: NMEA_ONLY"; falhou=1; }
grep -qx "CONFIG_LOG=y" "$CFG" && { echo "SOBRA: CONFIG_LOG=y, o log vai sujar o NMEA"; falhou=1; }
grep -qx "CONFIG_AT_HOST_LIBRARY=y" "$CFG" && { echo "SOBRA: CONFIG_AT_HOST_LIBRARY=y, as respostas do modem caem no mesmo UART"; falhou=1; }
[ "$falhou" -eq 0 ] && echo "OK: build de NMEA limpo"
exit "$falhou"
