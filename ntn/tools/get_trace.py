#!/usr/bin/env python3
"""
get_trace.py -- Automated LTE trace capture aligned with LEO satellite passes.

Starts `nrfutil trace lte` PRE minutes before rise and stops it POST minutes
after peak elevation, then waits for the next pass. Runs indefinitely.
"""

import sys
import os
import time
import signal
import subprocess
import argparse
from datetime import datetime, timedelta, timezone
from skyfield.api import Topos, load, EarthSatellite
from tle_fetcher import fetch_tle

GRAY   = "\033[90m"
RESET  = "\033[0m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"

LATITUDE  = -30.033027
LONGITUDE = -51.229685
LOOK_AHEAD_DAYS = 2

ALL_SATELLITES = {
    'SATELIOT_1': 60550,
    'SATELIOT_2': 60534,
    'SATELIOT_3': 60552,
    'SATELIOT_4': 60537,
}


_local_tz = None  # set in main() after timezone resolution

def log(msg, color=RESET):
    now = datetime.now(timezone.utc)
    if _local_tz is not None:
        ts = now.astimezone(_local_tz).strftime('%Y-%m-%d %H:%M:%S')
    else:
        ts = now.strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"{color}[{ts}] {msg}{RESET}", flush=True)


def local_fmt(dt_utc, fmt='%Y-%m-%d %H:%M:%S'):
    """Format a UTC datetime in local time."""
    if _local_tz is not None:
        return dt_utc.astimezone(_local_tz).strftime(fmt)
    return dt_utc.strftime(fmt + ' UTC')


def get_tles(ts, satellites):
    log("Refreshing TLE data from CelesTrak...", YELLOW)
    constellation = {}
    for name, norad_id in satellites.items():
        try:
            tle1, tle2 = fetch_tle(norad_id)
            constellation[name] = EarthSatellite(tle1, tle2, name, ts)
            log(f"  {name}: OK", GREEN)
        except Exception as e:
            log(f"  Failed to load {name}: {e}", RED)
    return constellation


def find_passes(ts, constellation, observer, t0, t1, min_elevation):
    passes = []
    for name, sat in constellation.items():
        times, events = sat.find_events(observer, t0, t1, altitude_degrees=min_elevation)
        current_rise = None
        current_peak_time = None
        current_peak_alt = None

        for ti, event in zip(times, events):
            if event == 0:
                current_rise = ti
                current_peak_time = None
                current_peak_alt = None
            elif event == 1 and current_rise is not None:
                alt, _, _ = (sat - observer).at(ti).altaz()
                current_peak_alt = alt.degrees
                current_peak_time = ti
            elif event == 2 and current_rise is not None:
                peak_t = current_peak_time if current_peak_time is not None else current_rise
                passes.append({
                    'name': name,
                    'rise': current_rise,
                    'peak': peak_t,
                    'set': ti,
                    'peak_alt': current_peak_alt or 0.0,
                })
                current_rise = None
                current_peak_time = None
                current_peak_alt = None

    passes.sort(key=lambda p: p['rise'].tt)
    return passes


def sat_short_name(name):
    """SATELIOT_3 -> SIOT3"""
    return name.replace('SATELIOT_', 'SIOT')


def build_filename(peak_utc_dt, sat_name, suffix, output_dir):
    short = sat_short_name(sat_name)
    fname = peak_utc_dt.strftime(f'%Y%m%d_%H%M_') + f'{short}_{suffix}.bin'
    return os.path.join(output_dir, fname)


def start_trace(port, filepath):
    cmd = ['nrfutil', 'trace', 'lte', '--input-serialport', port, '--output-raw', filepath,
           '--mfw-revision-id', 'mfw_nrf9151-ntn_1.0.1']
    log(f"Starting: {' '.join(cmd)}", CYAN)
    kwargs = {}
    if sys.platform == 'win32':
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(cmd, **kwargs)


def stop_trace(proc):
    if proc is None or proc.poll() is not None:
        return
    log("Stopping trace (sending CTRL+C)...", YELLOW)
    try:
        if sys.platform == 'win32':
            os.kill(proc.pid, signal.CTRL_C_EVENT)
        else:
            proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=8)
            log("Trace stopped.", GREEN)
            return
        except subprocess.TimeoutExpired:
            pass
        # CTRL+C was ignored -- force-kill the entire process tree
        log("Graceful stop timed out -- force killing process tree...", YELLOW)
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                           capture_output=True)
        else:
            proc.kill()
        proc.wait(timeout=5)
        log("Trace killed.", GREEN)
    except Exception as e:
        log(f"Error stopping trace: {e}", RED)


def fmt_hhmm(seconds):
    h, m = divmod(int(seconds) // 60, 60)
    return f"{h:02d}h{m:02d}m"


def wait_until(target_dt, label):
    """Sleep until target_dt, logging progress every 5 minutes."""
    now = datetime.now(timezone.utc)
    remaining = (target_dt - now).total_seconds()
    if remaining <= 0:
        return
    log(f"Waiting {fmt_hhmm(remaining)} until {label} ({local_fmt(target_dt)})", BLUE)
    last_log_mono = time.monotonic()
    while True:
        now = datetime.now(timezone.utc)
        remaining = (target_dt - now).total_seconds()
        if remaining <= 0:
            break
        sleep_chunk = min(10.0, remaining)
        time.sleep(sleep_chunk)
        elapsed_since_log = time.monotonic() - last_log_mono
        remaining2 = (target_dt - datetime.now(timezone.utc)).total_seconds()
        log_interval = 3600 if remaining2 > 3600 else 600
        if elapsed_since_log >= log_interval and remaining2 > 30:
            log(f"  {fmt_hhmm(remaining2)} remaining until {label}", GRAY)
            last_log_mono = time.monotonic()


def main():
    known = list(ALL_SATELLITES.keys())
    parser = argparse.ArgumentParser(
        description="Automated LTE trace capture aligned with LEO satellite passes.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('--port', required=True, metavar='PORT',
                        help="Serial port for nrfutil (e.g. COM4 or /dev/ttyUSB0)")
    parser.add_argument('--suffix', default='BRA', metavar='SUFFIX',
                        help="Output filename suffix (default: BRA)")
    parser.add_argument('--pre', type=float, default=10, metavar='MIN',
                        help="Minutes before pass rise to start trace (default: 10)")
    parser.add_argument('--post', type=float, default=10, metavar='MIN',
                        help="Minutes after pass peak to stop trace (default: 10)")
    parser.add_argument('-e', '--min-elevation', type=float, default=50, metavar='DEG',
                        help="Minimum elevation filter in degrees (default: 50)")
    parser.add_argument('--lat', type=float, default=LATITUDE, metavar='DEG',
                        help=f"Observer latitude (default: {LATITUDE})")
    parser.add_argument('--lon', type=float, default=LONGITUDE, metavar='DEG',
                        help=f"Observer longitude (default: {LONGITUDE})")
    parser.add_argument('-s', '--satellites', nargs='+', default=known,
                        choices=known, metavar='NAME',
                        help=f"Satellites to track (default: all).\nAvailable: {', '.join(known)}")
    parser.add_argument('--output-dir', default='.', metavar='DIR',
                        help="Directory to save trace files (default: current directory)")
    parser.add_argument('--test', action='store_true',
                        help="Start trace immediately for 1 minute, then exit (for testing)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    selected = {name: ALL_SATELLITES[name] for name in args.satellites}
    observer = Topos(latitude_degrees=args.lat, longitude_degrees=args.lon)

    # Resolve local timezone from position
    global _local_tz
    tz_label = "UTC"
    try:
        from timezonefinder import TimezoneFinder
        from zoneinfo import ZoneInfo
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=args.lat, lng=args.lon)
        if tz_name:
            _local_tz = ZoneInfo(tz_name)
            offset_h = datetime.now(_local_tz).utcoffset().total_seconds() / 3600
            tz_label = f"{tz_name} ({offset_h:+.1f}h)"
    except ImportError:
        sys.exit("Error: timezonefinder is not installed. Install with: pip install timezonefinder")
    except Exception as e:
        print(f"{YELLOW}Warning: could not detect timezone ({e}), falling back to UTC.{RESET}")

    log("=" * 55, YELLOW)
    log("  get_trace -- Automated LTE Trace Capture", YELLOW)
    log("=" * 55, YELLOW)
    log(f"  Port          : {args.port}")
    log(f"  Suffix        : {args.suffix}")
    log(f"  Pre-pass      : {args.pre} min before rise")
    log(f"  Post-peak     : {args.post} min after peak")
    log(f"  Min elevation : {args.min_elevation}deg")
    log(f"  Observer      : lat={args.lat}, lon={args.lon}")
    log(f"  Output dir    : {os.path.abspath(args.output_dir)}")
    log(f"  Satellites    : {', '.join(selected.keys())}")
    log(f"  Local timezone: {tz_label}")
    log("=" * 55, YELLOW)

    ts = load.timescale()
    proc = None

    if args.test:
        now = datetime.now(timezone.utc)
        filename = build_filename(now, 'TEST', args.suffix, args.output_dir)
        log(f"TEST MODE -- running trace for 1 minute.", YELLOW)
        log(f"Output file: {filename}", CYAN)
        try:
            proc = start_trace(args.port, filename)
            wait_until(now + timedelta(minutes=1), "test end")
            stop_trace(proc)
            log(f"Test complete. File: {filename}", GREEN)
        except KeyboardInterrupt:
            log("Interrupted.", YELLOW)
            if proc:
                stop_trace(proc)
        sys.exit(0)

    try:
        while True:
            constellation = get_tles(ts, selected)
            if not constellation:
                log("No satellite data available. Retrying in 5 minutes.", RED)
                time.sleep(300)
                continue

            t0 = ts.now()
            t1 = ts.from_datetime(t0.utc_datetime() + timedelta(days=LOOK_AHEAD_DAYS))
            passes = find_passes(ts, constellation, observer, t0, t1, args.min_elevation)

            if not passes:
                log(f"No passes found in the next {LOOK_AHEAD_DAYS} days. Retrying in 1 hour.", YELLOW)
                time.sleep(3600)
                continue

            p = passes[0]
            rise_utc  = p['rise'].utc_datetime().replace(tzinfo=timezone.utc)
            peak_utc  = p['peak'].utc_datetime().replace(tzinfo=timezone.utc)
            set_utc   = p['set'].utc_datetime().replace(tzinfo=timezone.utc)
            duration  = (set_utc - rise_utc).total_seconds()

            trace_start = rise_utc - timedelta(minutes=args.pre)
            trace_stop  = peak_utc + timedelta(minutes=args.post)
            filepath    = build_filename(peak_utc, p['name'], args.suffix, args.output_dir)

            log(f"Next pass  : {p['name']} | "
                f"Rise {local_fmt(rise_utc, '%H:%M:%S')} | "
                f"Peak {local_fmt(peak_utc, '%H:%M:%S')} ({p['peak_alt']:.1f}deg) | "
                f"Set {local_fmt(set_utc, '%H:%M:%S')} | "
                f"Duration {int(duration)//60}m{int(duration)%60:02d}s", GREEN)
            log(f"Trace start: {local_fmt(trace_start)}", CYAN)
            log(f"Trace stop : {local_fmt(trace_stop)}", CYAN)
            log(f"Output file: {filepath}", CYAN)

            now = datetime.now(timezone.utc)
            if trace_stop <= now:
                log("Pass already completed -- skipping.", YELLOW)
                time.sleep(5)
                continue

            # Wait until trace_start (may be in the past if pass already started)
            wait_until(trace_start, "trace start")

            proc = start_trace(args.port, filepath)

            wait_until(trace_stop, "trace stop")

            stop_trace(proc)
            proc = None

            log(f"Trace saved: {filepath} (stopped at {local_fmt(trace_stop, '%H:%M:%S')})", GREEN)
            log("-" * 55, GRAY)
            time.sleep(10)  # brief gap before searching for next pass

    except KeyboardInterrupt:
        log("Interrupted by user.", YELLOW)
        if proc:
            stop_trace(proc)
        sys.exit(0)


if __name__ == '__main__':
    main()
