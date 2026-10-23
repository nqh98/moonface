from __future__ import annotations

from moonface.core.bundle import DataBundle, _check_coverage, align_feature
from moonface.data.ohlcv import OhlcvCache, fetch_history
from moonface.data.series import (
    FundingCache, METRICS_FIELDS, align_basis, align_funding, align_metric,
    fetch_funding_history, fetch_metrics_history,
)


def load_bundle(asset: dict, start_ms: int, end_ms: int, cache_dir: str) -> DataBundle:
    """Full (unfenced) bundle for one asset. Mirrors the wiring of the
    bespoke probe CLIs; network access only through the existing CSV caches.
    Tests inject synthetic bundles instead of calling this.

    Moved out of core.bundle at G4 -- this is the one function in that
    module that actually calls the fetch layer (fetch_history,
    fetch_funding_history, fetch_metrics_history), which core/ can no
    longer hold once data/ exists. DataBundle itself and its pure
    alignment/validation helpers stay in core.bundle -- they are a shape,
    not a fetch."""
    candles = fetch_history(asset["exchange"], asset["symbol"], asset["timeframe"],
                            start_ms, end_ms, OhlcvCache(cache_dir))
    funding = None
    if "funding_symbol" in asset:
        points = fetch_funding_history(asset["exchange"], asset["funding_symbol"],
                                       start_ms, end_ms, FundingCache(cache_dir))
        funding = align_funding(candles, points)
    basis = None
    if "spot_symbol" in asset:
        spot = fetch_history(asset["exchange"], asset["spot_symbol"],
                             asset["timeframe"], start_ms, end_ms,
                             OhlcvCache(cache_dir))
        basis = align_basis(candles, spot)
    feature = None
    if "feature_symbol" in asset:
        feat = fetch_history(asset["exchange"], asset["feature_symbol"],
                             asset["timeframe"], start_ms, end_ms,
                             OhlcvCache(cache_dir))
        feature = align_feature(candles, feat)
        _check_coverage(feature, asset["feature_symbol"])
    elif "metrics_field" in asset:
        field = asset["metrics_field"]
        if field not in METRICS_FIELDS:
            raise ValueError(f"unknown metrics field {field!r}")
        archive_symbol = asset["symbol"].split(":")[0].replace("/", "")
        raw = fetch_metrics_history(archive_symbol, start_ms, end_ms, cache_dir)
        feature = align_metric(candles, [(ts, f[field]) for ts, f in raw
                                         if field in f])
        _check_coverage(feature, f"{archive_symbol} metrics {field}")
    return DataBundle(candles=candles, funding=funding, basis=basis, feature=feature)
