#!/usr/bin/env python3
# ==========================================================
# ogimet_sync.py — OGIMET SYNOP Data Synchronization
# For HyMetDash — Run via cron every 6 hours
# Cron: 0 */6 * * * cd /path/to/hymetdash && python ogimet_sync.py
# ==========================================================

import os
import re
import time
import math
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("ogimet_sync")

# ── Config ──
BASE_DIR = Path(__file__).parent
OGIMET_DIR = BASE_DIR / "data" / "ogimet_sync"
OGIMET_DIR.mkdir(parents=True, exist_ok=True)

COUNTRY_OGIMET = os.environ.get("OGIMET_COUNTRY", "Cote")
WINDOW_HOURS = int(os.environ.get("OGIMET_WINDOW_HOURS", "6"))
WIDEN_HOURS = int(os.environ.get("OGIMET_WIDEN_HOURS", "12"))
REQUEST_SLEEP = 0.5
TIMEOUT = 60
HEADERS = {"User-Agent": "HyMetDash-OGIMET-Sync/3.0 (SODEXAM)"}


@dataclass
class DecodedSynop:
    station_wmo: str
    dt_utc: datetime
    temp_c: float | None
    dewpoint_c: float | None
    rh_pct: float | None
    p_station_hpa: float | None
    p_msl_hpa: float | None
    wind_dir_deg: int | None
    wind_speed_ms: float | None
    rain_mm: float | None
    rain_period_h: int | None
    raw: str


# ── SYNOP Helpers ──
def _pressure_from_group(pppp):
    if not re.fullmatch(r"\d{4}", pppp):
        return None
    v = int(pppp)
    base = 10000 if v < 5000 else 9000
    return (base + v) / 10.0

def _temp_from_group(g):
    if not re.fullmatch(r"1[01]\d{3}", g):
        return None
    sn, ttt = int(g[1]), int(g[2:5])
    val = ttt / 10.0
    return -val if sn == 1 else val

def _dewpoint_from_group(g):
    if not re.fullmatch(r"2[01]\d{3}", g):
        return None
    sn, ttt = int(g[1]), int(g[2:5])
    val = ttt / 10.0
    return -val if sn == 1 else val

def _rh_from_t_td(t, td):
    if t is None or td is None:
        return None
    a, b = 17.62, 243.12
    es = 6.112 * math.exp((a * t) / (b + t))
    e = 6.112 * math.exp((a * td) / (b + td))
    return max(0.0, min(100.0, 100.0 * (e / es)))

def _wind_from_group(g, iw):
    if not re.fullmatch(r"\d{5}", g):
        return (None, None)
    dd, ff = int(g[1:3]), int(g[3:5])
    wdir = None if dd == 99 else dd * 10
    speed = float(ff)
    if iw in (3, 4):
        speed *= 0.514444
    return (wdir, speed)

def _rain_from_group(g):
    if not re.fullmatch(r"6\d{4}", g):
        return (None, None)
    rrr, tr = int(g[1:4]), int(g[4])
    rain = 0.0 if rrr == 990 else (float(rrr) if 0 <= rrr <= 989 else None)
    tr_map = {1: 6, 2: 12, 3: 18, 4: 24, 5: 1, 6: 2, 7: 3, 8: 9, 9: 15}
    return (rain, tr_map.get(tr))


# ── OGIMET Fetch & Parse ──
LINE_START_RE = re.compile(r"^\s*(\d{12})\s+(AAXX)\s+(.*)$")
STATION_RE = re.compile(r"\b(\d{5})\b")

def build_ogimet_url(dt_start, dt_end):
    s, e = dt_start, dt_end
    return (
        f"https://www.ogimet.com/display_synopsc2.php"
        f"?lang=en&estado={COUNTRY_OGIMET}&tipo=ALL&ord=REV&nil=SI&fmt=txt"
        f"&ano={s:%Y}&mes={s:%m}&day={s:%d}&hora={s:%H}"
        f"&anof={e:%Y}&mesf={e:%m}&dayf={e:%d}&horaf={e:%H}&send=send"
    )

def fetch_synops_txt(dt_start, dt_end):
    url = build_ogimet_url(dt_start, dt_end)
    log.info(f"Fetching OGIMET: {url[:120]}...")
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

def parse_ogimet_messages(txt):
    messages = []
    current_dt = None
    current_buf = []

    for raw_line in txt.splitlines():
        line = raw_line.rstrip()
        m = LINE_START_RE.match(line)
        if m:
            if current_buf and current_dt:
                full = " ".join(current_buf).strip()
                if "AAXX" in full:
                    parts = full.split()
                    stn = None
                    if len(parts) >= 3 and parts[0] == "AAXX" and re.fullmatch(r"\d{5}", parts[2]):
                        stn = parts[2]
                    else:
                        sm = STATION_RE.search(full)
                        stn = sm.group(1) if sm else None
                    if stn:
                        messages.append((stn, current_dt, full))
            current_buf = []
            ymdhm = m.group(1)
            current_dt = datetime.strptime(ymdhm, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            current_buf = [f"{m.group(2)} {m.group(3)}"]
        else:
            if current_buf and line.strip():
                current_buf.append(line.strip())

        if current_buf and line.strip().endswith("="):
            full = " ".join(current_buf).strip().replace("= ", "=")
            parts = full.split()
            stn = None
            if len(parts) >= 3 and parts[0] == "AAXX" and re.fullmatch(r"\d{5}", parts[2]):
                stn = parts[2]
            else:
                sm = STATION_RE.search(full)
                stn = sm.group(1) if sm else None
            if stn and current_dt:
                messages.append((stn, current_dt, full))
            current_dt = None
            current_buf = []

    return messages

def decode_message(station, dt_utc, raw):
    raw_clean = re.sub(r"\s+", " ", raw.replace("=", " ").strip())
    parts = raw_clean.split()

    try:
        i_aaxx = parts.index("AAXX")
    except ValueError:
        return DecodedSynop(station, dt_utc, None, None, None, None, None, None, None, None, None, raw)

    iw = 0
    idx = i_aaxx + 1
    if idx < len(parts) and re.fullmatch(r"\d{5}", parts[idx]):
        iw = int(parts[idx][4])
        idx += 1
    if idx < len(parts) and re.fullmatch(r"\d{5}", parts[idx]):
        idx += 1

    groups = parts[idx:]
    t = td = p_station = p_msl = None
    wdir = ws = rain = rain_h = None

    for g in groups:
        if g.startswith("1"):
            v = _temp_from_group(g)
            if v is not None: t = v
        elif g.startswith("2"):
            v = _dewpoint_from_group(g)
            if v is not None: td = v
        elif g.startswith("3") and re.fullmatch(r"3\d{4}", g):
            p_station = _pressure_from_group(g[1:])
        elif g.startswith("4") and re.fullmatch(r"4\d{4}", g):
            p_msl = _pressure_from_group(g[1:])
        elif g.startswith("6"):
            r, h = _rain_from_group(g)
            if r is not None: rain, rain_h = r, h

    for g in groups:
        if re.fullmatch(r"\d{5}", g):
            n, dd, ff = int(g[0]), int(g[1:3]), int(g[3:5])
            if (0 <= n <= 9) and (dd <= 36 or dd == 99) and (0 <= ff <= 99):
                wdir, ws = _wind_from_group(g, iw)
                break

    rh = _rh_from_t_td(t, td)
    return DecodedSynop(station, dt_utc, t, td, rh, p_station, p_msl, wdir, ws, rain, rain_h, raw)


def make_excel_safe(df):
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64tz_dtype(df[col]):
            df[col] = df[col].dt.tz_convert("UTC").dt.tz_localize(None)
    return df


def upsert_station_file(station, new_rows):
    out_path = OGIMET_DIR / f"OGIMET_{station}.xlsx"
    new_rows = new_rows.copy()
    new_rows["datetime_utc"] = pd.to_datetime(new_rows["datetime_utc"], utc=True, errors="coerce")
    new_rows = new_rows.dropna(subset=["datetime_utc"])
    if new_rows.empty:
        return

    if out_path.exists():
        old = pd.read_excel(out_path)
        if "datetime_utc" in old.columns:
            old["datetime_utc"] = pd.to_datetime(old["datetime_utc"], utc=True, errors="coerce")
        merged = pd.concat([old, new_rows], ignore_index=True, sort=False)
        merged = merged.dropna(subset=["datetime_utc"])
        merged = merged.drop_duplicates(subset=["datetime_utc"], keep="last")
        merged = merged.sort_values("datetime_utc")
    else:
        merged = new_rows.sort_values("datetime_utc")

    merged = make_excel_safe(merged)
    merged.to_excel(out_path, index=False, sheet_name="data")
    log.info(f"  -> {out_path.name}: {len(merged)} rows total")


def run_sync():
    now = datetime.now(timezone.utc)
    start_fetch = now - timedelta(hours=WIDEN_HOURS)
    start_keep = now - timedelta(hours=WINDOW_HOURS)

    try:
        txt = fetch_synops_txt(start_fetch, now)
    except Exception as e:
        log.error(f"OGIMET fetch failed: {e}")
        return

    msgs = parse_ogimet_messages(txt)
    if not msgs:
        log.warning("No AAXX messages found.")
        return

    msgs = [(s, dt, raw) for s, dt, raw in msgs if dt >= start_keep]
    if not msgs:
        log.warning("Messages found but none in target window.")
        return

    decoded = [decode_message(s, dt, raw) for s, dt, raw in msgs]
    df = pd.DataFrame([{
        "station_wmo": d.station_wmo, "datetime_utc": d.dt_utc,
        "temp_c": d.temp_c, "dewpoint_c": d.dewpoint_c, "rh_pct": d.rh_pct,
        "p_station_hpa": d.p_station_hpa, "p_msl_hpa": d.p_msl_hpa,
        "wind_dir_deg": d.wind_dir_deg, "wind_speed_ms": d.wind_speed_ms,
        "rain_mm": d.rain_mm, "rain_period_h": d.rain_period_h, "raw": d.raw
    } for d in decoded])

    df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime_utc"])

    log.info(f"Decoded {len(df)} observations from {df['station_wmo'].nunique()} stations")

    for station, sub in df.groupby("station_wmo"):
        upsert_station_file(station, sub)

    # Write sync timestamp
    ts_file = OGIMET_DIR / ".last_sync"
    ts_file.write_text(now.strftime("%Y-%m-%d %H:%M UTC"))

    log.info("Sync complete.")


if __name__ == "__main__":
    run_sync()
