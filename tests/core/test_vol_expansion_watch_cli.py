import json

import tools.lanes.vol_expansion_watch as cli
from moonface.core.models import Candle

_TF = 14_400_000


def _series(n, start_ms=0):
    out, px = [], 1000.0
    for k in range(n):
        if k % 7 == 0:
            op = px
            px = px * 1.003 + 30
            hi, lo = px + 5, op - 5
        else:
            op = px
            px = px * 1.0003
            hi, lo = max(op, px) + 3, min(op, px) - 3
        out.append(Candle(timestamp_ms=start_ms + k * _TF, open=op, high=hi,
                          low=lo, close=px, volume=1.0))
    return out


def test_register_writes_frozen_config_and_doc(tmp_path):
    cfg_path = tmp_path / "vol_expansion_4h.json"
    rc = cli.main(["--register", "--config", str(cfg_path)])
    assert rc == 0
    cfg = json.loads(cfg_path.read_text())
    assert cfg["family"] == "vol_expansion"
    assert cfg["params"]["mult"] == 3.0
    assert cfg["exit_name"] == "atr_trail"
    assert cfg["status"] == "paper"
    assert isinstance(cfg["t0_ms"], int)
    assert (tmp_path / "VOL_EXPANSION_FORWARD_REGISTRATION.md").exists()


def test_report_is_read_only_and_emits_gate(tmp_path, monkeypatch):
    cfg_path = tmp_path / "vol_expansion_4h.json"
    cli.main(["--register", "--config", str(cfg_path)])
    monkeypatch.setattr(cli, "_load_candles", lambda cfg, cache_dir: _series(1500))
    rc = cli.main(["--report", "--config", str(cfg_path), "--json"])
    assert rc == 0
    # report must not have created a journal or any promotion artifact
    assert not (tmp_path / "signals.jsonl").exists()


def test_report_starts_inconclusive_when_no_forward_trades(tmp_path, monkeypatch):
    cfg_path = tmp_path / "vol_expansion_4h.json"
    cli.main(["--register", "--config", str(cfg_path)])
    # all candles BEFORE t0 -> 0 forward trades -> gate not passed
    monkeypatch.setattr(cli, "_load_candles",
                        lambda cfg, cache_dir: _series(800, start_ms=0))
    cfg = json.loads(cfg_path.read_text())
    cfg["t0_ms"] = 10 ** 13  # far future
    cfg_path.write_text(json.dumps(cfg))
    rep = cli.build_report(cfg, _series(800))
    assert rep["closed_trades"] == 0
    assert rep["gate"]["passed"] is False
