from moonface.models.engine.moe.config_moe import MoeConfig
from moonface.models.engine.moe.regimes import MoeRegime
from moonface.models.engine.moe.weights import EdgeSample, fit_weights, p_eff

EXPERTS = ["A", "B", "C"]


def _samples(regime, expert, edge, n):
    return [EdgeSample(regime, expert, 1, edge) for _ in range(n)]


def test_negative_edge_cells_are_zeroed():
    samples = _samples(MoeRegime.TREND, "A", 0.20, 60) + _samples(
        MoeRegime.TREND, "B", -0.20, 60
    )
    W = fit_weights(samples, EXPERTS, MoeConfig(), n_train_trades=600)
    assert W[MoeRegime.TREND]["A"] > 0.0
    assert W[MoeRegime.TREND]["B"] == 0.0


def test_thin_regime_shrinks_toward_equal_weight():
    strong = _samples(MoeRegime.TREND, "A", 0.20, 500)
    thin = _samples(MoeRegime.CHOP, "A", 0.20, 31)
    W = fit_weights(strong + thin, EXPERTS, MoeConfig(), n_train_trades=1000)
    assert 0.0 < W[MoeRegime.CHOP]["A"] < W[MoeRegime.TREND]["A"]


def test_budget_caps_p_eff():
    samples = []
    for i, regime in enumerate([MoeRegime.TREND, MoeRegime.CHOP, MoeRegime.STRESS]):
        for expert in EXPERTS:
            samples += _samples(regime, expert, 0.05 + 0.01 * i, 40)
    W = fit_weights(samples, EXPERTS, MoeConfig(), n_train_trades=100)
    assert p_eff(W) <= 2


def test_null_edges_collapse_to_zero_pool():
    samples = _samples(MoeRegime.TREND, "A", 0.0, 100)
    W = fit_weights(samples, EXPERTS, MoeConfig(), n_train_trades=1000)
    assert p_eff(W) == 0
