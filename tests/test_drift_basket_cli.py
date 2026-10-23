import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "drift_basket_cli", ROOT / "tools" / "drift_basket" / "drift_basket.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

DAY = 86_400_000


def test_parser_requires_a_mode():
    import pytest
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--start-ms", "0", "--end-ms", "1",
                                       "--out-dir", "/tmp/x"])


def test_register_writes_frozen_params(tmp_path):
    out = tmp_path / "out"
    rc = cli.run(["--register", "--start-ms", "0", "--end-ms", str(10 * DAY),
                  "--out-dir", str(out)])
    assert rc == 0
    reg = json.loads((out / "PREREGISTRATION.json").read_text())
    assert reg["params"]["donchian_n"] == 20
    assert reg["params"]["top_n"] == 30
    assert reg["params"]["vol_target_annual"] == 0.20
    assert reg["lane"] == "btc_drift_basket"


def test_funding_daily_sums_intraday_pairs():
    pairs = [(0, 0.0001), (3_600_000, 0.0001), (DAY, 0.0002)]
    daily = cli._funding_daily(pairs)
    assert abs(daily[0] - 0.0002) < 1e-12       # two intraday funds on day 0
    assert abs(daily[DAY] - 0.0002) < 1e-12
