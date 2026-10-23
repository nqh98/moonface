"""Streaming Binance Vision futures aggTrades -> per-second side counts.

Data acquisition only — no features, no returns, no analysis. Each daily
archive zip is downloaded, reduced in one pass to one row per active second
(`ts_ms, symbol, buy_count, sell_count, last_price` — the v2 Rung-0 input
schema; volumes are deliberately dropped), appended to a cache CSV, and the
raw payload discarded, so working disk stays bounded. Resumable per day via a
companion `.days` ledger. Side convention (v1 feasibility memo):
is_buyer_maker False -> buy aggressor, True -> sell aggressor."""
from __future__ import annotations

import csv
import datetime as dt
import io
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

_DAY_MS = 86_400_000
_SECOND_MS = 1_000
_URL = ("https://data.binance.vision/data/futures/um/daily/aggTrades/"
        "{symbol}/{symbol}-aggTrades-{date}.zip")
_HEADER = "ts_ms,symbol,buy_count,sell_count,last_price"
_RECENT_LAG_DAYS = 3
_ATTEMPTS = 3

SecondRow = tuple[int, int, int, float]  # ts_ms, buy_count, sell_count, last_price


def _day_str(day_ms: int) -> str:
    return dt.datetime.fromtimestamp(day_ms / 1000,
                                     dt.timezone.utc).strftime("%Y-%m-%d")


def parse_aggtrades_day(text_stream: io.TextIOBase) -> list[SecondRow]:
    """One pass over a daily aggTrades CSV (header optional): per-second
    aggressor print counts per side and the last trade price. Rows arrive in
    aggregate-trade-id order, which is chronological."""
    seconds: dict[int, list] = {}
    reader = csv.reader(text_stream)
    for rec in reader:
        if not rec or not rec[0].strip().isdigit():
            continue  # header or blank
        ts = int(rec[5])
        price = float(rec[1])
        is_buyer_maker = rec[6].strip().lower() == "true"
        sec = (ts // _SECOND_MS) * _SECOND_MS
        slot = seconds.get(sec)
        if slot is None:
            slot = seconds[sec] = [0, 0, price]
        if is_buyer_maker:
            slot[1] += 1  # buyer was maker -> seller was the aggressor
        else:
            slot[0] += 1
        slot[2] = price
    return [(sec, s[0], s[1], s[2]) for sec, s in sorted(seconds.items())]


def _download_day(symbol: str, day_ms: int, *, timeout: int = 60) -> bytes | None:
    url = _URL.format(symbol=symbol, date=_day_str(day_ms))
    last_exc: Exception | None = None
    for attempt in range(_ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                return None
            last_exc = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
        time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"download failed for {url}: {last_exc}")


def _cache_path(cache_dir: str, symbol: str) -> Path:
    return Path(cache_dir) / f"aggsec_{symbol}.csv"


def _ledger_path(cache_dir: str, symbol: str) -> Path:
    return Path(cache_dir) / f"aggsec_{symbol}.days"


def fetch_aggsec_history(symbol: str, start_ms: int, end_ms: int,
                         cache_dir: str, *, download=_download_day,
                         now_ms: int | None = None) -> dict:
    """Resumable day walk over [start_ms, end_ms). Appends reduced rows in
    strict day order; a day missing from the archive is permanent-missing when
    old, and ends the walk when within the recent publication lag."""
    cache = _cache_path(cache_dir, symbol)
    ledger = _ledger_path(cache_dir, symbol)
    cache.parent.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    if ledger.exists():
        done = {line.split()[0] for line in ledger.read_text().splitlines() if line.strip()}
    if not cache.exists():
        cache.write_text(_HEADER + "\n")
    now = int(time.time() * 1000) if now_ms is None else now_ms
    first_day = (start_ms // _DAY_MS) * _DAY_MS
    fetched = 0
    missing = 0
    day_ms = first_day
    while day_ms < end_ms:
        day = _day_str(day_ms)
        if day in done:
            day_ms += _DAY_MS
            continue
        payload = download(symbol, day_ms)
        if payload is None:
            if now - day_ms < _RECENT_LAG_DAYS * _DAY_MS:
                break  # archive publication lag; retry on a later run
            missing += 1
            with ledger.open("a") as f:
                f.write(f"{day} missing\n")
            day_ms += _DAY_MS
            continue
        zf = zipfile.ZipFile(io.BytesIO(payload))
        with zf.open(zf.namelist()[0]) as member:
            rows = parse_aggtrades_day(io.TextIOWrapper(member, encoding="utf-8"))
        with cache.open("a") as f:
            for ts, buy, sell, price in rows:
                f.write(f"{ts},{symbol},{buy},{sell},{price}\n")
        with ledger.open("a") as f:
            f.write(f"{day}\n")
        fetched += 1
        print(f"  {symbol} {day}: {len(rows)} active seconds")
        day_ms += _DAY_MS
    return {"fetched_days": fetched, "missing_days": missing,
            "cache": str(cache)}


def export_window(symbol: str, start_ms: int, end_ms: int, cache_dir: str,
                  out_path: Path) -> int:
    """Slice the cache to the frozen window, streaming (no full load)."""
    cache = _cache_path(cache_dir, symbol)
    n = 0
    with cache.open() as src, out_path.open("w") as dst:
        dst.write(_HEADER + "\n")
        for line in src:
            if line.startswith("ts_ms"):
                continue
            ts = int(line.split(",", 1)[0])
            if start_ms <= ts < end_ms:
                dst.write(line)
                n += 1
    return n
