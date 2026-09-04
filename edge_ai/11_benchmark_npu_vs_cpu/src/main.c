/*
 * 11_benchmark_npu_vs_cpu — o MESMO modelo, medido na CPU (Neuton) e na NPU (Axon).
 *
 * Codigo do curso nrf-manaus-2 (modulo edge_ai/11_benchmark_npu_vs_cpu). Os dois
 * modelos em src/nrf_edgeai_generated/{Neuton,Axon}/ vem do sample
 * nrf_edgeai/classification do Edge AI Add-on v2.3.0: a mesma solution de
 * estados de encomenda gerada nos dois backends. O CMake escolhe UM deles pelo
 * Kconfig CONFIG_NRF_EDGEAI_CLASSIFICATION_MODEL_{NEUTON,AXON} — o app nao muda
 * uma linha entre as duas variantes.
 *
 * O que o harness faz (padrao do sample axon_low_power da Nordic):
 *   - vetores embarcados (7 janelas de 50 amostras, uma por classe) — nenhum
 *     sensor: o estimulo e identico e deterministico nas duas variantes
 *   - mede so o nrf_edgeai_run_inference(), com o relogio do sistema
 *     (k_cycle_get_32 — o cycle counter da CPU congela nos estados de idle);
 *     o feed e um memcpy e fica fora da conta
 *   - roda varreduras de BENCH_SWEEPS x 7 inferencias e dorme
 *     BENCH_SLEEP_MS entre elas — no PPK2 cada rajada aparece como um degrau
 *     de corrente sobre o piso de sono
 *
 * Para a medicao de corrente, recompile com o fragmento power.conf (desliga
 * console/serial/log) e pendure o PPK2 na DK.
 */

#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include <nrf_edgeai/nrf_edgeai.h>

#include "nrf_edgeai_user_model.h"
#include "test_vectors.h"

#define BENCH_SWEEPS	100  /* inferencias por rajada = BENCH_SWEEPS * 7 */
#define BENCH_SLEEP_MS	2000 /* sono entre rajadas (piso de corrente no PPK2) */

#if IS_ENABLED(CONFIG_NRF_EDGEAI_CLASSIFICATION_MODEL_AXON)
#define VARIANTE "Axon (NPU)"
#else
#define VARIANTE "Neuton (CPU)"
#endif

int main(void)
{
	printk("\n=== 11_benchmark: %s ===\n", VARIANTE);

	nrf_edgeai_t *p_model = nrf_edgeai_user_model();

	if (p_model == NULL || nrf_edgeai_init(p_model) != NRF_EDGEAI_ERR_SUCCESS) {
		printk("ERRO: init do modelo falhou\n");
		return 0;
	}
	printk("Modelo: solution %s, janela %u, %u classes\n",
	       nrf_edgeai_solution_id_str(p_model),
	       (unsigned int)nrf_edgeai_input_window_size(p_model),
	       (unsigned int)nrf_edgeai_model_outputs_num(p_model));

	uint32_t sweep_num = 0;

	while (true) {
		uint64_t total_ns = 0;
		uint64_t min_ns = UINT64_MAX;
		uint64_t max_ns = 0;
		uint32_t inferences = 0;
		uint32_t erros = 0;

		for (uint32_t s = 0; s < BENCH_SWEEPS; s++) {
			for (size_t w = 0; w < BENCH_NUM_WINDOWS; w++) {
				const struct bench_window *bw = &bench_windows[w];

				nrf_edgeai_err_t res = nrf_edgeai_feed_inputs(
					p_model, (void *)bw->data, BENCH_WINDOW_SIZE);

				if (res != NRF_EDGEAI_ERR_SUCCESS) {
					printk("ERRO: feed '%s' (%d)\n", bw->label, res);
					continue;
				}

				uint32_t t0 = k_cycle_get_32();

				res = nrf_edgeai_run_inference(p_model);

				uint32_t t1 = k_cycle_get_32();

				if (res != NRF_EDGEAI_ERR_SUCCESS) {
					printk("ERRO: inferencia '%s' (%d)\n", bw->label, res);
					continue;
				}

				uint64_t ns = k_cyc_to_ns_floor64((uint32_t)(t1 - t0));

				total_ns += ns;
				inferences++;
				if (ns < min_ns) {
					min_ns = ns;
				}
				if (ns > max_ns) {
					max_ns = ns;
				}

				if (p_model->decoded_output.classif.predicted_class !=
				    bw->expected_class) {
					erros++;
				}
			}
		}

		sweep_num++;
		printk("[%s] rajada %u: %u inferencias, latencia us min/med/max = "
		       "%llu / %llu / %llu, classes erradas: %u\n",
		       VARIANTE, sweep_num, inferences, min_ns / 1000,
		       (total_ns / inferences) / 1000, max_ns / 1000, erros);

		k_sleep(K_MSEC(BENCH_SLEEP_MS));
	}

	return 0;
}
