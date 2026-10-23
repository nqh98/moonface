"""Stationarized per-bar features for the advval era-discrimination study.

All z-scores use the trailing window values strictly before the current index.
No self-inclusion, no lookahead. Features are returns, ratios, z-scores, or
bounded fractions only.
"""
from __future__ import annotations

import math
from statistics import fmean, stdev

from moonface.core.models import Candle

Z_WINDOW = 90
FRAC_WINDOW = 30


def trailing_z(values: list[float], window: int = Z_WINDOW) -> list[float | None]:
    out: list[float | None] = []
    if window < 2:
        return [None] * len(values)
    for i, x in enumerate(values):
        if i < window:
            out.append(None)
            continue
        past = values[i - window:i]
        sd = stdev(past)
        if sd == 0.0:
            out.append(None)
            continue
        out.append((x - fmean(past)) / sd)
    return out


def _z_of_optional(
    values: list[float | None], window: int = Z_WINDOW
) -> list[float | None]:
    out: list[float | None] = []
    if window < 2:
        return [None] * len(values)
    for i, x in enumerate(values):
        if i < window or x is None:
            out.append(None)
            continue
        past = values[i - window:i]
        if any(v is None for v in past):
            out.append(None)
            continue
        past_floats = [float(v) for v in past]
        sd = stdev(past_floats)
        if sd == 0.0:
            out.append(None)
            continue
        out.append((float(x) - fmean(past_floats)) / sd)
    return out


def _trailing_frac(
    flags: list[bool | None], window: int = FRAC_WINDOW
) -> list[float | None]:
    out: list[float | None] = []
    if window < 1:
        return [None] * len(flags)
    for i in range(len(flags)):
        if i + 1 < window:
            out.append(None)
            continue
        chunk = flags[i + 1 - window : i + 1]
        if any(flag is None for flag in chunk):
            out.append(None)
            continue
        out.append(sum(1.0 for flag in chunk if flag) / window)
    return out


def price_features(candles: list[Candle]) -> dict[str, list[float | None]]:
    n = len(candles)
    if n == 0:
        return {
            "log_ret": [],
            "abs_ret_z": [],
            "range_frac": [],
            "close_loc": [],
            "vol_z": [],
            "up_frac_30": [],
        }
    log_ret: list[float | None] = [None]
    for i in range(1, n):
        prev = candles[i - 1].close
        cur = candles[i].close
        if prev > 0.0 and cur > 0.0:
            log_ret.append(math.log(cur / prev))
        else:
            log_ret.append(None)
    abs_ret = [None if value is None else abs(value) for value in log_ret]
    range_frac = [
        ((c.high - c.low) / c.close) if c.close > 0.0 else None for c in candles
    ]
    close_loc = [
        0.5 if c.high == c.low else (c.close - c.low) / (c.high - c.low)
        for c in candles
    ]
    vol_log = [math.log1p(c.volume) for c in candles]
    up = [None if value is None else value > 0.0 for value in log_ret]
    return {
        "log_ret": log_ret,
        "abs_ret_z": _z_of_optional(abs_ret),
        "range_frac": range_frac,
        "close_loc": close_loc,
        "vol_z": trailing_z(vol_log),
        "up_frac_30": _trailing_frac(up),
    }


def funding_features(points: list[tuple[int, float]]) -> dict[str, list[float | None]]:
    rates = [rate for _, rate in points]
    if not rates:
        return {
            "rate": [],
            "rate_z": [],
            "rate_chg": [],
            "abs_rate_z": [],
            "pos_frac_30": [],
        }
    rate_chg: list[float | None] = [None]
    for i in range(1, len(rates)):
        rate_chg.append(rates[i] - rates[i - 1])
    pos = [rate > 0.0 for rate in rates]
    abs_rates = [abs(rate) for rate in rates]
    return {
        "rate": list(rates),
        "rate_z": trailing_z(rates),
        "rate_chg": rate_chg,
        "abs_rate_z": trailing_z(abs_rates),
        "pos_frac_30": _trailing_frac(pos),
    }


def oi_features(oi_aligned: list[float | None]) -> dict[str, list[float | None]]:
    n = len(oi_aligned)

    def log_chg(lag: int) -> list[float | None]:
        out: list[float | None] = []
        for i in range(n):
            prev = oi_aligned[i - lag] if i >= lag else None
            cur = oi_aligned[i]
            if prev is None or cur is None or prev <= 0.0 or cur <= 0.0:
                out.append(None)
            else:
                out.append(math.log(cur / prev))
        return out

    oi_chg = log_chg(1)
    abs_chg = [None if value is None else abs(value) for value in oi_chg]
    return {
        "oi_chg": oi_chg,
        "oi_chg_z": _z_of_optional(oi_chg),
        "oi_chg30": log_chg(30),
        "abs_chg_z": _z_of_optional(abs_chg),
    }


def build_dataset(
    feats: dict[str, list[float | None]],
    timestamps: list[int],
    era_split_ms: int,
) -> tuple[list[list[float]], list[int], list[int]]:
    keys = sorted(feats)
    if not keys:
        return [], [], []
    expected = len(timestamps)
    for key in keys:
        if len(feats[key]) != expected:
            raise ValueError(
                f"feature series {key!r} has length {len(feats[key])}, "
                f"expected {expected}"
            )
    X: list[list[float]] = []
    y: list[int] = []
    kept: list[int] = []
    for i, ts in enumerate(timestamps):
        row = [feats[key][i] for key in keys]
        if any(value is None for value in row):
            continue
        X.append([float(value) for value in row])
        y.append(0 if ts < era_split_ms else 1)
        kept.append(ts)
    return X, y, kept
