from __future__ import annotations

from moonface.feed.universe import select_top_volume


def _fake_tickers():
    return {
        "BTC/USDT:USDT": {"info": {"quoteVolume": "5000000000"}},
        "ETH/USDT:USDT": {"info": {"quoteVolume": "2000000000"}},
        "SOL/USDT:USDT": {"info": {"quoteVolume": "800000000"}},
        "DOGE/USDT:USDT": {"info": {"quoteVolume": 300000000}},          # fallback field
        "BTC/USDT": {"info": {"quoteVolume": "9999999999"}},   # spot, not a perp
        "FOO/USDC:USDT": {"info": {"quoteVolume": "999"}},     # not /USDT:USDT
        "BAR/USDT:USDT": {"info": {"quoteVolume": "0"}},       # zero volume
    }


def test_returns_top_n_usdt_perps_by_volume():
    top = select_top_volume("binance", 3, fetch_tickers=lambda: _fake_tickers())
    assert top == ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]


def test_size_caps_result():
    top = select_top_volume("binance", 1, fetch_tickers=lambda: _fake_tickers())
    assert top == ["BTC/USDT:USDT"]


def test_uses_quote_volume_fallback_field():
    top = select_top_volume("binance", 4, fetch_tickers=lambda: _fake_tickers())
    assert "DOGE/USDT:USDT" in top          # parsed from the top-level quoteVolume
    assert "FOO/USDC:USDT" not in top
    assert "BAR/USDT:USDT" not in top       # zero volume excluded
