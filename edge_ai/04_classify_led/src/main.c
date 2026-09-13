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
 * O MODELO QUE VEM LIGADO e o de exemplo da Nordic (pasta Neuton/): estados de
 * transporte de uma encomenda — parado, chacoalhando, impacto, queda livre,
 * carregando, no carro, colocado — a partir de UMA entrada, a magnitude da
 * aceleracao. Serve para a fiacao funcionar de ponta a ponta antes de existir
 * modelo proprio.
 *
 * O MODELO DO CURSO (pasta ventilador_95922/) e o que o aluno coloca no lugar:
 * velocidade de um ventilador pela vibracao (idle, vel1, vel2, vel3), treinado
 * no Edge AI Lab com o dataset de 05_data_forwarder/dataset_referencia/. Seis
 * entradas por amostra — os seis eixos do BMI270 em MICRO-unidades SI, como o
 * Data Forwarder gravou — janela de 128 amostras a 100 Hz, features de
 * frequencia.
 *
 * Para trocar de modelo (o do ventilador, ou O SEU):
 *   1. a pasta nrf_edgeai_generated/ do zip do Lab vai para uma subpasta de
 *      src/nrf_edgeai_generated/; aponte CURSO_MODELO no CMakeLists.txt
 *   2. ajuste as tres constantes USER_* abaixo (os valores estao no .c gerado:
 *      INPUT_WINDOW_SIZE, INPUT_UNIQ_FEATURES_NUM, MODEL_OUTPUTS_NUM)
 *   3. a tabela CLASS_COLORS, uma cor por classe, na ordem do dicionario
 *   4. recompile com -p
 *
 * As tres constantes NAO sao decorativas: os __ASSERT_NO_MSG() em main()
 * conferem cada uma contra o modelo carregado. Errar uma trava o boot com um
 * assert — que e exatamente a licao de que o modelo tem contrato.
 *
 * A ESCALA faz parte do contrato, e errar ela e SILENCIOSO: compila, roda e
 * classifica errado. O modelo espera os numeros na escala do dataset em que
 * foi treinado. Aqui: micro-unidades (sensor_value_to_micro()), porque o CSV
 * do Data Forwarder Host e assim. O modelo de exemplo da Nordic (pasta Neuton/)
 * espera outra coisa: UMA entrada, a magnitude da aceleracao em mili-g — veja
 * imu_read_magnitude() abaixo, que fica no binario so quando
 * USER_UNIQ_INPUTS_NUM == 1.
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
 * Trocar o modelo? Troque o bloco — junto com CURSO_MODELO no CMakeLists.txt
 * e a tabela CLASS_COLORS abaixo.
 * ------------------------------------------------------------------------ */
/* Neuton (exemplo da Nordic): 50 / 1 / 7 */
#define USER_WINDOW_SIZE      50U  /* amostras por janela de inferencia */
#define USER_UNIQ_INPUTS_NUM  1U   /* entradas por amostra: so a magnitude */
#define USER_MODELS_CLASS_NUM 7U   /* classes na saida */

/* ventilador_95922 (modelo do curso): 128 / 6 / 4 */
// #define USER_WINDOW_SIZE      128U /* amostras por janela de inferencia */
// #define USER_UNIQ_INPUTS_NUM  6U   /* entradas por amostra: ax,ay,az,gx,gy,gz */
// #define USER_MODELS_CLASS_NUM 4U   /* classes na saida */

/* Taxa de amostragem: a mesma da coleta (Data Forwarder a 100 Hz). Janela de
 * 50 amostras = 0,5 s por inferencia; de 128 = 1,28 s.
 */
#define SAMPLE_RATE_HZ 100U
#define SAMPLE_PERIOD_US (1000000U / SAMPLE_RATE_HZ)

/* O ritmo de amostragem e um k_timer periodico + semaforo, igual ao
 * 05_data_forwarder (src/sensor/bmi270.c). NAO use k_msleep(10) no laco: o
 * tempo da leitura SPI soma ao sleep e o laco cai para ~97 Hz (medido: janela
 * de 128 amostras em 1321 ms em vez de 1280). Com features de frequencia isso
 * desloca o espectro inteiro em 3% e o modelo passa a ver uma velocidade acima
 * da real. A taxa da inferencia tem de ser a taxa da coleta.
 */
static K_SEM_DEFINE(tick_sem, 0, 1);
static void tick_handler(struct k_timer *t)
{
	ARG_UNUSED(t);
	k_sem_give(&tick_sem);
}
static K_TIMER_DEFINE(tick_timer, tick_handler, NULL);

/* Tolerancia para o aviso de janela fora do ritmo: 2% de 1280 ms. */
#define WINDOW_EXPECTED_MS ((USER_WINDOW_SIZE * 1000U) / SAMPLE_RATE_HZ)
#define WINDOW_TOLERANCE_MS (WINDOW_EXPECTED_MS / 50U)

/* Fundo de escala do BMI270: o MESMO da coleta. O 05_data_forwarder do curso
 * e editado para +-4 g / +-1000 dps antes de coletar (bmi270.c:85 e :102).
 * Nao muda a unidade, so o teto antes de saturar — mas o modelo aprendeu com
 * um sinal que satura num ponto, e precisa ver o mesmo aqui.
 */
#define IMU_ACCEL_FS_G   4
#define IMU_GYRO_FS_DPS  1000

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

/* Uma cor por classe, NA ORDEM DO DICIONARIO de classes do dataset
 * (a ordem de --classes no fwd_to_lab.py). Trocou o modelo, troque esta tabela.
 *
 * O LED e GPIO liga/desliga por canal: 3 bits, 8 combinacoes, uma delas
 * apagada. Acima de 8 classes as cores se repetem e o LED deixa de identificar
 * a classe — use PWM (o board expoe rgb_led_1 como leds-group-multicolor) ou
 * numero de piscadas.
 */
/* Neuton (exemplo da Nordic): estados de transporte de uma encomenda */
static const class_color_t CLASS_COLORS[USER_MODELS_CLASS_NUM] = {
	{0, 0, 0, "Idle"},       /* apagado  */
	{1, 0, 0, "Shaking"},    /* vermelho */
	{1, 1, 0, "Impact"},     /* amarelo  */
	{1, 0, 1, "Free Fall"},  /* magenta  */
	{0, 1, 0, "Carrying"},   /* verde    */
	{0, 0, 1, "in Car"},     /* azul     */
	{0, 1, 1, "Placed"},     /* ciano    */
};

/* ventilador_95922 (modelo do curso): na ordem do dicionario do fwd_to_lab.py */
// static const class_color_t CLASS_COLORS[USER_MODELS_CLASS_NUM] = {
// 	{0, 0, 1, "idle"},  /* azul     */
// 	{0, 1, 0, "vel1"},  /* verde    */
// 	{1, 1, 0, "vel2"},  /* amarelo  */
// 	{1, 0, 0, "vel3"},  /* vermelho */
// };

/* Sem isto, aumentar USER_MODELS_CLASS_NUM e esquecer de acrescentar cores
 * COMPILA: o C preenche o resto com zero, e as classes novas ficam com LED
 * apagado e nome NULL indo para o %s do LOG_INF. Falha silenciosa. Diminuir ja
 * falhava no build ("excess elements").
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

#if USER_UNIQ_INPUTS_NUM == 6
/* Seis canais em MICRO-unidades SI: m/s2 x 1e6 e rad/s x 1e6 (o giroscopio
 * do Zephyr e rad/s, nao dps). E o que o Data Forwarder manda com
 * INT32_VALUES=y e o que esta no CSV que treinou o modelo: mesma funcao
 * (sensor_value_to_micro), mesma ordem (ax,ay,az,gx,gy,gz), nenhum fator.
 */
static int imu_read_sample(flt32_t out[6])
{
	struct sensor_value accel[3], gyro[3];
	int err = sensor_sample_fetch(imu);

	if (err) {
		return err;
	}
	err = sensor_channel_get(imu, SENSOR_CHAN_ACCEL_XYZ, accel);
	if (err) {
		return err;
	}
	err = sensor_channel_get(imu, SENSOR_CHAN_GYRO_XYZ, gyro);
	if (err) {
		return err;
	}
	for (int i = 0; i < 3; i++) {
		out[i] = (flt32_t)sensor_value_to_micro(&accel[i]);
		out[3 + i] = (flt32_t)sensor_value_to_micro(&gyro[i]);
	}
	return 0;
}

#elif USER_UNIQ_INPUTS_NUM == 1
/* Modelo de exemplo da Nordic (pasta Neuton/): UMA entrada, a magnitude da
 * aceleracao em MILI-G — sqrt(x^2 + y^2 + z^2) / 9.80665 * 1000.
 *
 * A unidade nao esta escrita na doc do sample; foi preciso ler os vetores
 * embarcados dele. O vetor da classe IDLE (TAG parada, so gravidade) tem
 * valores ~1017, nao ~9.8:
 *
 *     CLASS_0_PARCEL_IDLE_ACCEL_DATA[] = {1019.23, 1018.65, 1016.69, ...}
 *
 * Alimentar em m/s2 (1 g ~ 9.81) NAO da erro nenhum — compila, roda, e
 * classifica errado: 9.8 cai no fundo da faixa que o modelo conhece
 * (INPUT_FEATURES_SCALE_MIN = 6.26), e o fundo da faixa e justamente queda
 * livre. Verificado no hardware: a TAG parada na mesa reportava "Free Fall".
 */
#define MILLI_G_POR_MS2 (1000.0 / 9.80665)

static int imu_read_sample(flt32_t out[1])
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

	out[0] = (flt32_t)(sqrt(x * x + y * y + z * z) * MILLI_G_POR_MS2);
	return 0;
}
#else
#error "USER_UNIQ_INPUTS_NUM: so ha leitor de IMU para 1 (magnitude) ou 6 (eixos)"
#endif

static int imu_init(void)
{
	struct sensor_value fs_a = {.val1 = IMU_ACCEL_FS_G, .val2 = 0};
	struct sensor_value fs_g = {.val1 = IMU_GYRO_FS_DPS, .val2 = 0};
	struct sensor_value odr = {.val1 = SAMPLE_RATE_HZ, .val2 = 0};

	if (!device_is_ready(imu)) {
		LOG_ERR("BMI270 nao esta pronto");
		return -ENODEV;
	}
	/* Frequencia por ultimo: e ela que liga o sensor (mesma ordem do
	 * 05_data_forwarder/src/sensor/bmi270.c).
	 */
	(void)sensor_attr_set(imu, SENSOR_CHAN_ACCEL_XYZ, SENSOR_ATTR_FULL_SCALE, &fs_a);
	(void)sensor_attr_set(imu, SENSOR_CHAN_ACCEL_XYZ, SENSOR_ATTR_SAMPLING_FREQUENCY, &odr);
	(void)sensor_attr_set(imu, SENSOR_CHAN_GYRO_XYZ, SENSOR_ATTR_FULL_SCALE, &fs_g);
	(void)sensor_attr_set(imu, SENSOR_CHAN_GYRO_XYZ, SENSOR_ATTR_SAMPLING_FREQUENCY, &odr);
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
	LOG_INF("nRF Edge AI Lab Solution id: %s", nrf_edgeai_solution_id_str(p_model));
	LOG_INF("janela %u · entradas %u · classes %u · %u Hz",
		USER_WINDOW_SIZE, USER_UNIQ_INPUTS_NUM, USER_MODELS_CLASS_NUM, SAMPLE_RATE_HZ);

	if (leds_init() || imu_init()) {
		return -ENODEV;
	}

	int32_t ultima_classe = -1;
	uint32_t t_janela = k_uptime_get_32();
	uint32_t janelas = 0;

	k_timer_start(&tick_timer, K_NO_WAIT, K_USEC(SAMPLE_PERIOD_US));

	while (1) {
		flt32_t amostra[USER_UNIQ_INPUTS_NUM];

		k_sem_take(&tick_sem, K_FOREVER);

		if (imu_read_sample(amostra) == 0) {
			res = nrf_edgeai_feed_inputs(p_model, amostra, USER_UNIQ_INPUTS_NUM);

			/* INPROGRESS domina: o runtime so infere quando a janela
			 * fecha. Nao e erro.
			 */
			if (res == NRF_EDGEAI_ERR_SUCCESS) {
				/* Ritmo real da janela. Se sair da tolerancia, o
				 * espectro que o modelo ve nao e o do dataset.
				 */
				uint32_t agora = k_uptime_get_32();
				uint32_t dt = agora - t_janela;

				t_janela = agora;
				if (dt > WINDOW_EXPECTED_MS + WINDOW_TOLERANCE_MS ||
				    dt + WINDOW_TOLERANCE_MS < WINDOW_EXPECTED_MS) {
					LOG_WRN("janela em %u ms (esperado %u): taxa fora "
						"da da coleta", dt, WINDOW_EXPECTED_MS);
				} else if (janelas < 3) {
					/* As primeiras, para conferir o ritmo no boot. */
					LOG_INF("janela em %u ms (esperado %u)", dt,
						WINDOW_EXPECTED_MS);
				}
				janelas++;

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
	}

	return 0;
}
