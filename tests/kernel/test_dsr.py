from moonface.kernel.dsr import DSR_THRESHOLD, evaluate_lockbox, stage3_dsr
from moonface.kernel.spec import HypothesisSpec

ASSET = {"exchange": "x", "symbol": "S", "timeframe": "4h"}


def _row(h: str, status: str, sharpe: float, trades: int = 100) -> dict:
    return {"spec_hash": h, "status": status,
            "stage_results": {"research_sharpe": sharpe, "research_trades": trades,
                              "research_skew": 0.0, "research_kurtosis": 3.0}}


def test_dsr_threshold_is_0_95():
    assert DSR_THRESHOLD == 0.95


def test_dsr_computed_only_for_oos_pass_rows():
    rows = [_row("a", "oos_pass", 0.5), _row("b", "rejected", 0.1),
            _row("c", "oos_pass", -0.2)]
    dsr = stage3_dsr(rows, grid_size=10)
    assert set(dsr) == {"a", "c"}


def test_bigger_grid_deflates_more():
    rows = [_row("a", "oos_pass", 0.5), _row("b", "rejected", 0.1)]
    assert stage3_dsr(rows, 1000)["a"] < stage3_dsr(rows, 10)["a"]


def _spec():
    return HypothesisSpec(
        domain="d", version=1, asset=ASSET,
        entry={"family": "donchian_break", "params": {"n": 20}},
        exit={"name": "horizon_hold", "params": {"n_bars": 24, "atr_period": 14}},
        fraction=0.01)


def test_evaluate_lockbox_counts_only_tail_entries():
    spec = _spec()
    stream = [(0, 0.1, 0.01), (500, -0.2, 0.01), (999, 0.3, 0.01), (1200, 0.1, 0.01)]
    m = evaluate_lockbox(stream, spec, fence_index=1000)
    assert m["tail_trades"] == 1
    assert "tail_mar" in m and "tail_drawdown" in m


def test_evaluate_lockbox_empty_tail():
    spec = _spec()
    m = evaluate_lockbox([(0, 0.1, 0.01)], spec, fence_index=1000)
    assert m["tail_trades"] == 0
