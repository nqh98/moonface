import json

import pytest

from moonface.kernel.spec import HypothesisSpec, spec_hash
from moonface.kernel.store import Store
from tools.promote import mc_drawdown_p95, promote

SPEC = HypothesisSpec(
    domain="new_families.lead_lag", version=1,
    asset={"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "4h"},
    entry={"family": "eth_lead_momentum",
           "params": {"window": 180, "lookback": 12, "z_thr": 1.5}},
    exit={"name": "fixed_bracket",
          "params": {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0}},
    fraction=0.01)


def _store_with_row(tmp_path, status, stage_results):
    store = Store(str(tmp_path / "r.db"))
    now = 1_750_000_000_000
    store.register_domain("new_families.lead_lag", 1, "closed_positive",
                          {"assets": [SPEC.asset]}, now - 10_000, now, now - 2_000)
    store.insert_grid("new_families.lead_lag", 1, [SPEC])
    h = spec_hash(SPEC)
    store.advance(h, "screened", stage_results)
    store.advance(h, "oos_pass", {})
    store.advance(h, "corrected_survivor", {})
    store.advance(h, status, {})
    return store, h


GOOD = {"tail_mar": 2.5, "tail_drawdown": -0.1, "holdout_drawdown": -0.1,
        "screen_trades": 40, "screen_expectancy_r": 0.2}


def test_promote_writes_paper_strategy(tmp_path):
    store, h = _store_with_row(tmp_path, "lockbox_pass", GOOD)
    out = tmp_path / "strategy.json"
    promote(store, h, out, research_stream=[(1, 0.5, 0.02), (2, -1.0, 0.02),
                                            (3, 2.0, 0.02)] * 10)
    written = json.loads(out.read_text())
    assert written["status"] == "paper"
    assert written["family"] == "eth_lead_momentum"
    assert written["max_drawdown_p95"] > 0
    assert written["provenance"]["spec_hash"] == h


def test_promote_refuses_lockbox_fail(tmp_path):
    store, h = _store_with_row(tmp_path, "lockbox_fail", GOOD)
    with pytest.raises(SystemExit):
        promote(store, h, tmp_path / "s.json", research_stream=[(1, 0.5, 0.02)])


def test_promote_refuses_soft_tail_mar(tmp_path):
    weak = {**GOOD, "tail_mar": 1.2}
    store, h = _store_with_row(tmp_path, "lockbox_pass", weak)
    with pytest.raises(SystemExit, match="tail_mar"):
        promote(store, h, tmp_path / "s.json", research_stream=[(1, 0.5, 0.02)])


def test_mc_drawdown_p95_is_deterministic_and_positive():
    trades = [(0.5, 0.02), (-1.0, 0.02), (2.0, 0.02), (-1.0, 0.02)] * 10
    a = mc_drawdown_p95(trades, fraction=0.01)
    b = mc_drawdown_p95(trades, fraction=0.01)
    assert a == b
    assert a > 0
