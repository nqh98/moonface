from dataclasses import FrozenInstanceError

from moonface.research.breadth_internal import grid
from moonface.research.breadth_internal.evaluate import evaluate_spec


def test_grid_has_four_frozen_specs() -> None:
    specs = grid.all_specs()
    assert [spec.key for spec in specs] == [
        "breadth_thrust",
        "net_new_highs",
        "breadth_divergence",
        "dispersion_regime",
    ]
    for spec in specs:
        assert spec.exit_name == "atr_trail"
        assert spec.exit_params == {
            "k_trail": 2.0,
            "max_bars": 120,
            "atr_period": 14,
        }
        assert spec.h == 48
        try:
            spec.key = "mutated"  # type: ignore[misc]
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError("SignalSpec must be frozen")


def test_thrust_spec_matches_frozen_v1_params() -> None:
    spec = next(s for s in grid.all_specs() if s.key == "breadth_thrust")
    assert spec.params == {
        "base_period": 50,
        "low_band": 0.40,
        "high_band": 0.60,
        "window": 6,
    }


def test_signal_spec_params_are_not_mutable_in_place() -> None:
    spec = grid.all_specs()[0]

    try:
        spec.params["base_period"] = 60  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("SignalSpec.params must be read-only")

    try:
        spec.exit_params["k_trail"] = 3.0  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("SignalSpec.exit_params must be read-only")


def test_evaluate_spec_returns_metrics_and_records_shape() -> None:
    spec = grid.all_specs()[0]
    out = evaluate_spec({}, [], spec)
    assert out["key"] == "breadth_thrust"
    assert set(out) == {"key", "metrics", "records"}
    assert isinstance(out["metrics"], dict)
    assert out["metrics"]["trade_count"] == 0
    assert out["records"] == []
