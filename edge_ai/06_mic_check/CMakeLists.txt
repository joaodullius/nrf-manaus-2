#
# mic_check — prova de bancada do microfone PDM (curso nrf-manaus-2).
#
# Build (do SDK padrao, C:/ncs/v3.4.0 — e Zephyr puro, nao precisa do add-on):
#   west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild \
#        -d C:/work/nrf-manaus-2/edge_ai/06_mic_check/build_lm20 \
#        C:/work/nrf-manaus-2/edge_ai/06_mic_check
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(mic_check)

target_sources(app PRIVATE src/main.c)
