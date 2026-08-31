#
# Copyright (c) 2018 Nordic Semiconductor
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(central_uart)

# Falha cedo e com mensagem util, em vez de compilar um central que nunca conecta.
if(NOT CONFIG_LAB_TAG_ADDR_VALUE)
  message(FATAL_ERROR
    "CONFIG_LAB_TAG_ADDR_VALUE nao definido.\n"
    "Este central so conecta no tag cujo endereco BLE for informado.\n"
    "Descubra o endereco do seu tag na linha \"Identity:\" do log RTT dele e defina, "
    "por exemplo em um fragmento meu_tag.conf:\n"
    "  CONFIG_LAB_TAG_ADDR_VALUE=\"EF:12:34:56:78:9A\"\n"
    "  CONFIG_LAB_TAG_ADDR_TYPE=\"random\"\n"
    "e compile com -DEXTRA_CONF_FILE=meu_tag.conf")
endif()

# NORDIC SDK APP START
target_sources(app PRIVATE
  src/main.c
  src/leds.c
)
# NORDIC SDK APP END
