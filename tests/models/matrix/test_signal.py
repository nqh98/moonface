from dataclasses import FrozenInstanceError, fields

from moonface.models.matrix.signal import Signal


def test_signal_fields_and_frozen():
    assert [field.name for field in fields(Signal)] == [
        "ts_ms",
        "asset",
        "primary",
        "direction",
        "state_tag",
        "horizon_bars",
        "expected_r",
        "conviction",
        "target_exposure",
    ]

    signal = Signal(1, "BTC", "primary", 1, "state", 4, 1.5, 0.7, 0.25)

    try:
        signal.ts_ms = 2
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Signal must be frozen")
