#!/usr/bin/env python
"""Recon probe: Hyperliquid public tape -> BTC Aggressor Delta (net taker flow).

One-shot, keyless reconnaissance for the 15m Q-Sweep logic, testing Hyperliquid
as the microstructure-flow source after the Binance Vision aggTrades path was
retired. Fetches a recent-trades snapshot, computes the signed taker-volume delta,
and reports the UTC span the snapshot covers so we can see whether it reaches 15m.

Endpoint note: the WebSocket-style `{"type": "trades"}` request is rejected by
`/info` ("Failed to deserialize the JSON body into the target type"); the working
REST request type is `recentTrades`, which returns a rolling snapshot of the latest
prints with no time-window parameter.

Side convention (taker/aggressor): "B" -> taker buy (positive), "A" -> taker sell
(negative). `px`/`sz` arrive as strings; `time` is epoch milliseconds (UTC).
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

import pandas as pd

_INFO_URL = "https://api.hyperliquid.xyz/info"
_TIMEOUT_S = 15


def fetch_recent_trades(coin: str = "BTC") -> list[dict]:
    """POST a `recentTrades` request to the Hyperliquid /info endpoint and return
    the parsed JSON array of recent prints. Raises RuntimeError if the body is not
    a JSON list (e.g. the server's deserialize-error string)."""
    payload = json.dumps({"type": "recentTrades", "coin": coin}).encode()
    req = urllib.request.Request(
        _INFO_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        body = resp.read().decode()
    try:
        trades = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"non-JSON response from {_INFO_URL}: {body!r}") from exc
    if not isinstance(trades, list):
        raise RuntimeError(f"expected a JSON list of trades, got: {body!r}")
    return trades


def trades_to_frame(trades: list[dict]) -> pd.DataFrame:
    """Build a typed DataFrame from raw Hyperliquid trades: float `px`/`sz`, a
    UTC `time_utc` column from epoch-ms `time`, and `signed_size` (+sz for taker
    buys "B", -sz for taker sells "A")."""
    df = pd.DataFrame(trades)
    if df.empty:
        return df
    df["px"] = df["px"].astype(float)
    df["sz"] = df["sz"].astype(float)
    df["time_utc"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df["signed_size"] = df["sz"].where(df["side"] == "B", -df["sz"])
    return df


def aggressor_delta(df: pd.DataFrame) -> float:
    """Net taker flow: sum of signed taker sizes."""
    if df.empty:
        return 0.0
    return float(df["signed_size"].sum())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coin", default="BTC", help="Hyperliquid coin (default: BTC)")
    args = parser.parse_args()

    try:
        trades = fetch_recent_trades(args.coin)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise SystemExit(f"request failed: {exc}") from exc

    df = trades_to_frame(trades)
    if df.empty:
        print(f"no recent trades returned for {args.coin}")
        return

    print(df.head().to_string())
    span = df["time_utc"].max() - df["time_utc"].min()
    print()
    print(f"coin:            {args.coin}")
    print(f"trades:          {len(df)}")
    print(f"snapshot span:   {df['time_utc'].min()} -> {df['time_utc'].max()} ({span})")
    print(f"aggressor delta: {aggressor_delta(df):+.6f}")


if __name__ == "__main__":
    main()
