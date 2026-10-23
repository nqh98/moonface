# tests/test_pathsig_policy.py
from moonface.research.pathsig.policy import Distribution, decide


def test_low_edge_waits():
    dist = Distribution(p_up=0.52, exp_ret_r=0.05, exp_mae_r=-1.0, exp_mfe_r=1.0)
    d = decide(dist, edge_threshold=0.2, kelly_scale=1.0, max_fraction=0.02)
    assert d.action == "WAIT"
    assert d.size == 0.0


def test_strong_positive_edge_goes_long_and_sizes():
    dist = Distribution(p_up=0.7, exp_ret_r=0.8, exp_mae_r=-1.0, exp_mfe_r=2.0)
    d = decide(dist, edge_threshold=0.2, kelly_scale=0.02, max_fraction=0.02)
    assert d.action == "LONG"
    assert 0.0 < d.size <= 0.02


def test_negative_edge_goes_short():
    dist = Distribution(p_up=0.3, exp_ret_r=-0.8, exp_mae_r=-1.0, exp_mfe_r=2.0)
    d = decide(dist, edge_threshold=0.2, kelly_scale=0.02, max_fraction=0.02)
    assert d.action == "SHORT"


def test_size_is_capped():
    dist = Distribution(p_up=0.99, exp_ret_r=50.0, exp_mae_r=-0.1, exp_mfe_r=99.0)
    d = decide(dist, edge_threshold=0.2, kelly_scale=10.0, max_fraction=0.02)
    assert d.size == 0.02
