from tle_fetcher import fetch_tle

SATELLITES = {
    'SATELIOT_1': 60550,
    'SATELIOT_2': 60534,
    'SATELIOT_3': 60552,
    'SATELIOT_4': 60537,
}

for name, norad_id in SATELLITES.items():
    tle1, tle2 = fetch_tle(norad_id)
    print(f"{name}")
    print(tle1)
    print(tle2)
    print()
