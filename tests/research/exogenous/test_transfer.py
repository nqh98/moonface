from moonface.research.exogenous.transfer import transfer_passes


def test_transfer_requires_all_assets_pass():
    assert transfer_passes({"ETHUSDT": {"passed": True}, "SOLUSDT": {"passed": True}})
    assert not transfer_passes({"ETHUSDT": {"passed": True}, "SOLUSDT": {"passed": False}})
