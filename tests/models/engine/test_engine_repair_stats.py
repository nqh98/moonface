"""Dispatch, generalized block CI, and the Gate-1/Gate-2 ordering criteria."""
import pytest

from moonface.models.engine.audit import block_ci
from moonface.models.engine.repair import (
    CI_HI_Q,
    CI_LO_Q,
    block_ci_q,
    gate1_candidate,
    gate2_candidate,
    monotone_by_edges,
    score_trade,
    train_quartile_edges,
)

from tests.helpers_repair import ht

_ITEMS = [(i, float(i % 7)) for i in range(0, 3360)]


def _key(pair):
    return pair[0]


def _mean(sample):
    return sum(v for _, v in sample) / len(sample)


def test_block_ci_q_generalizes_the_audit_ci():
    assert block_ci_q(_ITEMS, _key, _mean, 0.025, 0.975) == \
        block_ci(_ITEMS, _key, _mean)


def test_family_corrected_ci_is_wider_than_95():
    lo95, hi95 = block_ci_q(_ITEMS, _key, _mean, 0.025, 0.975)
    lo_c, hi_c = block_ci_q(_ITEMS, _key, _mean, CI_LO_Q, CI_HI_Q)
    assert lo_c <= lo95 and hi_c >= hi95


def test_score_trade_dispatch():
    t = ht(0, 70, 0.1)
    assert score_trade("c1_tier_merge", (40, 60), t) == 2.0
    assert score_trade("c2_side_vol", {("LONG", "normal"): 5}, t) == 65.0
    assert score_trade("c3_isotonic", ((40, -0.1), (70, 0.2)), t) == 0.2
    with pytest.raises(ValueError):
        score_trade("bogus", None, t)


def test_train_quartile_edges_and_monotone_buckets():
    values = [float(v) for v in range(1, 101)]
    q1, q2, q3 = train_quartile_edges(values)
    assert (q1, q2, q3) == (25.0, 50.0, 75.0)
    trades = ([ht(i * 200, 45, -0.2) for i in range(100)]
              + [ht((100 + i) * 200, 80, 0.2) for i in range(100)])
    mono = monotone_by_edges(trades, "c1_tier_merge", (40, 60, 75),
                             (1.0, 2.0, 3.0))
    assert mono["monotone"] is True
    bad = ([ht(i * 200, 45, 0.2) for i in range(100)]
           + [ht((100 + i) * 200, 80, -0.2) for i in range(100)])
    mono_bad = monotone_by_edges(bad, "c1_tier_merge", (40, 60, 75),
                                 (1.0, 2.0, 3.0))
    assert mono_bad["monotone"] is False


def _gate_panel(n_blocks=70):
    """Each 168-bar block holds one (bad-low, good-mid, bad-top) trio, so the
    block bootstrap resamples i.i.d. trios: base rho ~ 0, C1-merged rho > 0."""
    trades = []
    for b in range(n_blocks):
        base_i = b * 1008
        trades.append(ht(base_i, 45, -0.4))
        trades.append(ht(base_i + 10, 65, 0.4 + 0.001 * b))
        trades.append(ht(base_i + 20, 80, -0.4 + 0.001 * b))
    return trades


def test_gate1_passes_repairing_candidate_and_fails_identity():
    panel = _gate_panel()
    good = gate1_candidate("c1_tier_merge", (40, 60), panel, panel)
    assert good["passed"] is True
    assert good["delta_rho"] > 0
    identity = gate1_candidate("c1_tier_merge", (40, 60, 75), panel, panel)
    assert identity["passed"] is False


def test_gate2_point_sign_rule():
    panel = _gate_panel()
    good = gate2_candidate("c1_tier_merge", (40, 60), panel, panel)
    assert good["passed"] is True
    identity = gate2_candidate("c1_tier_merge", (40, 60, 75), panel, panel)
    assert identity["passed"] is False


def test_gates_fail_below_panel_floor():
    small = _gate_panel(n_blocks=10)
    assert gate1_candidate("c1_tier_merge", (40, 60),
                           small, small)["passed"] is False
    assert gate2_candidate("c1_tier_merge", (40, 60),
                           small, small)["passed"] is False
