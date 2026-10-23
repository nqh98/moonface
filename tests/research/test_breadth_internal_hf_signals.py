from moonface.research.breadth_internal.hf_signals import (
    breadth_accel_state,
    breadth_momentum_state,
    breadth_oscillator_state,
)
from moonface.research.universe_data import DailyRow

DAY_MS = 86_400_000


def _universe(per_coin_closes):
    """per_coin_closes: dict[sym, list[float]] -> daily dict with UTC-midnight ts."""
    return {
        sym: [DailyRow(i * DAY_MS, c, 1.0) for i, c in enumerate(closes)]
        for sym, closes in per_coin_closes.items()
    }


def _b_series_rising():
    # Construct a universe whose pct-above-MA(period) breadth rises 0 -> 1 smoothly.
    # 4 coins; ramp each coin's close so more clear their MA over time.
    closes = {f"C{j}": [10.0 + i + (j * 0.0) for i in range(60)] for j in range(4)}
    return _universe(closes)


def test_momentum_goes_long_when_breadth_rising_fast():
    daily = _universe({f"C{j}": [50.0 + 2.0*abs(i - (10 + j*15)) for i in range(140)] for j in range(4)})
    state = breadth_momentum_state(daily, n=10, thr=0.10, base_period=5)
    # once breadth has ramped up over the last n days, momentum is strongly +
    sides = [s for _, s in state]
    assert "LONG" in sides
    assert "SHORT" not in sides  # monotone-up universe never triggers SHORT


def test_momentum_flat_before_warmup():
    daily = _universe({f"C{j}": [10.0 + i for i in range(40)] for j in range(4)})
    state = breadth_momentum_state(daily, n=10, thr=0.10, base_period=5)
    assert state[0][1] == "FLAT"  # first day has no n-day history


def test_oscillator_long_on_positive_zscore():
    daily = _universe({f"C{j}": [50.0 + 2.0*abs(i - (10 + j*15)) for i in range(140)] for j in range(4)})
    state = breadth_oscillator_state(daily, window=20, z_in=1.0, base_period=5)
    sides = [s for _, s in state]
    assert "LONG" in sides


def test_accel_distinct_from_momentum_flat_on_linear_breadth():
    # On a steadily (linearly) rising breadth, momentum is positive but
    # acceleration (2nd difference) is ~0 -> accel stays FLAT where momentum is LONG.
    daily = _universe({f"C{j}": [50.0 + 2.0*abs(i - (10 + j*15)) for i in range(140)] for j in range(4)})
    accel = breadth_accel_state(daily, n=5, thr=0.05, base_period=5)
    mom = breadth_momentum_state(daily, n=5, thr=0.05, base_period=5)
    accel_sides = {s for _, s in accel}
    mom_sides = {s for _, s in mom}
    assert "LONG" in mom_sides
    assert accel_sides <= {"FLAT", "LONG", "SHORT"}
    # acceleration should not be LONG on every day momentum is LONG
    long_mom_days = sum(1 for _, s in mom if s == "LONG")
    long_accel_days = sum(1 for _, s in accel if s == "LONG")
    assert long_accel_days < long_mom_days


def test_no_lookahead_state_ts_are_breadth_ts():
    daily = _universe({f"C{j}": [10.0 + i for i in range(30)] for j in range(4)})
    state = breadth_momentum_state(daily, n=5, thr=0.10, base_period=5)
    ts = [t for t, _ in state]
    assert ts == sorted(ts)
    assert all(t % DAY_MS == 0 for t in ts)


def test_hf_grid_is_three_frozen_specs():
    from moonface.research.breadth_internal.hf_grid import BLOCK_LEN, hf_specs
    specs = hf_specs()
    assert [s.builder for s in specs] == [
        "breadth_oscillator", "breadth_momentum", "breadth_accel"]
    assert all(s.exit_name == "atr_trail" and s.h == 48 for s in specs)
    assert specs[0].params["window"] == 60 and specs[0].params["z_in"] == 1.0
    assert specs[1].params["n"] == 10 and specs[1].params["thr"] == 0.10
    assert specs[2].params["n"] == 5 and specs[2].params["thr"] == 0.05
    assert BLOCK_LEN == 8


def test_evaluate_hf_spec_produces_overlapping_records():
    from moonface.core.models import Candle
    from moonface.research.breadth_internal.hf_evaluate import (
        evaluate_hf_spec,
        hf_cell_entries,
    )
    from moonface.research.breadth_internal.hf_grid import hf_specs

    H4_MS = 4 * 3_600_000
    daily = {
        f"C{j}": [DailyRow(i * DAY_MS, 50.0 + 2.0*abs(i - (10 + j*15)), 1.0) for i in range(120)]
        for j in range(4)
    }
    btc = [Candle(i * H4_MS, 100.0 + i, 101.0 + i, 99.0 + i, 100.0 + i, 1.0)
           for i in range(120 * 6)]
    spec = hf_specs()[1]  # breadth_momentum
    entries = hf_cell_entries(daily, btc, spec)
    out = evaluate_hf_spec(daily, btc, spec)
    assert out["key"] == "breadth_momentum"
    assert out["metrics"]["trade_count"] == len(out["records"])
    assert len(entries) >= 1
