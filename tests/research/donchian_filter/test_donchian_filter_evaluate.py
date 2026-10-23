from dataclasses import dataclass

from moonface.research.donchian_filter.evaluate import (
    gate,
    overlapping_robust_frac,
    slice_metrics,
)


@dataclass
class T:
    entry_index: int
    r_multiple: float


def test_gate_is_strict_subset_and_preserves_rows():
    base = [T(0, 1.0), T(5, -1.0), T(9, 2.0)]
    adx = [0.0] * 10
    adx[0] = 30.0
    adx[9] = 25.0
    g = gate(base, adx, threshold=20.0)
    assert g == [base[0], base[2]]
    assert all(t in base for t in g)


def test_gate_monotone_in_threshold():
    base = [T(0, 1.0), T(1, 1.0), T(2, 1.0)]
    adx = [10.0, 20.0, 30.0]
    g20 = gate(base, adx, 20.0)
    g25 = gate(base, adx, 25.0)
    assert set(id(t) for t in g25) <= set(id(t) for t in g20)


def test_slice_metrics_keys():
    m = slice_metrics([T(0, 1.0), T(1, -0.5)])
    assert set(m) == {"n", "net_r", "expectancy_r", "profit_factor", "max_dd_r", "mar"}
    assert m["n"] == 2


def test_robust_frac_counts_alive_windows():
    trades = [T(0, 1.0), T(1, 1.0), T(2, -1.0)]
    rf = overlapping_robust_frac(trades, n_bars=4, year_bars=2, step_bars=2)
    assert rf == 0.5
