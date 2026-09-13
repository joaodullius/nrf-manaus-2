# Button-driven NTN test application

Flash it, press buttons, read LEDs. No terminal, no command sequence, nothing to
type before it works.

## What the buttons do

| Button | Does | Notes |
| --- | --- | --- |
| **1** | Try now | Starts the satellite attach. If the kit has no fix yet, it gets one first and then attaches. Ignored while an attempt is running or the link is up |
| **2** | Send a packet | Only while connected; the log says so otherwise |
| **3** | Stop | Ends whatever is running, fix search or attach, and drops the link. The kit waits for button 1 |
| **4** | New GNSS fix | Press it after moving the kit. Ends an attach if one is running |

## What the LEDs mean

| LED | Off | Heartbeat | Blinking | Solid |
| --- | --- | --- | --- | --- |
| **1** | Stopped, no fix | Fix is good, waiting for button 1 | Slow: looking for a fix. Fast: connecting | Connected |
| **2** | No problem | — | Fast: no cell found, or the attempt failed | — |
| **3** | Nothing sent yet | — | Drops out briefly on each new packet | A packet has been sent |
| **4** | Reserved for the server's answer; not read in this version | — | — | — |

LED 1 tells the whole progress story, so the other three keep one meaning each.
The heartbeat is a short flash every three seconds: "alive, fix in hand, press
1". A dark LED 1 means the kit is stopped, after button 3 or after the fix
search gave up.

LED 3 stays lit rather than blinking once. The exchange is over in a
fraction of a second, so a blink is easy to miss and leaves nothing to read
afterwards. It clears when a new connection attempt starts, so what is lit
always belongs to the attempt you are watching.

## Powering on

The kit starts looking for a GNSS fix by itself. LED 1 blinks slowly while it
does. A cold fix can take several minutes with a clear view of the sky; a warm
one takes seconds. Once LED 1 settles into the heartbeat, the fix is good and
button 1 will connect.

If LED 2 lights and LED 1 goes dark, the fix search gave up
(`APP_NTN_GNSS_FIX_RETRY_SECONDS`). Button 4 tries again; button 1 also works,
it gets a fix first and then attaches.

## Attaching

Button 1 turns the modem on and LED 1 blinks fast. On Skylo the modem reports
"no suitable cell" within half a minute when no satellite is in view; LED 2
starts blinking fast and LED 1 keeps blinking: the modem stays on and keeps
searching by itself, every 2 s. A satellite coming into view is caught by the
next search, so there is nothing for a button to hurry. Nothing times out
either: the kit searches until it attaches or until button 3 stops it; button
1 starts over.

When the attach succeeds LED 1 goes solid and LED 2 goes out. The payload is
sent right away (LED 3), and the link is held open for
`APP_NTN_LINGER_SECONDS` after the last exchange so button 2 can send more.
When that runs out the kit goes back to idle with the heartbeat; button 1
attaches again.

LED 4 is reserved for the answer from the server. This version does not read
the downlink yet, so it never lights.

## Two builds

**Field (NTN, Skylo).** The default. Bring the SIM's overlay:

```
west build --board nrf9151dk/nrf9151/ns -- \
  "-DEXTRA_CONF_FILE=overlay-ntn-skylo-eminify.conf"
```

**Validation (TN, Cat-M1).** Attaches over Cat-M1 with an ordinary SIM, so the
state machine, the buttons, the LEDs and the socket can be checked indoors
without waiting for a satellite. The same code path: only the system mode and
the bands differ, plus the few things the terrestrial network refuses.

```
west build --board nrf9151dk/nrf9151/ns -- \
  "-DEXTRA_CONF_FILE=overlay-tn-catm1.conf"
```

The validation build also enables two things that must stay out of what ships:
an `att_ntn btn <1-4>` shell command that injects a button press, and a log
line on every LED change. They exist because an interface made of physical
buttons and visible LEDs cannot otherwise be exercised or observed by anything
automated. Either can be added to a field build with
`-DCONFIG_APP_NTN_BUTTON_INJECT_SHELL=y` and
`-DCONFIG_APP_NTN_STATUS_LEDS_TRACE=y`.

**Log in flash.** Add `overlay-log-flash.conf` to either build to keep a copy
of the log on the external flash for the runs nobody watched; see
`docs/common/flash_log.md`.

## Settings worth knowing

| Option | Default here | What it does |
| --- | --- | --- |
| `APP_NTN_AUTO_CONNECT` | off | Attach by itself as soon as there is a fix. Right for a tracker, wrong when a person decides |
| `APP_NTN_NATIVE_SEARCH` | on | After "no suitable cell", let the modem keep searching instead of timing out and retrying later |
| `APP_NTN_STAY_CONNECTED` / `APP_NTN_LINGER_SECONDS` | on / 300 | Hold the link after a send so button 2 can send more |
| `APP_NTN_GNSS_FIX_RETRY_SECONDS` | 180 (600 in the TN overlay) | How long a fix search runs before giving up |
| `APP_NTN_SERVER_ADDR` / `_PORT` | test server | Where the payload goes |
| `APP_NTN_BANDLOCK_ENABLE` / `APP_NTN_BANDLOCK` | per SIM overlay | The NTN band; Skylo is 255 |
