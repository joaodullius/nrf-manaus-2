"""
Aggregate elevation vs RSRP / SNR analysis across all .txt pass logs.

For each log file:
  - parse records (timestamp, rsrp, rsrq, snr) via plot_snr.load_log()
  - infer satellite from filename and fetch TLE-based elevation
  - interpolate elevation at each measurement timestamp
  - collect (elevation, rsrp, snr) tuples

Output:
  - plots/elevation_vs_signal.png  -- scatter + binned mean+/-std (5deg bins)
  - prints per-file summary and overall Pearson r

Usage:
    python analyze_elevation_signal.py
    python analyze_elevation_signal.py --dir path/to/logs
    python analyze_elevation_signal.py --no-open
"""

import argparse
import glob
import os
import sys
from datetime import timedelta

import matplotlib.pyplot as plt
import numpy as np

# Reuse helpers from plot_snr
from plot_snr import (
    dev_to_utc,
    fetch_elevation,
    guess_satellite_from_filename,
    load_log,
    parse_filename_timestamp,
    pick_best_anchor,
)

LATITUDE  = -30.033027
LONGITUDE = -51.229685

# Elevation bins (deg)
BIN_WIDTH = 5
BIN_EDGES = np.arange(0, 90 + BIN_WIDTH, BIN_WIDTH)
BIN_CENTERS = (BIN_EDGES[:-1] + BIN_EDGES[1:]) / 2


def collect_pass_data(log_path: str) -> dict | None:
    """Parse one log and return a dict with elevation-correlated signal arrays.

    Returns None if the file can't be processed.
    """
    try:
        (utc_fix, dev_fix_td, all_time_anchors, fallback_utc, fallback_dev_td,
         records, events, gnss_lat, gnss_lon, udp_packets, dl_packets, sib32_entries,
         cfun_ntn_on, no_cell_tds, rrc_idle_tds,
         rrc_release_tds, t310_tds, cereg_events) = load_log(log_path)
    except Exception as e:
        print(f"  [skip] {os.path.basename(log_path)}: load_log error: {e}")
        return None

    if not records:
        print(f"  [skip] {os.path.basename(log_path)}: no measurements")
        return None

    # Resolve time anchor
    filename_ts = parse_filename_timestamp(log_path)
    if all_time_anchors:
        dev_fix_td, utc_fix = pick_best_anchor(all_time_anchors, filename_ts)
    elif fallback_utc is not None:
        utc_fix, dev_fix_td = fallback_utc, fallback_dev_td
    elif filename_ts and records:
        utc_fix, dev_fix_td = filename_ts, records[0][0]
    else:
        print(f"  [skip] {os.path.basename(log_path)}: no time reference")
        return None

    sat_name = guess_satellite_from_filename(log_path)
    if sat_name is None:
        print(f"  [skip] {os.path.basename(log_path)}: unknown satellite")
        return None

    # Convert records to UTC
    meas_utc  = [dev_to_utc(r[0], utc_fix, dev_fix_td) for r in records]
    meas_rsrp = [r[1] for r in records]
    meas_snr  = [r[3] for r in records]

    t_start = min(meas_utc)
    t_end   = max(meas_utc)

    try:
        el_times, el_degs, _, _, _, _, _, _, _, _, _, _ = fetch_elevation(
            sat_name, t_start, t_end, gnss_lat or LATITUDE, gnss_lon or LONGITUDE)
    except Exception as e:
        print(f"  [skip] {os.path.basename(log_path)}: elevation fetch error: {e}")
        return None

    # Convert to seconds-since-epoch for numpy interpolation
    epoch = t_start
    el_sec  = np.array([(t - epoch).total_seconds() for t in el_times])
    meas_sec = np.array([(t - epoch).total_seconds() for t in meas_utc])

    # Interpolate elevation at each measurement time
    el_at_meas = np.interp(meas_sec, el_sec, np.array(el_degs))

    # Keep only samples where elevation > 0 (satellite above horizon)
    mask = el_at_meas > 0
    if not np.any(mask):
        print(f"  [skip] {os.path.basename(log_path)}: no above-horizon samples")
        return None

    label = os.path.basename(log_path).replace("_BRA.txt", "")
    print(f"  [ok]   {label}: {mask.sum()} samples, sat={sat_name}, "
          f"el=[{el_at_meas[mask].min():.1f}deg, {el_at_meas[mask].max():.1f}deg]")

    return {
        "label":     label,
        "sat":       sat_name,
        "elevation": el_at_meas[mask],
        "rsrp":      np.array(meas_rsrp)[mask].astype(float),
        "snr":       np.array(meas_snr)[mask].astype(float),
    }


def binned_stats(elevation, values):
    """Return (centers, means, stds) for BIN_EDGES bins; NaN where no data."""
    means = np.full(len(BIN_CENTERS), np.nan)
    stds  = np.full(len(BIN_CENTERS), np.nan)
    for i, (lo, hi) in enumerate(zip(BIN_EDGES[:-1], BIN_EDGES[1:])):
        mask = (elevation >= lo) & (elevation < hi)
        if mask.sum() >= 2:
            means[i] = np.mean(values[mask])
            stds[i]  = np.std(values[mask])
    return BIN_CENTERS, means, stds


def pearson_r(x, y):
    if len(x) < 2:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def plot_analysis(passes: list[dict], out_path: str, no_open: bool):
    all_el   = np.concatenate([p["elevation"] for p in passes])
    all_rsrp = np.concatenate([p["rsrp"]      for p in passes])
    all_snr  = np.concatenate([p["snr"]       for p in passes])

    r_rsrp = pearson_r(all_el, all_rsrp)
    r_snr  = pearson_r(all_el, all_snr)
    print(f"\nPearson r -- elevation vs RSRP: {r_rsrp:+.3f}   "
          f"elevation vs SNR: {r_snr:+.3f}")

    cmap   = plt.colormaps["tab20"]
    colors = [cmap(i / max(len(passes) - 1, 1)) for i in range(len(passes))]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # --- Scatter: elevation vs RSRP -----------------------------------------
    for p, col in zip(passes, colors):
        ax1.scatter(p["elevation"], p["rsrp"], s=6, alpha=0.5,
                    color=col, label=p["label"], zorder=2)

    centers, means_rsrp, stds_rsrp = binned_stats(all_el, all_rsrp)
    valid = ~np.isnan(means_rsrp)
    ax1.plot(centers[valid], means_rsrp[valid], "w-", linewidth=2.5, zorder=4)
    ax1.plot(centers[valid], means_rsrp[valid], "k-", linewidth=1.5,
             label="binned mean (5deg)", zorder=5)
    ax1.fill_between(centers[valid],
                     means_rsrp[valid] - stds_rsrp[valid],
                     means_rsrp[valid] + stds_rsrp[valid],
                     alpha=0.18, color="black", zorder=3, label="+/-1 sigma")

    ax1.set_xlabel("Elevation (deg)")
    ax1.set_ylabel("RSRP (dBm)")
    ax1.set_title(f"Elevation vs RSRP  (r = {r_rsrp:+.3f})")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="lower right", fontsize=6.5, ncol=2, framealpha=0.85)

    # --- Scatter: elevation vs SNR -------------------------------------------
    for p, col in zip(passes, colors):
        ax2.scatter(p["elevation"], p["snr"], s=6, alpha=0.5,
                    color=col, label=p["label"], zorder=2)

    centers, means_snr, stds_snr = binned_stats(all_el, all_snr)
    valid = ~np.isnan(means_snr)
    ax2.plot(centers[valid], means_snr[valid], "w-", linewidth=2.5, zorder=4)
    ax2.plot(centers[valid], means_snr[valid], "k-", linewidth=1.5,
             label="binned mean (5deg)", zorder=5)
    ax2.fill_between(centers[valid],
                     means_snr[valid] - stds_snr[valid],
                     means_snr[valid] + stds_snr[valid],
                     alpha=0.18, color="black", zorder=3, label="+/-1 sigma")

    ax2.set_xlabel("Elevation (deg)")
    ax2.set_ylabel("SNR (dB)")
    ax2.set_title(f"Elevation vs SNR  (r = {r_snr:+.3f})")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="lower right", fontsize=6.5, ncol=2, framealpha=0.85)

    fig.suptitle(
        f"Elevation vs Signal Quality -- {len(passes)} passes, "
        f"{len(all_el)} samples",
        fontsize=12,
    )
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")
    if not no_open:
        os.startfile(os.path.abspath(out_path))


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate elevation vs RSRP/SNR across all pass log files."
    )
    parser.add_argument(
        "--dir", default=".",
        help="Directory containing .txt log files (default: current directory)"
    )
    parser.add_argument(
        "--no-open", action="store_true",
        help="Save PNG without opening it."
    )
    args = parser.parse_args()

    log_files = sorted(glob.glob(os.path.join(args.dir, "*.txt")))
    if not log_files:
        sys.exit(f"No .txt files found in {args.dir}")

    print(f"Processing {len(log_files)} log files ...\n")
    passes = []
    for path in log_files:
        result = collect_pass_data(path)
        if result:
            passes.append(result)

    if not passes:
        sys.exit("No usable pass data found.")

    out_path = os.path.join("plots", "elevation_vs_signal.png")
    plot_analysis(passes, out_path, no_open=args.no_open)


if __name__ == "__main__":
    main()
