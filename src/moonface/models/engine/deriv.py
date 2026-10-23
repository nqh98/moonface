from __future__ import annotations

import json
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from moonface.research.universe_data import fetch_funding_rates

FUND_WINDOW_DAYS = 30
FUND_LOW = 10.0
FUND_HIGH = 90.0
FUND_CROWDED = 80.0
OI_FLUSH = -0.03
OI_WINDOW_H = 6

_DAY_MS = 86_400_000
_HOUR_MS = 3_600_000
_LEGACY_OI_FLUSH_Z = -1.5
_CACHE_DIR = str(Path(tempfile.gettempdir()) / "moonface_deriv")
_OI_URL = ("https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}"
           "&period=1h&limit=24&startTime={start}&endTime={end}")


@dataclass(frozen=True)
class DerivSnapshot:
    funding_pct: float | None = None
    oi_change_6h: float | None = None


def _get_json(url: str) -> list | dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_open_interest_points(symbol: str, start_ms: int,
                                end_ms: int) -> list[tuple[int, float]]:
    payload = _get_json(_OI_URL.format(symbol=symbol, start=start_ms, end=end_ms - 1))
    if not isinstance(payload, list):
        return []
    points: list[tuple[int, float]] = []
    for rec in payload:
        ts = rec.get("timestamp")
        raw = rec.get("sumOpenInterest")
        if ts is None or raw is None:
            continue
        points.append((int(ts), float(raw)))
    return sorted(points)


def _percentile_of_last(points: list[tuple[int, float]]) -> float | None:
    if not points:
        return None
    ordered = sorted(points)
    current = float(ordered[-1][1])
    rank = sum(1 for _, rate in ordered if float(rate) <= current)
    return 100.0 * rank / len(ordered)


def _oi_change_from_points(points: list[tuple[int, float]]) -> float | None:
    if len(points) < 2:
        return None
    ordered = sorted(points)
    current_ts, current_oi = ordered[-1]
    target_ts = current_ts - OI_WINDOW_H * _HOUR_MS
    past: tuple[int, float] | None = None
    for point in reversed(ordered[:-1]):
        if point[0] <= target_ts:
            past = point
            break
    if past is None or past[1] == 0:
        return None
    return current_oi / past[1] - 1.0


def _funding_pct_from_snapshot(snap: Any | None) -> float | None:
    if snap is None:
        return None
    pct = getattr(snap, "funding_pct", None)
    if pct is not None:
        return float(pct)
    rate = getattr(snap, "funding_rate", None)
    if rate is None:
        return None
    rate = float(rate)
    if rate > 0:
        return 100.0
    if rate < 0:
        return 0.0
    return 50.0


def _oi_change_from_snapshot(snap: Any | None) -> tuple[float | None, str]:
    if snap is None:
        return None, "oi unavailable"
    for name in ("oi_change_6h", "oi_change_pct"):
        value = getattr(snap, name, None)
        if value is not None:
            return float(value), name
    legacy = getattr(snap, "oi_change_z", None)
    if legacy is not None:
        return float(legacy), "oi_change_z"
    return None, "oi unavailable"


def funding_points_trend(snap: Any | None, direction: int) -> tuple[int, str]:
    pct = _funding_pct_from_snapshot(snap)
    if pct is None or direction not in (-1, 1):
        return 0, "funding unavailable"
    evidence = f"funding_pct={pct:.2f}"
    if direction > 0:
        if pct <= FUND_LOW:
            return 15, f"{evidence} <= {FUND_LOW:.2f}"
        if pct >= FUND_CROWDED:
            return 0, f"{evidence} >= {FUND_CROWDED:.2f}"
        return 5, f"{evidence} neutral"
    if pct >= FUND_HIGH:
        return 15, f"{evidence} >= {FUND_HIGH:.2f}"
    if pct <= 100.0 - FUND_CROWDED:
        return 0, f"{evidence} <= {100.0 - FUND_CROWDED:.2f}"
    return 5, f"{evidence} neutral"


def funding_points_ct(snap: Any | None, direction: int) -> tuple[int, str]:
    pct = _funding_pct_from_snapshot(snap)
    if pct is None or direction not in (-1, 1):
        return 0, "funding unavailable"
    evidence = f"funding_pct={pct:.2f}"
    if direction > 0:
        if pct <= FUND_LOW:
            return 15, f"{evidence} <= {FUND_LOW:.2f}"
        return 0, evidence
    if pct >= FUND_HIGH:
        return 15, f"{evidence} >= {FUND_HIGH:.2f}"
    return 0, evidence


def oi_flush_points(snap: Any | None) -> tuple[int, str]:
    change, source = _oi_change_from_snapshot(snap)
    if change is None:
        return 0, source
    if source == "oi_change_z":
        if change <= _LEGACY_OI_FLUSH_Z:
            return 10, f"oi_change_z={change:.4f} <= {_LEGACY_OI_FLUSH_Z:.4f}"
        return 0, f"oi_change_z={change:.4f}"
    if change <= OI_FLUSH:
        return 10, f"{source}={change:.4f} <= {OI_FLUSH:.4f}"
    return 0, f"{source}={change:.4f}"


def fetch_deriv_snapshot(symbol: str, now_ms: int) -> DerivSnapshot:
    start_ms = now_ms - FUND_WINDOW_DAYS * _DAY_MS
    try:
        funding_points = fetch_funding_rates(symbol, start_ms, now_ms + 1, _CACHE_DIR)
        funding_pct = _percentile_of_last(funding_points)
        oi_points = _fetch_open_interest_points(symbol, now_ms - 8 * _HOUR_MS, now_ms + 1)
        oi_change_6h = _oi_change_from_points(oi_points)
        return DerivSnapshot(funding_pct=funding_pct, oi_change_6h=oi_change_6h)
    except Exception:
        return DerivSnapshot(funding_pct=None, oi_change_6h=None)
