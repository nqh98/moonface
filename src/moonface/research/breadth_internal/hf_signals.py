from __future__ import annotations

from statistics import fmean, pstdev

from moonface.research.breadth.signals import _ALWAYS, pct_above_ma_series
from moonface.research.universe_data import DailyRow


def _breadth(daily, base_period, is_member):
    series = pct_above_ma_series(daily, base_period, is_member=is_member)
    ts = [t for t, _ in series]
    vals = [v for _, v in series]
    return ts, vals


def breadth_oscillator_state(
    daily: dict[str, list[DailyRow]],
    window: int,
    z_in: float,
    base_period: int = 50,
    is_member=_ALWAYS,
) -> list[tuple[int, str]]:
    ts, vals = _breadth(daily, base_period, is_member)
    out: list[tuple[int, str]] = []
    for i in range(len(vals)):
        if i < window:
            out.append((ts[i], "FLAT"))
            continue
        prior = vals[i - window:i]
        sd = pstdev(prior)
        if sd <= 0.0:
            out.append((ts[i], "FLAT"))
            continue
        z = (vals[i] - fmean(prior)) / sd
        if z >= z_in:
            out.append((ts[i], "LONG"))
        elif z <= -z_in:
            out.append((ts[i], "SHORT"))
        else:
            out.append((ts[i], "FLAT"))
    return out


def breadth_momentum_state(
    daily: dict[str, list[DailyRow]],
    n: int,
    thr: float,
    base_period: int = 50,
    is_member=_ALWAYS,
) -> list[tuple[int, str]]:
    ts, vals = _breadth(daily, base_period, is_member)
    out: list[tuple[int, str]] = []
    for i in range(len(vals)):
        if i < n:
            out.append((ts[i], "FLAT"))
            continue
        m = vals[i] - vals[i - n]
        if m >= thr:
            out.append((ts[i], "LONG"))
        elif m <= -thr:
            out.append((ts[i], "SHORT"))
        else:
            out.append((ts[i], "FLAT"))
    return out


def breadth_accel_state(
    daily: dict[str, list[DailyRow]],
    n: int,
    thr: float,
    base_period: int = 50,
    is_member=_ALWAYS,
) -> list[tuple[int, str]]:
    ts, vals = _breadth(daily, base_period, is_member)
    out: list[tuple[int, str]] = []
    for i in range(len(vals)):
        if i < 2 * n:
            out.append((ts[i], "FLAT"))
            continue
        a = (vals[i] - vals[i - n]) - (vals[i - n] - vals[i - 2 * n])
        if a >= thr:
            out.append((ts[i], "LONG"))
        elif a <= -thr:
            out.append((ts[i], "SHORT"))
        else:
            out.append((ts[i], "FLAT"))
    return out
