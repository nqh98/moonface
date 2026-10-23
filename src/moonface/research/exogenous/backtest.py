from __future__ import annotations

from statistics import pstdev

from moonface.core.metrics import Summary, summarize_r


def daily_returns(closes: list[float]) -> list[float]:
    return [(closes[i + 1] - closes[i]) / closes[i]
            for i in range(len(closes) - 1)]


def rolling_vol(rets: list[float], i: int, window: int):
    if i < window:
        return None
    w = rets[i - window:i]
    v = pstdev(w) if len(w) > 1 else 0.0
    return v if v > 0 else None


def episode_trades(positions: list[int], rets: list[float],
                   vol_window: int = 20, cost: float = 0.001) -> list[float]:
    n = min(len(positions), len(rets))
    trades: list[float] = []
    i = 0
    while i < n:
        side = positions[i]
        if side == 0:
            i += 1
            continue
        entry_vol = rolling_vol(rets, i, vol_window)
        if entry_vol is None:          # DEV: brief consumed the whole run here (i=j),
            i += 1                     # dropping the opening episode before vol warms.
            continue                   # Skip warmup bars so entry is at first valid-vol bar.
        acc = 0.0
        j = i
        while j < n and positions[j] == side:
            acc += side * rets[j]
            j += 1
        trades.append((acc - cost) / entry_vol)
        i = j
    return trades


def run_backtest(closes, positions, vol_window: int = 20, cost: float = 0.001) -> Summary:
    rets = daily_returns(closes)
    return summarize_r(episode_trades(positions, rets, vol_window, cost))
