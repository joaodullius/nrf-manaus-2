/*
 * Copyright (c) 2026 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#ifndef NTN_LED_H__
#define NTN_LED_H__

/* Status LEDs driven from the NTN state machine, on the four discrete LEDs of
 * the nRF9151 DK. The same code runs in the TN validation build and the NTN
 * field build; nothing here knows which one it is in.
 *
 *   led0 - progress: slow blink while acquiring a GNSS fix, fast blink while
 *          connecting, solid while connected, off when idle with a valid fix.
 *   led1 - error:    fast blink when no cell was found, off once cleared.
 *   led2 - transmit: lit once a packet has been sent, and stays lit. Drops out
 *          for a moment on each new packet.
 *   led3 - receive:  lit once a datagram has come back, same behaviour.
 *
 * The two activity LEDs latch rather than pulse. The whole exchange is over in
 * well under a second, so a blink is easy to miss, and once it has gone there
 * is nothing left to read. Both are cleared when a new connection attempt
 * starts, so what is lit always belongs to the attempt in progress.
 *
 * led0 carries the whole progress story so the other three keep one fixed
 * meaning each. Without it, the automatic fix at boot would leave the kit
 * looking dead for as long as a cold fix takes.
 *
 * Every entry point is safe to call from any thread.
 */

#ifdef __cplusplus
extern "C" {
#endif

#if defined(CONFIG_APP_NTN_STATUS_LEDS)

/** Acquiring a GNSS fix. */
void ntn_led_fix_searching(void);

/** Idle, no attempt running. With a valid fix the progress LED gives a
 * heartbeat, "ready, press 1"; without one it is off, "stopped".
 */
void ntn_led_idle(bool have_fix);

/** A connection attempt is in progress. */
void ntn_led_connecting(void);

/** The link is up. */
void ntn_led_connected(void);

/** No cell was found, or the attempt failed for another reason. */
void ntn_led_no_cell(void);

/** Clear the error indication. */
void ntn_led_error_clear(void);

/** A packet was sent. Latches the transmit LED on. */
void ntn_led_packet_sent(void);

/** A datagram came back. Latches the receive LED on. */
void ntn_led_packet_received(void);

#else /* !CONFIG_APP_NTN_STATUS_LEDS */

/* With the LEDs disabled these compile to nothing, so the state machine calls
 * them unconditionally.
 */
static inline void ntn_led_fix_searching(void) { }
static inline void ntn_led_idle(bool have_fix) { ARG_UNUSED(have_fix); }
static inline void ntn_led_connecting(void) { }
static inline void ntn_led_connected(void) { }
static inline void ntn_led_no_cell(void) { }
static inline void ntn_led_error_clear(void) { }
static inline void ntn_led_packet_sent(void) { }
static inline void ntn_led_packet_received(void) { }

#endif /* CONFIG_APP_NTN_STATUS_LEDS */

#ifdef __cplusplus
}
#endif

#endif /* NTN_LED_H__ */
