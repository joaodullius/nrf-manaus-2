import os
import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning

warnings.simplefilter('ignore', InsecureRequestWarning)

try:
    from config import N2YO_API_KEY as _N2YO_API_KEY
except ImportError:
    _N2YO_API_KEY = os.environ.get("N2YO_API_KEY", "")


def fetch_tle(norad_id: int) -> tuple[str, str]:
    """Return (tle1, tle2) for a NORAD ID.

    Tries in order: CelesTrak -> N2YO (if key set) -> SatNOGS.
    """
    # 1. CelesTrak
    try:
        url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
        r = requests.get(url, timeout=10, verify=False)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            if len(lines) >= 3:
                return lines[1].strip(), lines[2].strip()
    except Exception:
        pass

    # 2. N2YO (requires N2YO_API_KEY env var)
    if _N2YO_API_KEY:
        try:
            print(f"[tle_fetcher] CelesTrak failed for NORAD {norad_id}, trying N2YO...")
            url = f"https://api.n2yo.com/rest/v1/satellite/tle/{norad_id}&apiKey={_N2YO_API_KEY}"
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            lines = [l.strip() for l in r.json()["tle"].splitlines() if l.strip()]
            if len(lines) >= 2:
                return lines[0], lines[1]
        except Exception as e:
            print(f"[tle_fetcher] N2YO failed for NORAD {norad_id}: {e}")
    else:
        print(f"[tle_fetcher] CelesTrak failed for NORAD {norad_id}, N2YO_API_KEY not set.")

    # 3. SatNOGS (no auth required)
    try:
        print(f"[tle_fetcher] Trying SatNOGS for NORAD {norad_id}...")
        url = f"https://db.satnogs.org/api/tle/?norad_cat_id={norad_id}&format=json"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data:
            entry = data[0]
            return entry["tle1"], entry["tle2"]
    except Exception as e:
        print(f"[tle_fetcher] SatNOGS failed for NORAD {norad_id}: {e}")

    raise RuntimeError(f"All TLE sources failed for NORAD {norad_id}")
