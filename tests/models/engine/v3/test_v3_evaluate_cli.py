"""CLI wiring with injectable loaders (hermetic - no network/bundle)."""

import json
import types

from moonface.models.engine.v3.evaluate import VERDICTS
from tools.engine.v3_evaluate import run

from tests.helpers_v3 import uptrend

import pytest

pytestmark = pytest.mark.slow


def _loader_factory():
    def load(asset, start_ms, end_ms, cache_dir):
        return types.SimpleNamespace(candles=uptrend(1200))

    return {"BTC": load, "ETH": load, "SOL": load}


def test_cli_runs_and_writes_report(tmp_path):
    out = tmp_path / "rep.json"
    rc = run(
        ["--start-ms", "0", "--end-ms", "1", "--warmup", "400",
         "--lookback", "400", "--out", str(out)],
        loaders=_loader_factory(),
    )
    assert rc == 0
    report = json.loads(out.read_text())
    assert report["verdict"] in VERDICTS
