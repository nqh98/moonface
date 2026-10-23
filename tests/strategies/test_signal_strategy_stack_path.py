"""Tests for the stack_path strategy module.

The stack_path strategy combines two CS algorithms to produce signals:
1. Monotonic Stack Depth (MSD): PLE/PGE stack depths measure trend structure.
2. DAG Shortest-Path Piecewise Linear Segmentation: finds optimal breakpoints
   in the close series and reads the slope of the final segment.
"""
from dataclasses import replace

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.kernel.synth import make_candles
from moonface.models.evaluate import evaluate
from moonface.strategies.spec import PromotedStrategy
from moonface.strategies.impls.stack_path import (
    STACK_PATH,
    segment_sse,
)


# --- Fixtures -----------------------------------------------------------------

STRATEGY = PromotedStrategy(
    family="stack_path",
    params={
        "lookback_bars": 20,
        "penalty_factor": 1.0,
        "stack_threshold": 1,
        "slope_threshold": 0.01,
        "long_only": False,
    },
    exit={
        "name": "fixed_bracket",
        "params": {"atr_period": 14, "k_stop": 2.0},
    },
    fraction=0.01,
    status="paper",
    asset={
        "exchange": "binance",
        "symbol": "BTC/USDT:USDT",
        "timeframe": "4h",
    },
    provenance={},
    max_drawdown_p95=0.2,
)


def _rising_candles(n: int, start: float = 100.0) -> list[Candle]:
    """Generate a strongly rising series: every close > previous close."""
    out: list[Candle] = []
    ts = 1_600_000_000_000
    price = start
    for _ in range(n):
        c = price * 1.005
        h = c * 1.002
        lo = price * 0.999
        out.append(Candle(ts, round(price, 6), round(h, 6), round(lo, 6),
                          round(c, 6), 1000.0))
        price = c
        ts += 4 * 3_600_000
    return out


def _falling_candles(n: int, start: float = 200.0) -> list[Candle]:
    """Generate a strongly falling series: every close < previous close."""
    out: list[Candle] = []
    ts = 1_600_000_000_000
    price = start
    for _ in range(n):
        c = price * 0.995
        h = price * 1.001
        lo = c * 0.998
        out.append(Candle(ts, round(price, 6), round(h, 6), round(lo, 6),
                          round(c, 6), 1000.0))
        price = c
        ts += 4 * 3_600_000
    return out


def _flat_candles(n: int, price: float = 150.0) -> list[Candle]:
    """Generate a flat/sideways series: close ≈ open every bar."""
    out: list[Candle] = []
    ts = 1_600_000_000_000
    for _ in range(n):
        out.append(Candle(ts, price, price + 0.5, price - 0.5, price, 1000.0))
        ts += 4 * 3_600_000
    return out


# --- segment_sse unit tests ---------------------------------------------------

def test_segment_sse_same_index_returns_zero():
    assert segment_sse([100.0, 200.0, 300.0], 1, 1) == 0.0


def test_segment_sse_perfect_line_returns_zero():
    closes = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert segment_sse(closes, 0, 4) == 0.0


def test_segment_sse_deviation_is_positive():
    closes = [10.0, 50.0, 30.0, 40.0]
    assert segment_sse(closes, 0, 3) > 0.0


def test_segment_sse_symmetric():
    """Reversing a segment should give the same SSE."""
    closes = [10.0, 25.0, 15.0, 30.0, 20.0]
    sse_fwd = segment_sse(closes, 0, 4)
    closes_rev = list(reversed(closes))
    sse_rev = segment_sse(closes_rev, 0, 4)
    assert abs(sse_fwd - sse_rev) < 1e-9


# --- Validation tests ---------------------------------------------------------

def test_stack_path_module_accepts_current_configuration():
    assert STACK_PATH.validate(STRATEGY) is True


def test_stack_path_rejects_missing_lookback_bars():
    bad = replace(STRATEGY, params={
        "penalty_factor": 1.0, "stack_threshold": 1, "slope_threshold": 0.01,
    })
    assert STACK_PATH.validate(bad) is False


def test_stack_path_rejects_small_lookback():
    bad = replace(STRATEGY, params={**STRATEGY.params, "lookback_bars": 5})
    assert STACK_PATH.validate(bad) is False


def test_stack_path_rejects_negative_penalty():
    bad = replace(STRATEGY, params={**STRATEGY.params, "penalty_factor": -1.0})
    assert STACK_PATH.validate(bad) is False


def test_stack_path_rejects_missing_atr_period():
    bad = replace(STRATEGY, exit={"name": "fixed_bracket", "params": {"k_stop": 2.0}})
    assert STACK_PATH.validate(bad) is False


# --- Evaluate behaviour tests -------------------------------------------------

def test_insufficient_history_returns_wait():
    candles = _rising_candles(5)
    signal = STACK_PATH.evaluate(STRATEGY, DataBundle(candles=candles))
    assert signal.decision == "WAIT"
    assert "not enough closed candles" in signal.reason


def test_rising_series_fires_long():
    """A strongly uptrending series should fire LONG:
    - PLE stack should be deeper than PGE (each low is higher),
    - shortest-path last segment should have positive slope/ATR."""
    candles = _rising_candles(60)
    signal = STACK_PATH.evaluate(STRATEGY, DataBundle(candles=candles))
    assert signal.decision == "LONG"
    assert signal.price == candles[-1].close
    assert signal.invalidation is not None
    assert signal.invalidation < signal.price
    assert "MSD=" in signal.reason


def test_falling_series_fires_short():
    """A strongly downtrending series should fire SHORT:
    - PGE stack should be deeper than PLE (each high is lower),
    - shortest-path last segment should have negative slope/ATR."""
    candles = _falling_candles(60)
    signal = STACK_PATH.evaluate(STRATEGY, DataBundle(candles=candles))
    assert signal.decision == "SHORT"
    assert signal.price == candles[-1].close
    assert signal.invalidation is not None
    assert signal.invalidation > signal.price


def test_long_only_mode_suppresses_short():
    """With long_only=True, a falling series should get WAIT, not SHORT."""
    long_only_strategy = replace(STRATEGY, params={**STRATEGY.params, "long_only": True})
    candles = _falling_candles(60)
    signal = STACK_PATH.evaluate(long_only_strategy, DataBundle(candles=candles))
    assert signal.decision == "WAIT"


def test_flat_series_returns_wait():
    """A flat/sideways series should result in WAIT: stacks are balanced and
    slope is near zero."""
    candles = _flat_candles(60)
    signal = STACK_PATH.evaluate(STRATEGY, DataBundle(candles=candles))
    assert signal.decision == "WAIT"
    assert "no consensus" in signal.reason


def test_evaluate_dispatch_matches_direct_call():
    """The entry-point dispatch via `evaluate()` should produce the same result
    as calling STACK_PATH.evaluate() directly."""
    candles = _rising_candles(60)
    bundle = DataBundle(candles=candles)
    direct = STACK_PATH.evaluate(STRATEGY, bundle)
    dispatched = evaluate(STRATEGY, bundle)
    assert direct == dispatched


# --- Signal metadata tests ----------------------------------------------------

def test_signal_tier_matches_strategy_status():
    """A paper strategy should produce signals with tier='paper'."""
    candles = _rising_candles(60)
    signal = STACK_PATH.evaluate(STRATEGY, DataBundle(candles=candles))
    if signal.decision != "WAIT":
        assert signal.tier == "paper"


def test_signal_fraction_matches_strategy_fraction():
    candles = _rising_candles(60)
    signal = STACK_PATH.evaluate(STRATEGY, DataBundle(candles=candles))
    if signal.decision != "WAIT":
        assert signal.fraction == 0.01


def test_signal_risk_notes_contain_diagnostics():
    candles = _rising_candles(60)
    signal = STACK_PATH.evaluate(STRATEGY, DataBundle(candles=candles))
    if signal.decision != "WAIT":
        assert "MSD=" in signal.risk_notes
        assert "ShortestPath" in signal.risk_notes


# --- Determinism test ---------------------------------------------------------

def test_deterministic_on_synth_candles():
    """Running twice on the same deterministic input produces the same signal."""
    candles = make_candles(100)
    bundle = DataBundle(candles=candles)
    sig1 = STACK_PATH.evaluate(STRATEGY, bundle)
    sig2 = STACK_PATH.evaluate(STRATEGY, bundle)
    assert sig1 == sig2


# --- Registry test ------------------------------------------------------------

def test_strategy_registry_discovers_stack_path():
    from moonface.strategies.registry import supports_strategy
    assert supports_strategy("stack_path")
