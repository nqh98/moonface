"""Survivorship-clean USDT-perp universe data, stdlib only.

Symbol discovery walks the Binance Vision S3 listing (every symbol that ever
had a UM klines archive, including delisted ones — ccxt's load_markets only
sees live symbols, which is survivorship bias). Daily klines and funding come
from the unauthenticated fapi REST endpoints, which serve delisted symbols'
history too and include quote volume, which the OHLCV cache lacks."""
from __future__ import annotations

import csv
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from moonface.data.http import retrying

_DAY_MS = 86_400_000
_LISTING_URL = ("https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
                "?delimiter=/&prefix=data/futures/um/monthly/klines/")
_KLINES_URL = ("https://fapi.binance.com/fapi/v1/klines?symbol={symbol}"
               "&interval=1d&startTime={start}&endTime={end}&limit=1500")
_FUNDING_URL = ("https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}"
                "&startTime={start}&endTime={end}&limit=1000")

# Perpetual USDT contracts only: an underscore marks a dated future
# (BTCUSDT_230929). The rule is purely syntactic — index products like
# BTCDOMUSDT pass and are harmless, the volume ranking decides relevance.
_PERP_RE = re.compile(r"^[A-Z0-9]+USDT$")


@dataclass(frozen=True)
class DailyRow:
    ts_ms: int          # candle open time (UTC midnight)
    close: float
    quote_volume: float


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_symbol_listing(xml_text: str) -> tuple[list[str], bool, str | None]:
    """(perp symbols, is_truncated, next_marker) from one S3 listing page."""
    root = ET.fromstring(xml_text)
    symbols: list[str] = []
    truncated = False
    marker: str | None = None
    for el in root.iter():
        name = _localname(el.tag)
        if name == "IsTruncated":
            truncated = (el.text or "").strip().lower() == "true"
        elif name == "NextMarker":
            marker = (el.text or "").strip() or None
        elif name == "Prefix" and _localname(root.tag) != "Prefix":
            sym = (el.text or "").rstrip("/").rsplit("/", 1)[-1]
            if _PERP_RE.match(sym):
                symbols.append(sym)
    return symbols, truncated, marker


def parse_klines_payload(payload: list[list]) -> list[DailyRow]:
    """fapi klines arrays -> DailyRows (open time, close, quote volume)."""
    return [DailyRow(ts_ms=int(k[0]), close=float(k[4]),
                     quote_volume=float(k[7])) for k in payload]


def _get_text_once(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


_get_text = retrying(_get_text_once)


def list_um_perp_symbols(get_text=_get_text) -> list[str]:
    """Every USDT perp that ever had a Vision klines archive, sorted."""
    symbols: list[str] = []
    url = _LISTING_URL
    while True:
        page, truncated, marker = parse_symbol_listing(get_text(url))
        symbols.extend(page)
        if not truncated or marker is None:
            break
        url = _LISTING_URL + f"&marker={marker}"
    return sorted(set(symbols))


def _daily_cache_path(cache_dir: str, symbol: str) -> Path:
    return Path(cache_dir) / f"uni1d_{symbol}.csv"


def save_daily_cache(cache_dir: str, symbol: str, rows: list[DailyRow]) -> None:
    path = _daily_cache_path(cache_dir, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        for r in rows:
            w.writerow([r.ts_ms, r.close, r.quote_volume])


def load_daily_cache(cache_dir: str, symbol: str) -> list[DailyRow] | None:
    path = _daily_cache_path(cache_dir, symbol)
    if not path.exists():
        return None
    with open(path, newline="") as fh:
        return [DailyRow(int(t), float(c), float(q))
                for t, c, q in csv.reader(fh)]


def _get_json(url: str) -> list | dict:
    """fapi answers errors (invalid/delisted symbol) as HTTP 4xx with a JSON
    body like {"code": -1121}; surface that object so the fetchers can treat
    it as 'no data' instead of crashing the whole universe download."""
    try:
        return json.loads(_get_text(url))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            raise exc from None
    except (urllib.error.URLError, OSError, TimeoutError):
        return []


# ---------------------------------------------------------------------------
# cache coverage sidecar
#
# The whole-window kline caches store only data rows, so a cache hit could not
# tell "this window was fully fetched" from "the fetch happened to stop here".
# A request wider than what was cached silently returned the truncation. Each
# cache file now carries a `<file>.cov` sidecar recording the widest
# [start_ms, end_ms) actually requested; on a hit we fetch only the missing
# older/newer delta and widen the record — even when a delta comes back empty
# (pre-listing / delisted / not-yet-closed), so it is never re-requested.
# ---------------------------------------------------------------------------


def _cov_path(data_path) -> Path:
    return Path(f"{data_path}.cov")


def _read_cov(data_path) -> tuple[int, int] | None:
    path = _cov_path(data_path)
    if not path.exists():
        return None
    try:
        start_s, end_s = path.read_text().strip().split(",")
        return int(start_s), int(end_s)
    except (ValueError, OSError):
        return None


def _write_cov(data_path, start_ms: int, end_ms: int) -> None:
    path = _cov_path(data_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{start_ms},{end_ms}")


def _backfill_cached(cached, cov, start_ms, end_ms, step, ts_of, download):
    """Extend `cached` to cover [start_ms, end_ms) using `download(lo, hi)` for
    any missing older/newer range. Returns (rows, changed, cov_start, cov_end).
    A legacy cache (cov is None) infers its covered window from the data
    extent, so pre-existing caches self-heal on the first wider request."""
    if cov is None:
        if cached:
            cov_start, cov_end = ts_of(cached[0]), ts_of(cached[-1]) + step
        else:
            cov_start, cov_end = start_ms, end_ms
    else:
        cov_start, cov_end = cov
    rows = list(cached)
    changed = False
    if start_ms < cov_start:
        older = download(start_ms, cov_start)
        if older:
            rows = older + rows
            changed = True
    if end_ms > cov_end:
        newer = download(cov_end, end_ms)
        if newer:
            rows = rows + newer
            changed = True
    if changed:
        seen: set[int] = set()
        deduped = []
        for row in sorted(rows, key=ts_of):
            ts = ts_of(row)
            if ts not in seen:
                seen.add(ts)
                deduped.append(row)
        rows = deduped
    return rows, changed, min(cov_start, start_ms), max(cov_end, end_ms)


def _download_daily_range(symbol, start_ms, end_ms, get_json) -> list[DailyRow]:
    rows: list[DailyRow] = []
    cursor = start_ms
    while cursor < end_ms:
        payload = get_json(_KLINES_URL.format(symbol=symbol, start=cursor,
                                              end=end_ms - 1))
        if not isinstance(payload, list) or not payload:
            break  # error object ({"code": ...}) or no data: treat as empty
        page = parse_klines_payload(payload)
        rows.extend(r for r in page if r.ts_ms < end_ms)
        if len(payload) < 1500:
            break
        cursor = page[-1].ts_ms + _DAY_MS
    return rows


def fetch_daily_klines(symbol: str, start_ms: int, end_ms: int,
                       cache_dir: str, get_json=_get_json) -> list[DailyRow]:
    """Daily rows in [start_ms, end_ms), cached per symbol. A cache hit whose
    window does not cover the request backfills the missing older/newer range
    (see the coverage-sidecar note above); symbols listed after start_ms
    simply return less, and that gap is recorded so it is not re-requested."""
    data_path = _daily_cache_path(cache_dir, symbol)
    cached = load_daily_cache(cache_dir, symbol)
    if cached is None:
        rows = _download_daily_range(symbol, start_ms, end_ms, get_json)
        save_daily_cache(cache_dir, symbol, rows)
        _write_cov(data_path, start_ms, end_ms)
        return [r for r in rows if start_ms <= r.ts_ms < end_ms]
    cov = _read_cov(data_path)
    rows, changed, cov_start, cov_end = _backfill_cached(
        cached, cov, start_ms, end_ms, _DAY_MS, lambda r: r.ts_ms,
        lambda lo, hi: _download_daily_range(symbol, lo, hi, get_json))
    if changed:
        save_daily_cache(cache_dir, symbol, rows)
    if cov != (cov_start, cov_end):
        _write_cov(data_path, cov_start, cov_end)
    return [r for r in rows if start_ms <= r.ts_ms < end_ms]


_INTERVAL_MS = {"1d": _DAY_MS, "4h": 4 * 3_600_000, "2h": 2 * 3_600_000,
                "1h": 3_600_000, "30m": 30 * 60 * 1000, "15m": 15 * 60 * 1000}
_INTERVAL_URL = ("https://fapi.binance.com/fapi/v1/klines?symbol={symbol}"
                 "&interval={interval}&startTime={start}&endTime={end}"
                 "&limit=1500")


def _download_perp_range(symbol, interval, start_ms, end_ms, get_json):
    from moonface.core.models import Candle

    step = _INTERVAL_MS[interval]
    candles = []
    cursor = start_ms
    while cursor < end_ms:
        payload = get_json(_INTERVAL_URL.format(
            symbol=symbol, interval=interval, start=cursor, end=end_ms - 1))
        if not isinstance(payload, list) or not payload:
            break  # error object ({"code": ...}) or no data: treat as empty
        page = [Candle.from_ccxt([float(x) for x in k[:6]]) for k in payload]
        candles.extend(c for c in page if c.timestamp_ms < end_ms)
        if len(payload) < 1500:
            break
        cursor = int(page[-1].timestamp_ms) + step
    return candles


def fetch_perp_candles(symbol: str, interval: str, start_ms: int, end_ms: int,
                       cache_dir: str, get_json=_get_json):
    """Full Candle objects for any archive symbol (delisted included) via the
    fapi REST endpoint, cached in the standard OhlcvCache format. A cache hit
    whose window does not cover the request backfills the missing older/newer
    range (see the coverage-sidecar note above)."""
    from moonface.data.ohlcv import OhlcvCache

    cache = OhlcvCache(cache_dir)
    data_path = cache.path(symbol, interval)
    step = _INTERVAL_MS[interval]
    cached = cache.load(symbol, interval)
    if cached is None:
        candles = _download_perp_range(symbol, interval, start_ms, end_ms,
                                       get_json)
        cache.save(symbol, interval, candles)
        _write_cov(data_path, start_ms, end_ms)
        return [c for c in candles if start_ms <= c.timestamp_ms < end_ms]
    cov = _read_cov(data_path)
    candles, changed, cov_start, cov_end = _backfill_cached(
        cached, cov, start_ms, end_ms, step, lambda c: c.timestamp_ms,
        lambda lo, hi: _download_perp_range(symbol, interval, lo, hi, get_json))
    if changed:
        cache.save(symbol, interval, candles)
    if cov != (cov_start, cov_end):
        _write_cov(data_path, cov_start, cov_end)
    return [c for c in candles if start_ms <= c.timestamp_ms < end_ms]


def _funding_cache_path(cache_dir: str, symbol: str) -> Path:
    return Path(cache_dir) / f"unifunding_{symbol}.csv"


def fetch_funding_rates(symbol: str, start_ms: int, end_ms: int,
                        cache_dir: str,
                        get_json=_get_json) -> list[tuple[int, float]]:
    """(funding_time_ms, rate) pairs in [start_ms, end_ms), cached whole-window."""
    path = _funding_cache_path(cache_dir, symbol)
    if path.exists():
        with open(path, newline="") as fh:
            cached = [(int(t), float(r)) for t, r in csv.reader(fh)]
        return [(t, r) for t, r in cached if start_ms <= t < end_ms]
    points: list[tuple[int, float]] = []
    cursor = start_ms
    while cursor < end_ms:
        payload = get_json(_FUNDING_URL.format(symbol=symbol, start=cursor,
                                               end=end_ms - 1))
        if not isinstance(payload, list) or not payload:
            break  # error object ({"code": ...}) or no data: treat as empty
        for rec in payload:
            t = int(rec["fundingTime"])
            if t < end_ms:
                points.append((t, float(rec["fundingRate"])))
        last = int(payload[-1]["fundingTime"])
        if len(payload) < 1000 or last <= cursor:
            break
        cursor = last + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        for t, r in points:
            w.writerow([t, r])
    return points
