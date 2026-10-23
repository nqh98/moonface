# tests/test_regime_signals.py
from datetime import datetime, timezone

from moonface.research.edge.regime_signals import seasonality, vol_regime
from moonface.core.bundle import DataBundle
from moonface.research.entries import generate_entries
from moonface.kernel.synth import make_candles


def test_vol_regime_emits_sided_entries_after_warmup():
    candles = make_candles(400, noise=0.02)
    entries = vol_regime(candles, {"window": 90, "mode": "low", "trend_n": 50})
    assert entries
    warmup = max(90 * 2, 50)
    assert all(i >= warmup for i, _s in entries)
    assert all(s in ("LONG", "SHORT") for _i, s in entries)


def test_vol_regime_modes_partition_the_signal():
    candles = make_candles(400, noise=0.02)
    low = vol_regime(candles, {"window": 90, "mode": "low", "trend_n": 50})
    high = vol_regime(candles, {"window": 90, "mode": "high", "trend_n": 50})
    assert not (set(i for i, _ in low) & set(i for i, _ in high))


def test_vol_regime_is_causal():
    candles = make_candles(400, noise=0.02)
    cut = 300
    params = {"window": 90, "mode": "low", "trend_n": 50}
    full = [(i, s) for i, s in vol_regime(candles, params) if i < cut]
    assert vol_regime(candles[:cut], params) == full


def test_seasonality_fires_only_on_configured_weekdays():
    candles = make_candles(500)
    params = {"weekdays": [0], "trend_n": 100}
    entries = seasonality(candles, params)
    assert entries
    for i, _side in entries:
        wd = datetime.fromtimestamp(candles[i].timestamp_ms / 1000,
                                    tz=timezone.utc).weekday()
        assert wd == 0


def test_families_are_registered():
    bundle = DataBundle(candles=make_candles(400, noise=0.02))
    assert generate_entries("vol_regime",
                            {"window": 90, "mode": "low", "trend_n": 50}, bundle) \
        == vol_regime(bundle.candles, {"window": 90, "mode": "low", "trend_n": 50})
    assert generate_entries("seasonality", {"weekdays": [0], "trend_n": 100},
                            bundle) is not None
