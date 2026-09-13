#!/usr/bin/env python3
"""
Skylo GEO NTN modem setup and monitoring script (Serial Modem add-on v1.0.0).
Combines the Skylo AT-command sequence with the threading architecture used
across the module scripts for reliable URC monitoring.

Usage:
    python skylo_test.py --port COM26 --lat -3.1 --lon -60.0
    python skylo_test.py --port COM26 --lat -3.1 --lon -60.0 --server 64.181.168.22:5005
    python skylo_test.py --port COM26 --lat -3.1 --lon -60.0 --save skylo_session --timestamp
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

# Timeouts (seconds)
DEFAULT_TIMEOUT      = 5.0
CFUN1_TIMEOUT        = 30.0
GNSS_TIMEOUT         = 120
REGISTRATION_TIMEOUT = 180.0

# Shared state (initialised in main())
stop_event      = None
response_queue  = None
command_pending = None
log_file        = None
args            = None

# Timestamp of the last AT#XSEND=, used to compute the #XSENDNTF latency
_last_xsend_ts = [None]


# --- AT Command Groups -------------------------------------------------------

INIT_COMMANDS = [
    ("AT#XSMVER",    "SLM firmware version"),
    ("AT+CGMM",      "Model identification"),
    ("AT%HWVERSION", "Hardware version"),
    ("AT+CGMR",      "Firmware revision"),
    ("AT+CFUN=4",    "Disable RF (airplane mode)"),
]


def build_config_commands(lat, lon, alt, apn, bands="255,256"):
    """Skylo GEO NTN configuration sequence: system mode, bandlock, position, APN."""
    return [
        ("AT%XSYSTEMMODE=0,0,0,0,1", "Modo de sistema NTN NB-IoT"),
        (f'AT%XBANDLOCK=2,,"{bands}"', "Bandlock NTN (255 L-band, 256 S-band)"),
        ("AT%XBANDLOCK?", "Confere o bandlock"),
        (f'AT%LOCATION=2,"{lat}","{lon}","{alt}",0,0', "Posicao do kit, validade permanente"),
        ("AT%LOCATION=1", "Assina pedidos de posicao do modem"),
        (f'AT+CGDCONT=0,"ip","{apn}"', "PDN IPv4 no attach inicial"),
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

POST_REGISTRATION_COMMANDS = [
    # %SIBREQ so com o modem ativado (+CME ERROR 517 antes do CFUN=1); nunca %SIBCONFIG=32,0
    ("AT%SIBREQ=32", "Pede o SIB32 uma vez; termina com %SIBREQ: 0,<status>"),
    ("AT+COPS?",    "Operadora e AcT (14 = NTN NB-IoT)"),
    ("AT%XMONITOR", "Banda, EARFCN, PCI, RSRP da celula"),
]


def send_payload_cmd(handle, payload, notify=True):
    """Build the AT#XSEND for the given socket handle. notify=True asks for #XSENDNTF."""
    flags = 8192 if notify else 0
    return f'AT#XSEND={handle},0,{flags},"{payload}"'


# --- Logging -------------------------------------------------------------------

def log_message(message):
    """Print to console and optionally write to log file, with optional timestamp."""
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


# --- URC Decoders ----------------------------------------------------------

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


def decode_xsendntf(line):
    """Decode #XSENDNTF: URC -> elapsed time since the matching AT#XSEND, if known."""
    if _last_xsend_ts[0] is None:
        return None
    elapsed = time.time() - _last_xsend_ts[0]
    return f"{elapsed:.2f}s since #XSEND (network acknowledged)"


# --- URC Printer -------------------------------------------------------------

def _ts_indent():
    """Alignment indent to match the timestamp prefix width."""
    return " " * 26 if args.timestamp else ""


def _decode_and_format(s):
    """Return (colored_line, decoded_annotation_or_None) for a response/URC line."""
    if s.startswith("%CESQ:"):
        return f"{CYAN}{s}{RESET}", decode_cesq(s)
    elif s.startswith("+CEREG:"):
        return f"{GREEN}{s}{RESET}", decode_cereg(s)
    elif s.startswith("+CSCON:"):
        return f"{BLUE}{s}{RESET}", decode_cscon(s)
    elif s.startswith("#XSENDNTF:"):
        return f"{GREEN}{s}{RESET}", decode_xsendntf(s)
    elif s == "OK":
        return f"{GREEN}{s}{RESET}", None
    elif s.startswith("ERROR") or s.startswith("+CME ERROR") or s.startswith("+CMS ERROR"):
        return f"{RED}{s}{RESET}", None
    else:
        return f"{CYAN}{s}{RESET}", None


def print_urc(line):
    """Print an unsolicited result code with colour and decode annotation."""
    s = line.strip()
    colored, decoded = _decode_and_format(s)
    msg = colored
    if decoded:
        msg += f"\n{GRAY}{_ts_indent()}-> {decoded}{RESET}"
    log_message(msg)


# --- Threading Layer -----------------------------------------------------------

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

    if cmd.startswith("AT#XSEND="):
        _last_xsend_ts[0] = time.time()

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


# --- GNSS Flow -----------------------------------------------------------------
# Not used by the GEO demo: NTN and GNSS are mutually exclusive on the modem,
# and a cold GNSS fix takes minutes the live demo does not have. Kept for
# scripts/situations that do need a fix before running the NTN sequence.

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

    # Shutdown GNSS stack
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


# --- Setup Sequence --------------------------------------------------------

def wait_for_registration(ser, timeout=REGISTRATION_TIMEOUT):
    """Wait for +CEREG: 1 (home) or +CEREG: 5 (roaming) up to timeout seconds.

    Every URC seen while waiting is still printed/decoded. Returns True if
    registration was seen, False on timeout.
    """
    log_message(
        f"\n{YELLOW}Waiting for registration (+CEREG: 1/5, timeout {timeout:.0f}s)...{RESET}"
    )
    command_pending.set()
    deadline   = time.time() + timeout
    registered = False

    while time.time() < deadline:
        try:
            line = response_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        s = line.strip()
        print_urc(s)
        m = re.match(r'^\+CEREG:\s*"?(\d+)"?', s)
        if m and m.group(1) in ("1", "5"):
            registered = True
            break

    command_pending.clear()
    return registered


def run_setup(ser, lat, lon, alt, apn):
    """Execute the full Skylo GEO NTN setup sequence."""
    log_message(f"\n{YELLOW}{'='*50}{RESET}")
    log_message(f"{YELLOW}  Skylo GEO NTN Setup{RESET}")
    log_message(f"{YELLOW}{'='*50}{RESET}")

    log_message(f"\n{YELLOW}--- Phase 1: Modem Information ---{RESET}")
    for cmd, desc in INIT_COMMANDS:
        send_at(ser, cmd, desc)

    log_message(f"\n{YELLOW}--- Phase 2: Skylo NTN Configuration ---{RESET}")
    for cmd, desc in build_config_commands(lat, lon, alt, apn):
        send_at(ser, cmd, desc)

    log_message(f"\n{YELLOW}--- Phase 3: Enable Notifications ---{RESET}")
    for cmd, desc in NOTIFICATION_COMMANDS:
        send_at(ser, cmd, desc)

    log_message(f"\n{YELLOW}--- Phase 4: Connect ---{RESET}")
    for cmd, desc in CONNECT_COMMANDS:
        send_at(ser, cmd, desc, timeout=CFUN1_TIMEOUT)

    log_message(f"\n{YELLOW}--- Phase 5: Post-registration ---{RESET}")
    if wait_for_registration(ser):
        for cmd, desc in POST_REGISTRATION_COMMANDS:
            send_at(ser, cmd, desc)
        log_message(f"\n{GREEN}Setup complete.{RESET}")
    else:
        log_message(
            f"\n{RED}Timed out waiting for registration -- no satellite in view?{RESET}"
        )


# --- Interactive Shell ----------------------------------------------------------

def _parse_server(server):
    """Split 'HOST:PORT' into (host, port) or (None, None) if empty.

    Raises ValueError if server is non-empty and malformed (no port, or a
    non-numeric port) -- callers validate this before opening the serial
    port so a typo does not surface 180s into the demo.
    """
    if not server:
        return None, None
    host, _, port_s = server.rpartition(":")
    if not host or not port_s:
        raise ValueError(f"malformed --server '{server}', expected HOST:PORT")
    return host, int(port_s)


def _prompt_server():
    """Ask for host and port interactively; re-prompts on a bad port."""
    host = input(f"{BLUE}Server host: {RESET}").strip()
    while True:
        port_s = input(f"{BLUE}Server port: {RESET}").strip()
        try:
            return host, int(port_s)
        except ValueError:
            log_message(f"{RED}Porta invalida: '{port_s}' -- digite um numero{RESET}")


def interactive_shell(ser, server=""):
    """Interactive AT command shell with URC decode and numbered shortcuts.

    Shortcuts:
        1 - Socket init (create + connect)
        2 - Send message (auto-incrementing counter)
        3 - Receive data
        4 - Close socket
    """
    message_counter = [1]
    socket_number   = [None]
    host, port      = _parse_server(server)
    host_state      = [host]
    port_state      = [port]

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
                if not host_state[0] or not port_state[0]:
                    host_state[0], port_state[0] = _prompt_server()
                log_message(f"{YELLOW}Socket init -- creating UDP socket and connecting...{RESET}")
                lines = send_at(ser, "AT#XSOCKET=1,2,0", "Create UDP socket")
                for line in lines:
                    if line.startswith("#XSOCKET:"):
                        try:
                            socket_number[0] = int(line.split(":")[1].split(",")[0].strip())
                        except (ValueError, IndexError):
                            pass
                if socket_number[0] is None:
                    log_message(f"{RED}socket nao aberto: PDN ativo? rode a opcao 1{RESET}")
                else:
                    send_at(
                        ser,
                        f'AT#XCONNECT={socket_number[0]},"{host_state[0]}",{port_state[0]}',
                        "Connect to server",
                    )

            elif user_input == "2":
                if socket_number[0] is None:
                    log_message(f"{RED}socket nao aberto: PDN ativo? rode a opcao 1{RESET}")
                else:
                    n = message_counter[0]
                    log_message(f"{YELLOW}Sending message #{n}...{RESET}")
                    send_at(
                        ser,
                        send_payload_cmd(socket_number[0], f"Hello Skylo NTN #{n}"),
                        f"Send message #{n}",
                    )
                    message_counter[0] += 1

            elif user_input == "3":
                if socket_number[0] is None:
                    log_message(f"{RED}socket nao aberto: PDN ativo? rode a opcao 1{RESET}")
                else:
                    log_message(f"{YELLOW}Receiving data...{RESET}")
                    send_at(ser, f"AT#XRECVFROM={socket_number[0]},0,0,10", "Receive data")

            elif user_input == "4":
                if socket_number[0] is not None:
                    log_message(f"{YELLOW}Closing socket #{socket_number[0]}...{RESET}")
                    send_at(ser, f"AT#XCLOSE={socket_number[0]}", "Close socket")
                else:
                    log_message(f"{RED}No socket open -- use '1' to create one first{RESET}")

            else:
                # Treat as raw AT command
                cmd = user_input
                if not cmd.upper().startswith("AT"):
                    cmd = "AT" + cmd
                send_at(ser, cmd)

    except KeyboardInterrupt:
        pass
    finally:
        log_message(f"\n{YELLOW}Exiting interactive mode.{RESET}")


# --- Main ------------------------------------------------------------------------

def main():
    global stop_event, response_queue, command_pending, log_file, args

    parser = argparse.ArgumentParser(
        description="Skylo GEO NTN modem setup and monitoring (nRF9151-SMA-DK, Serial Modem).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-p", "--port",      required=True,
                        help="Serial port (e.g. COM26 or /dev/ttyUSB0)")
    parser.add_argument("-b", "--baud",      type=int, default=115200,
                        help="Baud rate")
    parser.add_argument("--lat",             required=True,
                        help="Observer latitude (required -- no default)")
    parser.add_argument("--lon",             required=True,
                        help="Observer longitude (required -- no default)")
    parser.add_argument("--alt",             default="50",
                        help="Observer altitude in meters")
    parser.add_argument("--apn",             default="em",
                        help="PDN APN (Skylo eminify SIM uses 'em')")
    parser.add_argument("--server",          default="64.181.168.22:5005", metavar="HOST:PORT",
                        help="udp_server.py address; if empty the shell asks before option 1")
    parser.add_argument("-g", "--gnss",      action="store_true",
                        help="Run GNSS fix to obtain current position (overrides --lat/--lon; "
                             "not used in the GEO demo, NTN and GNSS are mutually exclusive)")
    parser.add_argument("-s", "--save",      metavar="NAME",
                        help="Log to NAME_YYYYMMDD_HHMMSS.log")
    parser.add_argument("--timestamp",       action="store_true",
                        help="Prefix every message with a timestamp")
    args = parser.parse_args()

    # -- Validate --server before touching the port: a typo here must not
    # surface only after the ~180s setup sequence, inside interactive_shell --
    if args.server:
        try:
            _parse_server(args.server)
        except ValueError:
            parser.error(f"--server precisa de HOST:PORT (recebido: '{args.server}')")

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

    try:
        log_message(f"\n{YELLOW}Skylo GEO NTN Test Script{RESET}")
        log_message(f"{YELLOW}Port: {args.port}  Baud: {args.baud}{RESET}")

        # -- Determine observer location --
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

        # -- Run AT command setup sequence --
        run_setup(ser, lat, lon, alt, args.apn)

        # -- Interactive monitoring / shell --
        log_message(
            f"\n{YELLOW}URCs are decoded in real-time. Type commands below.{RESET}"
        )
        interactive_shell(ser, args.server)

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
