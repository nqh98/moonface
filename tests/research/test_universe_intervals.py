from moonface.research.universe_data import _INTERVAL_MS


def test_all_search_intervals_present():
    assert _INTERVAL_MS["15m"] == 15 * 60 * 1000
    assert _INTERVAL_MS["30m"] == 30 * 60 * 1000
    assert _INTERVAL_MS["1h"] == 3_600_000
    assert _INTERVAL_MS["2h"] == 2 * 3_600_000
    assert _INTERVAL_MS["4h"] == 4 * 3_600_000
