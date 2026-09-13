#!/usr/bin/env python3
"""
Minimal NTN satellite search script.
Configures the modem to continuously search for SatelIoT and monitors URCs.

Usage:
    python ntn_search.py --port COM3
"""

import argparse
import csv
import queue
import serial
import sys
import threading
import time
from datetime import datetime


GRAY   = "\033[90m"
RESET  = "\033[0m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"

LAT  = "-30.033027"
LON  = "-51.229685"
ALT  = "50"
BAUD = 115200

DEFAULT_TIMEOUT = 3.0
CFUN1_TIMEOUT   = 30.0

stop_event      = None
response_queue  = None
command_pending = None


# --- Command sequence --------------------------------------------------------
def build_setup_commands(lat, lon, alt):
    return [
        #  Command                                              Description
        ("AT+CFUN=0",                                          "Power off modem"),
        ("AT%CESQ=1",                                          "Enable signal quality URC"),
        ("AT%MDMEV=2",                                         "Enable modem events"),
        ("AT+CEER",                                            "Clear extended error report"),
        ("AT+CEREG=5",                                         "Enable extended network registration URC"),
        ("AT+CGEREP=1",                                        "Enable packet domain event reporting"),
        ("AT+CIND=1,1,1",                                      "Enable indicator events"),
        ("AT+CNEC=24",                                         "Enable network error codes"),
        ("AT+CSCON=3",                                         "Enable signaling connection status URC"),
        ("AT%XSYSTEMMODE=0,0,0,0,1",                          "Set NTN-only system mode"),
        ("AT+COPS=1,2,\"90197\"",                              "Select SatelIoT operator (PLMN 90197)"),
        ("AT%PERIODICSEARCHCONF=0,1,0,0,\"1,2\"",             "Configure periodic cell search"),
        (f'AT%LOCATION=2,"{lat}","{lon}","{alt}",0,0',       "Set observer location"),
        ("AT+CFUN=1",                                          "Enable modem -- start searching"),
    ]


# --- URC decoders ------------------------------------------------------------

def decode_cesq(line):
    try:
        values = [int(x.strip()) for x in line.split(":", 1)[1].split(",")]
        if len(values) != 4:
            return None
        rsrp, rsrp_thr, rsrq, rsrq_thr = values
        rsrp_thresholds = ["<20", "20-39", "40-59", "60-79", ">=80"]
        rsrq_thresholds = ["<7",  "7-13",  "14-20", "21-27", ">=28"]
        if rsrp == 255:
            rsrp_info = "RSRP: 255 (Invalid)"
        else:
            thr = rsrp_thresholds[rsrp_thr] if 0 <= rsrp_thr <= 4 else "?"
            rsrp_info = f"RSRP: {rsrp} ({rsrp - 141} dBm, thr: {thr})"
        if rsrq == 255:
            rsrq_info = "RSRQ: 255 (Invalid)"
        else:
            thr = rsrq_thresholds[rsrq_thr] if 0 <= rsrq_thr <= 4 else "?"
            rsrq_info = f"RSRQ: {rsrq} ({(rsrq - 40) / 2:.1f} dB, thr: {thr})"
        return f"{rsrp_info}, {rsrq_info}"
    except (ValueError, IndexError):
        return None


def decode_cereg(line):
    try:
        values_part = line.split(":", 1)[1].strip()
        values = [v.strip().strip('"') for v in list(csv.reader([values_part]))[0]]
        status_desc = {
            "0": "Not registered (not searching)",
            "1": "Registered (home)",
            "2": "Searching/attaching",
            "3": "Registration denied",
            "4": "Unknown (out of coverage)",
            "5": "Registered (roaming)",
            "91": "No suitable cell for NTN mode",
        }
        act_desc = {"7": "LTE-M", "9": "NB-IoT", "14": "NTN NB-IoT"}
        stat   = values[0]
        result = f"Status: {stat} ({status_desc.get(stat, f'Unknown ({stat})')})"
        if len(values) >= 4:
            tac, ci, act = values[1], values[2], values[3]
            if tac or ci:
                result += f", TAC: {tac or '-'}, Cell: {ci or '-'}"
            if act:
                result += f", AcT: {act} ({act_desc.get(act, act)})"
        return result
    except Exception:
        return None


def decode_cscon(line):
    try:
        values = [v.strip() for v in line.split(":", 1)[1].split(",")]
        mode_desc = {"0": "Idle", "1": "Connected"}
        mode   = values[0]
        result = f"Mode: {mode} ({mode_desc.get(mode, mode)})"
        if len(values) >= 2 and values[1]:
            result += f", State: {values[1]}"
        if len(values) >= 3 and values[2]:
            result += f", Access: {values[2]}"
        return result
    except Exception:
        return None


def decode_mdmev(line):
    search_status = {
        "1": "Search started",
        "2": "Pattern matched",
        "3": "Search timeout",
        "4": "Search aborted",
    }
    try:
        payload = line.split(":", 1)[1].strip()
        if payload.startswith("SEARCH STATUS"):
            code = payload.split()[-1]
            return f"Search status: {code} ({search_status.get(code, code)})"
        if payload.startswith("PRACH CE-LEVEL"):
            level = payload.split()[-1]
            return f"PRACH coverage enhancement level: {level}"
    except Exception:
        pass
    return None


# --- Formatting --------------------------------------------------------------

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{GRAY}[{ts}]{RESET} {msg}")

def print_line(s):
    if s.startswith("%CESQ:"):
        colored, decoded = f"{CYAN}{s}{RESET}", decode_cesq(s)
    elif s.startswith("+CEREG:"):
        colored, decoded = f"{GREEN}{s}{RESET}", decode_cereg(s)
    elif s.startswith("+CSCON:"):
        colored, decoded = f"{BLUE}{s}{RESET}", decode_cscon(s)
    elif s.startswith("%MDMEV:"):
        colored, decoded = f"{YELLOW}{s}{RESET}", decode_mdmev(s)
    elif s == "OK":
        colored, decoded = f"{GREEN}{s}{RESET}", None
    elif s.startswith("ERROR") or s.startswith("+CME ERROR") or s.startswith("+CMS ERROR"):
        colored, decoded = f"{RED}{s}{RESET}", None
    else:
        colored, decoded = f"{CYAN}{s}{RESET}", None
    log(colored + (f"\n             -> {GRAY}{decoded}{RESET}" if decoded else ""))


# --- Serial reader thread -----------------------------------------------------

def _reader(ser):
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
            print_line(line)


def send_at(ser, cmd, desc="", timeout=DEFAULT_TIMEOUT):
    header = f"{YELLOW}> {cmd}{RESET}"
    if desc:
        header += f"  {GRAY}# {desc}{RESET}"
    log(header)

    command_pending.set()
    ser.write((cmd + "\r\n").encode())

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            line = response_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        s = line.strip()
        print_line(s)
        if s in ("OK", "ERROR") or s.startswith("+CME ERROR") or s.startswith("+CMS ERROR"):
            break

    command_pending.clear()
    time.sleep(0.05)


# --- Setup -------------------------------------------------------------------

def run_setup(ser, lat, lon, alt):
    log(f"\n{YELLOW}{'='*48}{RESET}")
    log(f"{YELLOW}  NTN Satellite Search -- SatelIoT (PLMN 90197){RESET}")
    log(f"{YELLOW}{'='*48}{RESET}")
    log(f"{YELLOW}Location: {lat}, {lon}, {alt}m{RESET}\n")

    for cmd, desc in build_setup_commands(lat, lon, alt):
        timeout = CFUN1_TIMEOUT if cmd == "AT+CFUN=1" else DEFAULT_TIMEOUT
        send_at(ser, cmd, desc, timeout=timeout)

    log(f"\n{GREEN}Setup done. Modem is searching. URCs appear below.{RESET}")
    log(f"{GRAY}Ctrl+C to exit. Type AT commands to interact.{RESET}\n")


# --- Interactive shell --------------------------------------------------------

def interactive_shell(ser):
    while True:
        try:
            user_input = input(f"{BLUE}> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() == "exit":
            break
        cmd = user_input if user_input.upper().startswith("AT") else "AT" + user_input
        send_at(ser, cmd)


# --- Main --------------------------------------------------------------------

def main():
    global stop_event, response_queue, command_pending

    parser = argparse.ArgumentParser(description="Configure modem for continuous NTN satellite search.")
    parser.add_argument("-p", "--port", required=True, help="Serial port (e.g. COM3)")
    parser.add_argument("--lat", default=LAT, help=f"Observer latitude (default: {LAT})")
    parser.add_argument("--lon", default=LON, help=f"Observer longitude (default: {LON})")
    parser.add_argument("--alt", default=ALT, help=f"Observer altitude in meters (default: {ALT})")
    args = parser.parse_args()

    stop_event      = threading.Event()
    response_queue  = queue.Queue()
    command_pending = threading.Event()

    try:
        ser = serial.Serial(args.port, BAUD, timeout=0.1)
    except serial.SerialException as exc:
        print(f"{RED}Could not open {args.port}: {exc}{RESET}")
        sys.exit(1)

    time.sleep(0.5)
    ser.reset_input_buffer()

    reader = threading.Thread(target=_reader, args=(ser,), daemon=True)
    reader.start()

    # Disable echo
    command_pending.set()
    ser.write(b"ATE0\r\n")
    time.sleep(0.3)
    while True:
        try:
            response_queue.get_nowait()
        except queue.Empty:
            break
    command_pending.clear()

    try:
        run_setup(ser, args.lat, args.lon, args.alt)
        interactive_shell(ser)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        ser.close()
        print("\nPort closed.")


if __name__ == "__main__":
    main()
