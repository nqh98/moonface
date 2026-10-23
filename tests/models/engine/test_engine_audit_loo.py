"""LOO marginal contribution (spec §5.2): panel fixed, direction-changed bars
excluded; Δρ = ρ(LOO score) - ρ(current score) on the kept subset, per split."""
import random

from moonface.models.engine.audit import loo_analysis, loo_book_score

from tests.helpers_audit import _fixture, _mk_row, _mk_trade

import pytest

pytestmark = pytest.mark.slow


def test_loo_book_score_drops_one_module():
    row = _mk_row(0, {"m1_macro": 20, "m2_breakout": 20, "m4_pullback": 5})
    assert loo_book_score(row, "trend", "m2_breakout") == (1, 25)
    assert loo_book_score(row, "trend", "m1_macro") == (1, 25)
    assert loo_book_score(row, "trend", "m1_sweep") == (1, 45)


def test_loo_classes_informative_vs_noise():
    panel, rows_by_index = _fixture()
    table = loo_analysis(panel, rows_by_index, "trend")
    m2 = table["m2_breakout"]["splits"]["pooled"]
    assert m2["class"] == "CONTRIBUTES"
    assert m2["delta_ci_95"][1] < 0
    # m4 is noise ADDED to the score, so removing it improves ordering with a
    # CI-clean positive delta: HARMFUL by the pre-reg CI-only rule.
    assert table["m4_pullback"]["splits"]["pooled"]["class"] == "HARMFUL"
    assert table["m1_macro"]["splits"]["pooled"]["class"] == "DEAD"
    assert table["m2_breakout"]["n_direction_changed"] == 0


def test_loo_reports_all_splits():
    panel, rows_by_index = _fixture()
    table = loo_analysis(panel, rows_by_index, "trend")
    assert set(table["m2_breakout"]["splits"]) == {"pooled", "LONG", "SHORT"}
    assert (table["m2_breakout"]["splits"]["LONG"]["class"]
            == table["m2_breakout"]["splits"]["pooled"]["class"])
    short = table["m2_breakout"]["splits"]["SHORT"]
    assert short["n_kept"] == 0
    assert short["class"] == "UNDERPOWERED"


def test_loo_underpowered_below_floor():
    panel, rows_by_index = _fixture(n=100)
    table = loo_analysis(panel, rows_by_index, "trend")
    assert table["m2_breakout"]["splits"]["pooled"]["class"] == "UNDERPOWERED"


def test_loo_small_delta_with_clean_ci_still_contributes():
    # Regression: the class is defined by CI position ALONE (pre-reg criteria);
    # a weak module (|Δρ| well under 0.1) whose CI is entirely < 0 must class
    # CONTRIBUTES, never DEAD on magnitude.
    rng = random.Random(11)
    rows_by_index, panel = {}, []
    for k in range(1200):
        i = k * 35
        m2 = rng.choice((0, 20))
        m4 = rng.choice((0, 5, 10))
        rows_by_index[i] = _mk_row(i, {"m1_macro": 20, "m2_breakout": m2,
                                       "m4_pullback": m4})
        net_r = round(0.004 * m2 + rng.gauss(0.0, 0.5), 4)
        panel.append(_mk_trade(i, 20 + m2 + m4, net_r))
    pooled = loo_analysis(panel, rows_by_index,
                          "trend")["m2_breakout"]["splits"]["pooled"]
    assert abs(pooled["delta_rho"]) < 0.1
    assert pooled["delta_ci_95"][1] < 0
    assert pooled["class"] == "CONTRIBUTES"
