/*
 * Copyright (c) 2025 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#ifndef NTN_LED_H
#define NTN_LED_H

#ifdef __cplusplus
extern "C" {
#endif

/* Status LEDs driven from the NTN state machine (DK aliases led0..led3):
 *
 *   led0 - GNSS:      off at boot, blinks while searching, solid on fix.
 *   led1 - pass:      blinks during the pass window, fast blink once the
 *                     network is registered / RRC connected, solid (latched)
 *                     once the network acknowledged the uplink UDP payload
 *                     (NTN_SEND_ACK), slow blink (latched) if the payload was
 *                     never acknowledged (NTN_SEND_FAILED). Off means no pass
 *                     activity at all.
 *   led2 - schedule:  solid while a pass is scheduled, slow blink when the
 *                     prediction found no pass.
 *   led3 - error:     solid on fatal error, during the grace period before
 *                     the assert/reboot.
 */

#if defined(CONFIG_APP_NTN_STATUS_LEDS)

void ntn_led_gnss_searching(void);
void ntn_led_gnss_fix(void);
void ntn_led_gnss_timeout(void);

void ntn_led_pass_scheduled(void);
void ntn_led_no_pass(void);

void ntn_led_pass_start(void);
void ntn_led_pass_progress(void);
void ntn_led_udp_ok(void);
void ntn_led_send_failed(void);
void ntn_led_pass_end(void);

void ntn_led_fatal_error(void);

#else /* !CONFIG_APP_NTN_STATUS_LEDS */

static inline void ntn_led_gnss_searching(void) { }
static inline void ntn_led_gnss_fix(void) { }
static inline void ntn_led_gnss_timeout(void) { }

static inline void ntn_led_pass_scheduled(void) { }
static inline void ntn_led_no_pass(void) { }

static inline void ntn_led_pass_start(void) { }
static inline void ntn_led_pass_progress(void) { }
static inline void ntn_led_udp_ok(void) { }
static inline void ntn_led_send_failed(void) { }
static inline void ntn_led_pass_end(void) { }

static inline void ntn_led_fatal_error(void) { }

#endif /* CONFIG_APP_NTN_STATUS_LEDS */

#ifdef __cplusplus
}
#endif

#endif /* NTN_LED_H */
