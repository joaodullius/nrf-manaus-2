/*
 * ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
 *   Add-on  : Edge AI Add-on for nRF Connect SDK v2.3.0
 *   Upstream: samples/data_forwarder/src/main.c
 *   Local   : C:/ncs/sdk-edge-ai/edge-ai/samples/data_forwarder/src/main.c
 *   Copiado : 2026-08-30 — curso nrf-manaus-2, modulo edge_ai/05_data_forwarder
 *
 * Para conferir se divergiu do SDK:
 *   diff <este arquivo> C:/ncs/sdk-edge-ai/edge-ai/samples/data_forwarder/src/main.c
 *
 * DIVERGENCIA DO CURSO (unica): LED de estado — led_init() e led_tick().
 *   O upstream nao usa LED. Na aula a TAG roda na bateria, sem RTT, e o aluno
 *   precisa saber o que ela esta fazendo:
 *
 *     azul,  1 flash curto por segundo  -> anunciando, sem central conectado
 *     verde, piscando a 2 Hz            -> conectada e enviando amostras
 *
 *   O verde e um heartbeat do proprio laco de coleta, condicionado a haver um
 *   central conectado. Se parar de piscar, ou o laco parou (sensor) ou a
 *   conexao caiu. Requer CONFIG_GPIO=y no prj.conf.
 *
 *   Detalhe que engana: proto_send_samples() retorna 0 mesmo sem conexao —
 *   ele so enfileira; o envio real acontece numa work queue e falha la
 *   (-22, nus_mtu == 0). Por isso o estado vem de um bt_conn_cb proprio
 *   (BT_CONN_CB_DEFINE), sem tocar no transporte.
 */

/*
 * Copyright (c) 2026 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

#include "protocol/protocol.h"
#include "sensor/data_fwd_sensor.h"
#include "transport/transport.h"

LOG_MODULE_REGISTER(data_forwarder);

/* ---- DIVERGENCIA DO CURSO: LED de estado ------------------------------- */

static const struct gpio_dt_spec led_blue = GPIO_DT_SPEC_GET(DT_NODELABEL(led1_blue), gpios);
static const struct gpio_dt_spec led_green = GPIO_DT_SPEC_GET(DT_NODELABEL(led1_green), gpios);

/* Contado em amostras: o laco roda na taxa do sensor (100 Hz). */
#define LED_ADV_PERIOD 100U /* 1 s */
#define LED_ADV_ON     5U   /* 50 ms aceso */
#define LED_TX_PERIOD  50U  /* 0,5 s -> 2 Hz */
#define LED_TX_ON      10U  /* 100 ms aceso */

#if defined(CONFIG_DATA_FWD_TRANSPORT_BLE_NUS)
#include <zephyr/bluetooth/conn.h>

static atomic_t led_link;

static void led_on_connected(struct bt_conn *conn, uint8_t err)
{
	ARG_UNUSED(conn);
	if (err == 0U) {
		atomic_set(&led_link, 1);
	}
}

static void led_on_disconnected(struct bt_conn *conn, uint8_t reason)
{
	ARG_UNUSED(conn);
	ARG_UNUSED(reason);
	atomic_set(&led_link, 0);
}

BT_CONN_CB_DEFINE(led_conn_cb) = {
	.connected = led_on_connected,
	.disconnected = led_on_disconnected,
};

static inline bool led_link_up(void)
{
	return atomic_get(&led_link) != 0;
}
#else
/* UART: nao ha "conexao"; o verde reflete so o laco. */
static inline bool led_link_up(void)
{
	return true;
}
#endif

static int led_init(void)
{
	int err;

	if (!gpio_is_ready_dt(&led_blue) || !gpio_is_ready_dt(&led_green)) {
		return -ENODEV;
	}
	err = gpio_pin_configure_dt(&led_blue, GPIO_OUTPUT_INACTIVE);
	if (err) {
		return err;
	}
	return gpio_pin_configure_dt(&led_green, GPIO_OUTPUT_INACTIVE);
}

/* Uma chamada por amostra. sending = a ultima amostra foi enviada. */
static void led_tick(bool sending)
{
	static uint32_t n;

	n++;
	if (sending) {
		gpio_pin_set_dt(&led_blue, 0);
		gpio_pin_set_dt(&led_green, (n % LED_TX_PERIOD) < LED_TX_ON);
	} else {
		gpio_pin_set_dt(&led_green, 0);
		gpio_pin_set_dt(&led_blue, (n % LED_ADV_PERIOD) < LED_ADV_ON);
	}
}

/* ------------------------------------------------------------------------ */

int main(void)
{
	int err;

	struct proto_transport transport;
	const struct proto_session_config session = {
		.rate_hz = data_fwd_sensor_frequency(),
		.channels = data_fwd_sensor_channel_count(),
		.sensor_type = data_fwd_sensor_type_id(),
		.channel_names = data_fwd_sensor_channel_names(),
#if defined(CONFIG_BT_DEVICE_NAME)
		.device_name = CONFIG_BT_DEVICE_NAME,
#else
		.device_name = "nRF DataFwd",
#endif
	};

	/* DIVERGENCIA DO CURSO: LED. Falha aqui nao impede a coleta. */
	err = led_init();
	if (err) {
		LOG_WRN("LED init failed (err %d)", err);
	}

	err = transport_init(&transport);
	if (err) {
		LOG_ERR("Transport init failed (err %d)", err);
		return err;
	}

	err = proto_init(&transport);
	if (err) {
		LOG_ERR("Protocol init failed (err %d)", err);
		return err;
	}

	err = data_fwd_sensor_init();
	if (err) {
		LOG_ERR("Sensor init failed (err %d)", err);
		return err;
	}

	err = proto_start_session(&session);
	if (err) {
		LOG_ERR("Failed to start session (err %d)", err);
		return err;
	}

	LOG_INF("Data forwarder started (sid %u)", proto_get_session_id());

	while (1) {
		proto_value_t values[CONFIG_DATA_FWD_PROTO_MAX_CHANNELS];
		size_t count;

		err = data_fwd_sensor_fetch(values, ARRAY_SIZE(values), &count);
		if (err) {
			LOG_WRN("Sample fetch failed (err %d)", err);
			led_tick(false); /* DIVERGENCIA DO CURSO */
			continue;
		}

		err = proto_send_samples(values, count);
		if (err) {
			LOG_WRN("Sample send failed (err %d)", err);
		}
		led_tick((err == 0) && led_link_up()); /* DIVERGENCIA DO CURSO */
	}

	return 0;
}
