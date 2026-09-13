#
# ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
#   SDK     : nRF Connect SDK v3.4.0
#   Upstream: nrf/samples/wifi/twt/modules/traffic_gen/CMakeLists.txt
#   Local   : C:/ncs/v3.4.0/nrf/samples/wifi/twt/modules/traffic_gen/CMakeLists.txt
#   Copiado : 2026-09-06 — curso nrf-manaus-2, modulo comms/11_wifi_twt
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/wifi/twt/modules/traffic_gen/CMakeLists.txt
#
# DIVERGENCIA DO CURSO: nenhuma - byte a byte igual ao SDK (conferido em
# 2026-09-06, ignorando fim de linha).
#

#
# Copyright (c) 2023 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

zephyr_include_directories(inc)

target_sources_ifdef(CONFIG_TRAFFIC_GEN app PRIVATE src/main.c)
target_sources_ifdef(CONFIG_TRAFFIC_GEN app PRIVATE src/tcp.c)
