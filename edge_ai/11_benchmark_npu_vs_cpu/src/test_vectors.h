/*
 * Vetores de teste do benchmark: 7 janelas de magnitude de aceleracao (uma por
 * classe do modelo de estados de encomenda), 50 amostras f32 cada.
 *
 * ORIGEM: dados copiados de samples/nrf_edgeai/classification/src/main.c do
 * Edge AI Add-on v2.3.0 (capturas reais de sensor, uma sequencia por classe).
 */

#ifndef TEST_VECTORS_H_
#define TEST_VECTORS_H_

#include <stddef.h>

#include <nrf_edgeai/nrf_edgeai_ctypes.h>

#define BENCH_WINDOW_SIZE 50
#define BENCH_NUM_WINDOWS 7

struct bench_window {
	const char *label;
	int expected_class;
	const flt32_t *data; /* BENCH_WINDOW_SIZE amostras */
};

extern const struct bench_window bench_windows[BENCH_NUM_WINDOWS];

#endif /* TEST_VECTORS_H_ */
