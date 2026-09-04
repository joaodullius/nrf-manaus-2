/*
 * 10_sound_events — cinco detectores de som rodando "ao mesmo tempo" na NPU Axon.
 *
 * Codigo do curso nrf-manaus-2 (modulo edge_ai/10_sound_events). Nao vem do SDK.
 * Os modelos em src/models/ sao solucoes prontas do Nordic Edge AI Lab
 * (sound-event-*), copiadas dos zips baixados do Lab.
 *
 * O mesmo audio do PDM alimenta CINCO engines nrf_edgeai independentes (choro de
 * bebe, latido, ronco, tosse, miado). A NPU executa um job por vez (mutex no
 * driver), entao "ao mesmo tempo" = as cinco inferencias intercaladas dentro de
 * cada janela de 30 ms — sobra tempo de NPU de folga.
 *
 * Saida (console Zephyr = uart20 = VCOM1 da DK, 115200):
 *   - um painel por segundo com a probabilidade (EMA) dos cinco detectores
 *   - uma linha ">>> <EVENTO> (NN%)" a cada deteccao, com cooldown de 2 s
 */

#include <math.h>
#include <stdint.h>

#include <zephyr/audio/dmic.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include <nrf_edgeai/nrf_edgeai.h>

#include "models/baby_cry/nrf_edgeai_generated/nrf_edgeai_user_model.h"
#include "models/cough/nrf_edgeai_generated/nrf_edgeai_user_model.h"
#include "models/dog_bark/nrf_edgeai_generated/nrf_edgeai_user_model.h"
#include "models/meow/nrf_edgeai_generated/nrf_edgeai_user_model.h"
#include "models/snoring/nrf_edgeai_generated/nrf_edgeai_user_model.h"

/* Mesmos parametros de audio do 06_mic_check e do 07_ww_kws */
#define SAMPLES_BLOCK_LENGTH_MS 10
#define DMIC_SAMPLE_BYTES	2
#define DMIC_PCM_RATE		16000
#define DMIC_SAMPLES_IN_BLOCK	(DMIC_PCM_RATE * SAMPLES_BLOCK_LENGTH_MS / 1000)
#define BLOCK_SIZE		(DMIC_SAMPLE_BYTES * DMIC_SAMPLES_IN_BLOCK)
#define READ_TIMEOUT_MS		1000

/* Pos-processamento (do app, nao do modelo — mesmo padrao da wake word do
 * 07_ww_kws): conta quantos dos ultimos HISTORY_SIZE quadros (um a cada 30 ms)
 * tiveram probabilidade BRUTA acima do limiar do detector. Eventos curtos dao
 * picos de 1-3 quadros; media movel os apaga, contagem de quadros nao.
 * O limiar e o numero de quadros sao POR DETECTOR (calibrados na bancada):
 * modelos "gatilho facil" (latido) exigem mais; modelos timidos, menos. */
#define HISTORY_SIZE	15 /* ~450 ms de historico */
#define COOLDOWN_INFS	66 /* ~2 s sem repetir a mesma deteccao */
#define PANEL_PERIOD_MS 1000
#define EMA_ALPHA	0.35f /* so para o painel */

struct detector {
	const char *name;
	nrf_edgeai_t *(*get)(void);
	float raw_threshold; /* limiar por quadro (probabilidade bruta) */
	uint8_t min_hits;    /* quadros acima do limiar nos ultimos HISTORY_SIZE */
	nrf_edgeai_t *model;
	uint32_t history;
	uint8_t hits;
	float ema;  /* media movel: so exibicao no painel */
	float peak; /* maior probabilidade bruta desde o ultimo painel */
	int cooldown;
	uint32_t events;
};

static struct detector detectors[] = {
	{"bebe", nrf_edgeai_user_model_sound_event_baby_cry, 0.70f, 2},
	{"latido", nrf_edgeai_user_model_sound_event_dog_bark, 0.90f, 5},
	{"ronco", nrf_edgeai_user_model_sound_event_snoring, 0.50f, 3},
	{"tosse", nrf_edgeai_user_model_sound_event_cough, 0.50f, 2},
	{"miado", nrf_edgeai_user_model_sound_event_meow, 0.70f, 2},
};

#define NUM_DETECTORS ARRAY_SIZE(detectors)

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

static int32_t block_rms_peak; /* maior RMS de bloco desde o ultimo painel */

static void print_panel(void)
{
	/* ema%/pico%: o pico mostra o que o modelo viu de fato no ultimo segundo
	 * (eventos curtos decaem antes do print). rms = nivel de audio que chegou. */
	printk("[painel] rms:%5d", block_rms_peak);
	block_rms_peak = 0;
	for (size_t i = 0; i < NUM_DETECTORS; i++) {
		printk(" %s:%3d/%3d%%", detectors[i].name, (int)(detectors[i].ema * 100.0f),
		       (int)(detectors[i].peak * 100.0f));
		detectors[i].peak = 0.0f;
	}
	printk("\n");
}

static void trace_raw(void)
{
	/* Traco das probabilidades brutas quando alguma passa de 25%:
	 * e o que os modelos veem QUADRO A QUADRO, sem pos-processamento. */
	float top = 0.0f;

	for (size_t i = 0; i < NUM_DETECTORS; i++) {
		float p = detectors[i].model->decoded_output.classif.probabilities.p_f32[0];

		if (p > top) {
			top = p;
		}
	}
	if (top < 0.25f) {
		return;
	}
	printk("~");
	for (size_t i = 0; i < NUM_DETECTORS; i++) {
		printk(" %s:%3d", detectors[i].name,
		       (int)(detectors[i].model->decoded_output.classif.probabilities.p_f32[0] *
			     100.0f));
	}
	printk("\n");
}

int main(void)
{
	printk("\n=== 10_sound_events: %u detectores na NPU Axon (PDM CLK=P1.04 DAT=P1.05) ===\n",
	       (unsigned int)NUM_DETECTORS);

	for (size_t i = 0; i < NUM_DETECTORS; i++) {
		struct detector *d = &detectors[i];

		d->model = d->get();
		if (d->model == NULL || nrf_edgeai_init(d->model) != NRF_EDGEAI_ERR_SUCCESS) {
			printk("ERRO: init do modelo '%s' falhou\n", d->name);
			return 0;
		}
		printk("  modelo '%s' pronto (solution %s)\n", d->name,
		       nrf_edgeai_solution_id_str(d->model));
	}

	if (dmic_setup() < 0) {
		return 0;
	}
	printk("Escutando. Painel a cada 1 s; deteccoes com '>>>'.\n\n");

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

		/* Nivel de audio do bloco (para o painel dizer o que chegou) */
		const int16_t *samples = buf;
		int64_t sum_sq = 0;

		for (size_t i = 0; i < DMIC_SAMPLES_IN_BLOCK; i++) {
			sum_sq += (int64_t)samples[i] * samples[i];
		}
		int32_t rms = (int32_t)sqrtf((float)(sum_sq / DMIC_SAMPLES_IN_BLOCK));

		if (rms > block_rms_peak) {
			block_rms_peak = rms;
		}

		/* Alimenta TODOS os engines antes de devolver o bloco ao driver:
		 * cada feed copia as amostras para a janela interna do modelo. */
		nrf_edgeai_err_t feed[NUM_DETECTORS];

		for (size_t i = 0; i < NUM_DETECTORS; i++) {
			feed[i] = nrf_edgeai_feed_inputs(detectors[i].model, buf,
							 DMIC_SAMPLES_IN_BLOCK);
		}
		k_mem_slab_free(&dmic_mem_slab, buf);

		bool inferred = false;

		for (size_t i = 0; i < NUM_DETECTORS; i++) {
			struct detector *d = &detectors[i];

			/* INPROGRESS = janela ainda nao fechou; nada a inferir */
			if (feed[i] != NRF_EDGEAI_ERR_SUCCESS) {
				continue;
			}
			if (nrf_edgeai_run_inference(d->model) != NRF_EDGEAI_ERR_SUCCESS) {
				continue;
			}
			inferred = true;

			float prob = d->model->decoded_output.classif.probabilities.p_f32[0];

			d->ema = EMA_ALPHA * prob + (1.0f - EMA_ALPHA) * d->ema;
			if (prob > d->peak) {
				d->peak = prob;
			}

			/* Janela deslizante de quadros "quentes", como na wake word */
			bool hot = prob >= d->raw_threshold;
			bool oldest = (d->history >> (HISTORY_SIZE - 1)) & 1U;

			d->hits += hot;
			d->hits -= oldest;
			d->history = ((d->history << 1) | hot) & BIT_MASK(HISTORY_SIZE);

			if (d->cooldown > 0) {
				d->cooldown--;
			} else if (d->hits >= d->min_hits) {
				d->events++;
				d->cooldown = COOLDOWN_INFS;
				d->history = 0;
				d->hits = 0;
				printk(">>> %s (pico %d%%, %u quadros > %d%%) — evento %u\n",
				       d->name, (int)(d->peak * 100.0f), d->min_hits,
				       (int)(d->raw_threshold * 100.0f), d->events);
			}
		}

		if (inferred) {
			trace_raw();
		}

		if (k_uptime_get() >= next_panel) {
			next_panel += PANEL_PERIOD_MS;
			print_panel();
		}
	}

	return 0;
}
