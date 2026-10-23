from __future__ import annotations

import csv
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DVOL_URL = ("https://www.deribit.com/api/v2/public/get_volatility_index_data"
            "?currency={cur}&start_timestamp={start}&end_timestamp={end}&resolution={res}")


@dataclass(frozen=True)
class DvolPoint:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float


def parse_dvol_payload(payload: dict) -> list[DvolPoint]:
    rows = payload.get("result", {}).get("data", []) or []
    return [DvolPoint(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]))
            for r in rows]


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _cache_path(cache_dir: str, cur: str, res: int) -> Path:
    return Path(cache_dir) / f"dvol_{cur}_{res}.csv"


def fetch_dvol(currency: str, start_ms: int, end_ms: int, cache_dir: str,
               resolution: int = 43200, get_json=_get_json) -> list[DvolPoint]:
    """All DVOL bars in [start_ms, end_ms], ascending, cached permanently.

    Paginates BACKWARD on end_timestamp: the API returns the most RECENT
    ~1000 points inside the requested window, so paging forward from
    `start_ms` lands on the final page immediately and terminates having seen
    only the tail (SPEC vrp_measure section 2.1). `resolution` is in SECONDS;
    timestamps are in MILLISECONDS.
    """
    path = _cache_path(cache_dir, currency, resolution)
    if path.exists():
        with path.open(newline="") as fh:
            return [DvolPoint(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]))
                    for r in csv.reader(fh)]
    resolution_ms = resolution * 1000
    seen: dict[int, DvolPoint] = {}
    cursor = end_ms
    while cursor >= start_ms:
        page = parse_dvol_payload(get_json(
            DVOL_URL.format(cur=currency, start=start_ms, end=cursor, res=resolution)))
        if not page:
            break
        fresh = [p for p in page if p.ts_ms not in seen]
        for p in page:
            seen[p.ts_ms] = p
        if not fresh:  # page is entirely re-served data: no backward progress
            break
        cursor = min(p.ts_ms for p in page) - resolution_ms
    pts = [seen[k] for k in sorted(seen)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        for p in pts:
            w.writerow([p.ts_ms, p.open, p.high, p.low, p.close])
    return pts
