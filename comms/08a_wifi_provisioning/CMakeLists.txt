#
# ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
#   SDK     : nRF Connect SDK v3.4.0
#   Upstream: nrf/samples/wifi/provisioning/softap/CMakeLists.txt
#   Local   : C:/ncs/v3.4.0/nrf/samples/wifi/provisioning/softap/CMakeLists.txt
#   Copiado : 2026-09-06 — curso nrf-manaus-2, modulo comms/08a_wifi_provisioning
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/wifi/provisioning/softap/CMakeLists.txt
#
# DIVERGENCIA DO CURSO: nenhuma.
#

#
# Copyright (c) 2024 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(softap_wifi_provision_sample)

target_sources(app PRIVATE src/main.c)
