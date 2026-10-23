import json
from dataclasses import replace

from moonface.core.models import Candle
from moonface.research.reconfirm import (TFResult, anchor_breached,
                                         build_report, measure_timeframe,
                                         verdict)

_H4_MS = 4 * 3_600_000
_START = 1_600_000_000_000


def _result(**overrides) -> TFResult:
    base = TFResult(timeframe="4h", bars=1000, last_bar_ts=_START,
                    n_total=50, n_research=35, n_oos=15,
                    research_mean_r=0.5, oos_mean_r=0.5, net_r=25.0,
                    max_drawdown_r=10.0, n_fresh=None, fresh_mean_r=None)
    return replace(base, **overrides)


def _staircase(n: int, start_price: float = 1000.0) -> list[Candle]:
    """Every bar closes 1 higher: a new donchian high every bar, so every
    index >= 100 is a LONG break and every 24-bar horizon move is +24."""
    return [Candle(_START + i * _H4_MS, start_price + i,
                   start_price + i + 0.5, start_price + i - 0.5,
                   start_price + i, 10.0) for i in range(n)]


def _flat(n: int, price: float = 1000.0) -> list[Candle]:
    return [Candle(_START + i * _H4_MS, price, price + 0.5, price - 0.5,
                   price, 10.0) for i in range(n)]


def _downstairs(n: int, start_price: float = 5000.0) -> list[Candle]:
    """Every bar closes 1 lower: only SHORT breaks exist."""
    return [Candle(_START + i * _H4_MS, start_price - i,
                   start_price - i + 0.5, start_price - i - 0.5,
                   start_price - i, 10.0) for i in range(n)]


# -- verdict rules ------------------------------------------------------------

def test_verdict_insufficient_below_total_threshold():
    assert verdict(_result(n_total=29)) == "INSUFFICIENT"
    assert verdict(_result(n_total=30)) == "ALIVE"


def test_verdict_insufficient_below_oos_threshold():
    assert verdict(_result(n_oos=9)) == "INSUFFICIENT"
    assert verdict(_result(n_oos=10)) == "ALIVE"


def test_verdict_degraded_when_either_fold_nonpositive():
    assert verdict(_result(research_mean_r=-0.1)) == "DEGRADED"
    assert verdict(_result(oos_mean_r=0.0)) == "DEGRADED"


def test_anchor_breached_only_past_277():
    assert anchor_breached(_result(max_drawdown_r=276.0)) is False
    assert anchor_breached(_result(max_drawdown_r=278.0)) is True


# -- measure_timeframe --------------------------------------------------------

def test_staircase_measures_alive_shape():
    r = measure_timeframe("4h", _staircase(200))
    assert r.n_total >= 30 and r.n_oos >= 10
    assert r.research_mean_r > 0 and r.oos_mean_r > 0
    assert verdict(r) == "ALIVE"
    assert r.last_bar_ts == _START + 199 * _H4_MS
    assert r.bars == 200


def test_long_only_a_downtrend_yields_zero_events():
    r = measure_timeframe("4h", _downstairs(200))
    assert r.n_total == 0
    assert verdict(r) == "INSUFFICIENT"


def test_flat_series_yields_zero_events():
    assert measure_timeframe("4h", _flat(200)).n_total == 0


def test_unresolved_horizons_are_excluded():
    """The last evaluable entry index is len-1-24; the staircase breaks on
    every bar past warmup, so n_total counts exactly those indices."""
    cs = _staircase(150)
    r = measure_timeframe("4h", cs)
    # entries at i in [100, 125]: generator range stops at len-2=148, the
    # horizon filter cuts i > 149-24=125
    assert r.n_total == 26


def test_fold_split_assigns_by_entry_index():
    cs = _staircase(200)
    r = measure_timeframe("4h", cs)
    # research fold: i < 160; entries run i=100..175 => 60 research, 16 oos
    assert r.n_research == 60
    assert r.n_oos == 16
    assert r.n_total == 76


def test_fresh_slice_counts_entries_after_prev_last_ts():
    cs = _staircase(200)
    none_slice = measure_timeframe("4h", cs)
    assert none_slice.n_fresh is None and none_slice.fresh_mean_r is None
    prev_ts = cs[150].timestamp_ms
    r = measure_timeframe("4h", cs, prev_last_ts=prev_ts)
    # fresh entries: i in 151..175 => 25, all +R
    assert r.n_fresh == 25
    assert r.fresh_mean_r > 0


def test_determinism():
    cs = _staircase(200)
    assert measure_timeframe("4h", cs) == measure_timeframe("4h", cs)


# -- build_report -------------------------------------------------------------

def _all_results(four_h: TFResult) -> dict[str, TFResult]:
    return {"1h": _result(timeframe="1h"), "4h": four_h,
            "1d": _result(timeframe="1d", n_total=12, n_oos=2),
            "1w": _result(timeframe="1w", n_total=0, n_research=0, n_oos=0)}


META = {"generated_utc": "2026-06-12T12:00:00Z",
        "asset": {"exchange": "binance", "symbol": "BTC/USDT:USDT"},
        "window_days": 1095}


def test_report_recommends_bump_when_4h_alive():
    md, data = build_report(_all_results(_result()), META)
    assert "ALIVE" in md and "INSUFFICIENT" in md
    assert "bump reconfirm_by" in md
    assert data["timeframes"]["4h"]["verdict"] == "ALIVE"
    assert data["timeframes"]["1w"]["verdict"] == "INSUFFICIENT"
    assert data["anchor_breached"] is False
    json.dumps(data)  # must be JSON-serializable


def test_report_demands_review_when_4h_degraded():
    md, data = build_report(_all_results(_result(oos_mean_r=-0.2)), META)
    assert "HUMAN REVIEW" in md
    assert data["timeframes"]["4h"]["verdict"] == "DEGRADED"


def test_report_demands_review_when_anchor_breached():
    md, data = build_report(_all_results(_result(max_drawdown_r=300.0)), META)
    assert "ANCHOR BREACHED" in md and "HUMAN REVIEW" in md
    assert data["anchor_breached"] is True
    # verdict itself can still be ALIVE — the flag is independent
    assert data["timeframes"]["4h"]["verdict"] == "ALIVE"


def test_report_carries_last_bar_ts_for_next_fresh_slice():
    _, data = build_report(_all_results(_result()), META)
    assert data["timeframes"]["4h"]["last_bar_ts"] == _START
