/*
 * Copyright (c) 2026 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

/*
 * 04_classify_led — app minima do curso nrf-manaus-2.
 *
 * ORIGEM: derivado de samples/nrf_edgeai/classification do Edge AI Add-on v2.3.0.
 *   O sample original alimenta o modelo com VETORES EMBARCADOS. Aqui a entrada
 *   vem do IMU real e a saida pinta o LED RGB da nRF54L15-TAG.
 *
 * O objetivo do lab: mostrar a engine Edge AI inteira em uma tela. Sao quatro
 * chamadas, e nada mais:
 *
 *     nrf_edgeai_user_model()   pega o modelo gerado (o .c em nrf_edgeai_generated/)
 *     nrf_edgeai_init()         inicializa
 *     nrf_edgeai_feed_inputs()  entrega UMA amostra por vez; o runtime acumula
 *     nrf_edgeai_run_inference() roda quando a janela fecha
 *
 * O MODELO QUE VEM AQUI NAO E DE GESTOS. E o modelo de exemplo da Nordic
 * (estados de encomenda: parado, chacoalhando, impacto, queda livre, ...), que
 * recebe UMA entrada: a magnitude da aceleracao. Ele serve para a fiacao
 * funcionar de ponta a ponta antes de existir modelo proprio.
 *
 * No loop 2 o aluno troca:
 *   1. os arquivos em src/nrf_edgeai_generated/  pelo modelo dele
 *   2. as tres constantes USER_* abaixo, conforme o modelo treinado
 *   3. a tabela CLASS_COLORS, com uma cor por classe
 *
 * As tres constantes NAO sao decorativas: os __ASSERT_NO_MSG() em main()
 * conferem cada uma contra o modelo carregado. Errar uma trava o boot com um
 * assert — que e exatamente a licao de que o modelo tem contrato.
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>

#include <math.h>

#include <nrf_edgeai/nrf_edgeai.h>
#include "nrf_edgeai_user_model.h"

LOG_MODULE_REGISTER(main, LOG_LEVEL_INF);

/* ------------------------------------------------------------------------
 * Contrato do modelo — CONFERIDO contra o .c gerado pelos asserts em main().
 * Trocar o modelo? Ajuste estes tres.
 * ------------------------------------------------------------------------ */
#define USER_WINDOW_SIZE     50U /* amostras por janela de inferencia */
#define USER_UNIQ_INPUTS_NUM 1U  /* entradas por amostra: so a magnitude */
#define USER_MODELS_CLASS_NUM 7U /* classes na saida */

/* Taxa de amostragem. O modelo de exemplo espera magnitude da aceleracao;
 * 100 Hz e o mesmo do 01_gesture_recognition, entao a janela de 50 amostras
 * cobre 0,5 s.
 */
#define SAMPLE_RATE_HZ 100U
#define SAMPLE_PERIOD_MS (1000U / SAMPLE_RATE_HZ)

/* ------------------------------------------------------------------------
 * LED RGB da TAG (led1_red / led1_green / led1_blue no DTS do board)
 * ------------------------------------------------------------------------ */
static const struct gpio_dt_spec led_r = GPIO_DT_SPEC_GET(DT_NODELABEL(led1_red), gpios);
static const struct gpio_dt_spec led_g = GPIO_DT_SPEC_GET(DT_NODELABEL(led1_green), gpios);
static const struct gpio_dt_spec led_b = GPIO_DT_SPEC_GET(DT_NODELABEL(led1_blue), gpios);

typedef struct {
	uint8_t r, g, b;
	const char *nome;
} class_color_t;

/* Uma cor por classe. Trocou o modelo, troque esta tabela.
 *
 * O LED e GPIO liga/desliga por canal: 3 bits, 8 combinacoes, uma delas
 * apagada. Acima de 8 classes as cores se repetem e o LED deixa de identificar
 * a classe — use PWM (o board expoe rgb_led_1 como leds-group-multicolor) ou
 * numero de piscadas.
 */
static const class_color_t CLASS_COLORS[USER_MODELS_CLASS_NUM] = {
	{0, 0, 0, "Idle"},       /* apagado */
	{1, 0, 0, "Shaking"},    /* vermelho */
	{1, 1, 0, "Impact"},     /* amarelo */
	{1, 0, 1, "Free Fall"},  /* magenta */
	{0, 1, 0, "Carrying"},   /* verde */
	{0, 0, 1, "in Car"},     /* azul */
	{0, 1, 1, "Placed"},     /* ciano */
};

/* Sem isto, aumentar USER_MODELS_CLASS_NUM e esquecer de acrescentar cores
 * COMPILA: o C preenche o resto com zero, e as classes novas ficam com LED
 * apagado (igual a "Idle") e nome NULL indo para o %s do LOG_INF. Falha
 * silenciosa. Diminuir ja falhava no build ("excess elements").
 */
BUILD_ASSERT(ARRAY_SIZE(CLASS_COLORS) == USER_MODELS_CLASS_NUM,
	     "CLASS_COLORS precisa ter exatamente USER_MODELS_CLASS_NUM entradas");

static void led_set(const class_color_t *c)
{
	(void)gpio_pin_set_dt(&led_r, c->r);
	(void)gpio_pin_set_dt(&led_g, c->g);
	(void)gpio_pin_set_dt(&led_b, c->b);
}

static int leds_init(void)
{
	const struct gpio_dt_spec *leds[] = {&led_r, &led_g, &led_b};

	for (size_t i = 0; i < ARRAY_SIZE(leds); i++) {
		if (!gpio_is_ready_dt(leds[i])) {
			LOG_ERR("LED %zu nao esta pronto", i);
			return -ENODEV;
		}
		int err = gpio_pin_configure_dt(leds[i], GPIO_OUTPUT_INACTIVE);

		if (err) {
			LOG_ERR("gpio_pin_configure_dt LED %zu: %d", i, err);
			return err;
		}
	}
	return 0;
}

/* ------------------------------------------------------------------------
 * IMU
 * ------------------------------------------------------------------------ */
static const struct device *const imu = DEVICE_DT_GET_ONE(bosch_bmi270);

/* Magnitude da aceleracao em MILI-G: sqrt(x^2 + y^2 + z^2) / 9.80665 * 1000.
 *
 * A unidade importa, e nao esta escrita em lugar nenhum da doc do sample — foi
 * preciso ler os vetores embarcados dele para descobrir. O vetor da classe IDLE
 * (TAG parada, so gravidade) tem valores ~1017, nao ~9.8:
 *
 *     CLASS_0_PARCEL_IDLE_ACCEL_DATA[] = {1019.23, 1018.65, 1016.69, ...}
 *
 * Logo: mili-g, onde 1 g ~ 1000.
 *
 * Alimentar em m/s2 (1 g ~ 9.81) NAO da erro nenhum — compila, roda, e
 * classifica errado: 9.8 cai no fundo da faixa que o modelo conhece
 * (INPUT_FEATURES_SCALE_MIN = 6.26), e o fundo da faixa e justamente queda
 * livre. Verificado no hardware: a TAG parada na mesa reportava "Free Fall".
 *
 * E a licao central do loop 2: o modelo espera a escala do dataset, e errar
 * isso e silencioso.
 */
#define MILLI_G_POR_MS2 (1000.0 / 9.80665)

static int imu_read_magnitude(flt32_t *out)
{
	struct sensor_value accel[3];
	int err = sensor_sample_fetch(imu);

	if (err) {
		return err;
	}
	err = sensor_channel_get(imu, SENSOR_CHAN_ACCEL_XYZ, accel);
	if (err) {
		return err;
	}

	double x = sensor_value_to_double(&accel[0]);
	double y = sensor_value_to_double(&accel[1]);
	double z = sensor_value_to_double(&accel[2]);

	*out = (flt32_t)(sqrt(x * x + y * y + z * z) * MILLI_G_POR_MS2);
	return 0;
}

static int imu_init(void)
{
	struct sensor_value fs = {.val1 = 4, .val2 = 0};     /* +-4 g, como o 01 */
	struct sensor_value odr = {.val1 = SAMPLE_RATE_HZ, .val2 = 0};

	if (!device_is_ready(imu)) {
		LOG_ERR("BMI270 nao esta pronto");
		return -ENODEV;
	}
	(void)sensor_attr_set(imu, SENSOR_CHAN_ACCEL_XYZ, SENSOR_ATTR_FULL_SCALE, &fs);
	(void)sensor_attr_set(imu, SENSOR_CHAN_ACCEL_XYZ, SENSOR_ATTR_SAMPLING_FREQUENCY, &odr);
	return 0;
}

/* ------------------------------------------------------------------------ */

int main(void)
{
	nrf_edgeai_t *p_model = nrf_edgeai_user_model();

	/* O modelo tem contrato. Se voce trocou o modelo e nao ajustou as
	 * constantes la em cima, o boot para aqui — de proposito.
	 */
	__ASSERT_NO_MSG(nrf_edgeai_input_window_size(p_model) == USER_WINDOW_SIZE);
	__ASSERT_NO_MSG(nrf_edgeai_uniq_inputs_num(p_model) == USER_UNIQ_INPUTS_NUM);
	__ASSERT_NO_MSG(nrf_edgeai_model_outputs_num(p_model) == USER_MODELS_CLASS_NUM);

	nrf_edgeai_err_t res = nrf_edgeai_init(p_model);

	if (res != NRF_EDGEAI_ERR_SUCCESS) {
		LOG_ERR("nrf_edgeai_init falhou: %d", (int)res);
		return -EIO;
	}

	nrf_edgeai_rt_version_t v = nrf_edgeai_runtime_version();

	LOG_INF("04_classify_led — IMU -> inferencia -> LED");
	LOG_INF("Edge AI runtime %d.%d.%d", v.field.major, v.field.minor, v.field.patch);
	LOG_INF("janela %u · entradas %u · classes %u · %u Hz",
		USER_WINDOW_SIZE, USER_UNIQ_INPUTS_NUM, USER_MODELS_CLASS_NUM, SAMPLE_RATE_HZ);

	if (leds_init() || imu_init()) {
		return -ENODEV;
	}

	int32_t ultima_classe = -1;

	while (1) {
		flt32_t magnitude;

		if (imu_read_magnitude(&magnitude) == 0) {
			res = nrf_edgeai_feed_inputs(p_model, &magnitude, USER_UNIQ_INPUTS_NUM);

			/* INPROGRESS domina: o runtime so infere quando a janela
			 * fecha. Nao e erro.
			 */
			if (res == NRF_EDGEAI_ERR_SUCCESS) {
				res = nrf_edgeai_run_inference(p_model);
				if (res == NRF_EDGEAI_ERR_SUCCESS) {
					/* A saida decodificada fica no proprio handle. */
					uint16_t classe =
						p_model->decoded_output.classif.predicted_class;
					const flt32_t *probs =
						p_model->decoded_output.classif.probabilities.p_f32;

					if (classe < USER_MODELS_CLASS_NUM &&
					    (int32_t)classe != ultima_classe) {
						ultima_classe = classe;
						led_set(&CLASS_COLORS[classe]);
						LOG_INF("classe %u — %s (%u%%)", classe,
							CLASS_COLORS[classe].nome,
							(uint16_t)(probs[classe] * 100.0f));
					}
				} else {
					LOG_WRN("run_inference: %d", (int)res);
				}
			} else if (res != NRF_EDGEAI_ERR_INPROGRESS) {
				LOG_WRN("feed_inputs: %d", (int)res);
			}
		}

		k_msleep(SAMPLE_PERIOD_MS);
	}

	return 0;
}
