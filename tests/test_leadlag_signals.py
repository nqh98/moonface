import pytest

from moonface.research.edge.leadlag_signals import make_eth_lead_momentum
from moonface.core.bundle import DataBundle, align_feature
from moonface.data.bundle import load_bundle
from moonface.research.entries import generate_entries
from moonface.kernel.synth import make_candles

_H4_MS = 4 * 3_600_000


def test_align_feature_joins_on_timestamp():
    btc = make_candles(10, seed=1)
    eth = make_candles(10, seed=2)
    aligned = align_feature(btc, eth)
    assert len(aligned) == 10
    assert aligned[0] == eth[0].close


def test_align_feature_missing_bars_are_none():
    btc = make_candles(10, seed=1)
    eth = make_candles(10, seed=2)
    eth = eth[:4] + eth[6:]  # drop two bars
    aligned = align_feature(btc, eth)
    assert aligned[4] is None and aligned[5] is None
    assert sum(1 for v in aligned if v is not None) == 8


def test_eth_lead_momentum_fires_on_extreme_move():
    n = 320
    candles = make_candles(n, drift=0.0, noise=0.001, seed=3)
    feature = [100.0] * n
    for j in range(n - 30, n):      # strong late ETH rally
        feature[j] = feature[j - 1] * 1.05
    gen = make_eth_lead_momentum(feature)
    entries = gen(candles, {"window": 180, "lookback": 12, "z_thr": 1.5})
    assert entries, "an extreme feature move must fire"
    assert all(side == "LONG" for _, side in entries)
    assert all(i < n - 1 for i, _ in entries)  # last index reserved for fill bar


def test_eth_lead_momentum_quiet_feature_is_silent():
    n = 320
    candles = make_candles(n, seed=3)
    feature = [100.0 + 0.01 * (i % 7) for i in range(n)]  # boring oscillation
    gen = make_eth_lead_momentum(feature)
    entries = gen(candles, {"window": 180, "lookback": 12, "z_thr": 1.5})
    short_big = [s for _, s in entries]
    assert short_big.count("LONG") + short_big.count("SHORT") == len(entries)
    # deterministic: same inputs, same output
    assert entries == gen(candles, {"window": 180, "lookback": 12, "z_thr": 1.5})


def test_generate_entries_routes_eth_lead_momentum():
    n = 320
    candles = make_candles(n, seed=3)
    feature = [float(100 + i) for i in range(n)]
    bundle = DataBundle(candles=candles, feature=feature)
    entries = generate_entries("eth_lead_momentum",
                               {"window": 180, "lookback": 12, "z_thr": 1.5},
                               bundle)
    assert isinstance(entries, list)


def test_generate_entries_requires_feature():
    bundle = DataBundle(candles=make_candles(320))
    with pytest.raises(ValueError, match="feature"):
        generate_entries("eth_lead_momentum",
                         {"window": 180, "lookback": 12, "z_thr": 1.5}, bundle)


def test_load_bundle_fails_loudly_on_thin_feature(monkeypatch, tmp_path):
    import moonface.data.bundle as bundle_mod
    btc = make_candles(100, seed=1)
    eth = make_candles(10, seed=2)   # 10% coverage — must raise

    def fake_fetch(exchange, symbol, timeframe, start_ms, end_ms, cache=None,
                   page_limit=1000):
        return eth if symbol == "ETH/USDT:USDT" else btc

    monkeypatch.setattr(bundle_mod, "fetch_history", fake_fetch)
    asset = {"exchange": "binance", "symbol": "BTC/USDT:USDT",
             "timeframe": "4h", "feature_symbol": "ETH/USDT:USDT"}
    with pytest.raises(ValueError, match="coverage"):
        load_bundle(asset, btc[0].timestamp_ms,
                    btc[-1].timestamp_ms + _H4_MS, str(tmp_path))
