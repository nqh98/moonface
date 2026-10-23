from moonface.research.breadth_confirm.grid import (
    BLOCK_LEN,
    DISCOVERY_SLICE,
    GATED_SLICES,
    K,
    net_new_highs_spec,
)


def test_constants_frozen():
    assert DISCOVERY_SLICE == (0, 20)
    assert GATED_SLICES == ((20, 40), (40, 60))
    assert BLOCK_LEN == 20
    assert K == 2


def test_gated_slices_disjoint_from_discovery_and_each_other():
    def span(s):
        return set(range(s[0], s[1]))

    disc = span(DISCOVERY_SLICE)
    for s in GATED_SLICES:
        assert span(s) & disc == set()
    assert span(GATED_SLICES[0]) & span(GATED_SLICES[1]) == set()


def test_spec_is_byte_frozen_net_new_highs():
    spec = net_new_highs_spec()
    assert spec.key == "net_new_highs"
    assert spec.builder == "net_new_highs"
    assert dict(spec.params) == {"n": 20, "long_thr": 0.30, "short_thr": -0.30}
    assert spec.exit_name == "atr_trail"
    assert dict(spec.exit_params) == {"k_trail": 2.0, "max_bars": 120, "atr_period": 14}
    assert spec.h == 48
