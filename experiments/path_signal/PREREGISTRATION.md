# Path Signal — Pre-Registration (frozen 2026-06-16)

Design spec: docs/research-log/specs/2026-06-16-btc-distributional-path-signal-design.md

## Frozen before any model fit
- Timeframe: 4h decisions. Horizons predicted: h ∈ {6, 12} bars.
- ATR period for the R unit: 14 (matches the prior program).
- Deployment asset: BTCUSDT. Training/feature pool: the 16-asset 4h universe
  + BTC/ETH/SOL (cross-sectional inputs only).
- Label (per 4h bar, LONG frame): (ret_r, mae_r, mfe_r) from event_outcome().
- Feature list (frozen, order-stable) — see FEATURE_NAMES in
  src/moonface/research/pathsig/features.py. No feature may be added without a
  version bump and a fresh lockbox.
- Split: anchored walk-forward, purged + embargoed by the label horizon.
  Final 20% of the series is the one-touch lockbox tail.
- Gate: deflated Sharpe ≥ 0.95, n_trials = every hyperparameter combination ×
  every rung evaluated (set by the model plans). Reported under both the
  risk-adjusted (sized MAR/Sharpe) and fixed −15R-cap frames.

## Rungs (each must beat the rung below AND clear the gate)
0. raw existing signals (baseline replay)
1. regime-weighted ensemble of existing signals
2. distributional path model (the hypothesis)
3. sequence model (optional, gated)

Kill rule: rung 2 fails to beat rung 1 OR fails the gate ⇒ the "framework was
the limiting factor" thesis is falsified on existing data; escalate to a
separate new-data program. No parameter rescue.
