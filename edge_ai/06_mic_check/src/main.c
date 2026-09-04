/*
 * mic_check — prova de bancada do microfone PDM (Adafruit 3492) na nRF54LM20-DK.
 *
 * Codigo do curso nrf-manaus-2 (modulo edge_ai/06_mic_check). Nao vem do SDK.
 *
 * Configura o PDM20 exatamente como o app ww_kws da Nordic (16 kHz, 16 bits,
 * canal esquerdo, blocos de 10 ms) e imprime, a cada 100 ms, o nivel do sinal
 * (RMS, pico, DC) com uma barra de VU. Serve para provar que CLK, DAT, SEL e
 * a alimentacao do microfone estao certos ANTES de colocar o modelo no meio.
 *
 * Leitura do resultado (console Zephyr = uart20 = VCOM1 da DK):
 *   - silencio na sala : RMS na casa de dezenas a poucas centenas, DC pequeno
 *   - falando perto    : RMS sobe para milhares, barra enche
 *   - "amostras todas iguais": DAT solto, SEL no lado errado ou mic sem VDD
 */

#include <stdint.h>
#include <stdlib.h>
#include <math.h>

#include <zephyr/audio/dmic.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

/* Mesmos parametros de applications/ww_kws/src/dmic.h */
#define SAMPLES_BLOCK_LENGTH_MS 10
#define DMIC_SAMPLE_BYTES	2
#define DMIC_PCM_RATE		16000
#define DMIC_SAMPLES_IN_BLOCK	(DMIC_PCM_RATE * SAMPLES_BLOCK_LENGTH_MS / 1000)
#define BLOCK_SIZE		(DMIC_SAMPLE_BYTES * DMIC_SAMPLES_IN_BLOCK)

#define BLOCKS_PER_REPORT	10 /* 10 x 10 ms = um relatorio a cada 100 ms */
#define READ_TIMEOUT_MS		1000
#define VU_WIDTH		30

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

static void print_vu(int32_t rms)
{
	/* Escala em dBFS: -90 dB (barra vazia) ate 0 dB (cheia) */
	float db = (rms > 0) ? 20.0f * log10f((float)rms / 32768.0f) : -90.0f;
	int filled = (int)((db + 90.0f) * VU_WIDTH / 90.0f);

	if (filled < 0) {
		filled = 0;
	}
	if (filled > VU_WIDTH) {
		filled = VU_WIDTH;
	}

	printk("|");
	for (int i = 0; i < VU_WIDTH; i++) {
		printk(i < filled ? "#" : " ");
	}
	printk("| %4d dBFS", (int)db);
}

int main(void)
{
	printk("\n=== mic_check: PDM20 CLK=P1.04 DAT=P1.05 SEL=GND, 16 kHz mono (canal esquerdo) ===\n");

	if (dmic_setup() < 0) {
		return 0;
	}
	printk("PDM rodando. Fale perto do microfone e veja a barra subir.\n\n");

	uint32_t report = 0;

	while (true) {
		int64_t sum = 0;
		int64_t sum_sq = 0;
		int16_t peak = 0;
		int16_t first = 0;
		bool all_equal = true;
		uint32_t n = 0;

		for (int b = 0; b < BLOCKS_PER_REPORT; b++) {
			void *buf;
			size_t size;
			int err = dmic_read(dmic_dev, 0, &buf, &size, READ_TIMEOUT_MS);

			if (err < 0) {
				printk("ERRO: dmic_read falhou (%d): o PDM nao esta entregando blocos\n",
				       err);
				k_sleep(K_SECONDS(1));
				continue;
			}

			const int16_t *s = buf;
			size_t cnt = size / DMIC_SAMPLE_BYTES;

			if (n == 0 && cnt > 0) {
				first = s[0];
			}
			for (size_t i = 0; i < cnt; i++) {
				int32_t v = s[i];

				sum += v;
				sum_sq += (int64_t)v * v;
				if (abs(v) > peak) {
					peak = (int16_t)abs(v);
				}
				if (s[i] != first) {
					all_equal = false;
				}
			}
			n += cnt;
			k_mem_slab_free(&dmic_mem_slab, buf);
		}

		if (n == 0) {
			continue;
		}

		int32_t dc = (int32_t)(sum / n);
		int32_t rms = (int32_t)sqrtf((float)(sum_sq / n));

		printk("[%5u] rms=%5d pico=%5d dc=%6d ", report++, rms, peak, dc);
		print_vu(rms);
		if (all_equal) {
			printk("  <-- AMOSTRAS TODAS IGUAIS (%d): sem dado do mic: confira DAT, SEL e VDD",
			       first);
		}
		printk("\n");
	}

	return 0;
}
