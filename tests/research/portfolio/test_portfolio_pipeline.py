"""Tests for portfolio grid + staged pipeline (Task 10)."""
from __future__ import annotations

from moonface.core.models import Candle
from moonface.research.portfolio.grid import FROZEN_PORTFOLIOS, N_TRIALS
from moonface.research.portfolio.pipeline import (
    to_leaderboard,
    freeze_candidates,
    run_explore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candles(n: int, base_price: float = 100.0) -> list[Candle]:
    """Synthetic flat candles for smoke tests (no price movement)."""
    return [
        Candle(
            timestamp_ms=t * 3_600_000,
            open=base_price,
            high=base_price + 1.0,
            low=base_price - 1.0,
            close=base_price,
            volume=1.0,
        )
        for t in range(n)
    ]


def _make_component_positions(n: int, n_components: int = 3) -> list[list[float]]:
    """Alternating +1/0/-1 positions for n_components * n bars."""
    positions = []
    for c in range(n_components):
        row = []
        for t in range(n):
            if c == 0:
                row.append(1.0 if t % 3 == 0 else 0.0)
            elif c == 1:
                row.append(-1.0 if t % 3 == 1 else 0.0)
            else:
                row.append(1.0 if t % 3 == 2 else 0.0)
        positions.append(row)
    return positions


# ---------------------------------------------------------------------------
# Brief Step 1 unit tests
# ---------------------------------------------------------------------------


def test_frozen_grid_size():
    assert len(FROZEN_PORTFOLIOS) == 8
    assert N_TRIALS == 8


def test_freeze_candidates_preserves_survivors():
    survivors = [{"label": "vote_majority", "metrics": {"mar": 0.6}}]
    frozen = freeze_candidates(survivors)
    assert frozen == survivors


def test_to_leaderboard_sorts_by_mar():
    rows = [
        {
            "label": "a",
            "verdict": "candidate",
            "metrics": {"mar": 0.4, "max_dd_r": -0.2, "sharpe": 0.5, "n": 40},
        },
        {
            "label": "b",
            "verdict": "candidate",
            "metrics": {"mar": 0.9, "max_dd_r": -0.1, "sharpe": 0.7, "n": 40},
        },
    ]
    lb = to_leaderboard(rows)
    assert lb[0]["label"] == "b"


# ---------------------------------------------------------------------------
# Controller addition #2: smoke test for run_explore wiring
# ---------------------------------------------------------------------------


def test_run_explore_produces_eight_rows():
    """run_explore returns exactly 8 rows (one per FROZEN_PORTFOLIOS), each
    with the expected keys.  This is a wiring smoke test — synthetic data,
    not an edge test."""
    n_bars = 60
    n_components = 3
    positions_by_comp = _make_component_positions(n_bars, n_components)
    grid_candles = _candles(n_bars)

    # asset_bar_r: constant 1.0 (flat price → ATR undefined, falls back to 0;
    # streams.asset_bar_r returns 0 for bar 0, 0 when ATR is None; use all
    # 0.0 so returns are driven purely by position changes).
    asset_bar_r = [0.0] * n_bars

    # Do NOT pass trial_srs — exercise the honest internal path (portfolios'
    # own Sharpes as the multiple-comparison reference).
    rows = run_explore(positions_by_comp, asset_bar_r, grid_candles)

    assert len(rows) == 8, f"expected 8 rows, got {len(rows)}"

    expected_keys = {"label", "operator", "kw", "positions", "returns", "metrics", "dsr"}
    for i, row in enumerate(rows):
        missing = expected_keys - set(row.keys())
        assert not missing, (
            f"row {i} ({row.get('label')}) missing keys: {missing}"
        )
        m = row["metrics"]
        for mk in ("mar", "max_dd_r", "n"):
            assert mk in m, f"row {i} metrics missing key '{mk}'"
        dsr = row["dsr"]
        assert isinstance(dsr["dsr"], float), (
            f"row {i} dsr['dsr'] should be float, got {type(dsr.get('dsr'))}"
        )
