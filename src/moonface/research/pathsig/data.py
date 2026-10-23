"""Real-data assembly for the path-signal rung-0 baseline.

Builds the BTC Sample grid through the existing build_dataset: HTF (1d/1w)
blocks come from closed-bar resampling of the 4h series, and the two
cross-sectional rank features come from point-in-time ranking against the
16-asset pool. Readers are injectable so tests run with no network or disk."""
from __future__ import annotations

from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from moonface.research.pathsig.dataset import build_dataset

H4_MS = 14_400_000
D1_MS = 86_400_000
W1_MS = 604_800_000


def resample_ohlc(candles: list[Candle], group_dur_ms: int,
                  base_dur_ms: int) -> list[Candle]:
    """Aggregate fine bars into coarse bars. Only complete groups (with the
    full expected sub-bar count) are emitted, so the coarse bar is truly
    closed at group start + group_dur_ms."""
    if not candles or group_dur_ms <= 0 or base_dur_ms <= 0:
        return []
    expected = group_dur_ms // base_dur_ms
    groups: dict[int, list[Candle]] = {}
    for c in candles:
        key = (c.timestamp_ms // group_dur_ms) * group_dur_ms
        groups.setdefault(key, []).append(c)
    out: list[Candle] = []
    for key in sorted(groups):
        bars = groups[key]
        if len(bars) < expected:
            continue
        out.append(Candle(
            timestamp_ms=key,
            open=bars[0].open,
            high=max(b.high for b in bars),
            low=min(b.low for b in bars),
            close=bars[-1].close,
            volume=sum(b.volume for b in bars)))
    return out


def _trailing_return(candles: list[Candle], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(candles)
    for i in range(len(candles)):
        if i - n >= 0 and candles[i - n].close > 0:
            out[i] = candles[i].close / candles[i - n].close - 1.0
    return out


def _align_to_grid(grid_ts: list[int], series: list[Candle],
                   values: list[float | None]) -> list[float | None]:
    by_ts = {c.timestamp_ms: v for c, v in zip(series, values)}
    return [by_ts.get(ts) for ts in grid_ts]


def cross_sectional_ranks(btc_values: list[float | None],
                          pool_values: list[list[float | None]]
                          ) -> list[float]:
    """Per-bar percentile rank of BTC's value among the peers present at that
    bar (fraction of peers strictly below BTC). 0.5 when BTC's value is missing
    or no peer is present, so the feature is never None for a price-complete
    bar."""
    out: list[float] = []
    for i in range(len(btc_values)):
        b = btc_values[i]
        peers = [pv[i] for pv in pool_values if pv[i] is not None]
        if b is None or not peers:
            out.append(0.5)
            continue
        out.append(sum(1 for v in peers if v < b) / len(peers))
    return out


def build_btc_dataset(readers: dict, h: int, atr_period: int,
                      pool_symbols: list[str], *, deploy: str = "BTCUSDT",
                      metrics_field: str = "sum_open_interest",
                      xs_lookback: int = 24):
    """Assemble the real BTC Sample grid. `readers` is a dict of
    candles/funding/metrics/bookdepth callables (see
    multifamily_loader.default_readers). Returns (btc_bundle, samples)."""
    candles_r = readers["candles"]
    funding_r = readers["funding"]
    metrics_r = readers["metrics"]
    bookdepth_r = readers["bookdepth"]

    btc = candles_r(deploy, "4h")
    if not btc:
        raise ValueError(f"no candles for {deploy}")
    bundle = DataBundle(candles=btc, funding=funding_r(deploy),
                        feature=metrics_r(deploy, metrics_field),
                        bookdepth=bookdepth_r(deploy))

    d1 = resample_ohlc(btc, D1_MS, H4_MS)
    w1 = resample_ohlc(btc, W1_MS, H4_MS)

    grid = [c.timestamp_ms for c in btc]
    peer_ret: list[list[float | None]] = []
    peer_fund: list[list[float | None]] = []
    for sym in pool_symbols:
        pc = candles_r(sym, "4h")
        if not pc:
            continue
        peer_ret.append(_align_to_grid(grid, pc, _trailing_return(pc, xs_lookback)))
        pf = funding_r(sym)
        if pf is not None:
            peer_fund.append(_align_to_grid(grid, pc, pf))

    xs_ret_rank = cross_sectional_ranks(_trailing_return(btc, xs_lookback), peer_ret)
    btc_fund = bundle.funding or [None] * len(btc)
    xs_funding_rank = cross_sectional_ranks(btc_fund, peer_fund)

    samples = build_dataset(bundle, h=h, atr_period=atr_period,
                            xs_ret_rank=xs_ret_rank,
                            xs_funding_rank=xs_funding_rank,
                            d1_candles=d1, w1_candles=w1)
    return bundle, samples
