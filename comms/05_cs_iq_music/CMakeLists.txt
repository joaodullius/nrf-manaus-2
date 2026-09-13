#
# Copyright (c) 2024 Nordic Semiconductor
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(05_cs_iq_music)

# ALTERADO PELO CURSO (nrf-manaus-2): falha cedo e com mensagem util, em vez de
# compilar um initiator que conecta no TAG do colega.
if(NOT CONFIG_LAB_TAG_ADDR_VALUE)
  message(FATAL_ERROR
    "CONFIG_LAB_TAG_ADDR_VALUE nao definido.\n"
    "Este initiator so conecta no TAG cujo endereco BLE for informado.\n"
    "E o MESMO endereco do edge_ai/03_central_uart — copie o meu_tag.conf de la,\n"
    "ou leia a linha \"Identity:\" do log RTT do TAG e preencha:\n"
    "  CONFIG_LAB_TAG_ADDR_VALUE=\"EF:12:34:56:78:9A\"\n"
    "  CONFIG_LAB_TAG_ADDR_TYPE=\"random\"\n"
    "e compile com -DEXTRA_CONF_FILE=meu_tag.conf")
endif()

FILE(GLOB app_sources src/*.c)
# NORDIC SDK APP START
target_sources(app PRIVATE
  ${app_sources}
)
# NORDIC SDK APP END
