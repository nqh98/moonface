"""Frozen operator grid (8 portfolios). Components are inputs; this IS the search space."""
from __future__ import annotations

# Each spec: (label, operator, kwargs). Operators resolved in pipeline.run_explore.
FROZEN_PORTFOLIOS: list[tuple[str, str, dict]] = [
    ("vote_2", "vote", {"k": 2}),
    ("vote_majority", "vote", {"k": "majority"}),
    ("vol_target_vote_24", "vol_target", {"base": "vote_majority", "vol_lookback": 24, "target_vol": 1.0}),
    ("vol_target_vote_48", "vol_target", {"base": "vote_majority", "vol_lookback": 48, "target_vol": 1.0}),
    ("vol_target_lsn_24", "vol_target", {"base": "long_short_net", "vol_lookback": 24, "target_vol": 1.0}),
    ("vol_target_lsn_48", "vol_target", {"base": "long_short_net", "vol_lookback": 48, "target_vol": 1.0}),
    ("regime_switch", "regime_switch", {"floor": 0.10, "lookback": 50}),
    ("long_short_net", "long_short_net", {}),
]
N_TRIALS = len(FROZEN_PORTFOLIOS)  # = 8, the pooled DSR n_trials
