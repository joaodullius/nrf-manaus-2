/*
 * 08_cough_detection — um zip do Edge AI Lab rodando na NPU Axon.
 *
 * Codigo do curso nrf-manaus-2 (modulo edge_ai/08_cough_detection). O modelo em
 * src/nrf_edgeai_generated/ e a solucao pronta "sound-event-cough" do Nordic
 * Edge AI Lab, copiada literal do zip baixado do Lab.
 *
 * O app segue o template do README que vem no zip (README_edgeai_lab.md):
 * com UM modelo no binario, o alias generico nrf_edgeai_user_model() aponta
 * para ele, e a inferencia sao 4 chamadas:
 *
 *   nrf_edgeai_user_model() -> nrf_edgeai_init() ->
 *   nrf_edgeai_feed_inputs() -> nrf_edgeai_run_inference()
 *
 * Audio: PDM 16 kHz mono (mesma pinagem do 06_mic_check). Saida no console
 * (uart20 = VCOM1 da DK, 115200): painel 1x/s com o pico de probabilidade e
 * uma linha ">>>" a cada tosse detectada.
 */

#include <stdint.h>

#include <zephyr/audio/dmic.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include <nrf_edgeai/nrf_edgeai.h>

#include "nrf_edgeai_generated/nrf_edgeai_user_model.h"

/* Mesmos parametros de audio do 06_mic_check e do 07_ww_kws */
#define SAMPLES_BLOCK_LENGTH_MS 10
#define DMIC_SAMPLE_BYTES	2
#define DMIC_PCM_RATE		16000
#define DMIC_SAMPLES_IN_BLOCK	(DMIC_PCM_RATE * SAMPLES_BLOCK_LENGTH_MS / 1000)
#define BLOCK_SIZE		(DMIC_SAMPLE_BYTES * DMIC_SAMPLES_IN_BLOCK)
#define READ_TIMEOUT_MS		1000

/* Pos-processamento (do app): o modelo e um detector de 1 classe e devolve,
 * a cada ~30 ms, a probabilidade de haver tosse na janela. Uma tosse e um
 * evento CURTO — 1 a 3 quadros altos — entao contamos quadros brutos acima
 * do limiar numa janela deslizante (mesmo padrao da wake word do 07_ww_kws).
 * Valores calibrados na bancada do curso. */
#define RAW_THRESHOLD	0.50f
#define MIN_HITS	2
#define HISTORY_SIZE	15 /* ~450 ms */
#define COOLDOWN_INFS	66 /* ~2 s sem redisparar */
#define PANEL_PERIOD_MS 1000

K_MEM_SLAB_DEFINE_STATIC(dmic_mem_slab, BLOCK_SIZE, 4, 4);

static const struct device *const dmic_dev = DEVICE_DT_GET(DT_NODELABEL(dmic_dev));

static int dmic_setup(void)
{
	struct pcm_stream_cfg stream = {
		.pcm_rate = DMIC_PCM_RATE,
		.pcm_width = DMIC_SAMPLE_BYTES * 8,
		.block_size = BLOCK_SIZE,
		.mem_slab = &dmic_mem_slab,
	};
	struct dmic_cfg cfg = {
		.io = {
			.min_pdm_clk_freq = 1000000,
			.max_pdm_clk_freq = 3250000,
			.min_pdm_clk_dc = 40,
			.max_pdm_clk_dc = 60,
		},
		.streams = &stream,
		.channel = {
			.req_chan_map_lo = dmic_build_channel_map(0, 0, PDM_CHAN_LEFT),
			.req_chan_map_hi = 0,
			.req_num_chan = 1,
			.req_num_streams = 1,
		},
	};

	if (!device_is_ready(dmic_dev)) {
		printk("ERRO: pdm20 nao esta pronto\n");
		return -ENODEV;
	}

	int err = dmic_configure(dmic_dev, &cfg);

	if (err < 0) {
		printk("ERRO: dmic_configure falhou (%d)\n", err);
		return err;
	}

	err = dmic_trigger(dmic_dev, DMIC_TRIGGER_START);
	if (err < 0) {
		printk("ERRO: dmic_trigger START falhou (%d)\n", err);
		return err;
	}

	return 0;
}

int main(void)
{
	printk("\n=== 08_cough_detection: detector de tosse na NPU Axon ===\n");

	/* Passos 1 e 2 do template do Lab: pegar o modelo e inicializar */
	nrf_edgeai_t *p_model = nrf_edgeai_user_model();

	if (p_model == NULL || nrf_edgeai_init(p_model) != NRF_EDGEAI_ERR_SUCCESS) {
		printk("ERRO: init do modelo falhou\n");
		return 0;
	}
	printk("Modelo pronto: solution %s, janela de %u amostras\n",
	       nrf_edgeai_solution_id_str(p_model),
	       (unsigned int)nrf_edgeai_input_window_size(p_model));

	if (dmic_setup() < 0) {
		return 0;
	}
	printk("Escutando. Tussa perto do microfone.\n\n");

	float peak = 0.0f;
	uint32_t history = 0;
	uint8_t hits = 0;
	int cooldown = 0;
	uint32_t events = 0;
	int64_t next_panel = k_uptime_get() + PANEL_PERIOD_MS;

	while (true) {
		void *buf;
		size_t size;
		int err = dmic_read(dmic_dev, 0, &buf, &size, READ_TIMEOUT_MS);

		if (err < 0) {
			printk("ERRO: dmic_read falhou (%d)\n", err);
			k_sleep(K_SECONDS(1));
			continue;
		}

		/* Passo 3 do template: alimentar o modelo (copia para a janela
		 * interna; o bloco do DMIC pode ser devolvido em seguida) */
		nrf_edgeai_err_t res =
			nrf_edgeai_feed_inputs(p_model, buf, DMIC_SAMPLES_IN_BLOCK);

		k_mem_slab_free(&dmic_mem_slab, buf);

		/* INPROGRESS = janela interna ainda nao fechou */
		if (res != NRF_EDGEAI_ERR_SUCCESS) {
			continue;
		}

		/* Passo 4: inferencia (na NPU; a CPU dorme ate a interrupcao) */
		if (nrf_edgeai_run_inference(p_model) != NRF_EDGEAI_ERR_SUCCESS) {
			continue;
		}

		/* Resultado em decoded_output: detector de 1 classe -> p_f32[0] */
		float prob = p_model->decoded_output.classif.probabilities.p_f32[0];

		if (prob > peak) {
			peak = prob;
		}

		bool hot = prob >= RAW_THRESHOLD;
		bool oldest = (history >> (HISTORY_SIZE - 1)) & 1U;

		hits += hot;
		hits -= oldest;
		history = ((history << 1) | hot) & BIT_MASK(HISTORY_SIZE);

		if (cooldown > 0) {
			cooldown--;
		} else if (hits >= MIN_HITS) {
			events++;
			cooldown = COOLDOWN_INFS;
			history = 0;
			hits = 0;
			printk(">>> TOSSE (pico %d%%) — evento %u\n",
			       (int)(peak * 100.0f), events);
		}

		if (k_uptime_get() >= next_panel) {
			next_panel += PANEL_PERIOD_MS;
			printk("[tosse] pico do ultimo segundo: %3d%%  (eventos: %u)\n",
			       (int)(peak * 100.0f), events);
			peak = 0.0f;
		}
	}

	return 0;
}
