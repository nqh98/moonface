"""Binance Vision futures *metrics* archive: 5-minute open-interest and
positioning-ratio snapshots, free and unauthenticated, from 2020-09-01.

The live REST endpoints retain only ~30 days of open-interest history; this
daily-zip archive is the only free deep-history source, which is what makes
the positioning hypothesis family OOS-testable at all.

Also the canonical home for the basis and funding series adapters.
"""
from __future__ import annotations

import ccxt
import csv
import datetime as dt
import io
import os
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from moonface.core.models import Candle

# ---------------------------------------------------------------------------
# basis
# ---------------------------------------------------------------------------


def align_basis(perp: list[Candle], spot: list[Candle]) -> list[float | None]:
    """As-of join (no lookahead): each perp bar gets the spot-perp basis
    ``(perp_close - spot_close) / spot_close`` using the most-recent spot
    close whose timestamp is ``<=`` the perp bar's open time.

    Bars before the first spot point are ``None``.
    Both inputs must be timestamp-sorted (the data layer guarantees this).
    """
    aligned: list[float | None] = []
    j = 0
    n = len(spot)
    current: float | None = None
    for c in perp:
        while j < n and spot[j].timestamp_ms <= c.timestamp_ms:
            current = spot[j].close
            j += 1
        if current is None:
            aligned.append(None)
        else:
            aligned.append((c.close - current) / current)
    return aligned


# ---------------------------------------------------------------------------
# funding
# ---------------------------------------------------------------------------

_FUNDING_INTERVAL_MS = 8 * 3_600_000  # canonical 8h funding cadence


@dataclass
class FundingCache:
    """CSV cache of perp funding rates, one file per funding symbol: rows `ts_ms,rate`."""

    directory: str

    def path(self, symbol: str) -> str:
        safe = symbol.replace("/", "_").replace(":", "_")
        return os.path.join(self.directory, f"funding_{safe}.csv")

    def load(self, symbol: str) -> list[tuple[int, float]] | None:
        path = self.path(symbol)
        if not os.path.exists(path):
            return None
        rows: list[tuple[int, float]] = []
        with open(path, newline="") as handle:
            for row in csv.reader(handle):
                rows.append((int(row[0]), float(row[1])))
        return rows

    def save(self, symbol: str, points: list[tuple[int, float]]) -> None:
        os.makedirs(self.directory, exist_ok=True)
        with open(self.path(symbol), "w", newline="") as handle:
            writer = csv.writer(handle)
            for ts, rate in points:
                writer.writerow([ts, rate])


def fetch_funding_history(
    exchange_name: str,
    funding_symbol: str,
    start_ms: int,
    end_ms: int,
    cache: FundingCache | None = None,
    page_limit: int = 1000,
) -> list[tuple[int, float]]:
    """Ordered (timestamp_ms, funding_rate) pairs in [start_ms, end_ms). Cache-first;
    otherwise pages ccxt fetchFundingRateHistory off the futures market."""
    if cache is not None:
        cached = cache.load(funding_symbol)
        if cached:
            head_start = cached[-1][0] + 1
            if head_start <= end_ms - _FUNDING_INTERVAL_MS:
                fresh = fetch_funding_history(exchange_name, funding_symbol,
                                              head_start, end_ms, cache=None,
                                              page_limit=page_limit)
                fresh = [p for p in fresh if p[0] > cached[-1][0]]
                if fresh:
                    cached = cached + fresh
                    cache.save(funding_symbol, cached)
            if start_ms <= cached[0][0] - _FUNDING_INTERVAL_MS:
                older = fetch_funding_history(exchange_name, funding_symbol,
                                              start_ms, cached[0][0], cache=None,
                                              page_limit=page_limit)
                older = [p for p in older if p[0] < cached[0][0]]
                if older:
                    cached = older + cached
                    cache.save(funding_symbol, cached)
            return [(ts, r) for ts, r in cached if start_ms <= ts < end_ms]
    exchange = getattr(ccxt, exchange_name)(
        {"enableRateLimit": True, "options": {"defaultType": "future"}})
    points: list[tuple[int, float]] = []
    since = start_ms
    while since < end_ms:
        rows = exchange.fetch_funding_rate_history(
            funding_symbol, since=since, limit=page_limit)
        if not rows:
            break
        for row in rows:
            ts = int(row["timestamp"])
            if ts >= end_ms:
                break
            points.append((ts, float(row["fundingRate"])))
        last = int(rows[-1]["timestamp"])
        if last <= since:
            break
        since = last + 1
    points.sort(key=lambda p: p[0])
    deduped: list[tuple[int, float]] = []
    seen: set[int] = set()
    for ts, rate in points:
        if ts not in seen:
            seen.add(ts)
            deduped.append((ts, rate))
    if cache is not None:
        cache.save(funding_symbol, deduped)
    return deduped


def align_funding(
    candles: list[Candle], points: list[tuple[int, float]]
) -> list[float | None]:
    """As-of join (no lookahead): each candle gets the most-recent funding rate whose
    timestamp is <= the candle's open time. Bars before the first point are None.
    Both inputs must be timestamp-sorted (the data layer guarantees this)."""
    aligned: list[float | None] = []
    j = 0
    n = len(points)
    current: float | None = None
    for c in candles:
        while j < n and points[j][0] <= c.timestamp_ms:
            current = points[j][1]
            j += 1
        aligned.append(current)
    return aligned


# ---------------------------------------------------------------------------
# metrics_data
# ---------------------------------------------------------------------------

METRICS_FIELDS = {
    "sum_open_interest",
    "sum_open_interest_value",
    "count_toptrader_long_short_ratio",
    "sum_toptrader_long_short_ratio",
    "count_long_short_ratio",
    "sum_taker_long_short_vol_ratio",
}

_DAY_MS = 86_400_000
_FLUSH_EVERY_DAYS = 100   # persist partial backfills; ~1100 days on first run
_URL = ("https://data.binance.vision/data/futures/um/daily/metrics/"
        "{symbol}/{symbol}-metrics-{date}.zip")

Row = tuple[int, dict[str, float]]


def parse_metrics_csv(text: str) -> list[Row]:
    """(utc_ms, {field: value}) per snapshot row. create_time is naive UTC.
    The archive has rows with empty fields (early files lack some ratios);
    those fields are simply omitted from the row — the as-of join carries the
    previous value, and the loader's coverage gate catches systemic holes."""
    out: list[Row] = []
    for rec in csv.DictReader(io.StringIO(text)):
        try:
            t = dt.datetime.strptime(rec["create_time"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, TypeError, ValueError):
            continue
        ts = int(t.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        fields: dict[str, float] = {}
        for f in METRICS_FIELDS:
            value = rec.get(f)
            if value is None or value == "":
                continue
            try:
                fields[f] = float(value)
            except ValueError:
                continue
        out.append((ts, fields))
    return out


def align_metric(candles: list[Candle],
                 points: list[tuple[int, float]]) -> list[float | None]:
    """As-of join (no lookahead), mirroring align_funding: each candle gets
    the most recent snapshot whose timestamp is <= the candle's open time.
    Bars before the first snapshot are None. Inputs must be sorted."""
    aligned: list[float | None] = []
    j = 0
    n = len(points)
    current: float | None = None
    for c in candles:
        while j < n and points[j][0] <= c.timestamp_ms:
            current = points[j][1]
            j += 1
        aligned.append(current)
    return aligned


def _download_day(symbol: str, day_ms: int) -> str | None:
    """CSV text for one archive day, or None when the archive has no file
    (recent days lag ~24h; S3 answers 403/404 for missing keys)."""
    date = dt.datetime.fromtimestamp(day_ms / 1000,
                                     dt.timezone.utc).strftime("%Y-%m-%d")
    url = _URL.format(symbol=symbol, date=date)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            return None
        raise
    zf = zipfile.ZipFile(io.BytesIO(payload))
    return zf.read(zf.namelist()[0]).decode("utf-8")


def _cache_path(cache_dir: str, symbol: str) -> Path:
    return Path(cache_dir) / f"metrics_{symbol}.csv"


_CACHE_COLUMNS = ["ts_ms"] + sorted(METRICS_FIELDS)


def _read_cache(path: Path) -> list[Row]:
    if not path.exists():
        return []
    out: list[Row] = []
    for rec in csv.DictReader(path.read_text().splitlines()):
        out.append((int(rec["ts_ms"]),
                    {f: float(rec[f]) for f in METRICS_FIELDS
                     if rec.get(f, "") != ""}))
    return out


def _write_cache(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_CACHE_COLUMNS)
        for ts, fields in rows:
            w.writerow([ts] + [fields.get(f, "") for f in _CACHE_COLUMNS[1:]])


def fetch_metrics_history(symbol: str, start_ms: int, end_ms: int,
                          cache_dir: str) -> list[Row]:
    """All snapshots for the UTC days containing [start_ms, end_ms], cached
    permanently per day. Days absent from the archive (recent lag, rare gaps)
    are skipped — the bundle loader's coverage gate decides whether the
    resulting gaps are fatal."""
    path = _cache_path(cache_dir, symbol)
    rows = _read_cache(path)
    have_days = {ts // _DAY_MS for ts, _ in rows}
    fresh: list[Row] = []
    downloaded = 0
    for day in range(start_ms // _DAY_MS, end_ms // _DAY_MS + 1):
        if day in have_days:
            continue
        try:
            text = _download_day(symbol, day * _DAY_MS)
        except Exception:
            if fresh:  # don't lose a partial backfill to one bad request
                rows = sorted(rows + fresh)
                _write_cache(path, rows)
            raise
        downloaded += 1
        if text is not None:
            fresh.extend(parse_metrics_csv(text))
        if fresh and downloaded % _FLUSH_EVERY_DAYS == 0:
            rows = sorted(rows + fresh)
            _write_cache(path, rows)
            fresh = []
    if fresh:
        rows = sorted(rows + fresh)
        _write_cache(path, rows)
    last_day_end = (end_ms // _DAY_MS + 1) * _DAY_MS
    return [r for r in rows if start_ms <= r[0] < last_day_end]
