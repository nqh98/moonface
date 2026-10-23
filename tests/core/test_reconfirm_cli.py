import json

from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from tools import reconfirm as cli

_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
       "1w": 604_800_000}
NOW = 1_700_000_000_000 - (1_700_000_000_000 % 604_800_000)  # 1w boundary


def _staircase(tf: str, n: int = 200) -> list[Candle]:
    """Fresh staircase ending at the last closed bar for this timeframe:
    deterministic ALIVE shape (every bar is a new donchian high)."""
    tf_ms = _MS[tf]
    end = (NOW // tf_ms) * tf_ms
    start = end - n * tf_ms
    return [Candle(start + i * tf_ms, 1000.0 + i, 1000.5 + i, 999.5 + i,
                   1000.0 + i, 10.0) for i in range(n)]


def _flat(tf: str, n: int = 200) -> list[Candle]:
    tf_ms = _MS[tf]
    end = (NOW // tf_ms) * tf_ms
    start = end - n * tf_ms
    return [Candle(start + i * tf_ms, 1000.0, 1000.5, 999.5, 1000.0, 10.0)
            for i in range(n)]


def _patch(monkeypatch, make_candles_for):
    monkeypatch.setattr(cli, "_now_ms", lambda: NOW)
    monkeypatch.setattr(
        cli, "load_bundle",
        lambda asset, s, e, c: DataBundle(
            candles=make_candles_for(asset["timeframe"])))


def test_alive_run_writes_report_and_exits_zero(tmp_path, capsys, monkeypatch):
    _patch(monkeypatch, _staircase)
    rc = cli.run(["--out", str(tmp_path), "--cache-dir", str(tmp_path)])
    assert rc == 0
    out_dirs = list(tmp_path.iterdir())
    run_dirs = [d for d in out_dirs if d.is_dir()]
    assert len(run_dirs) == 1
    report = (run_dirs[0] / "report.md").read_text()
    data = json.loads((run_dirs[0] / "results.json").read_text())
    for tf in ("1h", "4h", "1d", "1w"):
        assert tf in data["timeframes"]
        assert data["timeframes"][tf]["verdict"] == "ALIVE"
    assert "bump reconfirm_by" in report
    assert "ALIVE" in capsys.readouterr().out


def test_insufficient_4h_exits_one(tmp_path, capsys, monkeypatch):
    _patch(monkeypatch, _flat)  # zero LONG breaks everywhere
    rc = cli.run(["--out", str(tmp_path), "--cache-dir", str(tmp_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "INSUFFICIENT" in out and "HUMAN REVIEW" in out


def test_fetch_failure_aborts_whole_run(tmp_path, capsys, monkeypatch):
    """No partial verdicts: a single failing timeframe writes nothing."""
    monkeypatch.setattr(cli, "_now_ms", lambda: NOW)

    def boom(asset, s, e, c):
        if asset["timeframe"] == "1d":
            raise ConnectionError("vision archive down")
        return DataBundle(candles=_staircase(asset["timeframe"]))

    monkeypatch.setattr(cli, "load_bundle", boom)
    rc = cli.run(["--out", str(tmp_path), "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert not [d for d in tmp_path.iterdir() if d.is_dir()]
    assert "1d" in capsys.readouterr().err


def test_stale_series_aborts(tmp_path, capsys, monkeypatch):
    def stale(tf):
        cs = _staircase(tf)
        tf_ms = _MS[tf]
        return [Candle(c.timestamp_ms - 10 * tf_ms, c.open, c.high, c.low,
                       c.close, c.volume) for c in cs]

    _patch(monkeypatch, stale)
    rc = cli.run(["--out", str(tmp_path), "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert "stale" in capsys.readouterr().err.lower()


def test_second_run_picks_up_fresh_slice(tmp_path, capsys, monkeypatch):
    _patch(monkeypatch, _staircase)
    assert cli.run(["--out", str(tmp_path), "--cache-dir", str(tmp_path)]) == 0
    # second run, 100 bars later on the 1w clock so dir names differ
    later = NOW + 100 * _MS["1w"]
    monkeypatch.setattr(cli, "_now_ms", lambda: later)

    def fresh(tf):
        tf_ms = _MS[tf]
        end = (later // tf_ms) * tf_ms
        start = end - 400 * tf_ms
        return [Candle(start + i * tf_ms, 1000.0 + i, 1000.5 + i,
                       999.5 + i, 1000.0 + i, 10.0) for i in range(400)]

    monkeypatch.setattr(cli, "load_bundle",
                        lambda asset, s, e, c: DataBundle(
                            candles=fresh(asset["timeframe"])))
    assert cli.run(["--out", str(tmp_path), "--cache-dir", str(tmp_path)]) == 0
    run_dirs = sorted(d for d in tmp_path.iterdir() if d.is_dir())
    assert len(run_dirs) == 2
    data = json.loads((run_dirs[-1] / "results.json").read_text())
    assert data["timeframes"]["4h"]["n_fresh"] is not None
    assert data["timeframes"]["4h"]["n_fresh"] > 0


def test_json_flag_prints_results_dict(tmp_path, capsys, monkeypatch):
    _patch(monkeypatch, _staircase)
    rc = cli.run(["--out", str(tmp_path), "--cache-dir", str(tmp_path),
                  "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["timeframes"]["4h"]["verdict"] == "ALIVE"
