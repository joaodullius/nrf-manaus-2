#
# ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
#   SDK     : nRF Connect SDK v3.4.0
#   Upstream: nrf/samples/wifi/provisioning/ble/CMakeLists.txt
#   Local   : C:/ncs/v3.4.0/nrf/samples/wifi/provisioning/ble/CMakeLists.txt
#   Copiado : 2026-09-07 — curso nrf-manaus-2, modulo comms/08b_wifi_provisioning_ble
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/wifi/provisioning/ble/CMakeLists.txt
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
project(wifi_ble_provisioning)

target_sources(app PRIVATE src/main.c)

zephyr_library_include_directories($<TARGET_PROPERTY:wifi_prov_core,BINARY_DIR>)

target_link_libraries(app PRIVATE wifi_prov_ble)
