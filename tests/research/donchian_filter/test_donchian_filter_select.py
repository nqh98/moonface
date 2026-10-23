from moonface.research.donchian_filter.select import (
    DESTROYS_INACTIVE,
    IMPROVES,
    NEUTRAL,
    holdout_verdict,
    qualifies,
    select_threshold,
)


def _m(n=100, net=80.0, dd=-10.0):
    return {
        "n": n,
        "net_r": net,
        "expectancy_r": net / max(n, 1),
        "profit_factor": 1.8,
        "max_dd_r": dd,
        "mar": 5.0,
    }


def test_qualifies_pass():
    base = _m(net=80.0, dd=-14.0, n=100)
    gated = _m(net=75.0, dd=-9.0, n=70)
    ok, reasons = qualifies(base, gated, base_rf=0.6, gated_rf=0.7)
    assert ok and reasons == []


def test_qualifies_fails_on_trend_capture():
    base = _m(net=80.0, dd=-14.0, n=100)
    gated = _m(net=50.0, dd=-5.0, n=70)
    ok, reasons = qualifies(base, gated, 0.6, 0.7)
    assert not ok and any("trend capture" in r for r in reasons)


def test_qualifies_fails_on_degenerate_activity():
    base = _m(net=80.0, dd=-14.0, n=100)
    gated = _m(net=75.0, dd=-2.0, n=20)
    ok, reasons = qualifies(base, gated, 0.6, 0.9)
    assert not ok and any("activity" in r for r in reasons)


def test_select_picks_least_negative_dd_among_qualifiers():
    rows = [
        {"threshold": 18, "gated": _m(net=78, dd=-12, n=80), "robust_frac": 0.7, "qualifies": True},
        {"threshold": 20, "gated": _m(net=76, dd=-8, n=70), "robust_frac": 0.7, "qualifies": True},
        {"threshold": 25, "gated": _m(net=40, dd=-3, n=30), "robust_frac": 0.5, "qualifies": False},
    ]
    assert select_threshold(rows) == 20


def test_select_returns_none_when_no_qualifier():
    rows = [{"threshold": 18, "gated": _m(), "robust_frac": 0.5, "qualifies": False}]
    assert select_threshold(rows) is None


def test_holdout_verdict_labels():
    base = _m(net=-12.0, dd=-15.0, n=30)
    assert holdout_verdict(base, _m(net=-2.0, dd=-9.0, n=25)) == IMPROVES
    assert holdout_verdict(base, _m(net=-13.0, dd=-16.0, n=25)) == NEUTRAL
    assert holdout_verdict(base, _m(net=-40.0, dd=-30.0, n=25)) == DESTROYS_INACTIVE
    assert holdout_verdict(base, _m(net=-2.0, dd=-9.0, n=4)) == DESTROYS_INACTIVE
