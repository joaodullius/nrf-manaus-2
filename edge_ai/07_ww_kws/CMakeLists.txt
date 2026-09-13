#
# ORIGEM: copia literal de arquivo do SDK — nao e codigo do curso.
#   Add-on  : Edge AI Add-on for nRF Connect SDK v2.3.0 (tag v2.3.0, commit 1c24f3a)
#   SDK     : nRF Connect SDK v3.4.0 (workspace do add-on)
#   Upstream: applications/ww_kws/CMakeLists.txt
#   Local   : C:/ncs/sdk-edge-ai/edge-ai/applications/ww_kws/CMakeLists.txt
#   Copiado : 2026-09-04 — curso nrf-manaus-2, modulo edge_ai/07_ww_kws
#
# Para conferir se divergiu do SDK:
#   diff <este arquivo> C:/ncs/sdk-edge-ai/edge-ai/applications/ww_kws/CMakeLists.txt
#
#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(ww_kws)

target_sources(app PRIVATE
  src/main.c

  src/control_output.c
  src/dmic.c
  src/leds.c

  src/ww/wakeword.c
  src/ww/nrf_edgeai_generated/nrf_edgeai_user_model.c

  src/kws/kws.c
  src/kws/nrf_edgeai_generated/nrf_edgeai_user_model.c
)

target_sources_ifdef(CONFIG_MODELS_OBSERVABILITY_MDS app PRIVATE src/ble/ble_mds.c)
