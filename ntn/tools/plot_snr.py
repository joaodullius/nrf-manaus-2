"""
Plot SNR (and RSRP/RSRQ) from a Nordic modem firmware trace log.
Optionally overlay satellite elevation for the pass that coincides with the log.

Time calibration: the GNSS fix event emits a +CCLK AT command with the real
UTC time.  That timestamp is used as an anchor to convert all subsequent
device-uptime timestamps to real UTC.

Usage:
    python plot_snr.py <log_file>
    python plot_snr.py <log_file> --satellite SATELIOT_1
    python plot_snr.py <log_file> --no-elevation
"""

import argparse
import math
import os
import pathlib
import re
import sys
import webbrowser
from collections import namedtuple
import nrf_trace
from datetime import datetime, time as dtime, timedelta, timezone

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpecFromSubplotSpec
from tle_fetcher import fetch_tle


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
# Aceita os dois padroes de log: "HH:MM:SS.ffffff" (export antigo do nRFInsight,
# cujos timestamps sao uptime do modem) e "YYYY-MM-DD HH:MM:SS.ffffff"
# (nrf_trace.write_txt, ja em UTC absoluto).
RE_TS = re.compile(r"^(?:(\d{4}-\d{2}-\d{2})[ T])?(\d{2}:\d{2}:\d{2}\.\d+)")
RE_GNSS_FIX    = re.compile(r"GNSS_POS_REP_PV")
RE_GNSS_LATLON = re.compile(r"GNSS_POS_REP_PV.*Lat\s+(-?\d+\.\d+)\s+Lon\s+(-?\d+\.\d+)")
RE_CCLK = re.compile(r'\+CCLK[:=]?\s*"(\d{2}/\d{2}/\d{2},\d{2}:\d{2}:\d{2})[+\-]\d+"')
RE_MEAS = re.compile(
    r"L1_DEFAULT_INFO_SERVING_CELL_MEASUREMENTS"
    r".*rsrp:\s*(-?\d+).*rsrq:\s*(-?\d+).*SNR:\s*(-?\d+)"
)

# Modem event patterns
RE_MIB      = re.compile(r"L1_DCI_DEC_NBIOT_MIB_DECODE")
RE_SIB1     = re.compile(r"ERRC_PDU_TYPE_BCCH_SIB1_NB")
RE_SIBX     = re.compile(r"ERRC_PDU_TYPE_BCCH_SI_NB")
RE_TX_OFF   = re.compile(r"RFHAL_KERNEL_BIN_TRACE_TX_OFF")
RE_RAR      = re.compile(r"L1_DCI_DEC_NBIOT_RAR_UL_GRANT_CONTENT_NPUSCH")
RE_DL_GRANT = re.compile(r"L1_DCI_DEC_N1_CONTENT_PHY_ALLOC")
RE_UL_GRANT = re.compile(r"L1_DCI_DEC_N0_CONTENT_PHY_ALLOC")
# HARQ-ACK do UE no NPUCCH e PDUs L3 de descida, usados para inferir o ack de rede
RE_PUCCH    = re.compile(r"L1_DEFAULT_INFO_PUCCH_POWER_CONTROL")
RE_DL_PDU   = re.compile(r"ERRC_PDU_TYPE_DL_|EPDCP_UP_PACKET_DL")
RE_NAS_SVC_ACCEPT  = re.compile(r"NAS_PDU_SERVICE_ACCEPT")
RE_NAS_REJECT      = re.compile(r"NAS_PDU_ATTACH_REJECT")
RE_NAS_ATTACH_REQ  = re.compile(r"NAS_PDU_ATTACH_REQUEST")
RE_NAS_ATTACH_ACC  = re.compile(r"NAS_PDU_ATTACH_ACCEPT")
RE_NAS_ATTACH_COMP = re.compile(r"NAS_PDU_ATTACH_COMPLETE")
RE_NAS_DETACH      = re.compile(r"NAS_PDU_DETACH_REQUEST")
RE_CSCON_ON        = re.compile(r"\+CSCON:\s*1")
RE_CSCON_OFF       = re.compile(r"\+CSCON:\s*0")

RE_RRC_RELEASE = re.compile(r"ERRC PDU: RRCConnectionRelease-NB")
RE_T310_START  = re.compile(r"TIMER_T310\) START")
RE_CEREG_VAL   = re.compile(r"AT_STRING <= \+CEREG:\s*(\d+)")

# SIB32 NTN orbital parameters response
RE_SIBCONFIG32 = re.compile(r"AT_STRING <= %SIBCONFIG:\s*32,(.+)")

# UDP payload extraction from raw IP packets queued for uplink / received downlink
RE_UDP_PACKET    = re.compile(r"EPDCP_UP_PACKET_UL_MULTI\s+\[([0-9a-fA-F]+)\]")
RE_UDP_DL_PACKET = re.compile(r"EPDCP_UP_PACKET_DL\s+\[([0-9a-fA-F]+)\]")
RE_ANSI = re.compile(r"\x1b\[[0-9;]*[mK]")

# PRACH CE level events from modem trace
RE_PRACH_CE0 = re.compile(r"L1_DEFAULT_INFO_PRACH_REPORT.*\bce_level:\s*0\b")
RE_PRACH_CE1 = re.compile(r"L1_DEFAULT_INFO_PRACH_REPORT.*\bce_level:\s*1\b")
RE_PRACH_CE2 = re.compile(r"L1_DEFAULT_INFO_PRACH_REPORT.*\bce_level:\s*2\b")

# XSYSTEMMODE with NTN flag (5 params, last = 1)
RE_XSYSTEMMODE_NTN = re.compile(r"XSYSTEMMODE=\d+,\d+,\d+,\d+,1\b")
# CFUN activation command sent to modem (outgoing: =>)
RE_CFUN_SET = re.compile(r"AT_STRING => \+CFUN=(\d+)")
# RRC cell-search states
RE_NO_CELL  = re.compile(r"ERRC_CNTRL_RRC_NO_CELL")
RE_RRC_IDLE = re.compile(r"ERRC_CNTRL_RRC_IDLE")
# Ordered list of (label, regex, color) for the events subplot
EVENT_DEFS = [
    ("MIB",            RE_MIB,            "mediumpurple"),
    ("SIB1",           RE_SIB1,           "dodgerblue"),
    ("SIBx",           RE_SIBX,           "cornflowerblue"),
    ("SIB32",          RE_SIBCONFIG32,    "gold"),
    ("RAR",            RE_RAR,            "crimson"),
    ("DL Grant",       RE_DL_GRANT,       "darkorange"),
    ("UL Grant",       RE_UL_GRANT,       "forestgreen"),
    ("Tx OFF",         RE_TX_OFF,         "sienna"),
    ("NAS Svc Accept", RE_NAS_SVC_ACCEPT, "limegreen"),
    ("NAS Reject",     RE_NAS_REJECT,     "red"),
    ("Attach Req",     RE_NAS_ATTACH_REQ,  "royalblue"),
    ("Attach Accept",  RE_NAS_ATTACH_ACC,  "limegreen"),
    ("Attach Done",    RE_NAS_ATTACH_COMP, "darkgreen"),
    ("Detach",         RE_NAS_DETACH,      "tomato"),
    ("CSCON=1",        RE_CSCON_ON,        "teal"),
    ("CSCON=0",        RE_CSCON_OFF,       "lightcoral"),
    ("UDP Send",       RE_UDP_PACKET,      "mediumorchid"),
    ("UDP Recv",       RE_UDP_DL_PACKET,   "deepskyblue"),
    ("Net ACK",        None,               "black"),
    ("PRACH CE0",      RE_PRACH_CE0,       "seagreen"),
    ("PRACH CE1",      RE_PRACH_CE1,       "gold"),
    ("PRACH CE2",      RE_PRACH_CE2,       "crimson"),
]

ALL_SATELLITES = {
    'SATELIOT_1': 60550,
    'SATELIOT_2': 60534,
    'SATELIOT_3': 60552,
    'SATELIOT_4': 60537,
}

# Patterns in filenames that hint at a specific satellite (case-insensitive)
FILENAME_SAT_HINTS = [
    (re.compile(r"SATELIOT_?3|SIOT3", re.IGNORECASE), "SATELIOT_3"),
    (re.compile(r"SATELIOT_?1|SIOT1", re.IGNORECASE), "SATELIOT_1"),
    (re.compile(r"SATELIOT_?2|SIOT2", re.IGNORECASE), "SATELIOT_2"),
    (re.compile(r"SATELIOT_?4|SIOT4", re.IGNORECASE), "SATELIOT_4"),
]


def _handler_command(ext):
    """Linha de comando do handler padrao da extensao, ou None.

    Handlers classicos gravam o executavel no valor padrao de
    shell/open/command. Handlers AppX criam a chave mas deixam o valor vazio,
    usando so DelegateExecute, um objeto COM que nao sobe a partir de um
    processo de console e falha sem levantar erro.
    """
    if sys.platform != "win32":
        return None
    import winreg
    key = (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
           r"\FileExts" "\\" + ext + r"\UserChoice")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            progid = winreg.QueryValueEx(k, "ProgId")[0]
    except OSError:
        progid = ext
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                            progid + r"\shell\open\command") as k:
            return winreg.QueryValueEx(k, "")[0]
    except OSError:
        return None


def _default_handler_is_runnable(ext=".png", read_command=None):
    """True quando a extensao tem handler com linha de comando de verdade."""
    if read_command is None:
        read_command = _handler_command
    return bool((read_command(ext) or "").strip())


def open_file(path, *, handler_runnable=None, shell_open=None, browser_open=None):
    """Abre o arquivo no visualizador padrao, com o navegador como plano B.

    Devolve "shell" ou "browser", conforme o caminho efetivamente usado.
    """
    if handler_runnable is None:
        handler_runnable = _default_handler_is_runnable
    if shell_open is None:
        shell_open = getattr(os, "startfile", None)
    if browser_open is None:
        browser_open = webbrowser.open

    if shell_open is not None and handler_runnable():
        try:
            shell_open(os.path.abspath(path))
            return "shell"
        except OSError:
            pass
    browser_open(pathlib.Path(path).resolve().as_uri())
    return "browser"


RE_ANCHOR = re.compile(r"^#\s*anchor:\s*(\S+)\s*\(([^)]*)\)(.*)$")

TraceAnchor = namedtuple("TraceAnchor", "kind note trustworthy")


def read_anchor(path):
    """Le a marca de procedencia do relogio gravada por nrf_trace.write_txt.

    Devolve None para um .txt sem a marca (conversao antiga): nao da para
    afirmar nada sobre a hora dele, nem que e boa nem que e ruim.
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("#"):
                return None
            m = RE_ANCHOR.match(line)
            if m:
                kind, note, resto = m.groups()
                return TraceAnchor(kind, note.strip(),
                                   nrf_trace.UNTRUSTWORTHY not in resto)
    return None


def anchor_warning(anchor, path):
    """Texto do aviso quando a hora do trace nao serve para casar com a orbita."""
    nome = os.path.basename(path)
    if anchor is None:
        return (f"{nome}: .txt sem marca de ancora (conversao antiga). "
                "Reconverta com sync_traces.py --force-convert para saber "
                "de onde veio a hora.")
    if not anchor.trustworthy:
        return (f"{nome}: hora ancorada em '{anchor.kind}' ({anchor.note}) -- "
                "pode estar minutos errada, entao a elevacao nao vai ser "
                "desenhada. Use --force-elevation para desenhar assim mesmo.")
    return None


def guess_satellite_from_filename(path: str) -> str | None:
    """Return a satellite name suggested by the filename, or None."""
    basename = os.path.basename(path)
    for pattern, sat_name in FILENAME_SAT_HINTS:
        if pattern.search(basename):
            return sat_name
    return None


_RE_FILENAME_TS = re.compile(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})")


def parse_filename_timestamp(path: str) -> datetime | None:
    """Extract a UTC datetime from a YYYYMMDD_HHMM filename pattern, or None."""
    m = _RE_FILENAME_TS.search(os.path.basename(path))
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            int(m.group(4)), int(m.group(5)))
        except ValueError:
            return None
    return None


def pick_best_anchor(all_time_anchors, filename_ts):
    """Return (dev_fix_td, utc_fix) from all_time_anchors closest to filename_ts.

    If filename_ts is None, returns the last anchor.
    """
    if not all_time_anchors:
        return None, None
    if filename_ts is None:
        return all_time_anchors[-1]
    return min(all_time_anchors, key=lambda a: abs((a[1] - filename_ts).total_seconds()))

LATITUDE  = -30.033027
LONGITUDE = -51.229685


def decode_udp_packet(hex_str: str) -> dict | None:
    """Decode a raw IPv4/UDP packet from hex and return a dict with header + payload info."""
    raw = bytes.fromhex(hex_str)
    if len(raw) < 28:  # minimum IP (20) + UDP (8)
        return None
    # IPv4 header
    ihl = (raw[0] & 0x0F) * 4
    if len(raw) < ihl + 8:
        return None
    proto = raw[9]
    if proto != 17:  # not UDP
        return None
    src_ip = ".".join(str(b) for b in raw[12:16])
    dst_ip = ".".join(str(b) for b in raw[16:20])
    # UDP header
    src_port = int.from_bytes(raw[ihl:ihl+2], "big")
    dst_port = int.from_bytes(raw[ihl+2:ihl+4], "big")
    udp_len  = int.from_bytes(raw[ihl+4:ihl+6], "big")
    # Payload (after 8-byte UDP header)
    payload_bytes = raw[ihl+8:]
    try:
        payload_str = payload_bytes.decode("ascii")
    except (UnicodeDecodeError, ValueError):
        payload_str = payload_bytes.hex()
    return {
        "src_ip": src_ip, "dst_ip": dst_ip,
        "src_port": src_port, "dst_port": dst_port,
        "udp_len": udp_len,
        "payload": payload_str,
        "payload_hex": payload_bytes.hex(),
    }


def parse_device_td(ts: str) -> timedelta:
    """Convert 'HH:MM:SS.ffffff' to a timedelta from midnight."""
    h, m, rest = ts.split(":")
    return timedelta(hours=int(h), minutes=int(m), seconds=float(rest))


def find_net_acks(send_tds, dl_grant_tds, rar_tds, pucch_tds, dl_pdu_tds,
                  burst_gap=timedelta(milliseconds=200),
                  window=timedelta(milliseconds=300)):
    """Pair each uplink send with the DL block that acknowledged it at L2.

    The external trace database does not decode the RLC STATUS PDU, so the
    acknowledgement is inferred from what L1 does log: after the send, the
    first DCI N1 burst that is not a RAR, is confirmed by the UE on NPUCCH
    (HARQ-ACK) and carries no decoded ERRC/NAS PDU is a bare L2 control
    block, i.e. the RLC ack. Returns [(send_td, ack_td)].
    """
    bursts = []
    for td in sorted(dl_grant_tds):
        if bursts and td - bursts[-1][-1] <= burst_gap:
            bursts[-1].append(td)
        else:
            bursts.append([td])
    starts = [b[0] for b in bursts]
    rar_tds, pucch_tds, dl_pdu_tds = sorted(rar_tds), sorted(pucch_tds), sorted(dl_pdu_tds)

    def within(tds, lo, hi):
        return any(lo < td <= hi for td in tds)

    acks = []
    for send in sorted(send_tds):
        for i, start in enumerate(starts):
            if start <= send:
                continue
            end = min(start + window, starts[i + 1]) if i + 1 < len(starts) else start + window
            if within(rar_tds, start, end):
                continue
            if not within(pucch_tds, start, end):
                continue
            if within(dl_pdu_tds, start, end):
                continue
            acks.append((send, start))
            break
    return acks


def load_log(path: str):
    """
    Parse the log file and return:
      - utc_fix        : datetime of the GNSS fix (UTC), or None
      - dev_fix_td     : timedelta (device uptime) at the GNSS fix, or None
      - fallback_utc   : datetime from first standalone +CCLK (no GNSS required)
      - fallback_dev_td: timedelta at that +CCLK line
      - records        : list of (dev_timedelta, rsrp, rsrq, snr)
      - events         : dict[label -> list[dev_timedelta]]
      - gnss_lat       : latitude from first GNSS_POS_REP_PV, or None
      - gnss_lon       : longitude from first GNSS_POS_REP_PV, or None
      - cfun_ntn_on    : list of (dev_timedelta, cfun_value) for modem-on after NTN XSYSTEMMODE
    """
    utc_fix = None
    dev_fix_td = None
    all_time_anchors = []    # all (dev_fix_td, utc_fix) pairs from GNSS+CCLK events
    base_date = None         # data do 1o registro quando o log traz data (padrao novo)
    pending_gnss_td = None   # device time of the most-recent GNSS_POS_REP_PV
    fallback_utc = None      # first +CCLK seen anywhere (tier-2 anchor)
    fallback_dev_td = None
    gnss_lat = None
    gnss_lon = None
    records = []
    events = {label: [] for label, _, _ in EVENT_DEFS}
    udp_packets    = []  # list of (dev_timedelta, decoded_dict) -- uplink
    dl_packets     = []  # list of (dev_timedelta, decoded_dict) -- downlink
    sib32_entries = []  # list of (dev_timedelta, raw_value_str)
    no_cell_tds = []   # device timedeltas for ERRC_CNTRL_RRC_NO_CELL
    rrc_idle_tds = []  # device timedeltas for ERRC_CNTRL_RRC_IDLE
    cfun_ntn_on = []  # list of (dev_timedelta, cfun_value) for modem-on after NTN XSYSTEMMODE
    pending_ntn_sysmode_td = None  # dev_td when last NTN XSYSTEMMODE was seen
    rrc_release_tds = []   # timedeltas of RRCConnectionRelease-NB
    t310_tds        = []   # timedeltas of TIMER_T310 START
    cereg_events    = []   # (dev_td, int value) for each +CEREG: N
    pucch_tds       = []   # HARQ-ACK do UE (NPUCCH)
    dl_pdu_tds      = []   # PDUs L3 / dados de descida decodificados

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = RE_ANSI.sub("", line)
            m_ts = RE_TS.match(line)
            if not m_ts:
                continue
            date_str, ts_str = m_ts.group(1), m_ts.group(2)
            dev_td = parse_device_td(ts_str)

            # --- Padrao novo: a linha ja traz a data e o horario e UTC real ---
            # O primeiro registro vira ancora exata, dispensando GNSS e +CCLK, e
            # dev_td passa a contar da meia-noite desse primeiro dia, de modo que
            # continua crescendo se a captura atravessar a meia-noite.
            if date_str:
                day = datetime.strptime(date_str, "%Y-%m-%d").date()
                if base_date is None:
                    base_date = day
                    utc_fix = datetime.combine(day, dtime()) + dev_td
                    dev_fix_td = dev_td
                    all_time_anchors.append((dev_fix_td, utc_fix))
                dev_td += timedelta(days=(day - base_date).days)

            # --- GNSS fix position report -----------------------------------
            if RE_GNSS_FIX.search(line):
                pending_gnss_td = dev_td
                if gnss_lat is None:
                    m_ll = RE_GNSS_LATLON.search(line)
                    if m_ll:
                        gnss_lat = float(m_ll.group(1))
                        gnss_lon = float(m_ll.group(2))

            # --- +CCLK sets UTC time right after the fix (tier 1) ----------
            # Only accept a CCLK within 60 s of the GNSS fix; stale logs may
            # contain CCLK lines from a previous session hours later.
            MAX_CCLK_WINDOW = timedelta(seconds=60)
            if pending_gnss_td is not None:
                if dev_td - pending_gnss_td > MAX_CCLK_WINDOW:
                    pending_gnss_td = None  # window elapsed, give up on this fix
                else:
                    m_cclk = RE_CCLK.search(line)
                    if m_cclk:
                        utc_fix = datetime.strptime(m_cclk.group(1), "%y/%m/%d,%H:%M:%S")
                        dev_fix_td = pending_gnss_td
                        all_time_anchors.append((dev_fix_td, utc_fix))
                        pending_gnss_td = None

            # --- First standalone +CCLK anywhere (tier-2 fallback) ---------
            if fallback_utc is None:
                m_cclk2 = RE_CCLK.search(line)
                if m_cclk2:
                    fallback_utc = datetime.strptime(m_cclk2.group(1), "%y/%m/%d,%H:%M:%S")
                    fallback_dev_td = dev_td

            # --- Cell measurements ------------------------------------------
            m_meas = RE_MEAS.search(line)
            if m_meas:
                records.append((dev_td, int(m_meas.group(1)),
                                int(m_meas.group(2)), int(m_meas.group(3))))

            # --- Modem events -----------------------------------------------
            for label, regex, _ in EVENT_DEFS:
                if regex is not None and regex.search(line):
                    events[label].append(dev_td)

            if RE_PUCCH.search(line):
                pucch_tds.append(dev_td)
            if RE_DL_PDU.search(line):
                dl_pdu_tds.append(dev_td)

            # --- RRC cell-search state --------------------------------------
            if RE_NO_CELL.search(line):
                no_cell_tds.append(dev_td)
            elif RE_RRC_IDLE.search(line):
                rrc_idle_tds.append(dev_td)

            # --- NTN XSYSTEMMODE -> CFUN activation sequence ------------------
            if RE_XSYSTEMMODE_NTN.search(line):
                pending_ntn_sysmode_td = dev_td
            if pending_ntn_sysmode_td is not None:
                m_cfun = RE_CFUN_SET.search(line)
                if m_cfun:
                    cfun_val = int(m_cfun.group(1))
                    # CFUN=1 or CFUN=21 are the modem-on commands; ignore 0/4/30
                    if cfun_val not in (0, 4, 30):
                        if dev_td - pending_ntn_sysmode_td <= timedelta(seconds=5):
                            cfun_ntn_on.append((dev_td, cfun_val))
                        pending_ntn_sysmode_td = None

            # --- SIB32 NTN orbital parameters --------------------------------
            m_sib32 = RE_SIBCONFIG32.search(line)
            if m_sib32:
                sib32_entries.append((dev_td, m_sib32.group(1).strip()))

            # --- RRC release / RLF indicators --------------------------------
            if RE_RRC_RELEASE.search(line):
                rrc_release_tds.append(dev_td)
            if RE_T310_START.search(line):
                t310_tds.append(dev_td)
            m_cereg = RE_CEREG_VAL.search(line)
            if m_cereg:
                cereg_events.append((dev_td, int(m_cereg.group(1))))

            # --- UDP packets (raw IP in EPDCP) --------------------------------
            m_udp = RE_UDP_PACKET.search(line)
            if m_udp:
                pkt = decode_udp_packet(m_udp.group(1))
                if pkt:
                    udp_packets.append((dev_td, pkt))

            m_udp_dl = RE_UDP_DL_PACKET.search(line)
            if m_udp_dl:
                pkt = decode_udp_packet(m_udp_dl.group(1))
                if pkt:
                    dl_packets.append((dev_td, pkt))

    events["Net ACK"] = [ack for _, ack in find_net_acks(
        events["UDP Send"], events["DL Grant"], events["RAR"], pucch_tds, dl_pdu_tds)]

    return utc_fix, dev_fix_td, all_time_anchors, fallback_utc, fallback_dev_td, records, events, gnss_lat, gnss_lon, udp_packets, dl_packets, sib32_entries, cfun_ntn_on, no_cell_tds, rrc_idle_tds, rrc_release_tds, t310_tds, cereg_events


def dev_to_utc(dev_td: timedelta, utc_fix: datetime, dev_fix_td: timedelta) -> datetime:
    """Convert a device-uptime timedelta to a real UTC datetime."""
    offset = utc_fix - datetime(utc_fix.year, utc_fix.month, utc_fix.day) - dev_fix_td
    midnight = datetime(utc_fix.year, utc_fix.month, utc_fix.day)
    return midnight + dev_td + offset


def read_tle_file(path: str) -> tuple[str, str]:
    """Le um TLE local de duas ou tres linhas (nome opcional na primeira)."""
    with open(path, encoding="ascii") as fh:
        lines = [l.strip() for l in fh if l.strip()]
    if len(lines) >= 3:
        lines = lines[-2:]
    if len(lines) != 2 or not lines[0].startswith("1 ") or not lines[1].startswith("2 "):
        raise ValueError(f"{path}: esperado TLE de duas linhas (mais nome opcional)")
    return lines[0], lines[1]


def fetch_elevation(sat_name: str, t_start: datetime, t_end: datetime,
                    lat: float, lon: float, tle_file: str | None = None):
    """Fetch TLE and compute elevation/azimuth samples over [t_start, t_end],
    plus the rise/set times and a full rise->set arc trajectory for the pass
    (which may extend beyond the log's own [t_start, t_end] window).

    Com tle_file, usa o TLE local (sem rede); a epoca deve ser proxima da passada.
    """
    from skyfield.api import Topos, load, EarthSatellite

    if tle_file:
        print(f"Using local TLE for {sat_name}: {tle_file}")
        tle1, tle2 = read_tle_file(tle_file)
    else:
        norad_id = ALL_SATELLITES[sat_name]
        print(f"Fetching TLE for {sat_name} ...")
        tle1, tle2 = fetch_tle(norad_id)
    ts = load.timescale()
    sat = EarthSatellite(tle1, tle2, sat_name, ts)
    observer = Topos(latitude_degrees=lat, longitude_degrees=lon)

    # Precise peak via Skyfield culmination event
    t0 = ts.from_datetime(t_start.replace(tzinfo=timezone.utc))
    t1 = ts.from_datetime(t_end.replace(tzinfo=timezone.utc))
    times_ev, events = sat.find_events(observer, t0, t1, altitude_degrees=0)
    peak_time_exact = None
    peak_el_exact   = None
    for ti, ev in zip(times_ev, events):
        if ev == 1:  # culmination
            alt, _, _ = (sat - observer).at(ti).altaz()
            peak_time_exact = ti.utc_datetime().replace(tzinfo=None)
            peak_el_exact   = alt.degrees

    total_sec = int((t_end - t_start).total_seconds())
    step = 1  # seconds between samples
    el_times, el_degs, az_degs = [], [], []
    for i in range(0, total_sec + step, step):
        dt = t_start + timedelta(seconds=i)
        t  = ts.from_datetime(dt.replace(tzinfo=timezone.utc))
        alt, az, _ = (sat - observer).at(t).altaz()
        el_times.append(dt)
        el_degs.append(alt.degrees)
        az_degs.append(az.degrees)

    # --- Rise/set of the pass (may fall outside the log's own window) -------
    pad = timedelta(minutes=20)
    t0_wide = ts.from_datetime((t_start - pad).replace(tzinfo=timezone.utc))
    t1_wide = ts.from_datetime((t_end + pad).replace(tzinfo=timezone.utc))
    times_ev_wide, events_wide = sat.find_events(observer, t0_wide, t1_wide, altitude_degrees=0)

    anchor = peak_time_exact if peak_time_exact is not None else t_start
    rise_time = None
    set_time  = None
    for ti, ev in zip(times_ev_wide, events_wide):
        t_dt = ti.utc_datetime().replace(tzinfo=None)
        if ev == 0 and t_dt <= anchor:
            rise_time = t_dt  # closest rise at or before the peak
        elif ev == 2 and t_dt >= anchor and set_time is None:
            set_time = t_dt   # first set at or after the peak

    # --- Full rise->set arc trajectory (for the polar sky-path plot) --------
    arc_times, arc_el_degs, arc_az_degs = [], [], []
    if rise_time is not None and set_time is not None:
        arc_total_sec = int((set_time - rise_time).total_seconds())
        for i in range(0, arc_total_sec + step, step):
            dt = rise_time + timedelta(seconds=i)
            t  = ts.from_datetime(dt.replace(tzinfo=timezone.utc))
            alt, az, _ = (sat - observer).at(t).altaz()
            arc_times.append(dt)
            arc_el_degs.append(alt.degrees)
            arc_az_degs.append(az.degrees)

    return (el_times, el_degs, az_degs, peak_time_exact, peak_el_exact, sat, observer,
            rise_time, set_time, arc_times, arc_el_degs, arc_az_degs)


def azel_at(sat, observer, dt: datetime):
    """Return (elevation_deg, azimuth_deg) for sat/observer at a specific UTC datetime."""
    from skyfield.api import load

    ts = load.timescale()
    t = ts.from_datetime(dt.replace(tzinfo=timezone.utc))
    alt, az, _ = (sat - observer).at(t).altaz()
    return alt.degrees, az.degrees


_CAUSE_COLORS = {
    "RELEASE":     "seagreen",
    "RLF":         "crimson",
    "NO_CONNECTION": "gray",
    "UNDETERMINED":  "darkorange",
}


def classify_disconnects(events, rrc_release_tds, t310_tds,
                         cereg_events, no_cell_tds, rrc_idle_tds, records):
    """Classify each +CSCON: 0 as RELEASE, RLF, NO_CONNECTION, or UNDETERMINED.

    Priority (5-second look-back window before each +CSCON: 0):
      1. RRCConnectionRelease-NB present  -> RELEASE
      2. TIMER_T310 START present         -> RLF
      3. Post-drop state (within POST_WINDOW):
           IDLE before NO_CELL            -> RELEASE  (lost cell only after going idle)
           CEREG=5 at drop, NO_CELL later -> RELEASE  (no service event, still registered)
           NO_CELL before IDLE / CEREG=4  -> RLF
           IDLE / CEREG=5 (no NO_CELL)    -> RELEASE
           otherwise                      -> UNDETERMINED

    Returns list of dicts: {cause, cscon_off_td, rsrp_at_drop}.
    """
    WINDOW      = timedelta(seconds=5)
    POST_WINDOW = timedelta(seconds=30)
    cscon_on_tds  = sorted(events.get("CSCON=1", []))
    cscon_off_tds = sorted(events.get("CSCON=0", []))

    if not cscon_on_tds:
        return [{"cause": "NO_CONNECTION", "cscon_off_td": None, "rsrp_at_drop": None}]

    sorted_no_cell  = sorted(no_cell_tds)
    sorted_idle     = sorted(rrc_idle_tds)
    sorted_cereg    = sorted(cereg_events)

    results = []
    for off_td in cscon_off_tds:
        win_start  = off_td - WINDOW
        post_limit = off_td + POST_WINDOW

        rsrp_at_drop = next(
            (rsrp for r_td, rsrp, _, _ in reversed(records) if r_td <= off_td),
            None,
        )

        # CEREG value at the moment of drop (most recent at or before off_td)
        cereg_at_drop = next(
            (v for td, v in reversed(sorted_cereg) if td <= off_td),
            None,
        )

        has_release = any(win_start <= td <= off_td for td in rrc_release_tds)
        has_t310    = any(win_start <= td <= off_td for td in t310_tds)

        if has_release:
            cause = "RELEASE"
        elif has_t310:
            cause = "RLF"
        else:
            next_no_cell = next(
                (td for td in sorted_no_cell if off_td < td <= post_limit), None
            )
            next_idle    = next(
                (td for td in sorted_idle    if off_td < td <= post_limit), None
            )
            next_cereg_4 = next(
                (td for td, v in sorted_cereg if off_td < td <= post_limit and v == 4), None
            )
            next_cereg_5 = next(
                (td for td, v in sorted_cereg if off_td < td <= post_limit and v == 5), None
            )

            if next_idle and next_no_cell and next_idle < next_no_cell:
                # Went idle first; losing the cell afterward is normal idle behaviour
                cause = "RELEASE"
            elif next_no_cell and cereg_at_drop == 5 and next_cereg_4 is None:
                # Cell lost after drop but CEREG was already registered-idle (5) and
                # never dropped to no-service (4) -> graceful, satellite passed overhead
                cause = "RELEASE"
            elif next_no_cell or next_cereg_4:
                cause = "RLF"
            elif next_idle or next_cereg_5 or cereg_at_drop == 5:
                cause = "RELEASE"
            else:
                cause = "UNDETERMINED"

        results.append({"cause": cause, "cscon_off_td": off_td, "rsrp_at_drop": rsrp_at_drop})

    return results


def draw_polar_panel(fig, subplot_spec, log_path: str, sat_name: str, el_times, el_degs, az_degs,
               arc_el_degs, arc_az_degs, rise_time, set_time, peak_time, peak_el,
               cfun_ntn_on, disconnects, utc_fix: datetime, dev_fix_td: timedelta,
               sat, observer):
    """Draw a polar azimuth x elevation view of the full pass (rise->set) into
    the given subplot_spec of fig, marking Rise/Peak/Set plus attach/drop
    events. Falls back to the log's own sampling window (el_degs/az_degs) if
    the full arc could not be resolved."""
    ax = fig.add_subplot(subplot_spec, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)

    # --- Trajectory: full rise->set arc when available, no FOV shading ------
    traj_el = arc_el_degs if arc_el_degs else el_degs
    traj_az = arc_az_degs if arc_az_degs else az_degs
    az_rad  = [math.radians(a) for a in traj_az]
    r       = [90 - e for e in traj_el]
    ax.plot(az_rad, r, color="royalblue", linewidth=1.8, label="Trajectory (actual elev.)")

    ax.set_rlim(0, 90)
    ax.set_yticks([0, 30, 60, 90])
    ax.set_yticklabels(["90deg", "60deg", "30deg", "Horizon"])

    legend_handles = {}

    def _mark(dt, marker, color, label, size=90):
        el, az = azel_at(sat, observer, dt)
        h = ax.scatter(math.radians(az), 90 - el, marker=marker, color=color,
                        s=size, zorder=5, label=label)
        legend_handles.setdefault(label, h)

    # --- Rise / Peak / Set ----------------------------------------------------
    if rise_time is not None:
        _mark(rise_time, "o", "green", "Rise (0deg)")
    if peak_time is not None:
        _mark(peak_time, "*", "navy", f"Peak ({peak_el:.1f}deg)", size=160)
    if set_time is not None:
        _mark(set_time, "o", "red", "Set (0deg)")

    # --- Attach start marker(s) ----------------------------------------------
    for dev_td, cfun_val in cfun_ntn_on:
        dt = dev_to_utc(dev_td, utc_fix, dev_fix_td)
        _mark(dt, "s", "orange", "Attach start")

    # --- Disconnect markers (colored by cause) --------------------------------
    for d in disconnects:
        if d["cscon_off_td"] is None:
            continue
        dt     = dev_to_utc(d["cscon_off_td"], utc_fix, dev_fix_td)
        cause  = d["cause"]
        color  = _CAUSE_COLORS.get(cause, "black")
        marker = "X" if cause == "RLF" else "o"
        _mark(dt, marker, color, cause)

    handles = list(legend_handles.values())
    labels  = [h.get_label() for h in handles]
    ax.legend(handles, labels, loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=8)

    ax.set_title(f"{sat_name} -- pass {log_path}", fontsize=10)


def elevation_ylim(el_degs, frac=0.10, min_margin=0.1):
    """Return (lo, hi) y-limits that frame the elevation curve.

    The margin is a fraction of the curve's own span, so a full rise->set arc
    keeps a few degrees of air while a 16 s window near the peak, where the
    satellite moves well under a degree, is not flattened into a straight
    line. `min_margin` keeps a flat series from collapsing to zero height.
    """
    lo, hi = min(el_degs), max(el_degs)
    margin = max((hi - lo) * frac, min_margin)
    return lo - margin, hi + margin


def compute_snr_layout(events, el_times, el_degs):
    """Return (has_elev, has_events, n_rows, height_ratios, total_height) for
    the SNR panel's internal row layout (SNR always on top, then events if
    any, then elevation)."""
    has_elev   = el_times is not None and el_degs is not None
    has_events = events is not None and any(len(v) > 0 for v in events.values())

    n_rows = 1 + has_events + has_elev
    height_ratios = [3]
    if has_events:
        height_ratios.append(1.8)
    if has_elev:
        height_ratios.append(1.5)

    total_height = 5 + 2 * has_events + 2 * has_elev
    return has_elev, has_events, n_rows, height_ratios, total_height


def draw_snr_panel(fig, subplot_spec, log_path: str, utc_fix: datetime, dev_fix_td: timedelta, records,
         events, el_times, el_degs, sat_name, time_source, no_cell_tds, rrc_idle_tds,
         disconnects, has_elev, has_events, n_rows, height_ratios):
    """Draw the SNR/RSRP + events swim-lane + elevation stack into the given
    subplot_spec of fig."""
    times = [dev_to_utc(r[0], utc_fix, dev_fix_td) for r in records]
    rsrp  = [r[1] for r in records]
    rsrq  = [r[2] for r in records]
    snr   = [r[3] for r in records]

    gs = GridSpecFromSubplotSpec(
        n_rows, 1, subplot_spec=subplot_spec, height_ratios=height_ratios, hspace=0.15
    )
    axes = [fig.add_subplot(gs[0])]
    for i in range(1, n_rows):
        axes.append(fig.add_subplot(gs[i], sharex=axes[0]))

    ax1    = axes[0]
    ax_ev  = axes[1] if has_events else None
    ax_el  = axes[-1] if has_elev else None

    # --- RRC-connected windows (shade SNR background between CSCON=1/0) -----
    if events:
        cscon_on_times  = sorted(dev_to_utc(td, utc_fix, dev_fix_td)
                                 for td in events.get("CSCON=1", []))
        cscon_off_times = sorted(dev_to_utc(td, utc_fix, dev_fix_td)
                                 for td in events.get("CSCON=0", []))
        for t_on in cscon_on_times:
            t_off_candidates = [t for t in cscon_off_times if t > t_on]
            t_off = t_off_candidates[0] if t_off_candidates else times[-1]
            ax1.axvspan(t_on, t_off, alpha=0.12, color="teal", zorder=0)
            duration_s = (t_off - t_on).total_seconds()
            t_mid = t_on + (t_off - t_on) / 2
            ax1.text(
                t_mid, 0.97, f"{duration_s:.0f}s",
                transform=ax1.get_xaxis_transform(),
                ha="center", va="top", fontsize=7.5,
                color="teal", fontweight="bold",
            )

    # --- NO_CELL search windows (shade SNR background) ----------------------
    if no_cell_tds:
        no_cell_times  = sorted(dev_to_utc(td, utc_fix, dev_fix_td) for td in no_cell_tds)
        rrc_idle_times = sorted(dev_to_utc(td, utc_fix, dev_fix_td) for td in (rrc_idle_tds or []))
        i = 0
        while i < len(no_cell_times):
            t_start = no_cell_times[i]
            if t_start >= times[-1]:
                break
            candidates = [t for t in rrc_idle_times if t > t_start]
            t_end = candidates[0] if candidates else times[-1]
            ax1.axvspan(t_start, t_end, alpha=0.10, color="salmon", zorder=0)
            i = next((j for j, t in enumerate(no_cell_times) if t > t_end),
                     len(no_cell_times))

    # --- Disconnect cause annotations (RELEASE / RLF / ...) ----------------
    if disconnects:
        for d in disconnects:
            if d["cscon_off_td"] is None:
                continue
            t_drop = dev_to_utc(d["cscon_off_td"], utc_fix, dev_fix_td)
            color  = _CAUSE_COLORS.get(d["cause"], "black")
            ax1.axvline(t_drop, color=color, linestyle="--", linewidth=1.2, alpha=0.8, zorder=4)
            rsrp_lbl = f"\n{d['rsrp_at_drop']} dBm" if d["rsrp_at_drop"] is not None else ""
            ax1.text(
                t_drop, 0.02, f" {d['cause']}{rsrp_lbl}",
                transform=ax1.get_xaxis_transform(),
                ha="left", va="bottom", fontsize=7.5,
                color=color, fontweight="bold", rotation=90,
            )

    # --- SNR (primary axis) -------------------------------------------------
    ax1.plot(times, snr, color="steelblue", linewidth=1.8, label="SNR (dB)")
    ax1.set_ylabel("SNR (dB)", color="steelblue")
    ax1.tick_params(axis="y", labelcolor="steelblue")
    ax1.axhline(0, color="steelblue", linestyle=":", linewidth=0.8, alpha=0.5)

    # --- RSRP (secondary axis) ----------------------------------------------
    ax2 = ax1.twinx()
    ax2.plot(times, rsrp, color="darkorange", linewidth=1.4,
             linestyle="--", label="RSRP (dBm)")
    ax2.set_ylabel("RSRP (dBm)", color="darkorange")
    ax2.tick_params(axis="y", labelcolor="darkorange")

    # --- Title & metadata ---------------------------------------------------
    if time_source == "GNSS+CCLK":
        ttff = dev_fix_td - parse_device_td("03:10:21.000000")  # approx GNSS start
        anchor_str = (
            f"GNSS FIX @ {utc_fix.strftime('%Y-%m-%d %H:%M:%S')} UTC  "
            f"(TTFF ~ {ttff.seconds}s)"
        )
    else:
        anchor_str = ""
    title = f"NB-IoT Cell SNR  |  {log_path}\n{anchor_str}" if anchor_str else f"NB-IoT Cell SNR  |  {log_path}"
    ax1.set_title(title, fontsize=10)
    ax1.set_xlim(left=times[0] - timedelta(seconds=2))

    # --- Legends & grid -----------------------------------------------------
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)
    ax1.grid(True, alpha=0.3)

    # --- Events subplot (swim-lane style) -----------------------------------
    if has_events:
        # Only include event types that actually have occurrences
        _swimlane_hide = {"CSCON=1", "CSCON=0"}
        active = [(label, color) for label, _, color in EVENT_DEFS
                  if events.get(label) and label not in _swimlane_hide]
        y_labels = [label for label, _ in active]
        y_pos    = range(len(active))

        for yi, (label, color) in zip(y_pos, active):
            ev_times = [dev_to_utc(td, utc_fix, dev_fix_td) for td in events[label]]
            ax_ev.scatter(ev_times, [yi] * len(ev_times),
                          marker="|", s=200, linewidths=1.5,
                          color=color, label=label, zorder=3)
            if label == "Net ACK":
                sends = sorted(events.get("UDP Send", []))
                for td, t_ack in zip(events[label], ev_times):
                    prior = [s for s in sends if s <= td]
                    if prior:
                        delta = (td - prior[-1]).total_seconds()
                        ax_ev.annotate(f"+{delta:.1f}s", (t_ack, yi),
                                       xytext=(5, 0), textcoords="offset points",
                                       fontsize=7, color=color, va="center")

        ax_ev.set_yticks(list(y_pos))
        ax_ev.set_yticklabels(y_labels, fontsize=8)
        ax_ev.set_ylabel("Events", fontsize=9)
        ax_ev.set_ylim(-0.6, len(active) - 0.4)
        ax_ev.grid(axis="x", alpha=0.3)
        ax_ev.tick_params(axis="y", length=0)
        # Light horizontal separator lines between swim lanes
        for yi in range(1, len(active)):
            ax_ev.axhline(yi - 0.5, color="lightgray", linewidth=0.6)

    # --- X-axis formatting (tick labels only on the bottom subplot) ---------
    bottom_ax = ax_el if has_elev else (ax_ev if has_events else ax1)
    bottom_ax.set_xlabel("UTC Time")
    bottom_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    # intervalo de tick proporcional a janela: ~12 rotulos, para nao sobrepor em passadas longas
    x0, x1 = bottom_ax.get_xlim()
    span_s = max(1.0, (x1 - x0) * 86400.0)
    step = next((s for s in (5, 10, 15, 30, 60, 120, 300) if span_s / s <= 14), 600)
    bottom_ax.xaxis.set_major_locator(mdates.SecondLocator(interval=step) if step < 60
                                      else mdates.MinuteLocator(interval=step // 60))
    plt.setp(bottom_ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    for ax in axes:
        if ax is not bottom_ax:
            ax.tick_params(axis="x", labelbottom=False)

    # --- Elevation subplot --------------------------------------------------
    if has_elev:
        ax_el.plot(el_times, el_degs, color="seagreen", linewidth=1.6,
                   label=f"{sat_name} elevation")
        ax_el.set_ylim(*elevation_ylim(el_degs))
        ax_el.axhline(0, color="gray", linestyle=":", linewidth=0.8, alpha=0.5)
        ax_el.set_ylabel("Elevation (deg)", color="seagreen")
        ax_el.tick_params(axis="y", labelcolor="seagreen")
        ax_el.legend(loc="upper right", fontsize=9)
        ax_el.grid(True, alpha=0.3)


def plot_combined(log_path: str, utc_fix: datetime, dev_fix_td: timedelta, records,
         events=None, el_times=None, el_degs=None, az_degs=None, sat_name=None,
         time_source="GNSS+CCLK", no_cell_tds=None, rrc_idle_tds=None,
         no_open=False, disconnects=None, arc_el_degs=None, arc_az_degs=None,
         rise_time=None, set_time=None, peak_time=None, peak_el=None,
         cfun_ntn_on=None, sat=None, observer=None, out_dir="plots"):
    """Build the combined figure: SNR/events/elevation panel on the left, and
    (when pass data is available) the polar sky-path panel on the right.
    Saves a single PNG and opens it unless no_open."""
    has_elev, has_events, n_rows, height_ratios, total_height = compute_snr_layout(
        events, el_times, el_degs
    )
    has_polar = (sat_name is not None and el_times is not None
                 and el_degs is not None and az_degs is not None)

    if has_polar:
        fig = plt.figure(figsize=(20, total_height))
        outer = fig.add_gridspec(1, 2, width_ratios=[12, 8], wspace=0.3)
        draw_snr_panel(fig, outer[0, 0], log_path, utc_fix, dev_fix_td, records,
                       events, el_times, el_degs, sat_name, time_source,
                       no_cell_tds, rrc_idle_tds, disconnects,
                       has_elev, has_events, n_rows, height_ratios)
        draw_polar_panel(fig, outer[0, 1], log_path, sat_name, el_times, el_degs, az_degs,
                         arc_el_degs, arc_az_degs, rise_time, set_time, peak_time, peak_el,
                         cfun_ntn_on, disconnects, utc_fix, dev_fix_td, sat, observer)
        base_name = "combined"
    else:
        fig = plt.figure(figsize=(12, total_height))
        outer = fig.add_gridspec(1, 1)
        draw_snr_panel(fig, outer[0, 0], log_path, utc_fix, dev_fix_td, records,
                       events, el_times, el_degs, sat_name, time_source,
                       no_cell_tds, rrc_idle_tds, disconnects,
                       has_elev, has_events, n_rows, height_ratios)
        base_name = "snr"

    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(log_path))[0]
    out = os.path.join(out_dir, f"{base_name}_{base}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    if not no_open:
        open_file(out)


def main():
    parser = argparse.ArgumentParser(
        description="Plot NB-IoT SNR from a Nordic modem trace log, "
                    "calibrating time via the GNSS fix."
    )
    parser.add_argument("log_file", help="Path to the exported trace log (.txt)")
    parser.add_argument("--tle-file", default=None, metavar="ARQUIVO",
                        help="TLE local (2 ou 3 linhas) em vez de baixar do CelesTrak")
    parser.add_argument("--out-dir", default="plots", metavar="DIR",
                        help="Diretorio do PNG (padrao: plots/)")
    parser.add_argument(
        "--satellite", "-s",
        choices=list(ALL_SATELLITES.keys()),
        default=None,
        metavar="NAME",
        help=(
            f"Satellite to overlay elevation for. "
            f"Choices: {', '.join(ALL_SATELLITES)}. "
            "If omitted you will be prompted interactively."
        )
    )
    parser.add_argument(
        "--lat", type=float, default=None,
        help=f"Observer latitude in degrees (default: from log GNSS fix, else {LATITUDE})"
    )
    parser.add_argument(
        "--lon", type=float, default=None,
        help=f"Observer longitude in degrees (default: from log GNSS fix, else {LONGITUDE})"
    )
    parser.add_argument(
        "--force-elevation", action="store_true",
        help="Desenha a elevacao mesmo com a hora do trace nao confiavel."
    )
    parser.add_argument(
        "--no-elevation", action="store_true",
        help="Skip the elevation subplot entirely."
    )
    parser.add_argument(
        "--no-open", action="store_true",
        help="Save the PNG but do not open it with the OS viewer."
    )
    parser.add_argument(
        "--duration", "-d", type=float, default=None, metavar="SECONDS",
        help="Only plot the first N seconds of the trace (from the earliest measurement)."
    )
    args = parser.parse_args()

    if not os.path.isfile(args.log_file):
        sys.exit(f"Error: file not found: {args.log_file}")

    print(f"Parsing {args.log_file} ...")
    utc_fix, dev_fix_td, all_time_anchors, fallback_utc, fallback_dev_td, records, events, gnss_lat, gnss_lon, udp_packets, dl_packets, sib32_entries, cfun_ntn_on, no_cell_tds, rrc_idle_tds, rrc_release_tds, t310_tds, cereg_events = load_log(args.log_file)

    # Pick the anchor whose UTC is closest to the filename timestamp so that
    # multi-session logs (device rebooted between passes) use the right session.
    filename_ts = parse_filename_timestamp(args.log_file)
    if all_time_anchors:
        best_dev_td, best_utc = pick_best_anchor(all_time_anchors, filename_ts)
        if (best_utc, best_dev_td) != (utc_fix, dev_fix_td):
            print(f"Note: selected anchor {best_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC "
                  f"(of {len(all_time_anchors)} time anchor(s) in log)")
        utc_fix, dev_fix_td = best_utc, best_dev_td

    # Resolve observer coordinates: CLI > GNSS fix from log > hardcoded fallback
    if args.lat is not None:
        obs_lat, obs_lon = args.lat, args.lon if args.lon is not None else (gnss_lon or LONGITUDE)
    elif gnss_lat is not None:
        obs_lat, obs_lon = gnss_lat, gnss_lon
        print(f"Using GNSS position from log: lat={obs_lat}, lon={obs_lon}")
    else:
        obs_lat, obs_lon = LATITUDE, LONGITUDE
        print(f"No GNSS position in log; using hardcoded default: lat={obs_lat}, lon={obs_lon}")

    time_source = "GNSS+CCLK"
    if utc_fix is None and fallback_utc is not None:
        print("Warning: no GNSS fix found; using standalone +CCLK as time anchor.")
        utc_fix, dev_fix_td = fallback_utc, fallback_dev_td
        time_source = "+CCLK (no GNSS fix)"
    elif utc_fix is None:
        # Tier 3: parse timestamp from filename using the existing helper
        fn_ts = parse_filename_timestamp(args.log_file)
        if fn_ts:
            utc_fix = fn_ts
            dev_fix_td = records[0][0] if records else timedelta(0)
            print(f"Warning: no +CCLK found; using filename timestamp {utc_fix} UTC as time anchor.")
            time_source = "filename timestamp"
        else:
            sys.exit("Error: no time reference found (no +CCLK, no parseable filename timestamp).")

    trace_anchor = read_anchor(args.log_file)
    aviso = anchor_warning(trace_anchor, args.log_file)
    if aviso:
        print("\n!! " + aviso + "\n", file=sys.stderr)
    if trace_anchor is not None and not trace_anchor.trustworthy \
            and not args.force_elevation:
        args.no_elevation = True

    if not records:
        sys.exit("Error: no L1_DEFAULT_INFO_SERVING_CELL_MEASUREMENTS found in log.")

    if args.duration is not None:
        start_td = records[0][0]
        cutoff_td = start_td + timedelta(seconds=args.duration)
        records         = [r for r in records if r[0] <= cutoff_td]
        for label in events:
            events[label] = [td for td in events[label] if td <= cutoff_td]
        no_cell_tds     = [td for td in no_cell_tds     if td <= cutoff_td]
        rrc_idle_tds    = [td for td in rrc_idle_tds    if td <= cutoff_td]
        rrc_release_tds = [td for td in rrc_release_tds if td <= cutoff_td]
        t310_tds        = [td for td in t310_tds        if td <= cutoff_td]
        cereg_events    = [(td, v) for td, v in cereg_events if td <= cutoff_td]
        print(f"--duration: showing first {args.duration:.0f} s of trace")

    print(f"Found {len(records)} SNR measurements.")
    for label, tds in events.items():
        if tds:
            print(f"  Events [{label}]: {len(tds)}")

    if sib32_entries:
        print(f"\n  SIB32 NTN orbital data: {len(sib32_entries)} entry(ies)")
        for dev_td, val in sib32_entries:
            print(f"    [{dev_td}]  %SIBCONFIG: 32,{val}")

    if udp_packets:
        print(f"\n  UDP packets sent (UL): {len(udp_packets)}")
        for dev_td, pkt in udp_packets:
            print(f"    [{dev_td}]  {pkt['src_ip']}:{pkt['src_port']} -> "
                  f"{pkt['dst_ip']}:{pkt['dst_port']}  "
                  f"({pkt['udp_len']} bytes)")
            print(f"      Payload: {pkt['payload']}")

    if dl_packets:
        print(f"\n  UDP packets received (DL): {len(dl_packets)}")
        for dev_td, pkt in dl_packets:
            print(f"    [{dev_td}]  {pkt['src_ip']}:{pkt['src_port']} -> "
                  f"{pkt['dst_ip']}:{pkt['dst_port']}  "
                  f"({pkt['udp_len']} bytes)")
            print(f"      Payload: {pkt['payload']}")

    if cfun_ntn_on:
        print(f"\n  Modem ON after NTN XSYSTEMMODE: {len(cfun_ntn_on)} event(s)")
        for dev_td, cfun_val in cfun_ntn_on:
            utc_time = dev_to_utc(dev_td, utc_fix, dev_fix_td)
            print(f"    CFUN={cfun_val}  UTC {utc_time.strftime('%Y-%m-%d %H:%M:%S')}  (device uptime {dev_td})")

    el_times = el_degs = az_degs = sat_name = None
    sat = observer = None
    rise_time = set_time = peak_time = peak_el = None
    arc_el_degs = arc_az_degs = None

    if not args.no_elevation:
        sat_name = args.satellite
        if sat_name is None:
            suggestion = guess_satellite_from_filename(args.log_file)
            names = list(ALL_SATELLITES.keys())
            print("\nAvailable satellites:")
            for i, n in enumerate(names, 1):
                hint = "  <-- suggested" if n == suggestion else ""
                print(f"  {i}. {n}{hint}")
            prompt = (
                f"Enter satellite name or number (blank = {suggestion}): "
                if suggestion else
                "Enter satellite name or number (blank to skip): "
            )
            raw = input(prompt).strip()
            if raw == "" and suggestion:
                sat_name = suggestion
                print(f"Using suggested satellite: {sat_name}")
            elif raw:
                if raw.isdigit() and 1 <= int(raw) <= len(names):
                    sat_name = names[int(raw) - 1]
                elif raw.upper() in ALL_SATELLITES:
                    sat_name = raw.upper()
                else:
                    print(f"Unknown satellite '{raw}', skipping elevation.")

        if sat_name:
            times_utc = [dev_to_utc(r[0], utc_fix, dev_fix_td) for r in records]
            all_times = list(times_utc)
            for evt_list in events.values():
                for ts_dev in evt_list:
                    all_times.append(dev_to_utc(ts_dev, utc_fix, dev_fix_td))
            t_start = min(all_times)
            t_end   = max(all_times)
            try:
                (el_times, el_degs, az_degs, peak_time_exact, peak_el_exact, sat, observer,
                 rise_time, set_time, arc_times, arc_el_degs, arc_az_degs) = fetch_elevation(
                    sat_name, t_start, t_end, obs_lat, obs_lon, args.tle_file
                )
                if peak_time_exact is not None:
                    peak_time = peak_time_exact
                    peak_el   = peak_el_exact
                else:
                    peak_idx  = el_degs.index(max(el_degs))
                    peak_time = el_times[peak_idx]
                    peak_el   = el_degs[peak_idx]
                print(
                    f"Pass: {sat_name} | "
                    f"peak {peak_time.strftime('%y-%m-%d %H:%M')} UTC | "
                    f"elevation {peak_el:.1f}deg"
                )
            except Exception as e:
                print(f"Warning: could not fetch elevation data: {e}")
                el_times = el_degs = az_degs = sat_name = None
                sat = observer = None
                rise_time = set_time = peak_time = peak_el = None
                arc_el_degs = arc_az_degs = None

    disconnects = classify_disconnects(
        events, rrc_release_tds, t310_tds,
        cereg_events, no_cell_tds, rrc_idle_tds, records,
    )
    print("\n--- Disconnect classification ---")
    for d in disconnects:
        rsrp_str = f"  RSRP={d['rsrp_at_drop']} dBm" if d["rsrp_at_drop"] is not None else ""
        td_str   = f"  @ {d['cscon_off_td']}" if d["cscon_off_td"] else ""
        print(f"  {d['cause']}{td_str}{rsrp_str}")

    plot_combined(args.log_file, utc_fix, dev_fix_td, records, events, el_times, el_degs, az_degs,
         sat_name, time_source=time_source, no_cell_tds=no_cell_tds, rrc_idle_tds=rrc_idle_tds,
         no_open=args.no_open, disconnects=disconnects, arc_el_degs=arc_el_degs, arc_az_degs=arc_az_degs,
         rise_time=rise_time, set_time=set_time, peak_time=peak_time, peak_el=peak_el,
         cfun_ntn_on=cfun_ntn_on, sat=sat, observer=observer, out_dir=args.out_dir)


if __name__ == "__main__":
    main()