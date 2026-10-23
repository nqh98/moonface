# Quantitative Capitulation — Registered Results

Registered primary run executed on 2026-07-08 with:

```bash
experiments/capitulation/.venv/bin/python experiments/capitulation/capitulation_backtest.py \
  --ohlcv .backtest_cache/BTCUSDT_1h.csv \
  --funding .backtest_cache/unifunding_BTCUSDT.csv \
  --oos-cutoff 2024-07-01 --funding-mode percentile
```

## Primary Run (`--funding-mode percentile`)

```text
Quantitative Capitulation — funding_mode=percentile cutoff=2024-07-01
── IN-SAMPLE (descriptive) ──
  signals            : 25
  win-rate (TP/SL)   : 0.280   [descriptive]
  mean fwd  4H logret : +0.00181
  mean fwd 24H logret : +0.00419
  95% CI  4H         : [+0.00181, +0.00241]
  95% CI 24H (GATE)  : [-0.00017, +0.00419]

── SEALED OOS (confirmatory) ──
  signals            : 4
  win-rate (TP/SL)   : 0.000   [descriptive]
  mean fwd  4H logret : -0.00957
  mean fwd 24H logret : +0.02605
  95% CI  4H         : [-0.00957, -0.00957]
  95% CI 24H (GATE)  : [+0.02605, +0.02605]

VERDICT (sealed OOS, 24H CI vs 0): UNDERPOWERED — inconclusive
```

## Key Counts And CIs

- In-sample signals: 25
- Sealed OOS signals: 4
- In-sample 24H gate CI: `[-0.00017, +0.00419]`
- Sealed OOS 24H gate CI: `[+0.02605, +0.02605]`
- In-sample 4H CI: `[+0.00181, +0.00241]`
- Sealed OOS 4H CI: `[-0.00957, -0.00957]`
- Verdict: `UNDERPOWERED — inconclusive`

## Robustness Read (`--funding-mode fixed`)

Robustness variant executed with:

```bash
experiments/capitulation/.venv/bin/python experiments/capitulation/capitulation_backtest.py \
  --ohlcv .backtest_cache/BTCUSDT_1h.csv \
  --funding .backtest_cache/unifunding_BTCUSDT.csv \
  --oos-cutoff 2024-07-01 --funding-mode fixed
```

Observed output:

```text
Quantitative Capitulation — funding_mode=fixed cutoff=2024-07-01
── IN-SAMPLE (descriptive) ──
  signals            : 6
  win-rate (TP/SL)   : 0.500   [descriptive]
  mean fwd  4H logret : +0.02319
  mean fwd 24H logret : +0.06194
  95% CI  4H         : [+0.02319, +0.02319]
  95% CI 24H (GATE)  : [+0.06194, +0.06194]

── SEALED OOS (confirmatory) ──
  signals            : 0
  win-rate (TP/SL)   : nan   [descriptive]
  mean fwd  4H logret : +nan
  mean fwd 24H logret : +nan
  95% CI  4H         : [+nan, +nan]
  95% CI 24H (GATE)  : [+nan, +nan]

VERDICT (sealed OOS, 24H CI vs 0): UNDERPOWERED — inconclusive
```

The fixed-threshold robustness variant is materially sparser than the registered primary setup: 6 in-sample signals and 0 sealed-OOS signals, so it provides no positive confirmatory evidence and does not overturn the primary read.

## Interpretation

This study does not justify a deployment claim. The sealed OOS window produced only 4 accepted trades, which is below the pre-registered `min_n=20` guard, so the verdict is explicitly `UNDERPOWERED — inconclusive` even though the observed 24H OOS mean was positive. Under the pre-registration, the seal is now spent: this remains a candidate mechanism at most, not a confirmed edge, and any next step would need a new protocol such as additional forward observation or a separately registered follow-on study rather than post-hoc retuning from this result.
