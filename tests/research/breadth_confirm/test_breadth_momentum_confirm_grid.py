from moonface.research.breadth_confirm.momentum_grid import (
    DISCOVERY_SLICE,
    GATED_SLICES,
    K,
    MOMENTUM_BLOCK_LEN,
    breadth_momentum_spec,
)


def test_constants_frozen():
    assert DISCOVERY_SLICE == (0, 20)
    assert GATED_SLICES == ((20, 40), (40, 60))
    assert MOMENTUM_BLOCK_LEN == 8
    assert K == 2


def test_gated_slices_disjoint_from_discovery_and_each_other():
    def span(s):
        return set(range(s[0], s[1]))

    disc = span(DISCOVERY_SLICE)
    for s in GATED_SLICES:
        assert span(s) & disc == set()
    assert span(GATED_SLICES[0]) & span(GATED_SLICES[1]) == set()


def test_spec_is_byte_frozen_breadth_momentum():
    spec = breadth_momentum_spec()
    assert spec.key == "breadth_momentum"
    assert spec.builder == "breadth_momentum"
    assert dict(spec.params) == {"n": 10, "thr": 0.10, "base_period": 50}
    assert spec.exit_name == "atr_trail"
    assert dict(spec.exit_params) == {"k_trail": 2.0, "max_bars": 120, "atr_period": 14}
    assert spec.h == 48
