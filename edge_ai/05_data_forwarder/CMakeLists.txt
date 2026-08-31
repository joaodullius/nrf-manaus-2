cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(data_forwarder)

find_program(ZCBOR zcbor REQUIRED)

set(CDDL_FILE ${CMAKE_CURRENT_LIST_DIR}/cddl/data_forwarder.cddl)
set(GEN_SRC_DIR ${PROJECT_BINARY_DIR}/src)
set(GEN_INC_DIR ${PROJECT_BINARY_DIR}/include)
set(GEN_ENCODE_C ${GEN_SRC_DIR}/data_forwarder_encode.c)
set(GEN_ENCODE_H ${GEN_INC_DIR}/data_forwarder_encode.h)

file(MAKE_DIRECTORY ${GEN_SRC_DIR})
file(MAKE_DIRECTORY ${GEN_INC_DIR})

# ALTERADO PELO CURSO (nrf-manaus-2) — contorno de bug do zcbor no Windows.
#
# O upstream passa --output-c/--output-h ABSOLUTOS. O zcbor do toolchain faz
#
#     makedirs("./" + path.dirname(saida))          zcbor.py:2793
#
# o que num caminho absoluto do Windows vira "./C:" e explode com
# OSError: [WinError 123]. Resultado: o sample nao compila no Windows.
#
# Reproduzido com o sample INTOCADO do add-on (v2.3.0), direto de
# C:/ncs/sdk-edge-ai/edge-ai/samples/data_forwarder — nao e efeito da copia.
#
# Contorno: passar os caminhos RELATIVOS. O add_custom_command roda com
# working directory = CMAKE_CURRENT_BINARY_DIR = PROJECT_BINARY_DIR, que e
# exatamente a raiz de GEN_SRC_DIR/GEN_INC_DIR — entao "./src" resolve no
# mesmo lugar, e o OUTPUT segue absoluto para o ninja rastrear.
#
# Em Linux/macOS o upstream funciona; este contorno tambem.
file(RELATIVE_PATH GEN_ENCODE_C_REL ${PROJECT_BINARY_DIR} ${GEN_ENCODE_C})
file(RELATIVE_PATH GEN_ENCODE_H_REL ${PROJECT_BINARY_DIR} ${GEN_ENCODE_H})

add_custom_command(
  OUTPUT ${GEN_ENCODE_C} ${GEN_ENCODE_H}
  COMMAND ${ZCBOR} code
          -c ${CDDL_FILE}
          --output-c ${GEN_ENCODE_C_REL}
          --output-h ${GEN_ENCODE_H_REL}
          --default-max-qty ${CONFIG_DATA_FWD_PROTO_MAX_CHANNELS}
          -t envelope
          -e
  WORKING_DIRECTORY ${PROJECT_BINARY_DIR}
  DEPENDS ${CDDL_FILE}
  COMMENT "Generating CBOR encoder from ${CDDL_FILE}"
)

target_include_directories(app PRIVATE
  ${GEN_INC_DIR}
)

target_sources(app PRIVATE
  src/main.c
  src/protocol/protocol.c
  ${GEN_ENCODE_C}
)

if(CONFIG_DATA_FWD_SENSOR_BMI270)
  target_sources(app PRIVATE src/sensor/bmi270.c)
elseif(CONFIG_DATA_FWD_SENSOR_ADXL367)
  target_sources(app PRIVATE src/sensor/adxl367.c)
elseif(CONFIG_DATA_FWD_SENSOR_BME688)
  target_sources(app PRIVATE src/sensor/bme688.c)
endif()

if(CONFIG_DATA_FWD_TRANSPORT_BLE_NUS)
  target_sources(app PRIVATE src/transport/ble_nus.c)
elseif(CONFIG_DATA_FWD_TRANSPORT_UART)
  target_sources(app PRIVATE src/transport/uart.c)
endif()
