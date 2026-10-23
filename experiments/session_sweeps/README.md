# session_sweeps — Time-of-Day / Session Sweep (Fade) Baseline

**Status:** pre-registered confirmatory study. Fade prior-session high/low liquidity
sweeps on BTC 15m (3×8h UTC sessions). **Not an edge claim** until the sealed-OOS
bootstrap CI clears the gate. See `DESIGN.md`.

Quarantined from the stdlib-only main tree: numpy/pandas deps live only in this dir's venv.

## Setup

    python3 -m venv experiments/session_sweeps/.venv
    experiments/session_sweeps/.venv/bin/pip install -r experiments/session_sweeps/requirements.txt

## Run

    experiments/session_sweeps/.venv/bin/python experiments/session_sweeps/session_sweeps_backtest.py \
      --ohlcv .backtest_cache/BTCUSDT_15m.csv --oos-cutoff 2024-07-01 --mode reversal

## Test

    experiments/session_sweeps/.venv/bin/pytest experiments/session_sweeps/tests -v
