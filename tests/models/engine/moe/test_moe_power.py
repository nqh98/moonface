from moonface.models.engine.moe.power import allowed_p_eff, check_power_budget


def test_allowed_scales_with_trades():
    assert allowed_p_eff(300, 50) == 6
    assert allowed_p_eff(36, 50) == 0


def test_m_never_below_30():
    assert allowed_p_eff(300, 10) == 10


def test_check_rejects_overspend_and_empty():
    assert check_power_budget(300, 6, 50) is True
    assert check_power_budget(300, 7, 50) is False
    assert check_power_budget(300, 0, 50) is False
    assert check_power_budget(36, 1, 50) is False
