import importlib.util
import sys
from pathlib import Path

import pytest

import tools.breadth.breadth as _tools_breadth

ROOT = Path(__file__).resolve().parents[1]

_saved = sys.modules.get("breadth")
sys.modules["breadth"] = _tools_breadth
try:
    spec = importlib.util.spec_from_file_location(
        "breadth_xasset_confirm", ROOT / "tools" / "breadth" / "breadth_xasset_confirm.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
finally:
    if _saved is not None:
        sys.modules["breadth"] = _saved
    else:
        sys.modules.pop("breadth", None)


def test_parser_requires_a_mode():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--start-ms", "0", "--end-ms", "1",
                                       "--out-dir", "/tmp/x"])


def test_lead_eval_modes_match_construction():
    # net_new_highs is iid (non-overlap h=48); breadth_momentum is block_len=8.
    _, nnh_block, nnh_len = cli.LEAD_EVAL["net_new_highs"]
    _, mom_block, mom_len = cli.LEAD_EVAL["breadth_momentum"]
    assert nnh_block is False and nnh_len == 1
    assert mom_block is True and mom_len == 8


def test_anchor_constants_match_home_lanes():
    assert cli.ANCHOR["net_new_highs"] == {
        "val_exp": 0.5323, "seal_exp": 0.2588, "val_n": 34, "seal_n": 32}
    assert cli.ANCHOR["breadth_momentum"] == {
        "val_exp": 0.1652, "seal_exp": 0.1424, "val_n": 327, "seal_n": 326}


def test_anchor_ok_accepts_matching_and_rejects_drift():
    val = {"metrics": {"expectancy_r": 0.5323, "trade_count": 34}}
    seal = {"metrics": {"expectancy_r": 0.2588, "trade_count": 32}}
    assert cli._anchor_ok("net_new_highs", val, seal) is True

    bad = {"metrics": {"expectancy_r": 0.10, "trade_count": 34}}
    assert cli._anchor_ok("net_new_highs", bad, seal) is False
