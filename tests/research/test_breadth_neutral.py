from collections import namedtuple

from moonface.core.metrics import COST_FRACTION
from moonface.core.models import Candle
from moonface.research.breadth_confirm.neutral import (
    aligned_returns,
    entries_provider,
    hedge_entries,
    rolling_betas,
    simple_returns,
)

Stub = namedtuple("Stub", ["timestamp_ms", "close"])
EXIT = {"k_trail": 2.0, "max_bars": 120, "atr_period": 14}


def _rising(n=40, base=100.0, step=1.0):
    return [Candle(1000 * j, base + step * j, base + step * j + 0.5,
                   base + step * j - 0.5, base + step * j, 1.0) for j in range(n)]


def test_simple_and_aligned_returns():
    asset = [Stub(0, 100.0), Stub(1, 110.0), Stub(2, 99.0)]
    mkt = [Stub(0, 50.0), Stub(1, 55.0), Stub(2, 55.0)]
    sr = simple_returns(asset)
    assert sr[0][0] == 1 and abs(sr[0][1] - 0.10) < 1e-9
    al = aligned_returns(asset, mkt)
    # ts=1: asset +0.10, market +0.10 ; ts=2: asset -0.10, market 0.0
    assert al[0][0] == 1 and abs(al[0][1] - 0.10) < 1e-9 and abs(al[0][2] - 0.10) < 1e-9


def test_rolling_betas_recovers_known_beta_no_lookahead():
    # asset_ret = 2 * market_ret exactly -> beta 2.0, using only prior data.
    aligned = [(j, 2.0 * (0.01 * ((j % 7) - 3)), 0.01 * ((j % 7) - 3)) for j in range(200)]
    betas = rolling_betas(aligned, window=100, min_obs=20)
    # late timestamp has a full prior window -> beta ~ 2
    assert abs(betas[150] - 2.0) < 1e-6
    # earliest timestamps lack min_obs -> unit-beta fallback
    assert betas[0] == 1.0


def test_beta_zero_reproduces_raw_records():
    candles = _rising()
    entries = [(20, "LONG"), (22, "SHORT")]
    res = hedge_entries(candles, candles, entries, "atr_trail", EXIT, beta=0.0)
    assert len(res["hedged"]) == len(res["raw"]) >= 1
    for h, r in zip(res["hedged"], res["raw"]):
        assert h["net_r"] == r["net_r"]
        assert h["atr_frac"] == r["atr_frac"]


def test_flat_market_hedge_is_noop_even_at_unit_beta():
    asset = _rising()
    flat = [Candle(1000 * j, 50.0, 50.0, 50.0, 50.0, 1.0) for j in range(len(asset))]
    res = hedge_entries(asset, flat, [(20, "LONG")], "atr_trail", EXIT, beta=1.0)
    h, r = res["hedged"][0], res["raw"][0]
    assert abs(h["net_r"] - r["net_r"]) < 1e-9  # flat market contributes nothing


def test_perfectly_correlated_full_hedge_leaves_only_cost():
    # asset == market, beta=1, monotonic rise (no stop) -> residual is just cost drag.
    candles = _rising()
    res = hedge_entries(candles, candles, [(20, "LONG")], "atr_trail", EXIT, beta=1.0)
    h = res["hedged"][0]
    atr_frac = res["raw"][0]["atr_frac"]
    assert abs(h["net_r"] - (-COST_FRACTION / atr_frac)) < 1e-3


def test_entries_provider_maps_leads():
    from moonface.research.breadth_internal.evaluate import cell_entries
    from moonface.research.breadth_internal.hf_evaluate import hf_cell_entries
    assert entries_provider("net_new_highs") is cell_entries
    assert entries_provider("breadth_momentum") is hf_cell_entries
