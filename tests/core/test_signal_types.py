from moonface.core.signal_types import Signal, sentinel_extended, wait
from moonface.core.models import Candle
from moonface.core.bundle import DataBundle


def test_wait_builds_a_wait_signal():
    s = wait("no setup")
    assert s == Signal("WAIT", None, None, None, "no setup")


def test_sentinel_extended_appends_one_sentinel_candle():
    candles = [Candle(0, 1.0, 1.0, 1.0, 1.0, 0.0), Candle(3_600_000, 1.0, 1.0, 1.0, 1.0, 0.0)]
    bundle = DataBundle(candles=candles, funding=None, basis=None, feature=None)
    extended = sentinel_extended(bundle)
    assert len(extended.candles) == 3
    assert extended.candles[-1].timestamp_ms == 7_200_000
    assert extended.candles[-1].close == candles[-1].close
