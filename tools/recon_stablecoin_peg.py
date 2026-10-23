#!/usr/bin/env python
"""Recon probe: fiat-onramp stablecoin peg premium (Lane 2, Stage-0 feasibility).

Keyless reconnaissance of USDT/USD and USDC/USD on Kraken and Coinbase. This is a
readiness/data-quality probe ONLY - no signal, no premium indicator, no BTC test.
It answers whether >=180 days of <=1-minute fiat-stablecoin bars are collectable
under the free-data mandate, feeding
experiments/newdata/FREE_DATA_FEASIBILITY_stablecoin_peg.md.

Pure parser/analyzer functions are unit-tested against fixtures; network wrappers
are thin and exercised only by the live `probe` subcommand.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

_KRAKEN = "https://api.kraken.com/0/public"
_COINBASE = "https://api.exchange.coinbase.com"
_TIMEOUT_S = 20
_UA = {"User-Agent": "moonface-recon/1.0"}

_WANTED_KRAKEN = {
    "USDT/USD": ("USDTZUSD", "USDTUSD"),
    "USDC/USD": ("USDCZUSD", "USDCUSD"),
}
_COINBASE_PRODUCTS = {"USDT/USD": "USDT-USD", "USDC/USD": "USDC-USD"}


def kraken_pairs_present(
    assetpairs_result: dict, wanted: dict[str, tuple[str, ...]]
) -> dict[str, str | None]:
    """Return the first matching Kraken symbol for each logical pair label."""
    keys = set(assetpairs_result)
    altnames = {
        value.get("altname") for value in assetpairs_result.values() if isinstance(value, dict)
    }
    out: dict[str, str | None] = {}
    for label, candidates in wanted.items():
        found = None
        for candidate in candidates:
            if candidate in keys or candidate in altnames:
                found = candidate
                break
        out[label] = found
    return out


def ohlc_bar_span(ohlc_result: dict) -> dict:
    """Summarize a Kraken OHLC payload, ignoring the trailing cursor entry."""
    pair_keys = [key for key in ohlc_result if key != "last"]
    if not pair_keys or not ohlc_result.get(pair_keys[0]):
        return {
            "pair": pair_keys[0] if pair_keys else None,
            "bars": 0,
            "first_ts": None,
            "last_ts": None,
            "span_s": 0,
        }
    rows = ohlc_result[pair_keys[0]]
    first_ts, last_ts = int(rows[0][0]), int(rows[-1][0])
    return {
        "pair": pair_keys[0],
        "bars": len(rows),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "span_s": last_ts - first_ts,
    }


def coinbase_candles_span(candles: list) -> dict:
    """Summarize a Coinbase candles response including basic volume sanity."""
    if not candles:
        return {
            "bars": 0,
            "oldest_ts": None,
            "newest_ts": None,
            "span_s": 0,
            "all_have_volume": False,
        }
    times = [int(candle[0]) for candle in candles]
    newest_ts, oldest_ts = max(times), min(times)
    return {
        "bars": len(candles),
        "oldest_ts": oldest_ts,
        "newest_ts": newest_ts,
        "span_s": newest_ts - oldest_ts,
        "all_have_volume": all(len(candle) >= 6 and candle[5] > 0 for candle in candles),
    }


def coverage_report(timestamps_s: list[int], interval_s: int) -> dict:
    """Report span coverage and gap structure for fixed-interval timestamps."""
    if not timestamps_s:
        return {
            "monotonic": True,
            "coverage": 0.0,
            "gaps": 0,
            "longest_gap_bars": 0,
            "expected": 0,
            "present": 0,
        }
    monotonic = all(
        timestamps_s[index] < timestamps_s[index + 1]
        for index in range(len(timestamps_s) - 1)
    )
    ordered = sorted(set(timestamps_s))
    expected = (ordered[-1] - ordered[0]) // interval_s + 1
    present = len(ordered)
    gaps = 0
    longest = 0
    for index in range(len(ordered) - 1):
        step = (ordered[index + 1] - ordered[index]) // interval_s
        if step > 1:
            gaps += 1
            longest = max(longest, step - 1)
    return {
        "monotonic": monotonic,
        "coverage": round(present / expected if expected else 0.0, 4),
        "gaps": gaps,
        "longest_gap_bars": int(longest),
        "expected": int(expected),
        "present": present,
    }


def premium_stats(prices: list[float]) -> dict:
    """Summarize deviation from a 1.0 peg in basis points."""
    if not prices:
        return {
            "n": 0,
            "mean_px": None,
            "mean_bps": None,
            "min_bps": None,
            "max_bps": None,
            "peg_crosses": 0,
        }
    bps = [(price - 1.0) * 1e4 for price in prices]
    peg_crosses = 0
    for index in range(len(bps) - 1):
        if bps[index] == 0 or bps[index + 1] == 0:
            continue
        if (bps[index] > 0) != (bps[index + 1] > 0):
            peg_crosses += 1
    return {
        "n": len(prices),
        "mean_px": round(sum(prices) / len(prices), 6),
        "mean_bps": round(sum(bps) / len(bps), 3),
        "min_bps": round(min(bps), 3),
        "max_bps": round(max(bps), 3),
        "peg_crosses": peg_crosses,
    }


def trades_to_bars(trades: list, interval_s: int = 60) -> list[dict]:
    """Bucket Kraken trades into simple OHLCV bars."""
    buckets: dict[int, list[tuple[float, float, float]]] = {}
    for trade in trades:
        price, volume, ts = float(trade[0]), float(trade[1]), float(trade[2])
        bucket = int(ts // interval_s) * interval_s
        buckets.setdefault(bucket, []).append((ts, price, volume))
    bars = []
    for bucket in sorted(buckets):
        rows = sorted(buckets[bucket])
        bars.append(
            {
                "ts": bucket,
                "open": rows[0][1],
                "high": max(row[1] for row in rows),
                "low": min(row[1] for row in rows),
                "close": rows[-1][1],
                "volume": sum(row[2] for row in rows),
            }
        )
    return bars


def trades_page_span(trades_result: dict) -> dict:
    """Summarize a Kraken trades page and its pagination cursor."""
    pair_keys = [key for key in trades_result if key != "last"]
    rows = trades_result[pair_keys[0]] if pair_keys else []
    if not rows:
        return {
            "trades": 0,
            "first_ts": None,
            "last_ts": None,
            "span_s": 0,
            "cursor": trades_result.get("last"),
        }
    first_ts, last_ts = float(rows[0][2]), float(rows[-1][2])
    return {
        "trades": len(rows),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "span_s": last_ts - first_ts,
        "cursor": trades_result.get("last"),
    }


def _get_json(url: str, data: bytes | None = None):
    req = urllib.request.Request(url, data=data, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as response:  # noqa: S310
        return json.loads(response.read().decode())


def fetch_kraken_assetpairs() -> dict:
    return _get_json(f"{_KRAKEN}/AssetPairs").get("result", {})


def fetch_kraken_ohlc(pair: str, interval: int) -> dict:
    return _get_json(f"{_KRAKEN}/OHLC?pair={pair}&interval={interval}").get("result", {})


def fetch_kraken_trades(pair: str, since: str | None = None) -> dict:
    url = f"{_KRAKEN}/Trades?pair={pair}"
    if since:
        url += f"&since={since}"
    return _get_json(url).get("result", {})


def fetch_coinbase_candles(product: str, granularity: int) -> list:
    return _get_json(f"{_COINBASE}/products/{product}/candles?granularity={granularity}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    probe = subparsers.add_parser("probe", help="run keyless Kraken/Coinbase readiness probe")
    probe.add_argument("--interval", type=int, default=1, help="Kraken OHLC minutes (default 1)")
    probe.add_argument(
        "--granularity",
        type=int,
        default=60,
        help="Coinbase candle seconds (default 60)",
    )
    return parser


def _run_probe(interval: int, granularity: int) -> None:
    print("== Q1 Existence (Kraken AssetPairs) ==")
    kraken_pairs = kraken_pairs_present(fetch_kraken_assetpairs(), _WANTED_KRAKEN)
    for label, symbol in kraken_pairs.items():
        print(f"  Kraken {label}: {symbol or 'ABSENT'}")

    print("== Q2 History cap ==")
    for label, symbol in kraken_pairs.items():
        if not symbol:
            continue
        ohlc_span = ohlc_bar_span(fetch_kraken_ohlc(symbol, interval))
        hours = ohlc_span["span_s"] / 3600 if ohlc_span["span_s"] else 0
        print(f"  Kraken OHLC {label} i={interval}m: {ohlc_span['bars']} bars, {hours:.1f}h")
        trade_span = trades_page_span(fetch_kraken_trades(symbol))
        minutes = (trade_span["span_s"] or 0) / 60
        print(
            f"  Kraken Trades {label}: {trade_span['trades']} trades, "
            f"{minutes:.1f}m/page, cursor={trade_span['cursor']}"
        )

    print("== Q3 Quality/premium ==")
    for label, product in _COINBASE_PRODUCTS.items():
        try:
            candles = fetch_coinbase_candles(product, granularity)
        except urllib.error.HTTPError as exc:
            print(f"  Coinbase {product}: ABSENT (HTTP {exc.code})")
            continue
        span = coinbase_candles_span(candles)
        hours = span["span_s"] / 3600 if span["span_s"] else 0
        print(
            f"  Coinbase {product} g={granularity}s: {span['bars']} bars, "
            f"{hours:.1f}h, vol_ok={span['all_have_volume']}"
        )
        timestamps = [int(candle[0]) for candle in candles]
        closes = [float(candle[4]) for candle in candles]
        coverage = coverage_report(timestamps, granularity)
        premium = premium_stats(closes)
        print(
            f"  {product} coverage={coverage['coverage']} gaps={coverage['gaps']} "
            f"monotonic={coverage['monotonic']}"
        )
        print(
            f"  {product} premium mean={premium['mean_bps']}bps "
            f"range=[{premium['min_bps']},{premium['max_bps']}] "
            f"crosses={premium['peg_crosses']}"
        )


def main() -> None:
    args = build_parser().parse_args()
    if args.cmd == "probe":
        try:
            _run_probe(args.interval, args.granularity)
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise SystemExit(f"probe request failed: {exc}") from exc


if __name__ == "__main__":
    main()
