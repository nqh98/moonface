# lane1_twap (Track A) — Pre-Registration

Frozen **before any data look**. Track A is a stage-1 gross-drift **screen**:
in-sample, gross of cost, NO lockbox, NO paper. It only decides whether the
Track-B real-feed pre-registration is worth writing. Design spec:
`docs/research-log/specs/2026-07-09-lane1-liquidation-twap-design.md`.

## 1. Hypothesis (BTC/USDT:USDT 1h)
A liquidation cascade at bar t is proxied by, ALL of:
- `|close_t - open_t| / risk_unit_14(t) >= m` (ATR-normalized body, m=1.5),
- `level_zscore_180(log volume_t) >= +k` (participation),
- `zscore_180(Δlog OI_t) <= -k` (forced deleveraging; OI dropped),
with side = continuation of the bar sign (down→SHORT, up→LONG). The claim: mean
signed forward drift `ret_r(h)` (in R) is > 0 over h∈{1,2,3,4}h.

## 2. Treatment vs control (one variable)
Treatment = OI-drop cascades. Control = the SAME large-body + volume bars whose
OI did NOT drop (`require_oi_drop=false`, vol-matched by construction). Measured
at PRIMARY_H=2, k=1.5. Mechanism (TWAP overhang) requires treatment drift >
control drift; otherwise the effect is generic momentum.

## 3. Frozen gate (5 conditions, ALL required to PASS)
1. Sign: pooled mean ret_r across cells > 0.
2. Floor: max moving-block-bootstrap (block_len=4) effect-Z >= 3.0 on a cell
   with mean ret_r > 0.
3. Robustness: at the strong cell's horizon, BOTH k∈{1.5,2.0} have mean ret_r>0.
4. Treatment > control at PRIMARY_H.
5. Null calibration: direction-shuffled events do NOT clear the floor
   (max shuffled effect-Z < 3.0).

Grid: k∈{1.5,2.0} × h∈{1,2,3,4} (8 cells). W=180, m=1.5, atr_period=14.

## 4. Decision
- PASS (all 5) -> LICENSE writing the Track-B frozen pre-registration.
- FAIL -> CLOSED NEGATIVE. Kill rule: no grid expansion, no direction flip
  (continuation↔reversal is Setup 3, a different lane), no proxy swap, no
  multi-asset, no Track B without a NEW pre-registration.

Track B (real forceOrder feed) remains DEFERRED behind the readiness gate in
`experiments/newdata/FREE_DATA_FEASIBILITY_liquidations.md`.
