#
# mic_check — prova de bancada do microfone PDM (curso nrf-manaus-2).
#
# Build (do workspace do Edge AI Add-on, C:/ncs/sdk-edge-ai):
#   west build -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild \
#        -d C:/work/nrf-manaus-2/edge_ai/06_ww_kws/mic_check/build_lm20 \
#        C:/work/nrf-manaus-2/edge_ai/06_ww_kws/mic_check
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(mic_check)

target_sources(app PRIVATE src/main.c)
