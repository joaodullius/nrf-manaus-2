#
# ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
#   SDK     : nRF Connect SDK v3.4.0
#   Upstream: nrf/samples/wifi/twt/CMakeLists.txt
#   Local   : C:/ncs/v3.4.0/nrf/samples/wifi/twt/CMakeLists.txt
#   Copiado : 2026-09-06 — curso nrf-manaus-2, modulo comms/11_wifi_twt
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/wifi/twt/CMakeLists.txt
#
# DIVERGENCIA DO CURSO: src/lab_rede.c (rede digitada no terminal e gravada
# em settings), adicionado ao target_sources.
#

#
# Copyright (c) 2023 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(nrf_wifi_twt)


target_include_directories(app PUBLIC ${ZEPHYR_BASE}/subsys/net/ip)
target_include_directories(app PRIVATE modules/traffic_gen/inc)

add_subdirectory(modules/traffic_gen)

target_sources(app PRIVATE src/main.c src/lab_rede.c)
