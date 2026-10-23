from moonface.research.regime_selector import data as D


def test_load_macro_uses_injected_fetch():
    calls = []

    def fake(series_id, cache_dir):
        calls.append((series_id, cache_dir))
        return [("pt", series_id)]

    macro = D.load_macro("cache/x", fetch=fake)
    assert set(macro) == {"SP500", "VIXCLS", "DTWEXBGS"}
    assert macro["SP500"] == [("pt", "SP500")]
    assert all(cd == "cache/x" for _, cd in calls)


def test_load_btc_signature_calls_perp_only(monkeypatch):
    seen = {}

    def fake_candles(symbol, interval, start_ms, end_ms, cache_dir):
        seen.update(symbol=symbol, interval=interval, start=start_ms,
                    end=end_ms, cache=cache_dir)
        return ["c0", "c1"]

    monkeypatch.setattr(D, "fetch_perp_candles", fake_candles)
    out = D.load_btc(10, 20, "cache/y")
    assert out == ["c0", "c1"]
    assert seen == {"symbol": "BTCUSDT", "interval": "4h",
                    "start": 10, "end": 20, "cache": "cache/y"}
