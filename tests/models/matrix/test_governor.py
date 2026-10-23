from dataclasses import FrozenInstanceError, fields

import pytest

from moonface.models.matrix.governor import GovernorParams, size_stream


def test_governor_params_is_frozen_and_has_expected_fields() -> None:
    assert [field.name for field in fields(GovernorParams)] == [
        "target_vol",
        "size_min",
        "size_max",
        "dd_budget",
    ]

    params = GovernorParams(1.0, 0.1, 2.0, 3.0)

    with pytest.raises(FrozenInstanceError):
        params.target_vol = 2.0


def test_vol_target_downweights_higher_vol() -> None:
    params = GovernorParams(target_vol=0.2, size_min=0.0, size_max=10.0, dd_budget=10.0)

    sizes = size_stream(
        [
            (1.0, 0.1),
            (1.0, 0.4),
        ],
        params,
    )

    assert sizes == [2.0, 0.5]
    assert sizes[1] < sizes[0]


def test_size_is_clipped_to_bounds() -> None:
    params = GovernorParams(target_vol=1.0, size_min=0.25, size_max=1.5, dd_budget=10.0)

    sizes = size_stream(
        [
            (1.0, 10.0),
            (1.0, 0.1),
        ],
        params,
    )

    assert sizes == [0.25, 1.5]


def test_dd_throttle_bounds_drawdown() -> None:
    params = GovernorParams(target_vol=1.0, size_min=0.0, size_max=2.0, dd_budget=2.0)

    sizes = size_stream(
        [
            (1.0, 1.0),
            (-3.0, 1.0),
            (1.0, 1.0),
        ],
        params,
    )

    assert sizes == [1.0, 1.0, 0.0]


def test_later_outcomes_do_not_change_earlier_sizes() -> None:
    params = GovernorParams(target_vol=0.5, size_min=0.0, size_max=2.0, dd_budget=10.0)

    left = size_stream([(1.0, 0.5), (-4.0, 0.5)], params)
    right = size_stream([(1.0, 0.5), (-4.0, 0.5), (100.0, 0.5)], params)

    assert left == [1.0, 1.0]
    assert right[:2] == left
