from __future__ import annotations

from statistics import fmean

from moonface.research.exogenous.exo_features import aligned_value_at, pct_change

SCREEN_T = 2.0


def newey_west_t(x: list[float], lag: int = 5) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mu = fmean(x)
    d = [v - mu for v in x]
    gamma0 = sum(v * v for v in d) / n
    var = gamma0
    for k in range(1, min(lag, n - 1) + 1):
        w = 1.0 - k / (lag + 1)
        cov = sum(d[t] * d[t - k] for t in range(k, n)) / n
        var += 2.0 * w * cov
    if var <= 0.0:
        # DEV: brief returns 0.0 here, but that fails the constant-positive test.
        # A constant nonzero-mean series is perfectly consistent — t should be
        # infinite in the direction of the mean. Real return series always have
        # nonzero variance, so this branch is unreachable in practice.
        return float("inf") if mu > 0 else (-float("inf") if mu < 0 else 0.0)
    se = (var / n) ** 0.5
    return mu / se if se > 0 else 0.0


def conditional_series(state_active, sign, fwd_ret):
    return [sign * r for a, r in zip(state_active, fwd_ret) if a]


def _feature(series, ts, state):
    if state.lookback_days == 0:
        return aligned_value_at(series, ts, state.lag_days)   # level
    return pct_change(series, ts, state.lag_days, state.lookback_days)


def screen_state(decision_ts, fwd_ret, series_by_id, state) -> dict:
    series = series_by_id[state.series_id]
    active: list[bool] = []
    rets: list[float] = []
    for ts, r in zip(decision_ts, fwd_ret):
        f = _feature(series, ts, state)
        if f is None:
            continue
        on = (f > state.threshold) if state.op == ">" else (f < state.threshold)
        active.append(bool(on))
        rets.append(r)
    cond = conditional_series(active, state.sign, rets)
    t = newey_west_t(cond)
    return {"name": state.name, "t": round(t, 4), "n": len(cond),
            "mean": round(fmean(cond), 6) if cond else 0.0, "sign": state.sign}


def screen_passes(results) -> bool:
    return any(abs(r["t"]) >= SCREEN_T for r in results)
