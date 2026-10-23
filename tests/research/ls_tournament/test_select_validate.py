from dataclasses import asdict
import importlib

from moonface.research.ls_tournament.grid import all_configs

sel = importlib.import_module("moonface.research.ls_tournament.select")
val = importlib.import_module("moonface.research.ls_tournament.validate")
pipeline = importlib.import_module("moonface.research.ls_tournament.pipeline")


def test_render_findings_includes_data_sha():
    rows = [{"label": "x", "timeframe": "4h", "long_rule": {"family": "a"},
             "short_rule": {"family": "b"}, "verdict": "negative"}]
    out = pipeline.render_findings(rows, "2026-06-27", {"2h": "deadbeef", "4h": "cafef00d"})
    assert "data_sha: 2h=deadbeef, 4h=cafef00d" in out


def _row(axis=1.0):
    cfg = asdict(all_configs(["2h"])[0])
    cfg["axis"] = axis
    cfg["label"] = f"{cfg['label']}:{axis}"
    return cfg


def _metrics(net_r=5.0, expectancy_r=1.0, profit_factor=1.5):
    return {
        "trade_count": 40,
        "total_r": net_r,
        "net_r": net_r,
        "expectancy_r": expectancy_r,
        "profit_factor": profit_factor,
        "max_drawdown_r": -1.0,
        "long_expectancy_r": expectancy_r,
        "short_expectancy_r": expectancy_r,
        "twin_total_r": net_r - 1.0,
        "twin_expectancy_r": expectancy_r - 0.1,
    }


def test_select_keeps_winner_and_rejects_twin_drag(monkeypatch):
    rows = [_row(1.0), _row(2.0), _row(3.0)]
    rows[1]["metrics"] = {"profit_factor": 2.0}
    rows[0]["metrics"] = {"profit_factor": 2.0}
    rows[2]["metrics"] = {"profit_factor": 2.0}

    def fake_train_score(candles, config, context=None):
        return {
            "scored": {"metrics": _metrics(net_r=5.0)},
            "selection_checks": {
                "cost_stress": True,
                "outlier": True,
                "recent": True,
                "twin_beats": True,
            },
        }

    monkeypatch.setattr(sel, "_train_score", fake_train_score)
    survivors = sel.select(rows, {"2h": [object()] * 100})
    assert len(survivors) == 3

    def fake_train_score_drag(candles, config, context=None):
        return {
            "scored": {"metrics": _metrics(net_r=5.0)},
            "selection_checks": {
                "cost_stress": True,
                "outlier": True,
                "recent": True,
                "twin_beats": False,
            },
        }

    monkeypatch.setattr(sel, "_train_score", fake_train_score_drag)
    assert sel.select(rows, {"2h": [object()] * 100}) == []


def test_select_rejects_core_failure(monkeypatch):
    rows = [_row(1.0), _row(2.0), _row(3.0)]
    rows[0]["metrics"] = {"profit_factor": 2.0}
    rows[1]["metrics"] = {"profit_factor": 2.0}
    rows[2]["metrics"] = {"profit_factor": 2.0}

    def fake_train_score(candles, config, context=None):
        return {
            "scored": {"metrics": _metrics(net_r=0.1, profit_factor=0.5)},
            "selection_checks": {
                "cost_stress": True,
                "outlier": True,
                "recent": True,
                "twin_beats": True,
            },
        }

    monkeypatch.setattr(sel, "_train_score", fake_train_score)
    assert sel.select(rows, {"2h": [object()] * 100}) == []


def test_cost_multiple_gate_rejects_cost_fragile():
    # 30 small winners + 5 small losers: clears the +5bps additive stress but
    # collapses to negative expectancy once full round-trip cost is charged 3x.
    records = [{"net_r": 0.05, "atr_frac": 0.02}] * 30 + [{"net_r": -0.01, "atr_frac": 0.02}] * 5
    assert sel._cost_stress(records)["passed"]
    assert sel._cost_multiple(records, 2.0)["passed"] is False
    assert sel._cost_multiple(records, 3.0)["passed"] is False
    # mult=1 reproduces the base (no extra cost) series and must pass.
    assert sel._cost_multiple(records, 1.0)["passed"]
    # validate module shares the same gate.
    assert val._cost_multiple(records, 3.0)["passed"] is False


def test_validate_all_maps_windows_in_order(monkeypatch):
    # Guards the CLI<->validate_all argument order: train/validate/sealed data
    # must land in the matching verdict segment (was shuffled by a positional bug).
    row = _row(1.0)
    tf = row["timeframe"]
    tr, va, se = [("train",)], [("val",)], [("seal",)]

    def fake_segment(candles, config, context=None):
        return {"metrics": {**_metrics(), "tag": candles[0][0]}, "passed": True}

    monkeypatch.setattr(val, "_segment", fake_segment)
    out = val.validate_all([row], {tf: tr}, {tf: va}, {tf: se})
    r = out[0]
    assert r["train"]["tag"] == "train"
    assert r["validate"]["tag"] == "val"
    assert r["sealed"]["tag"] == "seal"


def test_validate_candidate_accepts_and_rejects(monkeypatch):
    row = _row(1.0)
    train = [object()]
    validate = [object(), 1]
    sealed = [object(), 2]

    def fake_segment(candles, config, context=None):
        if candles is validate:
            return {"metrics": _metrics(net_r=4.0, expectancy_r=0.8),
                    "passed": True}
        if candles is sealed:
            return {"metrics": _metrics(net_r=3.0, expectancy_r=0.7),
                    "passed": True}
        return {"metrics": _metrics(net_r=5.0, expectancy_r=0.9), "passed": True}

    monkeypatch.setattr(val, "_segment", fake_segment)
    ok = val.validate_candidate(row, validate, sealed, train_candles=train)
    assert ok["verdict"] == "paper_candidate"
    assert "train" in ok and "validate" in ok and "sealed" in ok

    def fake_segment_fail(candles, config, context=None):
        out = fake_segment(candles, config, context)
        if candles is sealed:
            out = {"metrics": _metrics(net_r=-3.0, expectancy_r=-0.2), "passed": False}
        return out

    monkeypatch.setattr(val, "_segment", fake_segment_fail)
    bad = val.validate_candidate(row, validate, sealed, train_candles=train)
    assert bad["verdict"] == "negative"
