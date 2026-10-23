# MTF Broadened Search — Findings

**Question (pre-registered in `BROADEN_PREREGISTRATION.md`):** broadening the 15m–1d
MTF grid along new structural axes — regime DEFINITION (trend sign / momentum sign
/ regime QUALITY) and hold horizon (1d / 2d) — is any cell BETTER than the frozen
headline, or does any cell clear the deployable bar? 72 cells, honest DSR
deflation by n_trials=72. Full leaderboard in `BROADEN.md`. Paper only.

## Verdict: BETTER-THAN-HEADLINE (re-rank, paper-only) — NOT deployable

- **No cell clears DSR ≥ 0.95** (best 0.507) and **no cell clears ECON_BAR** — the
  deployable verdict is NEGATIVE, exactly as the program's prior predicted. The
  drawdown wall binds every cell (walk-forward DD −172R … −2047R ≫ 30R cap).
- **But the frozen BETTER-THAN-HEADLINE rule fired** on a structurally new cell,
  and it survives the headline's own two discriminators (recent-OOS + transfer),
  so it is a genuine re-rank of the lane's best paper candidate, not noise.

## The new best cell

`4h:trend_strength|rsi_reversion|horizon_hold@2d` (`grid.broaden_best_cell()`):
a **4h regime-QUALITY gate** — trade only when price is ≥ 1σ from its 4h SMA50
(skip the chop) — gating the same 15m RSI counter-trend entry, held 2 days with
**no stop**.

### Single-path comparison vs the frozen headline (full 6.5y BTC)

| cell | n | PF | exp/trade | totalR | maxDD_R | MAR | years + |
|---|---|---|---|---|---|---|---|
| headline `1d:price_vs_sma\|rsi_reversion\|wide_stop@2d` | 973 | 1.239 | +0.581 | +565 | −124.8 | 4.53 | 6/7 |
| **new best `4h:trend_strength\|rsi_reversion\|hold@2d`** | 731 | 1.240 | +0.897 | +656 | −135.6 | **4.83** | **7/7** |

The regime-quality gate takes ~25% fewer trades but each is higher quality
(expectancy +0.581 → +0.897), and it is **positive in all 7 calendar years** —
fixing the headline's known weakness (2022/2024 weak-trend losers). The PF "win"
(+0.001) is noise; the real gains are expectancy, MAR, and robustness.

### Recent OOS (entries ≥ 2024-06) + cross-asset transfer — the discriminators

| asset | new best (recent) | headline (recent) |
|---|---|---|
| BTC | PF **1.406** / exp +1.413 / MAR 3.23 | PF 1.140 / +0.357 / MAR 1.00 |
| SOL | PF **1.310** / exp +1.125 / MAR 2.62 | PF 1.095 / +0.225 / MAR 0.89 |
| ETH | PF 1.047 / +0.226 / MAR 0.29 | PF 1.083 / +0.205 / MAR 0.72 |

The new cell is **materially stronger than the headline in the recent window on
BTC and SOL**, and transfers in sign to all three majors (full-history SOL MAR
7.23, BTC 4.83, ETH 0.91). On SOL it even cuts drawdown (−113 vs −156) while
tripling return. ETH stays the weak leg, as it is for the headline. These are the
same independent confirmations the headline passed — passed here more convincingly.

## What this does and does NOT mean

**Does:** the broadened search found a genuinely better paper candidate. The
`trend_strength` regime-quality gate — a new mechanism, not a parameter tweak —
is economically sensible (counter-trend dip-buying is higher quality inside a
*confirmed-strong* trend than inside a marginal one) and is confirmed out-of-
sample and cross-asset. It re-ranks which cell the lane tracks forward.

**Does NOT:** authorise live capital. It still fails the academic gate
(DSR 0.376, selection-consistent vs 72 trials) and the deployable drawdown cap
(no stop → single-path DD −135.6R ≫ 30R@f=0.01; f≈0.0022 maps it to ~30% equity).
It is the SAME class of result as the headline — a thin-PF, wall-bound, recent-
positive, transfer-confirmed paper signal — just a better-ranked member of it. The
no-stop exit means a worse absolute tail than the headline's wide stop; the 7/7
robustness comes from the regime-quality gate sidestepping the chop, not from risk
control inside the trade.

## Also learned (negative sub-results)

- **Momentum-sign regime (`roc`) is a worse gate than trend-sign** everywhere
  (e.g. 1d roc/rsi PF 1.167 vs price_vs_sma 1.255).
- **The 2-day hold is load-bearing.** Every `@1d` cell is far weaker than its
  `@2d` twin (headline-style rsi/wide_stop MAR 0.19 @1d vs 3.99 @2d) — the
  counter-trend dip needs ~2 days to revert; a 1-day swing exits before it works.

## Outcome & next step

Per the frozen rule this is a BETTER-THAN-HEADLINE re-rank, so the new cell gets
its OWN frozen forward registration (`BROADEN_FORWARD_REGISTRATION.md`), tracked
**in parallel with — not replacing —** the frozen headline registration (no
winner-version-bumping: the headline resolves honestly on its own forward sample).
The broadened grid is otherwise CLOSED per the kill rule: no per-cell parameter
rescue, no re-grid on the same data. Paper only; the 4h Donchian Slice-3 strategy
is untouched.
