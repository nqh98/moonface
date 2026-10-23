from moonface.research.newdata import assess_manifest


def _macro_manifest():
    return {
        "provider": "FRED", "data_class": "macro_series",
        "fields": ["ts_ms", "series_id", "value", "publish_lag_days"],
        "symbols": ["VIXCLS"], "history_days": 2000, "cadence_ms": 86_400_000,
        "coverage_ratio": 0.99, "monotonic_timestamps": True,
        "duplicate_timestamp_ratio": 0.0,
        "license": {"research_allowed": True, "derived_features_allowed": True,
                    "retention_allowed": True},
    }


def test_macro_series_ready():
    v = assess_manifest(_macro_manifest())
    assert v["status"] == "ready", v["failures"]


def test_macro_series_missing_field_blocked():
    m = _macro_manifest()
    m["fields"] = ["ts_ms", "value"]
    v = assess_manifest(m)
    assert v["status"] == "blocked"
    assert any("missing required fields" in f for f in v["failures"])


def test_implied_vol_requires_btc():
    m = {
        "provider": "Deribit", "data_class": "implied_vol",
        "fields": ["ts_ms", "symbol", "dvol_open", "dvol_high", "dvol_low", "dvol_close"],
        "symbols": ["ETHUSDT"], "history_days": 1500, "cadence_ms": 86_400_000,
        "coverage_ratio": 0.99, "monotonic_timestamps": True,
        "duplicate_timestamp_ratio": 0.0,
        "license": {"research_allowed": True, "derived_features_allowed": True,
                    "retention_allowed": True},
    }
    v = assess_manifest(m)
    assert v["status"] == "blocked"
    assert any("BTCUSDT" in f for f in v["failures"])


def test_existing_classes_unchanged():
    # regression: original l2_orderbook contract still parses
    m = {
        "provider": "X", "data_class": "l2_orderbook",
        "fields": ["ts_ms","symbol","bid_prices","bid_sizes","ask_prices","ask_sizes"],
        "symbols": ["BTCUSDT"], "history_days": 200, "coverage_ratio": 0.99,
        "monotonic_timestamps": True, "duplicate_timestamp_ratio": 0.0,
        "license": {"research_allowed": True, "derived_features_allowed": True,
                    "retention_allowed": True},
    }
    assert assess_manifest(m)["status"] == "ready"
