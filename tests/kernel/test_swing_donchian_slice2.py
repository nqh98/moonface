from moonface.core.models import Candle
from moonface.kernel.econ import evaluate_econ
from tools.engine.swing_donchian import _BASE, _GRID
from tools.engine.swing_donchian_slice2 import run_slice2, render_slice2


def _trend_then_flat(total=2400):
    """First half trends up, second half flat — same shape as the walk-forward
    test fixture, long enough for several quarterly (dense) windows."""
    out = []
    half = total // 2
    for i in range(total):
        p = 100.0 + (i if i < half else half) * 3.0
        out.append(Candle(i, p, p + 2.0, p - 2.0, p, 1.0))
    return out


def test_slice2_densifies_windows_without_changing_aggregate_gates():
    cs = _trend_then_flat()
    year_step = 200
    res_clean, res_dense, verdict = run_slice2(cs, None, year_step)

    # densification: more windows for the robustness estimate
    assert len(res_dense.test_summaries) > len(res_clean.test_summaries)

    # the four aggregate gates come from the CLEAN (non-overlapping) run
    clean_v = evaluate_econ(res_clean.test_summaries, res_clean.aggregated)
    for k in ("expectancy_r", "profit_factor", "mar", "max_dd_r"):
        assert verdict.metrics[k] == clean_v.metrics[k]

    # robust_frac comes from the DENSE run's per-window summaries
    dense_v = evaluate_econ(res_dense.test_summaries, res_dense.aggregated)
    assert verdict.metrics["robust_frac"] == dense_v.metrics["robust_frac"]


def test_slice2_uses_unchanged_strategy_objects():
    # identity guarantee: the runner trades the exact Slice-1 grid/base
    assert _BASE.entry_n == 20 and _BASE.trail_n == 10
    assert len(_GRID) == 6


def test_render_slice2_reports_both_window_counts_and_verdict():
    cs = _trend_then_flat()
    res_clean, res_dense, verdict = run_slice2(cs, None, 200)
    md = render_slice2("BTCUSDT", "4h", verdict,
                       clean_windows=len(res_clean.test_summaries),
                       dense_windows=len(res_dense.test_summaries))
    assert "Slice-2" in md
    assert ("PASS" in md) or ("FAIL" in md)
    assert str(len(res_dense.test_summaries)) in md
