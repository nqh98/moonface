import importlib.util
import sys
from pathlib import Path

import tools.breadth.breadth as _tools_breadth

ROOT = Path(__file__).resolve().parents[1]

# The CLI does `from breadth import ...`. Pytest's prepend collection caches the
# bare name `breadth` as the tests/research/breadth/ test package; point `breadth`
# at tools/breadth.py for the CLI load, then restore the prior binding.
_saved = sys.modules.get("breadth")
sys.modules["breadth"] = _tools_breadth
try:
    spec = importlib.util.spec_from_file_location(
        "breadth_internal_hf", ROOT / "tools" / "breadth_internal" / "breadth_internal_hf.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
finally:
    if _saved is not None:
        sys.modules["breadth"] = _saved
    else:
        sys.modules.pop("breadth", None)


def test_block_xcheck_detects_autocorrelation_shift():
    records = [{"net_r": (0.9 ** 0) * 0.1 + (i % 5) * 0.2 - 0.4, "atr_frac": 0.02,
                "side": "LONG", "i": i} for i in range(80)]
    assert cli._block_xcheck(records) is True  # block CI differs from iid


def test_parser_requires_a_mode():
    import pytest
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--start-ms", "0", "--end-ms", "1",
                                       "--out-dir", "/tmp/x"])
