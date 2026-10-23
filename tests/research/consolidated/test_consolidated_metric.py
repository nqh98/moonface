from moonface.research.consolidated.result import AdapterResult, metric_block

def _res(records=None, r_stream=None):
    return AdapterResult(key="k", lane="l", unit="r_trade", config={},
                         config_source="frozen_family", exit_name="atr_trail",
                         current_signal="FLAT", records=records, r_stream=r_stream)

def test_metric_block_from_records():
    recs = [{"i": 0, "side": "LONG", "net_r": 2.0, "atr_frac": 0.02},
            {"i": 1, "side": "SHORT", "net_r": -1.0, "atr_frac": 0.02}]
    m = metric_block(_res(records=recs))
    assert m["n"] == 2
    assert m["total_r"] == 1.0
    assert m["expectancy_r"] == 0.5
    assert m["pf"] == 2.0          # 2.0 gains / 1.0 losses
    assert m["max_dd_r"] <= 0.0

def test_metric_block_from_r_stream():
    m = metric_block(_res(r_stream=[2.0, -1.0]))
    assert m["n"] == 2
    assert m["expectancy_r"] == 0.5

def test_metric_block_empty():
    m = metric_block(_res(records=[]))
    assert m["n"] == 0 and m["expectancy_r"] == 0.0
