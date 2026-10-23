from moonface.core.bundle import DataBundle
from moonface.research.entries import generate_entries
from moonface.kernel.synth import make_candles
from moonface.models.evaluate import Signal, evaluate
from moonface.strategies.spec import PromotedStrategy

STRATEGY = PromotedStrategy(
    family="donchian_break", params={"n": 20},
    exit={"name": "fixed_bracket",
          "params": {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0}},
    fraction=0.01, status="paper",
    asset={"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "4h"},
    provenance={}, max_drawdown_p95=0.2)


def test_parity_with_probe_entries():
    """For every entry the probe emits at index i, evaluating the candle
    prefix [:i+1] must produce the same side; a quiet index must produce WAIT.
    This is the test that prevents live/backtest drift."""
    candles = make_candles(400)
    entries = generate_entries("donchian_break", {"n": 20},
                               DataBundle(candles=candles))
    assert entries, "synthetic drift data must produce entries"
    entry_index = dict(entries)
    for i, side in entries:
        sig = evaluate(STRATEGY, DataBundle(candles=candles[: i + 1]))
        assert sig.decision == side, f"index {i}"
    quiet = next(i for i in range(100, 399) if i not in entry_index)
    sig = evaluate(STRATEGY, DataBundle(candles=candles[: quiet + 1]))
    assert sig.decision == "WAIT"


def test_non_wait_signal_carries_prices():
    candles = make_candles(400)
    i, side = generate_entries("donchian_break", {"n": 20},
                               DataBundle(candles=candles))[-1]
    sig = evaluate(STRATEGY, DataBundle(candles=candles[: i + 1]))
    assert sig.decision == side
    assert sig.price == candles[i].close
    assert sig.fraction == 0.01
    if side == "LONG":
        assert sig.invalidation < sig.price
    else:
        assert sig.invalidation > sig.price


def test_too_few_candles_is_wait():
    candles = make_candles(3)
    sig = evaluate(STRATEGY, DataBundle(candles=candles))
    assert sig.decision == "WAIT"
    assert isinstance(sig, Signal)


def test_signal_has_defaulted_baseline_fields():
    from moonface.models.evaluate import Signal
    # backward-compatible 5-positional construction still works
    s = Signal("WAIT", None, None, None, "because")
    assert s.confidence == 0.0
    assert s.timeframe == ""
    assert s.risk_notes == ""
    assert s.tier == ""
    # new fields are settable by keyword
    s2 = Signal("LONG", 100.0, 95.0, 0.01, "fired",
                confidence=0.6, timeframe="4h", risk_notes="r", tier="baseline")
    assert s2.confidence == 0.6
    assert s2.tier == "baseline"
