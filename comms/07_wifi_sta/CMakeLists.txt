#
# ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
#   SDK     : nRF Connect SDK v3.4.0
#   Upstream: nrf/samples/wifi/sta/CMakeLists.txt
#   Local   : C:/ncs/v3.4.0/nrf/samples/wifi/sta/CMakeLists.txt
#   Copiado : 2026-09-06 — curso nrf-manaus-2, modulo comms/07_wifi_sta
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/wifi/sta/CMakeLists.txt
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

# ALTERADO PELO CURSO (nrf-manaus-2): falha cedo e com mensagem util, em vez de
# gravar um kit que nao conecta em rede nenhuma.
if(NOT CONFIG_WIFI_CREDENTIALS_STATIC_SSID)
  message(FATAL_ERROR
    "CONFIG_WIFI_CREDENTIALS_STATIC_SSID nao definido.\n"
    "Preencha o minha_rede.conf com o SSID e a senha da rede da sala:\n"
    "  CONFIG_WIFI_CREDENTIALS_STATIC_SSID=\"nrf-curso\"\n"
    "  CONFIG_WIFI_CREDENTIALS_STATIC_PASSWORD=\"...\"\n"
    "e compile com -DEXTRA_CONF_FILE=minha_rede.conf")
endif()

target_include_directories(app PUBLIC ${ZEPHYR_BASE}/subsys/net/ip)

target_sources(app PRIVATE src/main.c)
