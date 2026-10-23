# BTC 4h Long/Short Donchian n=100 — Exit Ablation

## Frozen entry (never varied)

- `donchian_break n=100`, symmetric long+short, 4h, non-overlap h=48
- BTCUSDT 4h, 14178 bars, data_sha=b3b004cb58258369, costs netted in R (round-trip 10bps base)
- split: 60/20/20 train/validate/**sealed**; sealed = recent ~2025-03..2026-06 window
- baseline (atr_trail k=2.0) sealed combined total_r = -10.600R

- cross-check vs tournament (atr_trail k=2.0 combined train/val/sealed = 74.517/10.739/-10.6): **PASS**

## Recent (sealed) window — combined long+short, ranked by total_r

| exit | trades | total_R | exp_R | PF | maxDD_R | cost2x/3x | outlier | verdict |
|---|---|---|---|---|---|---|---|---|
| time stop @120 bars (no stop) | 32 | 18.176 | 0.568 | 1.166 | -32.500 | Y/Y | n | improves: +raw R but fails risk/cost/outlier bar -> no edge |
| time stop @48 bars (no stop) | 32 | 9.058 | 0.283 | 1.140 | -24.551 | Y/Y | n | improves: +raw R but fails risk/cost/outlier bar -> no edge |
| hard stop k=2.0, no trail/TP | 32 | 5.241 | 0.164 | 1.097 | -24.051 | Y/n | n | improves: +raw R but fails risk/cost/outlier bar -> no edge |
| lock +1R after +2R reached | 32 | 0.155 | 0.005 | 1.004 | -32.137 | n/n | n | improves: +raw R but fails risk/cost/outlier bar -> no edge |
| atr_trail k=2.0 (BASELINE) | 32 | -10.600 | -0.331 | 0.639 | -13.073 | n/n | n | no-improvement (no better than baseline) |
| partial 50% @+2R + trail remainder | 32 | -12.695 | -0.397 | 0.581 | -14.861 | n/n | n | no-improvement (no better than baseline) |
| donchian channel trail (k=2.0,n=20) | 32 | -13.292 | -0.415 | 0.715 | -31.394 | n/n | n | no-improvement (no better than baseline) |
| atr_trail k=4.0 (widest) | 32 | -13.543 | -0.423 | 0.772 | -29.922 | n/n | n | no-improvement (no better than baseline) |
| atr_trail k=3.0 (wider) | 32 | -15.713 | -0.491 | 0.674 | -24.997 | n/n | n | no-improvement (no better than baseline) |
| chandelier atr_mult=3.0 | 32 | -16.887 | -0.528 | 0.623 | -26.966 | n/n | n | no-improvement (no better than baseline) |
| breakeven after +1R | 32 | -18.041 | -0.564 | 0.445 | -24.112 | n/n | n | no-improvement (no better than baseline) |
| fixed bracket stop=2.0 / TP=4.0 | 32 | -18.730 | -0.585 | 0.626 | -28.410 | n/n | n | no-improvement (no better than baseline) |
| chandelier atr_mult=4.0 | 32 | -23.666 | -0.740 | 0.585 | -39.685 | n/n | n | no-improvement (no better than baseline) |
| breakeven after +1.5R | 32 | -24.041 | -0.751 | 0.375 | -30.112 | n/n | n | no-improvement (no better than baseline) |

## Full path — combined (train -> validate -> sealed total_R)

| exit | train_R | val_R | sealed_R | sealed_PF | sealed_maxDD |
|---|---|---|---|---|---|
| atr_trail k=2.0 (BASELINE) | 74.517 | 10.739 | -10.600 | 0.639 | -13.073 |
| hard stop k=2.0, no trail/TP | 285.750 | 27.028 | 5.241 | 1.097 | -24.051 |
| fixed bracket stop=2.0 / TP=4.0 | 61.583 | -6.208 | -18.730 | 0.626 | -28.410 |
| donchian channel trail (k=2.0,n=20) | 141.452 | 10.764 | -13.292 | 0.715 | -31.394 |
| atr_trail k=3.0 (wider) | 57.006 | 6.425 | -15.713 | 0.674 | -24.997 |
| atr_trail k=4.0 (widest) | 71.823 | -5.483 | -13.543 | 0.772 | -29.922 |
| chandelier atr_mult=3.0 | 112.798 | 21.524 | -16.887 | 0.623 | -26.966 |
| chandelier atr_mult=4.0 | 135.403 | 8.996 | -23.666 | 0.585 | -39.685 |
| breakeven after +1R | 119.839 | 41.402 | -18.041 | 0.445 | -24.112 |
| breakeven after +1.5R | 176.906 | 33.402 | -24.041 | 0.375 | -30.112 |
| lock +1R after +2R reached | 119.896 | 41.402 | 0.155 | 1.004 | -32.137 |
| time stop @48 bars (no stop) | 84.074 | -30.860 | 9.058 | 1.140 | -24.551 |
| time stop @120 bars (no stop) | 214.154 | 12.944 | 18.176 | 1.166 | -32.500 |
| partial 50% @+2R + trail remainder | 41.291 | 0.679 | -12.695 | 0.581 | -14.861 |

## Recent (sealed) window — LONG vs SHORT separated

| exit | long_n | long_R | long_exp | short_n | short_R | short_exp |
|---|---|---|---|---|---|---|
| atr_trail k=2.0 (BASELINE) | 16 | -8.674 | -0.542 | 16 | -1.925 | -0.120 |
| hard stop k=2.0, no trail/TP | 16 | -0.827 | -0.052 | 16 | 6.068 | 0.379 |
| fixed bracket stop=2.0 / TP=4.0 | 16 | -15.523 | -0.970 | 16 | -3.206 | -0.200 |
| donchian channel trail (k=2.0,n=20) | 16 | -6.515 | -0.407 | 16 | -6.777 | -0.424 |
| atr_trail k=3.0 (wider) | 16 | -17.446 | -1.090 | 16 | 1.733 | 0.108 |
| atr_trail k=4.0 (widest) | 16 | -1.780 | -0.111 | 16 | -11.763 | -0.735 |
| chandelier atr_mult=3.0 | 16 | -5.565 | -0.348 | 16 | -11.322 | -0.708 |
| chandelier atr_mult=4.0 | 16 | -11.992 | -0.750 | 16 | -11.674 | -0.730 |
| breakeven after +1R | 16 | -12.251 | -0.766 | 16 | -5.790 | -0.362 |
| breakeven after +1.5R | 16 | -14.251 | -0.891 | 16 | -9.790 | -0.612 |
| lock +1R after +2R reached | 16 | 11.173 | 0.698 | 16 | -11.018 | -0.689 |
| time stop @48 bars (no stop) | 16 | 7.507 | 0.469 | 16 | 1.551 | 0.097 |
| time stop @120 bars (no stop) | 16 | 3.476 | 0.217 | 16 | 14.700 | 0.919 |
| partial 50% @+2R + trail remainder | 16 | -7.040 | -0.440 | 16 | -5.655 | -0.353 |

## Diagnosis

- best recent-window exit on raw R: **time stop @120 bars (no stop)** (sealed total_r 18.176R, exp 0.568R, PF 1.166, maxDD -32.500R, outlier_ok=n)
- **No exit clears the full risk-controlled bar in the recent window** (PF>=1.15, exp>0, |maxDD|<=30R, n>=30, 2x+3x cost, not outlier-dependent, validate same-sign).
- The only arms that go positive in 2025-2026 are the *no-stop / loosest* exits: time stop @120 bars (no stop) (+18.2R, maxDD -32.5R, outlier_ok=n); time stop @48 bars (no stop) (+9.1R, maxDD -24.6R, outlier_ok=n); hard stop k=2.0, no trail/TP (+5.2R, maxDD -24.1R, outlier_ok=n); lock +1R after +2R reached (+0.2R, maxDD -32.1R, outlier_ok=n). They buy raw R by **removing risk control**: every one is outlier-dependent (outlier_ok=n), and each additionally breaches at least one of PF>=1.15, the 30R drawdown budget, or the 3x cost gate. That is regime beta carried by a few trades, not an exit edge.
- **Verdict: the failure is the entry/regime having no recent edge, NOT atr_trail.** atr_trail is in fact the tightest-drawdown arm in the recent window (sealed maxDD -13.073R, well inside the 30R budget). Swapping it at most loses less while breaching that budget -> improves-but-no-edge, not a pass.

## Honest caveat

A negative outcome is expected and valid. Nothing here authorises live capital or promotion; the entry and EXIT_REGISTRY are untouched.
