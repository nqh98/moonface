import json

import pytest

from tools.regime_overlay.regime_overlay_btc import base_params, build_parser, run


def test_base_params_are_frozen_deployed_config():
    p = base_params()
    assert p.entry_n == 40 and p.trail_n == 20
    assert p.k_stop == 2.0 and p.atr_period == 14
    assert p.long_only is True


def test_register_writes_prereg(tmp_path):
    rc = run(["--register", "--out-dir", str(tmp_path)])
    assert rc == 0
    doc = json.loads((tmp_path / "PREREGISTRATION.json").read_text())
    assert doc["n_trials"] == 12
    assert len(doc["grid"]) == 12


def test_parser_requires_a_stage():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
