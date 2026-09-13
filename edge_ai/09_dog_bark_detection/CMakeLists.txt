#
# 09_dog_bark_detection — detector de latido do Edge AI Lab na NPU Axon
# (curso nrf-manaus-2; app do curso, modelo gerado pelo Lab).
#
# Build (do SDK padrao, C:/ncs/v3.4.0; o add-on entra como modulo extra):
#   west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild \
#        -d C:/work/nrf-manaus-2/edge_ai/09_dog_bark_detection/build_lm20 \
#        C:/work/nrf-manaus-2/edge_ai/09_dog_bark_detection \
#        -- -DEXTRA_ZEPHYR_MODULES=C:/ncs/sdk-edge-ai/edge-ai
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(dog_bark_detection)

target_sources(app PRIVATE
    src/main.c
    src/nrf_edgeai_generated/nrf_edgeai_user_model.c
)
