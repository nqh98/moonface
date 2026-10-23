from __future__ import annotations

from math import sqrt

_DAY_MS = 86_400_000


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2 or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0.0 or vy <= 0.0:
        return 0.0
    return cov / sqrt(vx * vy)


def trailing_return(day_rets: dict[int, float], t: int, days_back: int,
                    day_ms: int = _DAY_MS) -> float | None:
    """Compounded return over the days_back days ending at t; None on any gap."""
    factor = 1.0
    for i in range(days_back):
        r = day_rets.get(t - i * day_ms)
        if r is None:
            return None
        factor *= 1.0 + r
    return factor - 1.0


def distinctness_correlation(days, universe_by_day, daily_flags, daily_rets,
                             mom_days: int = 30) -> float:
    """Mean per-day Pearson corr between the active-long indicator and the
    trailing-mom_days return across that day's universe. ~0 => the time-series
    trigger is distinct from cross-sectional momentum rank."""
    corrs: list[float] = []
    for t in days:
        flags: list[float] = []
        moms: list[float] = []
        for s in universe_by_day.get(t, []):
            r = trailing_return(daily_rets.get(s, {}), t, mom_days)
            if r is None:
                continue
            flags.append(1.0 if daily_flags.get(s, {}).get(t) else 0.0)
            moms.append(r)
        if len(flags) >= 3 and len(set(flags)) > 1:
            corrs.append(pearson(flags, moms))
    return sum(corrs) / len(corrs) if corrs else 0.0


def cocrash_metrics(port_rets: list[float],
                    btc_aligned: list[float]) -> tuple[float, float]:
    """(full_beta, left_tail_corr): OLS beta of portfolio on BTC over all days,
    and Pearson corr within the worst-decile portfolio days."""
    n = len(port_rets)
    if n < 2:
        return 0.0, 0.0
    mx = sum(btc_aligned) / n
    my = sum(port_rets) / n
    cov = sum((b - mx) * (p - my) for b, p in zip(btc_aligned, port_rets))
    var = sum((b - mx) ** 2 for b in btc_aligned)
    full_beta = cov / var if var > 0.0 else 0.0
    k = max(2, n // 10)
    idx = sorted(range(n), key=lambda i: port_rets[i])[:k]
    pl = [port_rets[i] for i in idx]
    bl = [btc_aligned[i] for i in idx]
    return full_beta, pearson(bl, pl)
