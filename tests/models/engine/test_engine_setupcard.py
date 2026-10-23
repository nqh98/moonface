# tests/test_engine_setupcard.py
from moonface.models.engine.confluence import Decision
from moonface.models.engine.engine import NO_CLAIM
from moonface.models.engine.modules.base import ModuleScore
from moonface.models.engine.setupcard import CardPlan, render


def _m(module, direction, points, archetype="trend", data_ok=True,
      evidence=("above 20ma",)):
    return ModuleScore(module=module, direction=direction, points=points,
                       archetype=archetype, data_ok=data_ok, evidence=evidence)


def _modules():
    return (
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 20),
        _m("m1_sweep", 0, 0, "mean_revert", data_ok=False, evidence=()),
        _m("m2_reclaim", -1, 15, "mean_revert"),
    )


def _setup_decision():
    return Decision(
        action="SETUP", direction=1, archetype="trend", policy="ALLOW",
        score=80, max_attainable=100, breadth=4, tier="A", veto=None,
        shadow_score=None, shadow_direction=None, modules=_modules(),
        detail="SETUP trend LONG score=80 thr=60 breadth=4 tier=A",
    )


def _wait_decision():
    return Decision(
        action="WAIT", direction=0, archetype=None, policy=None,
        score=40, max_attainable=100, breadth=2, tier=None, veto=None,
        shadow_score=None, shadow_direction=None, modules=_modules(),
        detail="WAIT score=40 thr=60 breadth=2 (below threshold)",
    )


def _veto_decision():
    return Decision(
        action="WAIT", direction=0, archetype=None, policy=None,
        score=80, max_attainable=100, breadth=4, tier=None,
        veto="macro BEAR vetoes TREND long", shadow_score=80,
        shadow_direction=1,
        modules=_modules(),
        detail="WAIT macro BEAR vetoes TREND long; shadow_score=80 score=80"
              " thr=60 breadth=4",
    )


def _setup_plan():
    return CardPlan(action="OPEN", direction=1, entry=101.5, stop=98.0,
                    target=110.0, fraction=0.5, profile="WT", tier="A")


def _wait_plan():
    return CardPlan(action="WAIT", direction=0, entry=None, stop=None,
                    target=None, fraction=None, profile=None, tier=None)


def test_setup_card_shows_every_module_and_plan_fields():
    card = render(_setup_decision(), _setup_plan(), "active", "abc123def456")
    for m in _modules():
        assert m.module in card
    assert "A" in card  # tier
    assert "ALLOW" in card  # gate policy
    assert "101.5" in card  # entry
    assert "98.0" in card  # stop
    assert "110.0" in card  # target
    assert "discipline: active" in card
    assert NO_CLAIM in card
    assert "CONFLUENCE ENGINE v2" in card
    assert "abc123de" in card  # version[:8]


def test_wait_card_shows_wait_and_detail_and_still_lists_modules():
    card = render(_wait_decision(), _wait_plan(), "active", "abc123def456")
    assert "WAIT" in card
    assert "below threshold" in card
    assert NO_CLAIM in card
    for m in _modules():
        assert m.module in card


def test_no_data_module_marker():
    card = render(_wait_decision(), _wait_plan(), "active", "abc123def456")
    assert "[no data]" in card


def test_vetoed_decision_shows_veto_text_and_shadow_score():
    card = render(_veto_decision(), _wait_plan(), "active", "abc123def456")
    assert "macro BEAR vetoes TREND long" in card
    assert "80" in card


def test_render_none_decision_does_not_raise():
    card = render(None, _wait_plan(), "active", "abc123def456")
    assert "insufficient history" in card.lower()
    assert NO_CLAIM in card
    assert "CONFLUENCE ENGINE v2" in card
    assert "discipline: active" in card


def test_render_none_decision_shows_plan_action():
    card = render(None, CardPlan(action="WAIT", direction=0, entry=None,
                                 stop=None, target=None, fraction=None,
                                 profile=None, tier=None),
                 "cooldown", "abc123def456")
    assert "WAIT" in card
    assert "discipline: cooldown" in card


def test_long_evidence_is_truncated_not_raised():
    long_evidence = ("x" * 500,)
    modules = (_m("m1_macro", 1, 20, evidence=long_evidence),)
    decision = Decision(
        action="SETUP", direction=1, archetype="trend", policy="ALLOW",
        score=20, max_attainable=100, breadth=1, tier="B", veto=None,
        shadow_score=None, shadow_direction=None, modules=modules,
        detail="SETUP trend LONG",
    )
    card = render(decision, _setup_plan(), "active", "abc123def456")
    assert "m1_macro" in card
    # the raw 500-char evidence string must not appear verbatim (truncated)
    assert long_evidence[0] not in card
