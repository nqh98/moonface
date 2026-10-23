from moonface.research.breadth_confirm.xasset_grid import ASSETS, K, lead_specs


def test_constants_frozen():
    assert ASSETS == ("ETHUSDT", "SOLUSDT")
    assert K == 4  # 2 leads x 2 assets


def test_lead_specs_are_the_two_frozen_leads():
    specs = {s.key: s for s in lead_specs()}
    assert set(specs) == {"net_new_highs", "breadth_momentum"}

    nnh = specs["net_new_highs"]
    assert dict(nnh.params) == {"n": 20, "long_thr": 0.30, "short_thr": -0.30}
    assert nnh.h == 48

    mom = specs["breadth_momentum"]
    assert dict(mom.params) == {"n": 10, "thr": 0.10, "base_period": 50}
    assert mom.h == 48

    for s in specs.values():
        assert s.exit_name == "atr_trail"
        assert dict(s.exit_params) == {"k_trail": 2.0, "max_bars": 120, "atr_period": 14}
