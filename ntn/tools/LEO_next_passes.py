# Based on original code by Karol Schober

import sys
import argparse
from datetime import datetime, timedelta, timezone
from skyfield.api import Topos, load, EarthSatellite
import numpy as np
import matplotlib.pyplot as plt
from tle_fetcher import fetch_tle

# ANSI Colors
GRAY   = "\033[90m"
RESET  = "\033[0m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"

# --- CONFIGURATION ---
LOOK_AHEAD_DAYS_DEFAULT = 2

LATITUDE = -30.033027
LONGITUDE = -51.229685

ALL_SATELLITES = {
    'SATELIOT_1': 60550,
    'SATELIOT_2': 60534,
    'SATELIOT_3': 60552,
    'SATELIOT_4': 60537,
}

# --- 1. DATA LOADING ---
def get_tles(ts, satellites, print_tle=False):
    print(f"\n{YELLOW}--- REFRESHING ORBITAL DATA (TLE) ---{RESET}")
    constellation = {}
    for name, norad_id in satellites.items():
        try:
            tle1, tle2 = fetch_tle(norad_id)
            sat = EarthSatellite(tle1, tle2, name, ts)
            constellation[name] = (sat, tle1, tle2)
            print(f"{GREEN} -> {name}: OK.{RESET}")
            if print_tle:
                print(f"{GRAY}    {tle1}{RESET}")
                print(f"{GRAY}    {tle2}{RESET}")
        except Exception as e:
            print(f"{RED} -> Failed to download {name}: {e}{RESET}")
    return constellation

# --- 2. POSITIONAL CALCULATIONS ---
def get_alt_az(sat, observer, ts, dt_utc):
    t = ts.from_datetime(dt_utc.replace(tzinfo=timezone.utc))
    difference = sat - observer
    topocentric = difference.at(t)
    alt, az, _ = topocentric.altaz()
    return alt.degrees, az.degrees

def get_compass_direction(degrees):
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = int((degrees / 22.5) + 0.5)
    return points[idx % 16]

def get_pass_direction(sat, rise_t, set_t):
    """Determines pass direction by comparing satellite latitude at rise and set."""
    lat_start = sat.at(rise_t).subpoint().latitude.degrees
    lat_end = sat.at(set_t).subpoint().latitude.degrees
    return "^" if lat_end > lat_start else "v"

def az_in_window(az, min_azimuth, max_azimuth):
    """Check if azimuth falls within window, handling wrap-around through North."""
    if min_azimuth <= max_azimuth:
        return min_azimuth <= az <= max_azimuth
    else:  # wrap-around (e.g. 270->360->90)
        return az >= min_azimuth or az <= max_azimuth

def trajectory_intersects_window(sat, observer, ts, rise_t, set_t, min_azimuth, max_azimuth, step_sec=10):
    """Returns True if any trajectory point falls within the azimuth window."""
    rise_dt = rise_t.utc_datetime().replace(tzinfo=timezone.utc)
    duration_sec = int((set_t - rise_t) * 86400)
    for i in range(0, duration_sec + step_sec, step_sec):
        dt = rise_dt + timedelta(seconds=i)
        _, az, _ = (sat - observer).at(ts.from_datetime(dt)).altaz()
        if az_in_window(az.degrees, min_azimuth, max_azimuth):
            return True
    return False

# --- 3. PLOT GENERATION ---
def save_sky_plot(sat_name, rise_dt, altaz_list, culmination_data=None,
                  min_elevation=0, min_azimuth=0, max_azimuth=360, pass_index=None,
                  duration_data=None):
    import os
    os.makedirs("plots", exist_ok=True)
    timestamp_str = rise_dt.strftime('%d-%m-%y_%H%M')
    prefix = f"{pass_index}_" if pass_index is not None else ""
    filename = os.path.join("plots", f"{prefix}pass_{sat_name}_{timestamp_str}.png")

    fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(8, 8))
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 90)
    ax.set_yticks(range(0, 91, 30))
    ax.set_yticklabels(['90deg', '60deg', '30deg', 'Horizon'])

    # Azimuth field-of-view shading
    if min_azimuth <= max_azimuth:
        theta_fov = np.linspace(np.radians(min_azimuth), np.radians(max_azimuth), 200)
    else:
        # Wrap-around through North (e.g. 270 to 90)
        theta_fov = np.linspace(np.radians(min_azimuth), np.radians(max_azimuth + 360), 200)
    ax.fill_between(theta_fov, 0, 90, color='yellow', alpha=0.15, label="Field of view", zorder=0)

    # Min-elevation ring
    r_min_el = 90 - min_elevation
    theta_ring = np.linspace(0, 2 * np.pi, 360)
    ax.plot(theta_ring, np.full_like(theta_ring, r_min_el), '--', color='gray',
            linewidth=1, label=f"Min elevation ({min_elevation:.0f}deg)", zorder=1)

    az = [p[1].degrees for p in altaz_list]
    alt = [p[0].degrees for p in altaz_list]
    theta = np.radians(az)
    r = 90 - np.array(alt)

    ax.plot(theta, r, label="Trajectory", color='blue', lw=2, alpha=0.7)
    ax.scatter(theta[0], r[0], color='green', label="Rise", zorder=5)
    ax.scatter(theta[-1], r[-1], color='red', label="Set", zorder=5)

    if culmination_data:
        peak_alt, peak_az = culmination_data
        ax.scatter(np.radians(peak_az), 90 - peak_alt, color='darkblue', marker='*', s=150, label="Peak", zorder=6)

    if duration_data:
        total_sec = duration_data
        m, sec = divmod(int(total_sec), 60)
        fig.text(0.02, 0.02, f"Rise\u2192Set: {m}m {sec:02d}s",
                 fontsize=9, color='dimgray')

    plt.title(f"{sat_name} - {rise_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    plt.legend(loc='upper right', bbox_to_anchor=(1.1, 1.1))
    plt.savefig(filename)
    plt.close(fig)

# --- 4. GROUND TRACK MAP ---
def save_ground_track(sat_name, rise_dt, t_samples, sat_obj, observer_lat, observer_lon, culmination_data=None, pass_index=None):
    import folium
    import os
    os.makedirs("maps", exist_ok=True)
    timestamp_str = rise_dt.strftime('%d-%m-%y_%H%M')
    prefix = f"{pass_index}_" if pass_index is not None else ""
    filename = os.path.join("maps", f"{prefix}track_{sat_name}_{timestamp_str}.html")

    # Compute satellite subpoints for each time sample
    track = []
    for t in t_samples:
        sp = sat_obj.at(t).subpoint()
        track.append((sp.latitude.degrees, sp.longitude.degrees))

    m = folium.Map(location=[observer_lat, observer_lon], zoom_start=3)

    folium.PolyLine(track, color='blue', weight=2, opacity=0.8, tooltip=f"{sat_name} ground track").add_to(m)
    folium.Marker(track[0],  popup="Rise", icon=folium.Icon(color='green')).add_to(m)
    folium.Marker(track[-1], popup="Set",  icon=folium.Icon(color='red')).add_to(m)

    if culmination_data:
        mid_idx = len(track) // 2
        peak_alt, _ = culmination_data
        folium.Marker(track[mid_idx], popup=f"Peak: {peak_alt:.1f}deg",
                      icon=folium.Icon(color='darkblue', icon='star')).add_to(m)

    folium.Marker([observer_lat, observer_lon], popup="Observer",
                  icon=folium.Icon(color='orange', icon='home')).add_to(m)

    m.save(filename)

# --- 5. CLEANUP ---
def clean_generated_files():
    import glob, os
    patterns = [
        'plots/*_pass_*_*.png',
        'plots/pass_durations.png',
        'plots/elevation_timeline.png',
        'plots/peak_azimuths.png',
        'plots/all_paths.png',
        'plots/pass_timeline.png',
        'maps/*_track_*_*.html',
    ]
    deleted = 0
    for pattern in patterns:
        for f in glob.glob(pattern):
            os.remove(f)
            deleted += 1
    if deleted:
        print(f"{GREEN}Cleaned {deleted} generated file(s).{RESET}")

# --- 6. MAIN ---
def main():
    known = list(ALL_SATELLITES.keys())
    parser = argparse.ArgumentParser(
        description="Calculates upcoming LEO satellite passes.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--clean', action='store_true',
                        help="Delete the plots/ and maps/ folders, then continue.")
    parser.add_argument('-p', '--plot', action='store_true',
                        help="Generate sky-plot images (.png) for each pass.")
    parser.add_argument('-m', '--map', action='store_true',
                        help="Generate ground-track maps (.html) for each pass.")
    parser.add_argument('-e', '--min-elevation', type=float, default=45, metavar='DEG',
                        help="Minimum elevation filter in degrees (default: 45)")
    parser.add_argument('-a', '--min-azimuth', type=float, default=0, metavar='DEG',
                        help="Minimum azimuth of the view window in degrees (default: 0)")
    parser.add_argument('-A', '--max-azimuth', type=float, default=360, metavar='DEG',
                        help="Maximum azimuth of the view window in degrees (default: 360)")
    parser.add_argument('-s', '--satellites', nargs='+', default=known,
                        choices=known, metavar='NAME',
                        help=f"Satellites to track (default: all).\nAvailable: {', '.join(known)}")
    parser.add_argument('--lat', type=float, default=LATITUDE, metavar='DEG',
                        help=f"Observer latitude in degrees (default: {LATITUDE})")
    parser.add_argument('--lon', type=float, default=LONGITUDE, metavar='DEG',
                        help=f"Observer longitude in degrees (default: {LONGITUDE})")
    parser.add_argument('-d', '--days', type=float, default=LOOK_AHEAD_DAYS_DEFAULT, metavar='DAYS',
                        help=f"Look-ahead window in days (default: {LOOK_AHEAD_DAYS_DEFAULT})")
    parser.add_argument('--utc-offset', type=float, default=None, metavar='HOURS',
                        help="Local UTC offset in hours (overrides auto-detection from position)")
    parser.add_argument('--start', type=str, default=None, metavar='DATETIME_OR_DAYS',
                        help="Search window start: negative number = days before now (e.g. -1 = 1 day ago, -2 = 2 days ago), "
                             "or UTC datetime string 'YYYY-MM-DD HH:MM'. Defaults to now.")
    parser.add_argument('--tle', action='store_true',
                        help="Print TLE lines for each pass.")
    args = parser.parse_args()

    if args.clean:
        clean_generated_files()

    min_elevation = args.min_elevation
    min_azimuth = args.min_azimuth
    max_azimuth = args.max_azimuth
    selected = {name: ALL_SATELLITES[name] for name in args.satellites}
    observer = Topos(latitude_degrees=args.lat, longitude_degrees=args.lon)

    # Resolve local timezone from position or manual override
    tz_label = "unknown"
    if args.utc_offset is not None:
        local_tz = timezone(timedelta(hours=args.utc_offset))
        tz_label = f"manual ({args.utc_offset:+.1f}h)"
    else:
        try:
            from timezonefinder import TimezoneFinder
            from zoneinfo import ZoneInfo
            tf = TimezoneFinder()
            tz_name = tf.timezone_at(lat=args.lat, lng=args.lon)
            if tz_name:
                local_tz = ZoneInfo(tz_name)
                # Get current UTC offset (accounts for DST)
                now_local = datetime.now(local_tz)
                offset_h = now_local.utcoffset().total_seconds() / 3600
                tz_label = f"{tz_name} ({offset_h:+.1f}h)"
            else:
                raise ValueError("No timezone found for coordinates")
        except ImportError:
            sys.exit("Error: timezonefinder is not installed. Install it with: pip install timezonefinder")
        except Exception as e:
            if "ZoneInfoNotFoundError" in type(e).__name__ or "No time zone found" in str(e):
                sys.exit(f"Error: timezone data not found for '{tz_name}'. On Windows, install tzdata: pip install tzdata")
            raise

    print(f"{YELLOW}{'=' * 50}{RESET}")
    print(f"{YELLOW}  CONFIGURATION{RESET}")
    print(f"{YELLOW}{'=' * 50}{RESET}")
    print(f"  Observer       : lat={args.lat}, lon={args.lon}")
    print(f"  Min elevation  : {min_elevation} deg")
    print(f"  Azimuth window : {min_azimuth} - {max_azimuth} deg")
    if args.start:
        try:
            _h = float(args.start)
            _start_label = f"{abs(_h):.0f}d ago" if _h < 0 else args.start + ' UTC'
        except ValueError:
            _start_label = args.start + ' UTC'
    else:
        _start_label = 'now (default)'
    print(f"  Start time     : {_start_label}")
    print(f"  Look-ahead     : {args.days} day(s)")
    print(f"  Satellites     : {', '.join(selected.keys())}")
    print(f"  Generate plots : {args.plot}")
    print(f"  Generate maps  : {args.map}")
    print(f"  Local timezone : {tz_label}")
    print(f"{YELLOW}{'=' * 50}{RESET}")

    ts = load.timescale()
    constellation = get_tles(ts, selected, print_tle=args.tle)

    if not constellation:
        print(f"{RED}Error: could not load satellite data.{RESET}")
        return

    print(f"\n{YELLOW}{'=' * 144}{RESET}")
    print(f"{'#':<3} | {'Satellite':<12} | {'Peak UTC':<16} | {'Peak Local':<16} | {'Peak Azim':<12} | {'Max Elev':<9} | {'Dir':<3} | {'Duration':<16} |")
    print(f"{GRAY}{'-' * 144}{RESET}")

    now_utc = datetime.now(timezone.utc)
    if args.start:
        try:
            days_offset = float(args.start)
            start_dt = now_utc + timedelta(days=days_offset)
        except ValueError:
            try:
                start_dt = datetime.strptime(args.start, '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            except ValueError:
                sys.exit("Error: --start must be a negative number (days before now, e.g. -2) "
                         "or a UTC datetime 'YYYY-MM-DD HH:MM'")
        t0 = ts.from_datetime(start_dt)
    else:
        t0 = ts.now()
    t1 = ts.from_datetime(t0.utc_datetime() + timedelta(days=args.days))

    all_passes = []

    for name, (sat, _, _) in constellation.items():
        times, events = sat.find_events(observer, t0, t1, altitude_degrees=min_elevation)

        current_rise = None
        current_culmination = None

        for ti, event in zip(times, events):
            if event == 0: # Rise
                current_rise = ti
            elif event == 1: # Culmination
                p_alt, p_az = get_alt_az(sat, observer, ts, ti.utc_datetime())
                current_culmination = (p_alt, p_az)
            elif event == 2 and current_rise is not None: # Set
                if current_culmination:
                    p_alt, p_az = current_culmination

                    # Azimuth filter: accept if any trajectory point falls in the window
                    if trajectory_intersects_window(sat, observer, ts, current_rise, ti, min_azimuth, max_azimuth):
                        direction = get_pass_direction(sat, current_rise, ti)
                        all_passes.append({
                            'name': name,
                            'rise': current_rise,
                            'set': ti,
                            'peak_alt': p_alt,
                            'peak_az': p_az,
                            'direction': direction
                        })
                current_rise = None
                current_culmination = None

    if not all_passes:
        print(f"{YELLOW}No passes found in the next {args.days} day(s).{RESET}")
        return

    all_passes.sort(key=lambda x: x['rise'].tt)

    pass_profiles = []  # (idx, name, [datetime, ...], [elevation_deg, ...])

    for idx, p in enumerate(all_passes, start=1):
        utc_dt = p['rise'].utc_datetime()
        set_utc_dt = p['set'].utc_datetime()
        total_sec = (set_utc_dt - utc_dt).total_seconds()
        peak_utc_dt = utc_dt + (set_utc_dt - utc_dt) / 2
        peak_local_dt = peak_utc_dt.replace(tzinfo=timezone.utc).astimezone(local_tz)
        dur_m, dur_s = divmod(int(total_sec), 60)
        is_past = set_utc_dt.replace(tzinfo=timezone.utc) < now_utc
        dur_str = f"{dur_m}m {dur_s:02d}s" + (" [PAST]" if is_past else "")
        row_color = GRAY if is_past else ""
        print(f"{row_color}{idx:<3} | {p['name']:<12} | {peak_utc_dt.strftime('%y-%m-%d %H:%M'):<16} | {peak_local_dt.strftime('%y-%m-%d %H:%M'):<16} | "
              f"{p['peak_az']:>6.1f}deg {get_compass_direction(p['peak_az']):<4} | {p['peak_alt']:>5.1f}deg    |  {p['direction']}  | {dur_str:<16} |{RESET}")

        if args.plot or args.map:
            duration_sec = int((p['set'] - p['rise']) * 86400)
            t_samples = [ts.from_datetime(utc_dt + timedelta(seconds=i)) for i in range(0, duration_sec + 1)]
            sat_obj, _, _ = constellation[p['name']]

            if args.plot:
                altaz_samples = []
                for t_s in t_samples:
                    pos = (sat_obj - observer).at(t_s).altaz()
                    altaz_samples.append((pos[0], pos[1]))
                save_sky_plot(p['name'], utc_dt, altaz_samples,
                              culmination_data=(p['peak_alt'], p['peak_az']),
                              min_elevation=min_elevation,
                              min_azimuth=min_azimuth, max_azimuth=max_azimuth,
                              pass_index=idx,
                              duration_data=total_sec)
                step_times = [utc_dt + timedelta(seconds=i) for i in range(0, duration_sec + 1)]
                pass_profiles.append((idx, p['name'], step_times,
                                      [s[0].degrees for s in altaz_samples],
                                      [s[1].degrees for s in altaz_samples]))

            if args.map:
                save_ground_track(p['name'], utc_dt, t_samples, sat_obj,
                                  args.lat, args.lon,
                                  culmination_data=(p['peak_alt'], p['peak_az']),
                                  pass_index=idx)

    if args.plot:
        import os
        os.makedirs("plots", exist_ok=True)
        labels = [str(i) for i in range(1, len(all_passes) + 1)]
        durations = [(p['set'].utc_datetime() - p['rise'].utc_datetime()).total_seconds() for p in all_passes]
        colors = plt.cm.tab10(np.linspace(0, 1, len(set(p['name'] for p in all_passes))))
        name_color = {n: colors[i] for i, n in enumerate(sorted(set(p['name'] for p in all_passes)))}

        fig, ax = plt.subplots(figsize=(max(8, len(all_passes) * 0.6 + 2), 5))
        bar_colors = [name_color[p['name']] for p in all_passes]
        bars = ax.bar(labels, [d / 60 for d in durations], color=bar_colors, edgecolor='white', linewidth=0.5)
        for bar, d in zip(bars, durations):
            m, s = divmod(int(d), 60)
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    f"{m}m{s:02d}s", ha='center', va='bottom', fontsize=8)
        ax.set_xlabel("Pass #")
        ax.set_ylabel("Duration (minutes)")
        ax.set_title("Pass Duration Summary")
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=name_color[n], label=n) for n in sorted(name_color)]
        ax.legend(handles=legend_elements, loc='upper right')
        ax.yaxis.grid(True, linestyle='--', alpha=0.5)
        ax.set_axisbelow(True)
        plt.tight_layout()
        plt.savefig(os.path.join("plots", "pass_durations.png"))
        plt.close(fig)
        print(f"{GREEN}Duration summary plot saved to plots/pass_durations.png{RESET}")

        import matplotlib.dates as mdates

        # --- Elevation Timeline ---
        if pass_profiles:
            import datetime as _dt
            fig, ax = plt.subplots(figsize=(max(12, len(all_passes) * 0.8 + 4), 5))
            for pidx, pname, ptimes, pelevs, _ in pass_profiles:
                local_times = [t.replace(tzinfo=timezone.utc).astimezone(local_tz).replace(tzinfo=None) for t in ptimes]
                ax.plot(local_times, pelevs, color=name_color[pname], alpha=0.75, lw=1.5)
                peak_i = int(np.argmax(pelevs))
                ax.annotate(f"#{pidx}", xy=(local_times[peak_i], pelevs[peak_i]),
                            xytext=(0, 4), textcoords='offset points',
                            ha='center', fontsize=7, color=name_color[pname])
            ax.axhline(min_elevation, color='gray', linestyle='--', lw=1)
            # Build local-time bounds
            all_local = [t.replace(tzinfo=timezone.utc).astimezone(local_tz).replace(tzinfo=None)
                         for _, _, ptimes, _, _ in pass_profiles for t in ptimes]
            t_min, t_max = min(all_local), max(all_local)
            # 3-hour dashed reference lines
            tick = _dt.datetime(t_min.year, t_min.month, t_min.day)
            while tick < t_max:
                if tick.hour % 3 == 0 and tick.hour != 0:
                    ax.axvline(tick, color='gray', linestyle=(0, (4, 6)), linewidth=0.5, alpha=0.4, zorder=1)
                tick += _dt.timedelta(hours=3)
            # Midnight solid lines
            day = _dt.datetime(t_min.year, t_min.month, t_min.day)
            while day < t_max:
                ax.axvline(day, color='gray', linestyle='-', linewidth=1.8, alpha=0.75, zorder=2)
                day += _dt.timedelta(days=1)
            # X-axis ticks aligned to 3-hour grid
            if args.days <= 2:
                tick_hours = 3
            elif args.days <= 5:
                tick_hours = 6
            elif args.days <= 14:
                tick_hours = 12
            else:
                tick_hours = 24
            x_start = _dt.datetime(t_min.year, t_min.month, t_min.day)
            x_end   = _dt.datetime(t_max.year, t_max.month, t_max.day) + _dt.timedelta(days=1)
            ax.set_xlim(x_start, x_end)
            ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, tick_hours)))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')
            ax.set_xlabel(f"Local Time ({tz_label})")
            ax.set_ylabel("Elevation (deg)")
            ax.set_title("Elevation Timeline -- All Passes")
            el_legend = [Patch(facecolor=name_color[n], label=n) for n in sorted(name_color)]
            el_legend.append(plt.Line2D([0], [0], color='gray', linestyle='--', label=f"Min el. ({min_elevation:.0f}deg)"))
            ax.legend(handles=el_legend, loc='upper right')
            ax.yaxis.grid(True, linestyle='--', alpha=0.4)
            ax.set_axisbelow(True)
            plt.tight_layout()
            plt.savefig(os.path.join("plots", "elevation_timeline.png"))
            plt.close(fig)
            print(f"{GREEN}Elevation timeline saved to plots/elevation_timeline.png{RESET}")

        # --- Peak Azimuth & Elevation Summary ---
        fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(7, 7))
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 90)
        ax.set_yticks([0, 30, 60, 90])
        ax.set_yticklabels(['Zenith', '60deg', '30deg', 'Horizon'])

        # FOV shading -- same logic as individual sky plots
        if min_azimuth <= max_azimuth:
            theta_fov = np.linspace(np.radians(min_azimuth), np.radians(max_azimuth), 200)
        else:
            theta_fov = np.concatenate([
                np.linspace(np.radians(min_azimuth), np.radians(360), 100),
                np.linspace(np.radians(0), np.radians(max_azimuth), 100),
            ])
        ax.fill_between(theta_fov, 0, 90, color='yellow', alpha=0.15, label="Field of view")

        # Min elevation ring
        r_min = 90 - min_elevation
        ax.plot(np.linspace(0, 2 * np.pi, 360), np.full(360, r_min),
                '--', color='gray', lw=1)

        # One scatter point per pass
        for idx, p in enumerate(all_passes, start=1):
            theta = np.radians(p['peak_az'])
            r = 90 - p['peak_alt']
            color = name_color[p['name']]
            ax.scatter(theta, r, color=color, s=80, zorder=5)
            ax.annotate(f"#{idx}", xy=(theta, r), xytext=(4, 4),
                        textcoords='offset points', fontsize=7, color=color)

        ax.set_title("Peak Azimuth & Elevation -- All Passes", pad=14)
        peak_legend = [Patch(facecolor=name_color[n], label=n) for n in sorted(name_color)]
        peak_legend.append(plt.Line2D([0], [0], color='gray', linestyle='--',
                                      label=f"Min el. ({min_elevation:.0f}deg)"))
        ax.legend(handles=peak_legend, loc='upper right', bbox_to_anchor=(1.15, 1.1))
        plt.tight_layout()
        plt.savefig(os.path.join("plots", "peak_azimuths.png"))
        plt.close(fig)
        print(f"{GREEN}Peak azimuth plot saved to plots/peak_azimuths.png{RESET}")

        # --- All Paths Sky Plot ---
        if pass_profiles:
            fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(8, 8))
            ax.set_theta_zero_location('N')
            ax.set_theta_direction(-1)
            ax.set_ylim(0, 90)
            ax.set_yticks(range(0, 91, 30))
            ax.set_yticklabels(['90deg', '60deg', '30deg', 'Horizon'])

            # FOV shading
            if min_azimuth <= max_azimuth:
                theta_fov = np.linspace(np.radians(min_azimuth), np.radians(max_azimuth), 200)
            else:
                theta_fov = np.concatenate([
                    np.linspace(np.radians(min_azimuth), np.radians(360), 100),
                    np.linspace(np.radians(0), np.radians(max_azimuth), 100),
                ])
            ax.fill_between(theta_fov, 0, 90, color='yellow', alpha=0.15, label="Field of view")

            # Min elevation ring
            ax.plot(np.linspace(0, 2 * np.pi, 360), np.full(360, 90 - min_elevation),
                    '--', color='gray', lw=1)

            for pidx, pname, _, pelevs, pazims in pass_profiles:
                theta = np.radians(pazims)
                r = 90 - np.array(pelevs)
                color = name_color[pname]
                ax.plot(theta, r, color=color, lw=1.5, alpha=0.7)
                ax.scatter(theta[0],  r[0],  color='green', s=40, zorder=5)
                ax.scatter(theta[-1], r[-1], color='red',   s=40, zorder=5)
                peak_i = int(np.argmax(pelevs))
                ax.scatter(theta[peak_i], r[peak_i], color=color, marker='*', s=100, zorder=6)
                ax.annotate(f"#{pidx}", xy=(theta[peak_i], r[peak_i]),
                            xytext=(4, 4), textcoords='offset points', fontsize=7, color=color)

            ax.set_title("All Pass Trajectories -- Sky View", pad=14)
            paths_legend = [Patch(facecolor=name_color[n], label=n) for n in sorted(name_color)]
            paths_legend += [
                plt.Line2D([0], [0], color='gray', linestyle='--', label=f"Min el. ({min_elevation:.0f}deg)"),
                plt.scatter([], [], color='green', s=40, label="Rise"),
                plt.scatter([], [], color='red',   s=40, label="Set"),
            ]
            ax.legend(handles=paths_legend, loc='upper right', bbox_to_anchor=(1.15, 1.1))
            plt.tight_layout()
            plt.savefig(os.path.join("plots", "all_paths.png"))
            plt.close(fig)
            print(f"{GREEN}All-paths sky plot saved to plots/all_paths.png{RESET}")

        # --- Pass Distribution Timeline ---
        fig, ax = plt.subplots(figsize=(max(12, args.days * 4 + 4),
                                        max(3, len(set(p['name'] for p in all_passes)) * 1.2 + 1.5)))
        sat_names = sorted(set(p['name'] for p in all_passes))
        y_pos = {name: i for i, name in enumerate(sat_names)}

        for p in all_passes:
            rise_dt = p['rise'].utc_datetime().replace(tzinfo=timezone.utc).astimezone(local_tz).replace(tzinfo=None)
            set_dt  = p['set'].utc_datetime().replace(tzinfo=timezone.utc).astimezone(local_tz).replace(tzinfo=None)
            peak_dt = rise_dt + (set_dt - rise_dt) / 2
            y       = y_pos[p['name']]
            color   = name_color[p['name']]
            ax.plot([rise_dt, set_dt], [y, y], color=color, lw=8, alpha=0.3, solid_capstyle='round')
            ax.scatter(peak_dt, y, color=color, s=80, zorder=5)
            ax.annotate(f"{p['peak_alt']:.0f}deg", xy=(peak_dt, y),
                        xytext=(0, 8), textcoords='offset points',
                        ha='center', fontsize=7, color=color)

        # Midnight vertical lines + 3-hour tick lines
        all_times = [p['rise'].utc_datetime().replace(tzinfo=timezone.utc).astimezone(local_tz).replace(tzinfo=None) for p in all_passes] + \
                    [p['set'].utc_datetime().replace(tzinfo=timezone.utc).astimezone(local_tz).replace(tzinfo=None)  for p in all_passes]
        t_min, t_max = min(all_times), max(all_times)
        import datetime as _dt
        # 3-hour reference lines (thin dashed)
        tick = _dt.datetime(t_min.year, t_min.month, t_min.day)
        while tick < t_max:
            if tick.hour % 3 == 0 and tick.hour != 0:
                ax.axvline(tick, color='gray', linestyle=(0, (4, 6)), linewidth=0.5, alpha=0.4, zorder=1)
            tick += _dt.timedelta(hours=3)
        # Midnight lines (bold, solid)
        day = _dt.datetime(t_min.year, t_min.month, t_min.day)
        while day < t_max:
            ax.axvline(day, color='gray', linestyle='-', linewidth=1.8, alpha=0.75, zorder=2)
            day += _dt.timedelta(days=1)

        ax.set_yticks(range(len(sat_names)))
        ax.set_yticklabels(sat_names)

        # Align x-axis ticks with the 3-hour reference lines; scale interval with day range
        if args.days <= 2:
            tick_hours = 3
        elif args.days <= 5:
            tick_hours = 6
        elif args.days <= 14:
            tick_hours = 12
        else:
            tick_hours = 24
        x_start = _dt.datetime(t_min.year, t_min.month, t_min.day)
        x_end   = _dt.datetime(t_max.year, t_max.month, t_max.day) + _dt.timedelta(days=1)
        ax.set_xlim(x_start, x_end)
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, tick_hours)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')
        ax.set_xlabel(f"Local Time ({tz_label})")
        ax.set_title("Pass Distribution Timeline")
        ax.xaxis.grid(True, linestyle='--', alpha=0.4)
        ax.set_axisbelow(True)
        plt.tight_layout()
        plt.savefig(os.path.join("plots", "pass_timeline.png"))
        plt.close(fig)
        print(f"{GREEN}Pass timeline saved to plots/pass_timeline.png{RESET}")

    print(f"\n{GREEN}Report complete.{RESET}")

if __name__ == "__main__":
    main()
