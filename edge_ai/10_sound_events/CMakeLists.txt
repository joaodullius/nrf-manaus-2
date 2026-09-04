#
# 10_sound_events — cinco detectores de som do Edge AI Lab na NPU Axon
# (curso nrf-manaus-2; codigo do curso, modelos gerados pelo Lab).
#
# Build (do SDK padrao, C:/ncs/v3.4.0; o add-on entra como modulo extra):
#   west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild \
#        -d C:/work/nrf-manaus-2/edge_ai/10_sound_events/build_lm20 \
#        C:/work/nrf-manaus-2/edge_ai/10_sound_events \
#        -- -DEXTRA_ZEPHYR_MODULES=C:/ncs/sdk-edge-ai/edge-ai
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(sound_events)

target_sources(app PRIVATE
    src/main.c
    src/models/baby_cry/nrf_edgeai_generated/nrf_edgeai_user_model.c
    src/models/cough/nrf_edgeai_generated/nrf_edgeai_user_model.c
    src/models/dog_bark/nrf_edgeai_generated/nrf_edgeai_user_model.c
    src/models/meow/nrf_edgeai_generated/nrf_edgeai_user_model.c
    src/models/snoring/nrf_edgeai_generated/nrf_edgeai_user_model.c
)
