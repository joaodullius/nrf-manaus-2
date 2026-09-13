"""
A/B antenna comparison plot: elevation + RSRP + SNR for two (or more) trace logs
captured against the same satellite pass with different antennas.

Takes N logs (two is the usual case) and produces one figure with three
stacked panels sharing the UTC time axis:
  1) satellite elevation (deg)   -- shared geometry, one curve
  2) RSRP (dBm)                  -- one series per antenna
  3) SNR  (dB)                   -- one series per antenna

Deliberately NOT a dual-axis plot: elevation and signal are different scales,
so they get their own panels stacked on a common x.

Usage:
    python plot_ab_antennas.py traces-txt/20260907_0228_SIOT1_BRA_YG.txt \
                              traces-txt/20260907_0228_SIOT1_BRA_KY.txt
    python plot_ab_antennas.py <logs...> --out plots/ab_antennas.png --no-open
"""

import argparse
import os
import re
import sys
from datetime import timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

import plot_snr
from plot_snr import (
    LATITUDE,
    LONGITUDE,
    dev_to_utc,
    fetch_elevation,
    guess_satellite_from_filename,
    load_log,
    open_file,
    parse_filename_timestamp,
    pick_best_anchor,
)

# Antenna suffix -> human label
ANTENNA_LABELS = {
    "YG": "Yageo W5095",
    "KY": "Kyocera 9002418L0-L16S",
}

# Validated categorical pair (dataviz six-checks, light surface): all PASS
SERIES_COLORS = ["#1F6FB2", "#D95F02", "#1B7F5E", "#8C4BB5"]

EL_COLOR = "#8A8A85"   # recessive grey for the shared geometry curve


def antenna_from_filename(path: str) -> str:
    m = re.search(r"_([A-Z]{2})\.txt$", os.path.basename(path))
    if m:
        return ANTENNA_LABELS.get(m.group(1), m.group(1))
    return os.path.basename(path)


def series_label(dataset):
    """Rotulo da serie, com a incerteza do relogio quando ela importa.

    Um trace ancorado no mtime do arquivo vale +-10 s. Isso nao atrapalha a
    leitura de elevacao, mas precisa estar visivel: sem a marca, a comparacao
    entre duas antenas parece mais precisa no eixo do tempo do que e.
    """
    anchor = dataset.get("anchor")
    if anchor is None or anchor.kind == "cclk":
        return dataset["label"]
    return f"{dataset['label']} ({anchor.note})"


def drop_untrusted(datasets, force=False):
    """Separa as capturas cuja hora nao serve para casar com a orbita.

    Devolve (mantidas, descartadas). Um .txt sem marca de ancora e mantido:
    conversao antiga nao e prova de hora ruim. Ja um trace ancorado na epoca
    do cabecalho erra por minutos e nao pode entrar no A/B em silencio.
    """
    if force:
        return list(datasets), []
    kept, dropped = [], []
    for d in datasets:
        anchor = d.get("anchor")
        (dropped if anchor is not None and not anchor.trustworthy else kept).append(d)
    return kept, dropped


def collect(log_path: str) -> dict:
    (utc_fix, dev_fix_td, all_time_anchors, fallback_utc, fallback_dev_td,
     records, events, gnss_lat, gnss_lon, *_rest) = load_log(log_path)

    if not records:
        raise RuntimeError(f"{os.path.basename(log_path)}: no serving-cell measurements")

    filename_ts = parse_filename_timestamp(log_path)
    if all_time_anchors:
        dev_fix_td, utc_fix = pick_best_anchor(all_time_anchors, filename_ts)
    elif fallback_utc is not None:
        utc_fix, dev_fix_td = fallback_utc, fallback_dev_td
    elif filename_ts:
        utc_fix, dev_fix_td = filename_ts, records[0][0]
    else:
        raise RuntimeError(f"{os.path.basename(log_path)}: no time reference")

    t = [dev_to_utc(r[0], utc_fix, dev_fix_td) for r in records]
    return {
        "path":  log_path,
        "label": antenna_from_filename(log_path),
        "anchor": plot_snr.read_anchor(log_path),
        "sat":   guess_satellite_from_filename(log_path),
        "lat":   gnss_lat,
        "lon":   gnss_lon,
        "t":     t,
        "rsrp":  np.array([r[1] for r in records], dtype=float),
        "rsrq":  np.array([r[2] for r in records], dtype=float),
        "snr":   np.array([r[3] for r in records], dtype=float),
    }


def summarize(ds: dict, el_at_meas: np.ndarray) -> str:
    return (f"  {ds['label']:<16} n={len(ds['t']):3d}  "
            f"RSRP med {np.median(ds['rsrp']):+6.1f} dBm  "
            f"[{ds['rsrp'].min():+.0f}, {ds['rsrp'].max():+.0f}]   "
            f"SNR med {np.median(ds['snr']):+5.1f} dB  "
            f"[{ds['snr'].min():+.0f}, {ds['snr'].max():+.0f}]   "
            f"el {el_at_meas.min():.1f}-{el_at_meas.max():.1f} deg   "
            f"window {ds['t'][0]:%H:%M:%S}-{ds['t'][-1]:%H:%M:%S} UTC")


def series_colors(n: int) -> list:
    """One color per dataset, cycling the validated palette if there are more."""
    return [SERIES_COLORS[i % len(SERIES_COLORS)] for i in range(n)]


def build_figure(datasets, el_times, el_degs, peak_t, peak_el, sat_name,
                 lat, lon, t_start, t_end):
    """Three stacked panels on a shared UTC axis: elevation, RSRP, SNR.

    Deliberately NOT a dual-axis plot: elevation and signal are different
    scales, so they get their own panels stacked on a common x.
    """
    el_degs = np.asarray(el_degs)
    colors = series_colors(len(datasets))

    fig = plt.figure(figsize=(13, 9.5))
    fig.patch.set_facecolor("#FCFCFB")
    gs = fig.add_gridspec(3, 1, height_ratios=[1.0, 1.4, 1.4], hspace=0.13)

    ax_el   = fig.add_subplot(gs[0])
    ax_rsrp = fig.add_subplot(gs[1], sharex=ax_el)
    ax_snr  = fig.add_subplot(gs[2], sharex=ax_el)

    for ax in (ax_el, ax_rsrp, ax_snr):
        ax.set_facecolor("#FCFCFB")
        ax.grid(True, alpha=0.25, linewidth=0.7)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#C9C9C4")

    # Panel 1 - shared geometry
    ax_el.fill_between(el_times, 0, el_degs, color=EL_COLOR, alpha=0.14, zorder=1)
    ax_el.plot(el_times, el_degs, color=EL_COLOR, linewidth=2.0, zorder=2)
    if peak_t is not None:
        ax_el.axvline(peak_t, color=EL_COLOR, linestyle="--", linewidth=1.2, alpha=0.9)
        ax_el.annotate(f"peak {peak_el:.1f} deg  {peak_t:%H:%M:%S}",
                       xy=(peak_t, peak_el), xytext=(7, -2),
                       textcoords="offset points", fontsize=9,
                       color="#4A4A46", va="top")
    # shade each capture window
    for d, color in zip(datasets, colors):
        ax_el.axvspan(d["t"][0], d["t"][-1], color=color, alpha=0.10, zorder=0)
    ax_el.set_ylabel("Elevation (deg)", fontsize=10, color="#3A3A36")
    ax_el.set_ylim(0, float(el_degs.max()) * 1.25)
    ax_el.set_title("Same pass, different capture windows", fontsize=10,
                    color="#6A6A64", loc="left", pad=6)

    # Panels 2 & 3 - signal vs time
    for key, ax, ylabel in (("rsrp", ax_rsrp, "RSRP (dBm)"),
                            ("snr",  ax_snr,  "SNR (dB)")):
        for d, color in zip(datasets, colors):
            ax.plot(d["t"], d[key], color=color, linewidth=2.0,
                    marker="o", markersize=4.5, markeredgecolor="#FCFCFB",
                    markeredgewidth=0.8, label=series_label(d), zorder=3)
            ax.axhline(float(np.median(d[key])), color=color, linewidth=1.0,
                       linestyle=":", alpha=0.55, zorder=2)
        ax.set_ylabel(ylabel, fontsize=10, color="#3A3A36")
        if peak_t is not None:
            ax.axvline(peak_t, color=EL_COLOR, linestyle="--", linewidth=1.2, alpha=0.6)

    ax_rsrp.legend(loc="lower right", fontsize=9, frameon=True, framealpha=0.9,
                   edgecolor="#DCDCD7", ncol=1 if len(datasets) <= 4 else 2)

    ax_el.tick_params(labelbottom=False)
    ax_rsrp.tick_params(labelbottom=False)
    ax_snr.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax_snr.set_xlabel("UTC", fontsize=10, color="#3A3A36")
    ax_snr.set_xlim(t_start, t_end)

    day = datasets[0]["t"][0].strftime("%Y-%m-%d")
    fig.suptitle(f"Antenna A/B \u2014 {sat_name} pass {day}  "
                 f"(peak {peak_el:.1f} deg, {peak_t:%H:%M:%S} UTC)",
                 fontsize=15, y=0.955, color="#1A1A18")
    fig.text(0.5, 0.925,
             "Serving-cell measurements from the modem trace; elevation from TLE (SGP4) "
             f"at {lat:.4f}, {lon:.4f}.  Dotted lines = per-series median.",
             ha="center", fontsize=9, color="#6A6A64")
    return fig


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+", help="trace .txt logs (one per antenna)")
    ap.add_argument("--out", default=None, help="output PNG path")
    ap.add_argument("--pad", type=float, default=60.0,
                    help="seconds of elevation context before/after the data (default 60)")
    ap.add_argument("--force-elevation", action="store_true",
                    help="Inclui capturas cuja hora nao e confiavel.")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    datasets = [collect(p) for p in args.logs]
    datasets, descartadas = drop_untrusted(datasets, force=args.force_elevation)
    for d in descartadas:
        print(f"[warn] {os.path.basename(d['path'])}: hora ancorada em "
              f"'{d['anchor'].kind}' ({d['anchor'].note}) -- fora do A/B. "
              "Use --force-elevation para incluir assim mesmo.", file=sys.stderr)
    if not datasets:
        sys.exit("Nenhuma captura com hora confiavel; nada a comparar.")

    sats = {d["sat"] for d in datasets}
    if len(sats) > 1:
        print(f"[warn] logs span more than one satellite: {sats}", file=sys.stderr)
    sat_name = datasets[0]["sat"]
    if sat_name is None:
        sys.exit("Could not infer satellite from filename.")

    lat = next((d["lat"] for d in datasets if d["lat"]), LATITUDE)
    lon = next((d["lon"] for d in datasets if d["lon"]), LONGITUDE)

    t_start = min(min(d["t"]) for d in datasets) - timedelta(seconds=args.pad)
    t_end   = max(max(d["t"]) for d in datasets) + timedelta(seconds=args.pad)

    el_times, el_degs, _az, peak_t, peak_el, *_ = fetch_elevation(
        sat_name, t_start, t_end, lat, lon)
    el_degs = np.array(el_degs)
    epoch = t_start
    el_sec = np.array([(t - epoch).total_seconds() for t in el_times])

    print(f"\nPass: {sat_name}  peak {peak_t:%Y-%m-%d %H:%M:%S} UTC at {peak_el:.1f} deg"
          f"   observer {lat:.4f}, {lon:.4f}\n")
    for d in datasets:
        d["el"] = np.interp([(t - epoch).total_seconds() for t in d["t"]], el_sec, el_degs)
        print(summarize(d, d["el"]))
    print()

    fig = build_figure(datasets, el_times, el_degs, peak_t, peak_el,
                       sat_name, lat, lon, t_start, t_end)

    out = args.out
    if out is None:
        base = os.path.basename(datasets[0]["path"])
        base = re.sub(r"_[A-Z]{2}\.txt$", "", base)
        out = os.path.join("plots", f"ab_antennas_{base}.png")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved {out}")

    if not args.no_open:
        open_file(out)


if __name__ == "__main__":
    main()
