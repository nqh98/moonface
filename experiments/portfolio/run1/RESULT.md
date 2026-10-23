# BTC Portfolio Tournament — run1 RESULT

**Verdict: NEGATIVE (DSR stage). Sealed holdout NEVER opened.**

- asof: 2026-06-25
- symbol: BTCUSDT (free Binance perp OHLCV, 1h + 4h)
- window: `1577836800000..1782000000000` (~6.5y, 2020-01-01 → 2026-06)
- data: 1h n=56712, 4h n=14178 (full-span cache verified, no stale truncation)
- prereg: `experiments/portfolio/run1/PREREGISTRATION.md` (commit `ce8a6be`)
- stages run: `--register` → `--explore`. **`--select`/`--validate` NOT run**
  (zero DSR survivors ⇒ nothing to freeze, nothing to validate).

## Thesis tested

Single-mechanism directional families are exhaustively closed-negative on this
universe; the replicated obstacle is the drawdown wall. This lane tested whether
**combining weakly-correlated same-data signals (1h+4h) into risk-managed
portfolios** clears the locked economic bar where individuals cannot — attacking
the wall via diversification, not better single-signal exits. (Retires the old
4-factor confluence engine as a specific failed hypothesis; does not retire the
data universe.)

## Step-0 correlation screen — thesis survived the cheap kill

A genuine low-correlation basket existed (`verdict=ok`, `basket_size=8`):
off-diagonal correlations mostly −0.10 to +0.24, single max pair 0.56. The
diversification premise was **real** — the components do not co-move.

**Basket (8 of 9 frozen centers):**
`1h:roc_sign:period=24`, `1h:atr_channel_break:k=1.5`,
`1h:trend_pullback:pull_atr=1.0`, `1h:vol_regime:window=48`,
`4h:ma_cross:slow=100`, `4h:donchian_break:n=55`, `4h:atr_channel_break:k=1.5`,
`4h:vol_regime:window=48`.
**Dropped by the screen:** `1h:vol_expansion:mult=2.0`.

## Leaderboard — no portfolio clears DSR ≥ 0.95 (n_trials = 8 pooled)

| portfolio | DSR | sharpe | PF | exp_R | MAR | maxDD_R |
|---|---|---|---|---|---|---|
| regime_switch | **0.375** | 0.0110 | 1.996 | 0.00038 | −0.060 | −40.60 |
| vote_majority | 0.0004 | −0.0060 | 0.904 | −0.00064 | −1.000 | −1.00 |
| vol_target_vote_48 | 0.0002 | −0.0069 | 0.893 | −0.00108 | −0.854 | −1.17 |
| vol_target_vote_24 | 0.0002 | −0.0073 | 0.889 | −0.00114 | −0.886 | −1.13 |
| vote_2 | 0.0000 | −0.0089 | 0.966 | −0.00430 | −0.343 | −2.92 |
| long_short_net | 0.0000 | −0.0110 | 0.966 | −0.00635 | −0.486 | −2.06 |
| vol_target_lsn_48 | 0.0000 | −0.0152 | 0.954 | −0.01365 | −0.345 | −2.90 |
| vol_target_lsn_24 | 0.0000 | −0.0170 | 0.950 | −0.01529 | −0.301 | −3.32 |

**DSR survivors ≥ 0.95: 0.**

## Interpretation

- The strongest portfolio (`regime_switch`, DSR 0.375) is mid-pack for this
  program (all-time best `oi_build_momentum` ≈ 0.30; `positioning_transfer`
  ≈ 0.93) and far below the 0.95 gate. Its PF 1.996 is illusory: `net_return`
  is negative, `MAR −0.060`, and `MaxDD −40.6R` blows the ≤30R budget.
- 7 of 8 portfolios have **negative** Sharpe outright.
- Even with *genuine* cross-mechanism / cross-timeframe low correlation,
  combining the components did not yield a deflated-Sharpe-significant,
  drawdown-acceptable edge. **Diversification reduced correlation but did not
  beat the drawdown wall** on a risk-adjusted, overfit-corrected basis.

## Disposition (kill-rule)

Family **CLOSED NEGATIVE**. Not retuned with variations. Sealed holdout
untouched and intact. The data universe is not retired; the *portfolio-of-
same-data-signals* structural lever is now tested and closed on 6.5y BTC.
