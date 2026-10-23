from moonface.research.regime_overlay.data import load_macro
from moonface.research.regime_overlay.grid import FRED_SERIES


def test_load_macro_returns_each_series_via_injected_fetch():
    calls = []

    def fake_fetch(series_id, cache_dir):
        calls.append(series_id)
        return [object()]

    out = load_macro("cache/x", fetch=fake_fetch)
    assert set(out.keys()) == set(FRED_SERIES)
    assert sorted(calls) == sorted(FRED_SERIES)
