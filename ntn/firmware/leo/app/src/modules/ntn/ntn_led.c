/*
 * Copyright (c) 2025 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

#include "ntn_led.h"

LOG_MODULE_REGISTER(ntn_led, CONFIG_APP_NTN_LOG_LEVEL);

#define BLINK_NORMAL_MS	500
#define BLINK_FAST_MS	150
#define BLINK_SLOW_MS	1000

enum led_id {
	LED_GNSS,	/* led0 */
	LED_PASS,	/* led1 */
	LED_SCHED,	/* led2 */
	LED_ERROR,	/* led3 */
	LED_COUNT,
};

struct status_led {
	struct gpio_dt_spec spec;
	struct k_work_delayable blink_work;
	uint32_t period_ms;
	bool level;
};

static struct status_led leds[LED_COUNT] = {
	[LED_GNSS] = { .spec = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios) },
	[LED_PASS] = { .spec = GPIO_DT_SPEC_GET(DT_ALIAS(led1), gpios) },
	[LED_SCHED] = { .spec = GPIO_DT_SPEC_GET(DT_ALIAS(led2), gpios) },
	[LED_ERROR] = { .spec = GPIO_DT_SPEC_GET(DT_ALIAS(led3), gpios) },
};

/* Keeps led1 solid after a successful uplink until the next pass starts. */
static bool udp_ok_latched;

/* Keeps led1 slow-blinking after a pass whose payload was never acknowledged,
 * so the board distinguishes "pass happened but nothing was delivered" from
 * "no pass activity at all" (led1 off).
 */
static bool send_failed_latched;

static void blink_work_fn(struct k_work *work)
{
	struct k_work_delayable *dwork = k_work_delayable_from_work(work);
	struct status_led *led = CONTAINER_OF(dwork, struct status_led, blink_work);

	led->level = !led->level;
	(void)gpio_pin_set_dt(&led->spec, led->level);
	(void)k_work_schedule(&led->blink_work, K_MSEC(led->period_ms));
}

static void led_set(struct status_led *led, bool on)
{
	(void)k_work_cancel_delayable(&led->blink_work);

	led->level = on;
	(void)gpio_pin_set_dt(&led->spec, on);
}

static void led_blink(struct status_led *led, uint32_t period_ms)
{
	(void)k_work_cancel_delayable(&led->blink_work);

	led->period_ms = period_ms;
	led->level = true;
	(void)gpio_pin_set_dt(&led->spec, 1);
	(void)k_work_schedule(&led->blink_work, K_MSEC(period_ms));
}

void ntn_led_gnss_searching(void)
{
	led_blink(&leds[LED_GNSS], BLINK_NORMAL_MS);
}

void ntn_led_gnss_fix(void)
{
	led_set(&leds[LED_GNSS], true);
}

void ntn_led_gnss_timeout(void)
{
	led_set(&leds[LED_GNSS], false);
}

void ntn_led_pass_scheduled(void)
{
	led_set(&leds[LED_SCHED], true);
}

void ntn_led_no_pass(void)
{
	led_blink(&leds[LED_SCHED], BLINK_SLOW_MS);
}

void ntn_led_pass_start(void)
{
	udp_ok_latched = false;
	send_failed_latched = false;

	led_set(&leds[LED_SCHED], false);
	led_blink(&leds[LED_PASS], BLINK_NORMAL_MS);
}

void ntn_led_pass_progress(void)
{
	if (!udp_ok_latched) {
		led_blink(&leds[LED_PASS], BLINK_FAST_MS);
	}
}

void ntn_led_udp_ok(void)
{
	udp_ok_latched = true;
	send_failed_latched = false;

	led_set(&leds[LED_PASS], true);
}

void ntn_led_send_failed(void)
{
	if (udp_ok_latched) {
		return;
	}

	send_failed_latched = true;

	led_blink(&leds[LED_PASS], BLINK_SLOW_MS);
}

void ntn_led_pass_end(void)
{
	if (udp_ok_latched || send_failed_latched) {
		return;
	}

	led_set(&leds[LED_PASS], false);
}

void ntn_led_fatal_error(void)
{
	led_set(&leds[LED_ERROR], true);
}

static int ntn_led_init(void)
{
	int err;

	for (int i = 0; i < LED_COUNT; i++) {
		if (!gpio_is_ready_dt(&leds[i].spec)) {
			LOG_ERR("LED %d GPIO not ready", i);

			return -ENODEV;
		}

		err = gpio_pin_configure_dt(&leds[i].spec, GPIO_OUTPUT_INACTIVE);
		if (err) {
			LOG_ERR("Failed to configure LED %d, error: %d", i, err);

			return err;
		}

		k_work_init_delayable(&leds[i].blink_work, blink_work_fn);
	}

	return 0;
}

SYS_INIT(ntn_led_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);
