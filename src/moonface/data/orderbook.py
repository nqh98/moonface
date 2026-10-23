"""Binance Vision UM `bookDepth` archive: order-book depth snapshots every
~30s at fixed percentage bands, per symbol per day, history from 2023-01.

Only the ±1% band notional is retained (the pre-registered imbalance
feature); the cache stays ~100MB per symbol for a 2-year window. Mirrors
metrics_data: daily zips, permanent per-day cache, incremental flush so a
multi-hour backfill survives network failures, missing archive days skipped
(the study's freshness gate decides whether gaps are fatal)."""
from __future__ import annotations

import csv
import datetime as dt
import io
import zipfile
from pathlib import Path

from moonface.data.http import retrying

_DAY_MS = 86_400_000
_FLUSH_EVERY_DAYS = 50
_URL = ("https://data.binance.vision/data/futures/um/daily/bookDepth/"
        "{symbol}/{symbol}-bookDepth-{date}.zip")

Row = tuple[int, float, float]  # ts_ms, bid notional at -1%, ask at +1%


def parse_bookdepth_csv(text: str) -> list[Row]:
    """(ts_ms, bid_notional_1pct, ask_notional_1pct) per snapshot; snapshots
    missing either side of the ±1% band are dropped."""
    sides: dict[int, dict[str, float]] = {}
    order: list[int] = []
    for rec in csv.DictReader(io.StringIO(text)):
        try:
            pct = float(rec["percentage"])
            if pct not in (-1.0, 1.0):
                continue
            t = dt.datetime.strptime(rec["timestamp"], "%Y-%m-%d %H:%M:%S")
            ts = int(t.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            value = float(rec["notional"])
        except (KeyError, TypeError, ValueError):
            continue
        if ts not in sides:
            sides[ts] = {}
            order.append(ts)
        sides[ts]["bid" if pct < 0 else "ask"] = value
    return [(ts, sides[ts]["bid"], sides[ts]["ask"]) for ts in order
            if "bid" in sides[ts] and "ask" in sides[ts]]


def _get_bytes_once(url: str) -> bytes | None:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            return None  # S3 answers 403/404 for missing archive days
        raise


_get_bytes = retrying(_get_bytes_once)


def _cache_path(cache_dir: str, symbol: str) -> Path:
    return Path(cache_dir) / f"bookdepth_{symbol}.csv"


def _read_cache(path: Path) -> list[Row]:
    if not path.exists():
        return []
    with open(path, newline="") as fh:
        return [(int(t), float(b), float(a)) for t, b, a in csv.reader(fh)]


def _write_cache(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        for row in rows:
            w.writerow(row)


def fetch_bookdepth_history(symbol: str, start_ms: int, end_ms: int,
                            cache_dir: str, get_bytes=_get_bytes) -> list[Row]:
    """All ±1% snapshots for the UTC days containing [start_ms, end_ms),
    cached permanently per day with incremental flushes."""
    path = _cache_path(cache_dir, symbol)
    rows = _read_cache(path)
    have_days = {ts // _DAY_MS for ts, _b, _a in rows}
    fresh: list[Row] = []
    downloaded = 0
    for day in range((start_ms // _DAY_MS), (end_ms - 1) // _DAY_MS + 1):
        if day in have_days:
            continue
        date = dt.datetime.fromtimestamp(day * _DAY_MS / 1000,
                                         dt.timezone.utc).strftime("%Y-%m-%d")
        try:
            payload = get_bytes(_URL.format(symbol=symbol, date=date))
        except Exception:
            if fresh:  # don't lose a partial backfill to one bad request
                rows = sorted(rows + fresh)
                _write_cache(path, rows)
            raise
        downloaded += 1
        if payload is not None:
            zf = zipfile.ZipFile(io.BytesIO(payload))
            fresh.extend(parse_bookdepth_csv(
                zf.read(zf.namelist()[0]).decode("utf-8")))
        if fresh and downloaded % _FLUSH_EVERY_DAYS == 0:
            rows = sorted(rows + fresh)
            _write_cache(path, rows)
            fresh = []
    if fresh:
        rows = sorted(rows + fresh)
        _write_cache(path, rows)
    return [r for r in rows if start_ms <= r[0] < end_ms]
