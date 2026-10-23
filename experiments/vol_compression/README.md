# vol_compression — Volatility Compression → Expansion (Straddle-Proxy) Baseline

**Status:** pre-registered confirmatory study. At a volatility squeeze on BTC 1h, "buy"
a straddle priced off the *compressed* vol and win only if realized expansion beats that
fair price plus cost — a direction-agnostic payoff, distinct from every falsified
directional lane. **Not an edge claim** until the sealed-OOS bootstrap CI clears the gate.
See `DESIGN.md`.

Quarantined from the stdlib-only main tree: numpy/pandas deps live only in this dir's venv.

## Setup

    python3 -m venv experiments/vol_compression/.venv
    experiments/vol_compression/.venv/bin/pip install -r experiments/vol_compression/requirements.txt

## Run

    experiments/vol_compression/.venv/bin/python experiments/vol_compression/vol_compression_backtest.py \
      --ohlcv .backtest_cache/BTCUSDT_1h.csv --oos-cutoff 2024-07-01 --feature rv

## Test

    experiments/vol_compression/.venv/bin/pytest experiments/vol_compression/tests -v
