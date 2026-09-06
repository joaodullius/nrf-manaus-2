cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(lab_wifi_tcp)

# Codigo do curso (nrf-manaus-2): falha cedo em vez de gravar um kit que nao
# sabe para onde mandar os dados.
if(NOT CONFIG_LAB_SERVIDOR_IP)
  message(FATAL_ERROR
    "CONFIG_LAB_SERVIDOR_IP nao definido.\n"
    "Descubra o IP do seu PC na rede da sala (ipconfig) e passe:\n"
    "  -DCONFIG_LAB_SERVIDOR_IP=\"192.168.0.100\"")
endif()

target_sources(app PRIVATE src/main.c src/payload.c src/transporte.c)
