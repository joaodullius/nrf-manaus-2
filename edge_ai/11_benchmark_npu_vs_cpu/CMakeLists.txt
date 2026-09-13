#
# 11_benchmark_npu_vs_cpu — o mesmo modelo na CPU (Neuton) e na NPU (Axon)
# (curso nrf-manaus-2; app do curso, modelos do sample da Nordic).
#
# Build (do SDK padrao, C:/ncs/v3.4.0; o add-on entra como modulo extra):
#   Axon (padrao na LM20B):
#     west build -p -b nrf54lm20dk/nrf54lm20b/cpuapp --sysbuild \
#          -d .../11_benchmark_npu_vs_cpu/build_lm20_axon .../11_benchmark_npu_vs_cpu \
#          -- -DEXTRA_ZEPHYR_MODULES=C:/ncs/sdk-edge-ai/edge-ai
#   Neuton (CPU):
#     ... -d .../build_lm20_neuton ... \
#          -- -DEXTRA_ZEPHYR_MODULES=C:/ncs/sdk-edge-ai/edge-ai \
#             -D11_benchmark_npu_vs_cpu_CONFIG_NRF_EDGEAI_CLASSIFICATION_MODEL_NEUTON=y
#

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(benchmark_npu_vs_cpu)

if(CONFIG_NRF_EDGEAI_CLASSIFICATION_MODEL_AXON)
  target_sources(app PRIVATE src/nrf_edgeai_generated/Axon/nrf_edgeai_user_model.c)
  target_include_directories(app PRIVATE src/nrf_edgeai_generated/Axon)
  message(STATUS "Benchmark: modelo Axon (NPU)")
else()
  target_sources(app PRIVATE src/nrf_edgeai_generated/Neuton/nrf_edgeai_user_model.c)
  target_include_directories(app PRIVATE src/nrf_edgeai_generated/Neuton)
  message(STATUS "Benchmark: modelo Neuton (CPU)")
endif()

target_sources(app PRIVATE src/main.c src/test_vectors.c)
