#
# ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
#   SDK     : nRF Connect SDK v3.4.0
#   Upstream: nrf/samples/wifi/ble_coex/CMakeLists.txt
#   Local   : C:/ncs/v3.4.0/nrf/samples/wifi/ble_coex/CMakeLists.txt
#   Copiado : 2026-09-06 — curso nrf-manaus-2, modulo comms/12_wifi_coex
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/wifi/ble_coex/CMakeLists.txt
#
# DIVERGENCIA DO CURSO (duas): 1. minha_rede.conf; 2. falha de build no
# CMakeLists.
#

#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(nrf_wifi_sta)

target_sources(app PRIVATE
  src/bt_throughput_test.c
  src/main.c
)

# For net_private.h
target_include_directories(app PUBLIC ${ZEPHYR_BASE}/subsys/net/ip)

zephyr_library_include_directories(${ZEPHYR_BASE}/samples/bluetooth)

# ALTERADO PELO CURSO (nrf-manaus-2): falha cedo e com mensagem util, em vez de
# gravar um kit que nao conecta em rede nenhuma.
if(NOT CONFIG_WIFI_CREDENTIALS_STATIC_SSID)
  message(FATAL_ERROR
    "CONFIG_WIFI_CREDENTIALS_STATIC_SSID nao definido.\n"
    "Preencha o minha_rede.conf com o SSID e a senha da rede da sala:\n"
    "  CONFIG_WIFI_CREDENTIALS_STATIC_SSID=\"nrf-curso\"\n"
    "  CONFIG_WIFI_CREDENTIALS_STATIC_PASSWORD=\"...\"\n"
    "e compile com -D12_wifi_coex_EXTRA_CONF_FILE=minha_rede.conf")
endif()
