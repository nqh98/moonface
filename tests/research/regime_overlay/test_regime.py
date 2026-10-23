from moonface.research.exogenous.fred_data import MacroPoint
from moonface.research.regime_overlay.regime import REGIME_DEFS, regime_at

DAY = 86_400_000


def _series(start_ms, values, step=DAY):
    return [MacroPoint(ts_ms=start_ms + i * step, value=v) for i, v in enumerate(values)]


def test_four_defs_with_stable_ids():
    assert [d.id for d in REGIME_DEFS] == ["R1", "R2", "R3", "R4"]
    assert len({d.id for d in REGIME_DEFS}) == 4


def test_r1_equity_riskon_uses_20d_momentum_sign():
    r1 = next(d for d in REGIME_DEFS if d.id == "R1")
    sp = _series(0, [100.0] * 21 + [110.0])      # +10% over last 20d
    decision = 21 * DAY + DAY                      # after lag=1 publication of last point
    assert regime_at(decision, r1, {"SP500": sp}) == "risk_on"
    sp_down = _series(0, [100.0] * 21 + [90.0])
    assert regime_at(decision, r1, {"SP500": sp_down}) == "risk_off"


def test_missing_macro_defaults_risk_off():
    r1 = next(d for d in REGIME_DEFS if d.id == "R1")
    assert regime_at(10 * DAY, r1, {"SP500": []}) == "risk_off"


def test_no_lookahead_value_not_yet_published():
    r1 = next(d for d in REGIME_DEFS if d.id == "R1")
    sp = _series(0, [100.0] * 21 + [110.0])
    # decision BEFORE the last point's publication (sample ts + lag 1 day)
    early = 21 * DAY                               # last point sample ts, not yet +1d published
    # with only 21 flat points visible, 20d change is 0 -> not >0 -> risk_off
    assert regime_at(early, r1, {"SP500": sp}) == "risk_off"


def test_r3_requires_momentum_and_calm_vix():
    r3 = next(d for d in REGIME_DEFS if d.id == "R3")
    sp = _series(0, [100.0] * 21 + [110.0])
    decision = 22 * DAY
    calm = _series(0, [15.0] * 23)
    stressed = _series(0, [35.0] * 23)
    assert regime_at(decision, r3, {"SP500": sp, "VIXCLS": calm}) == "risk_on"
    assert regime_at(decision, r3, {"SP500": sp, "VIXCLS": stressed}) == "risk_off"


def test_r4_dollar_weak_when_usd_falls():
    r4 = next(d for d in REGIME_DEFS if d.id == "R4")
    decision = 22 * DAY
    usd_down = _series(0, [100.0] * 21 + [95.0])
    usd_up = _series(0, [100.0] * 21 + [105.0])
    assert regime_at(decision, r4, {"DTWEXBGS": usd_down}) == "risk_on"
    assert regime_at(decision, r4, {"DTWEXBGS": usd_up}) == "risk_off"
