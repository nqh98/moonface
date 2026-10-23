import importlib.util
import sys
from pathlib import Path

import pytest

import tools.breadth.breadth as _tools_breadth

ROOT = Path(__file__).resolve().parents[1]

# The CLI does `from breadth import ...`. Pytest's prepend collection caches the
# bare name `breadth` as the tests/research/breadth/ test package; point `breadth`
# at tools/breadth.py for the CLI load, then restore the prior binding.
_saved = sys.modules.get("breadth")
sys.modules["breadth"] = _tools_breadth
try:
    spec = importlib.util.spec_from_file_location(
        "breadth_momentum_confirm", ROOT / "tools" / "breadth" / "breadth_momentum_confirm.py")
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


def test_xcheck_constants_match_lane2_discovery():
    # Frozen Lane 2 HF breadth_momentum top-20 discovery (overlapping, split_60_20_20).
    assert cli._XCHECK == {
        "validate_exp": 0.1652,
        "sealed_exp": 0.1424,
        "validate_n": 327,
        "sealed_n": 326,
    }


def test_xcheck_ok_accepts_matching_metrics():
    val = {"metrics": {"expectancy_r": 0.1652, "trade_count": 327}}
    seal = {"metrics": {"expectancy_r": 0.1424, "trade_count": 326}}
    assert cli._xcheck_ok(val, seal) is True


def test_xcheck_ok_rejects_drifted_expectancy():
    val = {"metrics": {"expectancy_r": 0.40, "trade_count": 327}}
    seal = {"metrics": {"expectancy_r": 0.1424, "trade_count": 326}}
    assert cli._xcheck_ok(val, seal) is False


def test_lane_verdict_confirmed_only_when_a_slice_confirms():
    assert cli._lane_verdict([{"status": "mechanism_unconfirmed"}]) == "mechanism_unconfirmed"
    assert cli._lane_verdict(
        [{"status": "mechanism_unconfirmed"}, {"status": "confirmed"}]) == "confirmed"
