#!/usr/bin/env python3
"""
Generic serial modem test script for Nordic nRF9160/nRF9151.
Supports multiple RATs: NTN (Skylo), NB-IoT, and LTE-M.

Usage:
    python serial_modem_test.py --port COM26 --rat NTN
    python serial_modem_test.py --port COM26 --rat NB
    python serial_modem_test.py --port COM26 --rat M1
    python serial_modem_test.py --port COM26 --rat NB M1
    python serial_modem_test.py --port COM26 --rat NTN --gnss
    python serial_modem_test.py --port COM26 --rat NTN --lat -30.033 --lon -51.229
    python serial_modem_test.py --port COM26 --rat NTN --save session --timestamp
"""

import argparse
import csv
import queue
import re
import serial
import sys
import threading
import time
from datetime import datetime

# ANSI Colors
GRAY   = "\033[90m"
RESET  = "\033[0m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"

# Default observer location: Porto Alegre, Brazil
DEFAULT_LAT = "-30.033027"
DEFAULT_LON = "-51.229685"
DEFAULT_ALT = "10"

# Timeouts (seconds)
DEFAULT_TIMEOUT = 5.0
CFUN1_TIMEOUT   = 30.0
GNSS_TIMEOUT    = 120

# Shared state (initialised in main())
stop_event      = None
response_queue  = None
command_pending = None
log_file        = None
args            = None


# --- RAT Configuration -------------------------------------------------------

RAT_CONFIGS = {
    "NTN": {
        "label":        "Skylo NTN",
        "system_mode":  ('AT%XSYSTEMMODE=0,0,0,0,1',                             "NTN NB-IoT system mode"),
        "band_lock":    ('AT%XBANDLOCK=2,,"255","256"',                          "NTN band lock 255/256"),
        "use_location": True,
    },
    "NB": {
        "label":        "NB-IoT",
        "system_mode":  ('AT%XSYSTEMMODE=0,1,0,0',                               "NB-IoT system mode"),
        "band_lock":    ('AT%XBANDLOCK=1,"1000000000000000000000010100"',         "Band lock"),
        "use_location": False,
    },
    "M1": {
        "label":        "LTE-M",
        "system_mode":  ('AT%XSYSTEMMODE=1,0,0,0',                               "LTE-M system mode"),
        "band_lock":    ('AT%XBANDLOCK=1,"1000000000000000000000010100"',         "Band lock"),
        "use_location": False,
    },
}


def build_rat_config(rats):
    """Build a combined RAT config from a list of RAT names."""
    if len(rats) == 1:
        return RAT_CONFIGS[rats[0]]
    has_ntn = "NTN" in rats
    lte_m   = 1 if "M1"  in rats else 0
    nb      = 1 if "NB"  in rats else 0
    if has_ntn:
        mode_cmd = f"AT%XSYSTEMMODE={lte_m},{nb},0,0,1"
    else:
        mode_cmd = f"AT%XSYSTEMMODE={lte_m},{nb},0,0"
    return {
        "label":        "+".join(RAT_CONFIGS[r]["label"] for r in rats),
        "system_mode":  (mode_cmd, f"System mode: {'+'.join(rats)}"),
        "band_lock":    RAT_CONFIGS["NTN"]["band_lock"] if has_ntn else RAT_CONFIGS["NB"]["band_lock"],
        "use_location": has_ntn,
    }


# --- AT Command Groups ------------------------------------------------------

INIT_COMMANDS = [
    ("AT#XSMVER",    "SLM firmware version"),
    ("AT+CGMM",      "Model identification"),
    ("AT%HWVERSION", "Hardware version"),
    ("AT+CGMR",      "Firmware revision"),
    ("AT+CFUN=4",    "Disable RF (airplane mode)"),
]

NOTIFICATION_COMMANDS = [
    ("AT%CESQ=1",     "Signal quality URC"),
    ("AT%MDMEV=2",    "Modem events"),
    ("AT+CEER",       "Extended error report"),
    ("AT+CEREG=5",    "Extended registration URC"),
    ("AT+CGEREP=1",   "Packet domain events"),
    ("AT+CIND=1,1,1", "Indicator events"),
    ("AT+CNEC=24",    "Network error codes"),
    ("AT+CSCON=3",    "Signaling connection URC"),
]

CONNECT_COMMANDS = [
    ("AT+CFUN=1", "Enable modem (full functionality)"),
]


# --- Logging ----------------------------------------------------------------

def log_message(message):
    if args.timestamp:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"{GRAY}[{ts}]{RESET} {message}")
        if log_file:
            clean = re.sub(r'\033\[[0-9;]*m', '', f"[{ts}] {message}")
            log_file.write(clean + '\n')
            log_file.flush()
    else:
        print(message)
        if log_file:
            clean = re.sub(r'\033\[[0-9;]*m', '', message)
            log_file.write(clean + '\n')
            log_file.flush()


# --- URC Decoders -----------------------------------------------------------

def decode_cesq(line):
    """Decode %CESQ: <rsrp>,<rsrp_thr>,<rsrq>,<rsrq_thr> -> human-readable string."""
    try:
        if not line.startswith("%CESQ:"):
            return None
        values = [int(x.strip()) for x in line.split(":", 1)[1].split(",")]
        if len(values) != 4:
            return None
        rsrp, rsrp_thr, rsrq, rsrq_thr = values

        rsrp_thresholds = ["<20", "20-39", "40-59", "60-79", ">=80"]
        rsrq_thresholds = ["<7",  "7-13",  "14-20", "21-27", ">=28"]

        if rsrp == 255:
            rsrp_info = "RSRP: 255 (Invalid)"
        else:
            rsrp_dbm  = rsrp - 141
            thr_desc  = rsrp_thresholds[rsrp_thr] if 0 <= rsrp_thr <= 4 else "Unknown"
            rsrp_info = f"RSRP: {rsrp} ({rsrp_dbm} dBm, threshold: {thr_desc})"

        if rsrq == 255:
            rsrq_info = "RSRQ: 255 (Invalid)"
        else:
            rsrq_db   = (rsrq - 40) / 2
            thr_desc  = rsrq_thresholds[rsrq_thr] if 0 <= rsrq_thr <= 4 else "Unknown"
            rsrq_info = f"RSRQ: {rsrq} ({rsrq_db} dB, threshold: {thr_desc})"

        return f"{rsrp_info}, {rsrq_info}"
    except (ValueError, IndexError):
        return None


def decode_cereg(line):
    """Decode +CEREG: URC -> human-readable registration status string."""
    try:
        if not line.startswith("+CEREG:"):
            return None
        values_part = line.split(":", 1)[1].strip()
        values = [v.strip().strip('"') for v in list(csv.reader([values_part]))[0]]
        if not values:
            return None

        status_desc = {
            "0":  "Not registered (not searching)",
            "1":  "Registered (home network)",
            "2":  "Not registered (searching/attaching)",
            "3":  "Registration denied",
            "4":  "Unknown (out of coverage)",
            "5":  "Registered (roaming)",
            "50": "Not registered, not searching (receiver-only)",
            "51": "Registered, home network (receiver-only)",
            "52": "Not registered, searching (receiver-only)",
            "53": "Registration denied (receiver-only)",
            "54": "Unknown (receiver-only)",
            "55": "Registered, roaming (receiver-only)",
            "90": "Not registered (UICC failure)",
            "91": "Not registered (no suitable cell for configured system mode)",
        }
        act_desc = {
            "7":  "LTE-M",
            "9":  "NB-IoT",
            "14": "NTN NB-IoT",
        }

        stat   = values[0]
        result = f"Status: {stat} ({status_desc.get(stat, f'Unknown ({stat})')})"

        if len(values) >= 4:
            tac, ci, act = values[1], values[2], values[3]
            if tac or ci:
                result += f", TAC: {tac or '-'}, Cell ID: {ci or '-'}"
            if act:
                result += f", AcT: {act} ({act_desc.get(act, f'Unknown ({act})')})"
        return result
    except Exception:
        return None


def decode_cscon(line):
    """Decode +CSCON: URC -> human-readable signaling connection string."""
    try:
        if not line.startswith("+CSCON:"):
            return None
        values = [v.strip() for v in line.split(":", 1)[1].split(",")]
        if not values:
            return None

        mode_desc   = {"0": "Idle", "1": "Connected"}
        state_desc  = {"7": "E-UTRAN connected"}
        access_desc = {"4": "Radio access of type E-UTRAN FDD"}

        mode   = values[0]
        result = f"Mode: {mode} ({mode_desc.get(mode, f'Unknown ({mode})')})"

        if len(values) >= 2 and values[1]:
            s = values[1]
            result += f", State: {s} ({state_desc.get(s, f'Unknown ({s})')})"
        if len(values) >= 3 and values[2]:
            a = values[2]
            result += f", Access: {a} ({access_desc.get(a, f'Unknown ({a})')})"
        return result
    except Exception:
        return None


# --- URC Printer -------------------------------------------------------------

def _ts_indent():
    return " " * 26 if args.timestamp else ""


def _decode_and_format(s):
    """Return (colored_line, decoded_annotation_or_None) for a response/URC line."""
    if s.startswith("%CESQ:"):
        return f"{CYAN}{s}{RESET}", decode_cesq(s)
    elif s.startswith("+CEREG:"):
        return f"{GREEN}{s}{RESET}", decode_cereg(s)
    elif s.startswith("+CSCON:"):
        return f"{BLUE}{s}{RESET}", decode_cscon(s)
    elif s == "OK":
        return f"{GREEN}{s}{RESET}", None
    elif s.startswith("ERROR") or s.startswith("+CME ERROR") or s.startswith("+CMS ERROR"):
        return f"{RED}{s}{RESET}", None
    else:
        return f"{CYAN}{s}{RESET}", None


def print_urc(line):
    s = line.strip()
    colored, decoded = _decode_and_format(s)
    msg = colored
    if decoded:
        msg += f"\n{GRAY}{_ts_indent()}-> {decoded}{RESET}"
    log_message(msg)


# --- Threading Layer ---------------------------------------------------------

def _urc_reader(ser):
    """Background thread: reads every line from the serial port.

    Lines are routed to response_queue while a command is pending; otherwise
    they are printed immediately as URCs.
    """
    ser.timeout = 0.1
    while not stop_event.is_set():
        try:
            line = ser.readline().decode(errors="replace").strip()
        except serial.SerialException:
            break
        if not line:
            continue
        if command_pending.is_set():
            response_queue.put(line)
        else:
            print_urc(line)


def send_at(ser, cmd, desc="", timeout=DEFAULT_TIMEOUT):
    """Send an AT command, print the response lines, and return them as a list."""
    header = f"{YELLOW}> {cmd}{RESET}"
    if desc:
        header += f"  {GRAY}# {desc}{RESET}"
    log_message(header)

    command_pending.set()
    ser.write((cmd + "\r\n").encode())

    lines    = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            line = response_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        s = line.strip()
        colored, decoded = _decode_and_format(s)
        msg = colored
        if decoded:
            msg += f"\n{GRAY}{_ts_indent()}-> {decoded}{RESET}"
        log_message(msg)
        lines.append(s)

        if s in ("OK", "ERROR") or s.startswith("+CME ERROR") or s.startswith("+CMS ERROR"):
            break

    command_pending.clear()
    time.sleep(0.05)
    return lines


# --- GNSS Flow ---------------------------------------------------------------

def run_gnss_fix(ser):
    """Run GNSS fix sequence and return (lat, lon, alt) strings.

    Raises RuntimeError if no fix is obtained within GNSS_TIMEOUT seconds.
    """
    log_message(f"\n{YELLOW}--- GNSS Fix: acquiring current position ---{RESET}")
    send_at(ser, "AT%XSYSTEMMODE=0,0,1,0,0", "GNSS system mode")
    send_at(ser, "AT+CFUN=31",                "GNSS-only functional mode")
    send_at(ser, "AT#XGNSS=1,0,0,0",          "Start GNSS service")

    log_message(f"{YELLOW}Waiting for GPS fix (timeout: {GNSS_TIMEOUT}s)...{RESET}")

    # Keep command_pending set so GPS data lines flow into response_queue
    command_pending.set()
    deadline = time.time() + GNSS_TIMEOUT
    gps_line = None

    while time.time() < deadline:
        try:
            line = response_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        log_message(f"{CYAN}{line}{RESET}")
        if "#XGPS:" in line and line.count(",") >= 6:
            gps_line = line
            break

    command_pending.clear()

    if not gps_line:
        raise RuntimeError(f"No GPS fix received within {GNSS_TIMEOUT}s")

    # Format: #XGPS: <lat>,<lon>,<alt>,<speed>,<heading>,<accuracy>,<datetime>
    try:
        parts = gps_line.split(",")
        lat = parts[0].split(":")[1].strip()
        lon = parts[1].strip()
        alt = parts[2].strip()
    except Exception as exc:
        raise RuntimeError(f"Failed to parse GPS line '{gps_line}': {exc}") from exc

    log_message(f"\n{GREEN}GPS Fix: Lat={lat}, Lon={lon}, Alt={alt}{RESET}")

    log_message(f"\n{YELLOW}Shutting down GNSS stack...{RESET}")
    send_at(ser, "AT#XGPS=0", "Stop GNSS service")
    time.sleep(0.5)

    # Drain any trailing GNSS lines
    command_pending.set()
    drain_until = time.time() + 1.0
    while time.time() < drain_until:
        try:
            response_queue.get(timeout=0.1)
        except queue.Empty:
            break
    command_pending.clear()

    send_at(ser, "AT+CFUN=30", "Turn off GNSS mode")
    return lat, lon, alt


# --- Setup Sequence ----------------------------------------------------------

def run_setup(ser, lat, lon, alt):
    """Execute the full modem setup sequence in four phases."""
    rat_cfg = build_rat_config(args.rat)

    log_message(f"\n{YELLOW}{'='*50}{RESET}")
    log_message(f"{YELLOW}  {rat_cfg['label']} Modem Setup{RESET}")
    log_message(f"{YELLOW}{'='*50}{RESET}")

    log_message(f"\n{YELLOW}--- Phase 1: Modem Information ---{RESET}")
    for cmd, desc in INIT_COMMANDS:
        send_at(ser, cmd, desc)

    log_message(f"\n{YELLOW}--- Phase 2: RAT Configuration ({'+'.join(args.rat)}) ---{RESET}")
    send_at(ser, *rat_cfg["system_mode"])

    if rat_cfg["band_lock"]:
        send_at(ser, *rat_cfg["band_lock"])

    if rat_cfg["use_location"]:
        location_cmd = f'AT%LOCATION=2,"{lat}","{lon}","{alt}",0,0'
        send_at(ser, location_cmd, "Set NTN observer location")

    log_message(f"\n{YELLOW}--- Phase 3: Enable Notifications ---{RESET}")
    for cmd, desc in NOTIFICATION_COMMANDS:
        send_at(ser, cmd, desc)

    log_message(f"\n{YELLOW}--- Phase 4: Connect ---{RESET}")
    for cmd, desc in CONNECT_COMMANDS:
        send_at(ser, cmd, desc, timeout=CFUN1_TIMEOUT)

    log_message(f"\n{GREEN}Setup complete.{RESET}")


# --- Interactive Shell --------------------------------------------------------

def interactive_shell(ser):
    """Interactive AT command shell with URC decode and numbered shortcuts.

    Shortcuts:
        1 -- Socket init (create + connect)
        2 -- Send message (auto-incrementing counter)
        3 -- Receive data
        4 -- Close socket
    """
    message_counter = [1]
    socket_number   = [None]

    log_message(f"\n{YELLOW}=== Interactive Mode ==={RESET}")
    log_message(
        f"{YELLOW}Shortcuts: 1=socket init  2=send msg  3=recv  4=close socket{RESET}"
    )
    log_message(f"{YELLOW}Type any AT command, or 'exit' / Ctrl+C to quit.{RESET}\n")

    try:
        while True:
            try:
                user_input = input(f"{BLUE}> {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input.lower() == "exit":
                break

            # -- Shortcuts --
            if user_input == "1":
                log_message(f"{YELLOW}Socket init -- creating UDP socket and connecting...{RESET}")
                lines = send_at(ser, "AT#XSOCKET=1,2,0", "Create UDP socket")
                for line in lines:
                    if line.startswith("#XSOCKET:"):
                        try:
                            socket_number[0] = int(line.split(":")[1].split(",")[0].strip())
                        except (ValueError, IndexError):
                            pass
                host, port = args.server.rsplit(":", 1)
                send_at(ser, f'AT#XCONNECT={socket_number[0]},"{host}",{int(port)}', "Connect to test server")

            elif user_input == "2":
                n = message_counter[0]
                log_message(f"{YELLOW}Sending message #{n}...{RESET}")
                send_at(ser, f'AT#XSEND={socket_number[0]},0,0,"Hello {"+".join(args.rat)} #{n}"', f"Send message #{n}")
                message_counter[0] += 1

            elif user_input == "3":
                log_message(f"{YELLOW}Receiving data...{RESET}")
                send_at(ser, f"AT#XRECVFROM={socket_number[0]},0,0,10", "Receive data")

            elif user_input == "4":
                if socket_number[0] is not None:
                    log_message(f"{YELLOW}Closing socket #{socket_number[0]}...{RESET}")
                    send_at(ser, f"AT#XCLOSE={socket_number[0]}", "Close socket")
                else:
                    log_message(f"{RED}No socket open -- use '1' to create one first{RESET}")

            else:
                cmd = user_input
                if not cmd.upper().startswith("AT"):
                    cmd = "AT" + cmd
                send_at(ser, cmd)

    except KeyboardInterrupt:
        pass
    finally:
        log_message(f"\n{YELLOW}Exiting interactive mode.{RESET}")


# --- Main ---------------------------------------------------------------------

def main():
    global stop_event, response_queue, command_pending, log_file, args

    parser = argparse.ArgumentParser(
        description="Serial modem test for Nordic nRF9160/nRF9151 (multi-RAT).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-p", "--port",      required=True,
                        help="Serial port (e.g. COM26 or /dev/ttyUSB0)")
    parser.add_argument("-b", "--baud",      type=int, default=115200,
                        help="Baud rate")
    parser.add_argument("-r", "--rat",       choices=["NB", "M1", "NTN"], nargs="+", default=["NTN"],
                        help="Radio Access Technology (one or more): NB=NB-IoT, M1=LTE-M, NTN=Skylo NTN")
    parser.add_argument("--lat",             default=DEFAULT_LAT,
                        help="Observer latitude (NTN only)")
    parser.add_argument("--lon",             default=DEFAULT_LON,
                        help="Observer longitude (NTN only)")
    parser.add_argument("--alt",             default=DEFAULT_ALT,
                        help="Observer altitude in meters (NTN only)")
    parser.add_argument("-g", "--gnss",      action="store_true",
                        help="Run GNSS fix to obtain current position (NTN only, overrides --lat/--lon)")
    parser.add_argument("-s", "--save",      metavar="NAME",
                        help="Log to NAME_YYYYMMDD_HHMMSS.log")
    parser.add_argument("--server",          default="64.181.168.22:5005", metavar="HOST:PORT",
                        help="UDP server for the interactive shell (default: %(default)s)")
    parser.add_argument("--timestamp",       action="store_true",
                        help="Prefix every message with a timestamp")
    args = parser.parse_args()

    # -- Logging setup --
    if args.save:
        ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{args.save}_{ts}.log"
        log_file     = open(log_filename, 'w', encoding='utf-8')
        print(f"Logging to: {log_filename}")

    # -- Threading state --
    stop_event      = threading.Event()
    response_queue  = queue.Queue()
    command_pending = threading.Event()

    # -- Open serial port --
    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.1)
    except serial.SerialException as exc:
        print(f"{RED}ERROR: Could not open {args.port}: {exc}{RESET}")
        sys.exit(1)

    time.sleep(0.5)
    ser.reset_input_buffer()

    # -- Start background reader --
    reader = threading.Thread(target=_urc_reader, args=(ser,), daemon=True)
    reader.start()

    # Disable modem echo so echoed bytes don't appear as response lines
    command_pending.set()
    ser.write(b"ATE0\r\n")
    time.sleep(0.5)
    while True:
        try:
            response_queue.get_nowait()
        except queue.Empty:
            break
    command_pending.clear()

    rat_cfg = build_rat_config(args.rat)

    try:
        log_message(f"\n{YELLOW}Serial Modem Test  [{rat_cfg['label']}]{RESET}")
        log_message(f"{YELLOW}Port: {args.port}  Baud: {args.baud}{RESET}")

        # -- Determine observer location (NTN only) --
        if rat_cfg["use_location"]:
            if args.gnss:
                try:
                    lat, lon, alt = run_gnss_fix(ser)
                except RuntimeError as exc:
                    log_message(f"{RED}GNSS fix failed: {exc}{RESET}")
                    sys.exit(1)
            else:
                lat, lon, alt = args.lat, args.lon, args.alt
                log_message(
                    f"\n{YELLOW}Location: Lat={lat}, Lon={lon}, Alt={alt}m{RESET}"
                )
        else:
            lat = lon = alt = None

        # -- Run AT command setup sequence --
        run_setup(ser, lat, lon, alt)

        # -- Interactive monitoring / shell --
        log_message(
            f"\n{YELLOW}URCs are decoded in real-time. Type commands below.{RESET}"
        )
        interactive_shell(ser)

    except KeyboardInterrupt:
        log_message(f"\n{YELLOW}Interrupted by user.{RESET}")
    finally:
        stop_event.set()
        if log_file:
            log_file.close()
        ser.close()
        print("Port closed.")


if __name__ == "__main__":
    main()
