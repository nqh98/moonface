# capitulation — Quantitative Capitulation (Mean-Reversion) Baseline

**Status:** pre-registered confirmatory study. Long-only capitulation-fade on BTC 1H.
**Not an edge claim** until the sealed-OOS bootstrap CI clears the gate. See `DESIGN.md`.

Quarantined from the stdlib-only main tree: numpy/pandas deps live only in this dir's venv.

## Setup

    python3 -m venv experiments/capitulation/.venv
    experiments/capitulation/.venv/bin/pip install -r experiments/capitulation/requirements.txt

## Run

    experiments/capitulation/.venv/bin/python experiments/capitulation/capitulation_backtest.py \
      --ohlcv .backtest_cache/BTCUSDT_1h.csv \
      --funding .backtest_cache/unifunding_BTCUSDT.csv \
      --oos-cutoff 2024-07-01 --funding-mode percentile

## Test

    experiments/capitulation/.venv/bin/pytest experiments/capitulation/tests -v
