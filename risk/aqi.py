"""India air quality index (CPCB style) from PM2.5 and PM10."""

import math

# Each row: (conc_low, conc_high, index_low, index_high), concentration in ug/m3.
# The official Severe band has no upper end, so it is extended by the width of
# the Very poor band and capped at 500.
PM25 = ((0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200), (91, 120, 201, 300),
        (121, 250, 301, 400), (251, 380, 401, 500))
PM10 = ((0, 50, 0, 50), (51, 100, 51, 100), (101, 250, 101, 200), (251, 350, 201, 300),
        (351, 430, 301, 400), (431, 510, 401, 500))

BANDS = ((50, "Good"), (100, "Satisfactory"), (200, "Moderate"), (300, "Poor"),
         (400, "Very poor"), (500, "Severe"))


def _half_up(x: float) -> int:
    return math.floor(x + 0.5)


def sub_index(conc: float | None, table) -> int | None:
    if conc is None:
        return None
    c = _half_up(conc)
    for lo, hi, ilo, ihi in table:
        if c <= hi:
            if c < lo:
                c = lo
            return _half_up(ilo + (ihi - ilo) * (c - lo) / (hi - lo))
    return 500


def india_aqi(pm2_5: float | None, pm10: float | None) -> int | None:
    # shortcut: AQI from PM2.5 and PM10 only (CPCB uses up to eight pollutants); add more pollutants if the screens ever claim the official index
    subs = [s for s in (sub_index(pm2_5, PM25), sub_index(pm10, PM10)) if s is not None]
    return max(subs) if subs else None


def band(aqi: int) -> str:
    for high, name in BANDS:
        if aqi <= high:
            return name
    return BANDS[-1][1]
