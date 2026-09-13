/*
 * Copyright (c) 2026 Nordic Semiconductor ASA
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

/* How long a latched LED drops out before going solid again. Long enough to
 * register as a change, short enough not to read as a blink.
 */
#define LATCH_GAP_MS	150

/* The heartbeat: a short flash every few seconds. Reads as "alive and ready"
 * from across the room, and cannot be confused with either blink rate or
 * with off.
 */
#define HEARTBEAT_ON_MS		100
#define HEARTBEAT_OFF_MS	2900

enum led_id {
	LED_PROGRESS,	/* led0 */
	LED_ERROR,	/* led1 */
	LED_TX,		/* led2 */
	LED_RX,		/* led3 */
	LED_COUNT,
};

enum led_mode {
	/** On or off, nothing scheduled. */
	LED_MODE_STEADY,
	/** Toggling every period_ms. */
	LED_MODE_BLINK,
	/** Off now, solid after the gap, and stays there. */
	LED_MODE_LATCH,
	/** On for HEARTBEAT_ON_MS, off for HEARTBEAT_OFF_MS, repeat. */
	LED_MODE_HEARTBEAT,
};

struct status_led {
	struct gpio_dt_spec spec;
	struct k_work_delayable work;
	enum led_mode mode;
	uint32_t period_ms;
	bool level;
};

static struct status_led leds[LED_COUNT] = {
	[LED_PROGRESS] = { .spec = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios) },
	[LED_ERROR] = { .spec = GPIO_DT_SPEC_GET(DT_ALIAS(led1), gpios) },
	[LED_TX] = { .spec = GPIO_DT_SPEC_GET(DT_ALIAS(led2), gpios) },
	[LED_RX] = { .spec = GPIO_DT_SPEC_GET(DT_ALIAS(led3), gpios) },
};

/* The LEDs are the whole interface of this application, and during unattended
 * validation nobody is in front of the kit to read them. Tracing every change
 * is what lets a host-side driver assert on them.
 */
#if defined(CONFIG_APP_NTN_STATUS_LEDS_TRACE)
static const char *const led_name[LED_COUNT] = {
	[LED_PROGRESS] = "LED0", [LED_ERROR] = "LED1",
	[LED_TX] = "LED2", [LED_RX] = "LED3",
};

static const char *current[LED_COUNT] = {
	[LED_PROGRESS] = "off", [LED_ERROR] = "off",
	[LED_TX] = "off", [LED_RX] = "off",
};

static void trace(enum led_id id, const char *to)
{
	if (current[id] == to) {
		return;
	}

	LOG_INF("%s: %s -> %s", led_name[id], current[id], to);

	current[id] = to;
}

static const char *blink_name(uint32_t period_ms)
{
	switch (period_ms) {
	case BLINK_SLOW_MS:
		return "slow-blink";
	case BLINK_FAST_MS:
		return "fast-blink";
	default:
		return "blink";
	}
}
#else
static inline void trace(enum led_id id, const char *to)
{
	ARG_UNUSED(id);
	ARG_UNUSED(to);
}

static inline const char *blink_name(uint32_t period_ms)
{
	ARG_UNUSED(period_ms);

	return "";
}
#endif /* CONFIG_APP_NTN_STATUS_LEDS_TRACE */

static void work_fn(struct k_work *work)
{
	struct k_work_delayable *dwork = k_work_delayable_from_work(work);
	struct status_led *led = CONTAINER_OF(dwork, struct status_led, work);

	if (led->mode == LED_MODE_LATCH) {
		/* End of the gap: go solid and stop. */
		led->mode = LED_MODE_STEADY;
		led->level = true;
		(void)gpio_pin_set_dt(&led->spec, 1);

		return;
	}

	led->level = !led->level;
	(void)gpio_pin_set_dt(&led->spec, led->level);

	if (led->mode == LED_MODE_HEARTBEAT) {
		(void)k_work_schedule(&led->work, K_MSEC(led->level ? HEARTBEAT_ON_MS :
								       HEARTBEAT_OFF_MS));
		return;
	}

	(void)k_work_schedule(&led->work, K_MSEC(led->period_ms));
}

static void led_set(enum led_id id, bool on)
{
	struct status_led *led = &leds[id];

	(void)k_work_cancel_delayable(&led->work);

	led->mode = LED_MODE_STEADY;
	led->level = on;
	(void)gpio_pin_set_dt(&led->spec, on);

	trace(id, on ? "on" : "off");
}

static void led_blink(enum led_id id, uint32_t period_ms)
{
	struct status_led *led = &leds[id];

	(void)k_work_cancel_delayable(&led->work);

	led->mode = LED_MODE_BLINK;
	led->period_ms = period_ms;
	led->level = true;
	(void)gpio_pin_set_dt(&led->spec, 1);
	(void)k_work_schedule(&led->work, K_MSEC(period_ms));

	trace(id, blink_name(period_ms));
}

static void led_heartbeat(enum led_id id)
{
	struct status_led *led = &leds[id];

	(void)k_work_cancel_delayable(&led->work);

	led->mode = LED_MODE_HEARTBEAT;
	led->level = true;
	(void)gpio_pin_set_dt(&led->spec, 1);
	(void)k_work_schedule(&led->work, K_MSEC(HEARTBEAT_ON_MS));

	trace(id, "heartbeat");
}

/* Latch an activity LED on.
 *
 * A pulse was the obvious thing and it was wrong: the whole transaction is over
 * in well under a second, so the blink is easy to miss, and once it is gone
 * there is nothing to read. Latching answers the question later, and dropping
 * out for a moment first is what makes a second packet visible when the LED is
 * already lit.
 */
static void led_latch(enum led_id id)
{
	struct status_led *led = &leds[id];

	(void)k_work_cancel_delayable(&led->work);

	led->mode = LED_MODE_LATCH;
	led->level = false;
	(void)gpio_pin_set_dt(&led->spec, 0);
	(void)k_work_schedule(&led->work, K_MSEC(LATCH_GAP_MS));

#if defined(CONFIG_APP_NTN_STATUS_LEDS_TRACE)
	/* Report the event, not the resulting state: two packets in a row have
	 * to produce two lines, and both end with the LED lit.
	 */
	LOG_INF("%s: latch", led_name[id]);
	current[id] = "on";
#endif
}

void ntn_led_fix_searching(void)
{
	led_blink(LED_PROGRESS, BLINK_SLOW_MS);
}

void ntn_led_idle(bool have_fix)
{
	if (have_fix) {
		led_heartbeat(LED_PROGRESS);
	} else {
		led_set(LED_PROGRESS, false);
	}
}

void ntn_led_connecting(void)
{
	/* A new attempt starts a new story. Clear what the last one left lit so
	 * that a latched packet LED is never read as belonging to this one.
	 */
	led_set(LED_TX, false);
	led_set(LED_RX, false);

	led_blink(LED_PROGRESS, BLINK_FAST_MS);
}

void ntn_led_connected(void)
{
	led_set(LED_PROGRESS, true);
}

void ntn_led_no_cell(void)
{
	led_blink(LED_ERROR, BLINK_FAST_MS);
}

void ntn_led_error_clear(void)
{
	led_set(LED_ERROR, false);
}

void ntn_led_packet_sent(void)
{
	led_latch(LED_TX);
}

void ntn_led_packet_received(void)
{
	led_latch(LED_RX);
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

		k_work_init_delayable(&leds[i].work, work_fn);
	}

	return 0;
}

SYS_INIT(ntn_led_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);
