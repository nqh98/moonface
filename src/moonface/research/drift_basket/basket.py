from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import pstdev

_ANNUAL_DAYS = 365
_MAX_LEVERAGE = 5.0


@dataclass(frozen=True)
class BasketParams:
    donchian_n: int = 20
    hold_bars: int = 12
    top_n: int = 30
    min_history_days: int = 180
    vol_days: int = 30
    vol_window: int = 30
    vol_target_annual: float = 0.20
    beta_window: int = 30
    fee: float = 0.0005


def inverse_vol_weights(vols: dict[str, float]) -> dict[str, float]:
    """sym -> normalized 1/vol weight (sum=1). Zero/negative-vol legs dropped."""
    inv = {s: 1.0 / v for s, v in vols.items() if v and v > 0.0}
    tot = sum(inv.values())
    if tot <= 0.0:
        return {}
    return {s: w / tot for s, w in inv.items()}


def rolling_beta(book: list[float], btc: list[float], k: int, window: int) -> float:
    lo = max(0, k - window)
    xs, ys = btc[lo:k], book[lo:k]
    if len(xs) < 2:
        return 0.0
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    var = sum((x - mx) ** 2 for x in xs)
    return cov / var if var > 0.0 else 0.0


def simulate_basket(
    days: list[int],
    universe_by_day: dict[int, list[str]],
    daily_flags: dict[str, dict[int, bool]],
    daily_rets: dict[str, dict[int, float]],
    btc_rets: dict[int, float],
    funding: dict[str, dict[int, float]],
    params: BasketParams,
) -> list[tuple[int, float]]:
    """Daily (ts, leveraged portfolio return). Strictly causal: weights,
    leverage and beta at day k use only data with index < k; the book return
    is realized k -> k+1."""
    n = len(days)
    weights_by_k: list[dict[str, float]] = []
    u = [0.0] * n  # unleveraged book return realized k -> k+1
    for k in range(n):
        t = days[k]
        vols: dict[str, float] = {}
        for s in universe_by_day.get(t, []):
            if not daily_flags.get(s, {}).get(t):
                continue
            hist = [daily_rets[s][d] for d in days[:k] if d in daily_rets.get(s, {})]
            tail = hist[-params.vol_window:]
            v = pstdev(tail) if len(tail) >= 2 else 0.0
            if v > 0.0:
                vols[s] = v
        w = inverse_vol_weights(vols)
        weights_by_k.append(w)
        if k + 1 < n:
            nxt = days[k + 1]
            u[k] = sum(wi * daily_rets[s].get(nxt, 0.0) for s, wi in w.items())

    btc = [btc_rets.get(days[k + 1], 0.0) if k + 1 < n else 0.0 for k in range(n)]
    daily_target = params.vol_target_annual / sqrt(_ANNUAL_DAYS)
    out: list[tuple[int, float]] = []
    for k in range(n):
        prior = u[max(0, k - params.vol_window):k]
        sig = pstdev(prior) if len(prior) >= 2 else 0.0
        lev = min(_MAX_LEVERAGE, daily_target / sig) if sig > 0.0 else 0.0
        beta = rolling_beta(u, btc, k, params.beta_window)
        prev = weights_by_k[k - 1] if k > 0 else {}
        cur = weights_by_k[k]
        turnover = sum(abs(cur.get(s, 0.0) - prev.get(s, 0.0))
                       for s in set(cur) | set(prev))
        fund = sum(wi * funding.get(s, {}).get(days[k], 0.0) for s, wi in cur.items())
        gross = lev * (u[k] - beta * btc[k])
        out.append((days[k], gross - params.fee * turnover * lev - fund))
    return out
