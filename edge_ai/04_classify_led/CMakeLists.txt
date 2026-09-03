#
# Copyright (c) 2025 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)

# Zephyr CMake project
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(classify_led)

# ==============================================================================
# CURSO: qual modelo entra no binario. Cada subpasta de src/nrf_edgeai_generated/
# tem os arquivos gerados pelo Edge AI Lab (nrf_edgeai_user_model.c/.h e
# nrf_edgeai_user_types.h) de UM modelo:
#
#   Neuton           modelo de exemplo da Nordic — estados de transporte de uma
#                    encomenda a partir da magnitude da aceleracao: 1 entrada
#                    (mili-g), janela 50, 7 classes. E o ponto de partida da
#                    aula: funciona sem treinar nada.
#   ventilador_95922 modelo do curso — velocidade de um ventilador por vibracao:
#                    6 entradas (IMU em micro-unidades), janela 128, 4 classes
#                    (idle, vel1, vel2, vel3).
#   <seu_modelo>     copie a pasta nrf_edgeai_generated/ do zip do Lab para ca.
#
# Trocar o modelo = trocar este nome E, em src/main.c, as constantes USER_* e a
# tabela CLASS_COLORS (os dois conjuntos estao la, um comentado).
# Recompile com -p: o CMake so rele este arquivo num build pristine — sem o -p
# voce grava o modelo antigo achando que trocou.
# ==============================================================================
set(CURSO_MODELO "Neuton")
# set(CURSO_MODELO "ventilador_95922")

if(CONFIG_NRF_EDGEAI_CLASSIFICATION_MODEL_AXON)
  set(CURSO_MODELO "Axon")
endif()

set(NN_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/src/nrf_edgeai_generated/${CURSO_MODELO}")
if(NOT EXISTS "${NN_SOURCE}/nrf_edgeai_user_model.c")
  message(FATAL_ERROR "Modelo '${CURSO_MODELO}' nao encontrado em ${NN_SOURCE}. "
                      "Confira CURSO_MODELO no CMakeLists.txt.")
endif()
message(STATUS "Edge AI model: ${CURSO_MODELO}")

target_sources(app PRIVATE ${NN_SOURCE}/nrf_edgeai_user_model.c)
target_include_directories(app PRIVATE ${NN_SOURCE})

target_sources(app PRIVATE src/main.c)
