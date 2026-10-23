from moonface.models.engine.moe.combiner import confluence, decide_moe, master_score
from moonface.models.engine.moe.config_moe import MoeConfig
from moonface.models.engine.moe.regimes import MoeRegime

W = {
    MoeRegime.TREND: {"A": 1.0, "B": 1.0, "C": 0.0},
    MoeRegime.CHOP: {"A": 0.0, "B": 0.0, "C": 0.0},
    MoeRegime.STRESS: {"A": 1.0, "B": 0.0, "C": 0.0},
}


def test_master_score_is_row_normalized():
    m = master_score({"A": 1.0, "B": 1.0, "C": -1.0}, W[MoeRegime.TREND], 1e-9)
    assert abs(m - 1.0) < 1e-6


def test_flat_regime_never_trades():
    d = decide_moe({"A": 1.0, "B": 1.0}, MoeRegime.FLAT, W, MoeConfig())
    assert d.action == "WAIT"


def test_confluence_guard_blocks_single_voter():
    d = decide_moe({"A": 0.9, "B": 0.0, "C": 0.0}, MoeRegime.TREND, W, MoeConfig())
    assert d.action == "WAIT"


def test_high_conviction_confluent_enters():
    d = decide_moe({"A": 0.9, "B": 0.8, "C": 0.0}, MoeRegime.TREND, W, MoeConfig())
    assert d.action == "ENTER"
    assert d.direction == 1
    assert d.score >= MoeConfig().tau


def test_empty_weight_row_scores_zero():
    m = master_score({"A": 1.0, "B": 1.0}, W[MoeRegime.CHOP], 1e-9)
    assert m == 0.0


def test_confluence_counts_only_weighted_voters():
    assert confluence({"A": 1.0, "B": -1.0, "C": 1.0}, W[MoeRegime.TREND], 1) == 1
