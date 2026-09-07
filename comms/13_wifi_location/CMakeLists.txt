cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(lab_wifi_location)

# Codigo do curso (nrf-manaus-2): mesma falha proposital do lab 9 -- um kit
# sem IP de destino nao teria para onde mandar a lista de pontos de acesso.
if(NOT CONFIG_LAB_SERVIDOR_IP)
  message(FATAL_ERROR
    "CONFIG_LAB_SERVIDOR_IP nao definido.\n"
    "Descubra o IP do seu PC na rede da sala (ipconfig) e passe:\n"
    "  -D13_wifi_location_CONFIG_LAB_SERVIDOR_IP=\"192.168.0.100\"\n"
    "O prefixo 13_wifi_location e o nome da imagem no sysbuild, e e a forma que o\n"
    "curso usa em todos os labs. Precisa bater com o nome da pasta do lab.")
endif()

target_sources(app PRIVATE src/main.c)
