from __future__ import annotations

from moonface.research.exogenous.exo_features import aligned_value_at, pct_change
from moonface.research.exogenous.grid import PRECOMMITTED_STATES


def _feature(series, ts, state):
    if state.lookback_days == 0:
        return aligned_value_at(series, ts, state.lag_days)
    return pct_change(series, ts, state.lag_days, state.lookback_days)


def _active(series, ts, state) -> bool:
    f = _feature(series, ts, state)
    if f is None:
        return False
    return (f > state.threshold) if state.op == ">" else (f < state.threshold)


def state_positions(decision_ts, series_by_id, states=PRECOMMITTED_STATES) -> list[int]:
    out: list[int] = []
    for ts in decision_ts:
        total = 0
        for s in states:
            if s.series_id in series_by_id and _active(series_by_id[s.series_id], ts, s):
                total += s.sign
        out.append((total > 0) - (total < 0))   # sign(total) in {-1,0,+1}
    return out
