"""Lane 3 — Forced-Error Harvesting entry families (spec 2026-07-08).

Two predatory trap setups plus their isolation controls:
  * failed_breakout_harvest (SHORT): resistance pierced intrabar, closes back
    inside, OI expanded into the move (crowd loaded), volume spiked
    (participation proxy — UNSIGNED, not CVD). use_volume=False is the OI-only
    ablation reference. Control = failed_breakout_naive (pierce+fail only).
  * failed_fade_squeeze (LONG): price rallied (z_r high), funding deeply
    negative (crowd short), OI climbing (fresh shorts), and a downward probe is
    absorbed (low<prev low but close>prev close). Control = funding_fade_long
    (deeply-negative funding alone).
"""
from __future__ import annotations

from math import log
from statistics import fmean, pstdev

from moonface.core.models import Candle
from moonface.research.edge.divergence_signals import _log_changes, _zscore

Entry = tuple[int, str]


def _level_zscore(series: list, i: int, window: int) -> float | None:
    x = series[i]
    if x is None:
        return None
    sample = [v for v in series[i - window + 1:i + 1] if v is not None]
    if len(sample) < window // 2:
        return None
    sd = pstdev(sample)
    if sd == 0:
        return None
    return (x - fmean(sample)) / sd


def _percentile(values: list[float], q: float) -> float:
    s = sorted(values)
    if not s:
        raise ValueError("percentile of empty sequence")
    idx = q * (len(s) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    frac = idx - lo
    return s[lo] * (1.0 - frac) + s[hi] * frac


def _resistance(candles: list[Candle], i: int, n_back: int) -> float:
    return max(c.high for c in candles[i - n_back:i])


def failed_breakout_naive(candles: list[Candle], params: dict) -> list[Entry]:
    R = params["donchian_n"]
    n = len(candles)
    out: list[Entry] = []
    for i in range(R, n - 1):
        res = _resistance(candles, i, R)
        if candles[i].high > res and candles[i].close < res:
            out.append((i, "SHORT"))
    return out


def make_failed_breakout_harvest(feature: list):
    oi = list(feature)

    def gen(candles: list[Candle], params: dict) -> list[Entry]:
        R, W = params["donchian_n"], params["window"]
        L, k = params["lookback"], params["k"]
        use_volume = params.get("use_volume", True)
        n = len(candles)
        o_log = _log_changes(oi, L, n)
        vol_log = [log(c.volume) if c.volume and c.volume > 0 else None
                   for c in candles]
        out: list[Entry] = []
        for i in range(max(R, W + L) + 1, n - 1):
            res = _resistance(candles, i, R)
            if candles[i].high <= res or candles[i].close >= res:
                continue
            z_o = _zscore(o_log, i, W)
            if z_o is None or z_o < k:
                continue
            if use_volume:
                z_v = _level_zscore(vol_log, i, W)
                if z_v is None or z_v < k:
                    continue
            out.append((i, "SHORT"))
        return out

    return gen


def make_failed_fade_squeeze(feature: list, funding: list):
    oi = list(feature)
    fund = list(funding)

    def gen(candles: list[Candle], params: dict) -> list[Entry]:
        W, L, k = params["window"], params["lookback"], params["k"]
        f_pct, f_win = params["funding_pct"], params["funding_window"]
        n = len(candles)
        r_log = _log_changes([c.close for c in candles], L, n)
        o_log = _log_changes(oi, L, n)
        out: list[Entry] = []
        start = max(W + L, f_win) + 1
        for i in range(start, n - 1):
            if i >= len(fund) or fund[i] is None:
                continue
            recent = [v for v in fund[i - f_win + 1:i + 1] if v is not None]
            if len(recent) < f_win // 2:
                continue
            if fund[i] > _percentile(recent, f_pct) or fund[i] >= 0:
                continue
            z_r = _zscore(r_log, i, W)
            z_o = _zscore(o_log, i, W)
            if z_r is None or z_o is None or z_r < k or z_o < k:
                continue
            if (candles[i].low < candles[i - 1].low
                    and candles[i].close > candles[i - 1].close):
                out.append((i, "LONG"))
        return out

    return gen


def make_funding_fade_long(funding: list):
    fund = list(funding)

    def gen(candles: list[Candle], params: dict) -> list[Entry]:
        f_pct, f_win = params["funding_pct"], params["funding_window"]
        n = len(candles)
        out: list[Entry] = []
        for i in range(f_win + 1, n - 1):
            if i >= len(fund) or fund[i] is None:
                continue
            recent = [v for v in fund[i - f_win + 1:i + 1] if v is not None]
            if len(recent) < f_win // 2:
                continue
            # Same deeply-negative trigger as failed_fade_squeeze (bottom
            # percentile AND actually negative), so the control isolates ONLY
            # the OI-climb + absorption gates (prereg s2).
            if fund[i] <= _percentile(recent, f_pct) and fund[i] < 0:
                out.append((i, "LONG"))
        return out

    return gen
