#
# ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
#   SDK     : nRF Connect SDK v3.4.0
#   Upstream: nrf/samples/wifi/shell/CMakeLists.txt
#   Local   : C:/ncs/v3.4.0/nrf/samples/wifi/shell/CMakeLists.txt
#   Copiado : 2026-09-06 — curso nrf-manaus-2, modulo comms/06_wifi_shell
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/wifi/shell/CMakeLists.txt
#
# DIVERGENCIA DO CURSO: nenhuma.
#

#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(nrf_wifi_shell)

target_sources_ifdef(CONFIG_NRF70_RAW_DATA_TX app PRIVATE src/wifi_raw_tx_pkt_shell.c)

target_sources_ifdef(CONFIG_NRF70_PROMISC_DATA_RX app PRIVATE src/wifi_promiscuous_shell.c)

target_sources(app PRIVATE src/main.c)
