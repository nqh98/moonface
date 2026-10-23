# funding_fade_voltarget — Design Spec (pre-registered research program)

- **Registered:** 2026-07-02
- **Status:** design approved 2026-07-02; pre-registration to be frozen by the `register` command before any out-of-sample evaluation.
- **Lineage:** successor to `funding_fade_transfer` (closed negative 2026-06-15) and the profit-maximization program (`docs/findings/PROGRAM_CONCLUSION.md`). Explicitly NOT a continuation of either; the single new lever is per-trade **vol/risk targeting**, which no prior program applied to `funding_fade`.
- **Falsification-first:** one frozen construction, decided once, no rescue optimization.

## 1. Hypothesis

`funding_fade{window:60, z_thr:1.5}` (entry) + `fixed_bracket{k_stop:2.0, m_tp:4.0, atr_period:14}` (exit), sized by **vol/risk targeting** (constant stop-risk per trade, iso-average-risk calibrated), earns positive out-of-sample risk-adjusted return on ETH and SOL **and beats the fixed-fractional baseline on both MAR and Sharpe**.

Falsifiable complement: if vol/risk targeting does not beat fixed-fractional sizing on both MAR and Sharpe out-of-sample, then the prior negative was not a sizing artifact — the edge is dead under every sizing rule tested, and the lever is closed.

## 2. Why this is a new program, not a v2

- `funding_fade_transfer` (closed negative) tested the MAR + fractional-sizing reframe with **fixed-fractional `f=0.01`** on ETH/SOL. All 4 specs failed stage 2 (holdout MAR −0.97 / −0.83 / −0.78 / −0.75).
- The 15R-DD program used fixed-fractional sizing throughout.
- `drift_basket` (closed negative) applied vol targeting to a **different signal** (donchian) at **portfolio level** (market-neutral basket).

**The single variable changed here is the per-trade sizing rule.** It is isolated by iso-average-risk calibration (§5), so a "win" can only come from *redistributing* risk away from high-vol entries toward low-vol entries — not from sizing up or down overall. This is a distinct, testable mechanism that no closed program evaluated.

## 3. Data, universe, splits

- **Universe:** `ETH/USDT:USDT` and `SOL/USDT:USDT` perpetuals, 4h, Binance USDⓈ-M (free OHLCV + funding, same provider as all prior programs). **BTC is excluded** — it is the discovery asset for the `funding_fade` family and therefore in-sample regardless of windowing. ETH and SOL are clean (no family selection was performed on them).
- **Window:** full available history, 2020-01-01 → 2026-06-21 (~6.5 yr, 4h). `funding_fade` requires `window=60` bars of funding history before its first signal; that burn-in is part of the window, not extra data.
- **Lockbox tail:** final **20%** of the window is sealed as a one-touch lockbox (`LOCKBOX_FRACTION = 0.2`). It is currently **pristine** — `funding_fade_transfer` failed at stage 2 and never spent it. It is spent exactly once, only if stages 1–3.5 pass, as the final arbiter.
- **Research window (first 80%):** standard ladder split — screen = first 70%, holdout = remaining 30% — **plus** rolling walk-forward folds (§6.4).

## 4. Construction (frozen, single per asset)

- Entry: `funding_fade {window: 60, z_thr: 1.5}` — `src/moonface/research/edge/funding_signals.py:11`.
- Exit: `fixed_bracket {k_stop: 2.0, m_tp: 4.0, atr_period: 14}` — `src/moonface/foundation/exits.py:61`.
- Two registered specs: `(ETH, treatment)` and `(SOL, treatment)`. `n_trials = 2`. No entry/exit/lookback grid.

## 5. Treatment vs control — the one variable

Both consume the identical `(entry_index, net_R, atr_frac)` stream from `ladder.r_stream` (`src/moonface/research/ladder.py:23`), where `atr_frac_i = ATR(14)/price_i` is the bracket's own risk unit, already emitted per trade. **Same entries, same exits, same splits — only the sizing rule differs.**

### Control (baseline)
Fixed-fractional `f = 0.01` via the existing path `equity_summary(trades, fraction)` (`src/moonface/foundation/metrics.py:70`): per-trade return `= min(0.01, MAX_LEVERAGE·atr_frac_i) · net_R_i`. Identical to `funding_fade_transfer`.

### Treatment — vol/risk targeting, iso-average-risk
Equalize **stop-risk per trade** using the bracket's own risk unit (no new parameter, no second vol lookback — `ATR(14)/price` is already the per-trade `atr_frac`):

1. Raw per-trade notional fraction: `f_raw_i = target_risk / atr_frac_i` (notional inversely proportional to ATR ⇒ constant stop-risk `target_risk`).
2. Clamp: `f_i = clamp(f_raw_i, floor, MAX_LEVERAGE · atr_frac_i)` with `floor = 0` and `MAX_LEVERAGE = 5.0`. The upper bound is the existing leverage clamp.
3. **Iso-average-risk calibration:** choose the scalar `target_risk` (1-D monotone search, unique) so that `mean(f_i over screen-window trades) = 0.01`. The treatment therefore carries the **same average risk footprint as the control**; any MAR/Sharpe delta is purely from risk *stabilization*, not overall size.
4. Per-trade sized return `= f_i · net_R_i`; the sized return stream feeds the existing `equity_summary_from_returns(returns)` (`src/moonface/foundation/metrics.py:48`), which already accepts per-trade-sized returns.

> **Parameter resolution (recorded):** the design discussion listed both "vol lookback L=60" and "the bracket's own risk unit." These conflict. This spec freezes on the **bracket's own risk unit `atr_frac = ATR(14)/price`** — it adds zero parameters, directly equalizes the actual stop distance, and reuses the per-trade quantity `r_stream` already emits. The separate L=60 lookback is dropped.

## 6. Evaluation structure — Hybrid (standard ladder + rolling walk-forward + lockbox)

Stages 1–4 are the program's standard ladder (`src/moonface/research/ladder.py`), unchanged in threshold. Stage 3.5 is new. **Control and treatment are both evaluated on identical splits.** The absolute ladder gate applies to the treatment; in addition, **the paired-dominance requirement (treatment `MAR > control MAR` AND treatment `Sharpe > control Sharpe`, strict) is enforced uniformly at stages 2, 3.5, and 4** — the three OOS venues (holdout, WF aggregate, lockbox tail).

| Stage | Gate (treatment) | Implementation |
|---|---|---|
| 1 Screen | `screen_trades ≥ 30` and `screen_expectancy_R > 0` | `ladder.stage1_passed` (unchanged) |
| 2 Holdout | `holdout_MAR > 0` and `holdout_DD ≥ −0.30`, **AND** treatment dominates control on MAR & Sharpe | `ladder.stage2_passed` (unchanged) + paired check |
| 3 DSR | Deflated Sharpe ≥ 0.95, deflated over the 2 registered treatment specs | `ladder.stage3_dsr` (unchanged), `grid_size = 2` |
| **3.5 WF (new)** | WF aggregate-OOS: treatment `MAR > 0` **and** treatment dominates control on MAR & Sharpe | new `walk_forward_funding_fade` |
| 4 Lockbox | one-touch tail `MAR ≥ 1.0` and `DD ≥ −0.30` and `tail_trades ≥ 10`, **AND** treatment dominates control on MAR & Sharpe | `ladder.stage4_passed` (unchanged) + paired check |

### 6.4 Rolling walk-forward (stage 3.5) — frozen geometry
- Train window **3 yr**, test window **6 mo**, step **6 mo**, all on 4h bars, within the research window only (never the lockbox tail).
- Per fold: calibrate `target_risk` on that fold's **train window only** (iso-average-risk, `mean(f_i)=0.01` over train trades — no lookahead into the test window); size the test-window trades for treatment; control uses constant `f=0.01`.
- Pool test-window returns across all folds; compute aggregate `EquitySummary` for treatment and control via `equity_summary_from_returns`.
- Gate: treatment aggregate `MAR > 0` and strict dominance of control on both MAR and Sharpe.

### 6.5 Calibration windows (no-lookahead discipline)
- Ladder screen/holdout and lockbox: `target_risk` calibrated on the **screen window** (first 70% of research); that scalar is frozen and applied unchanged to holdout and lockbox tail.
- Walk-forward: `target_risk` re-calibrated in each fold's train window (the only place WF recalibrates).
- The lockbox tail is sized with the screen-window `target_risk` — never re-fit on tail data.

## 7. Decision — the clear verdict

- **→ PAPER-LIVE WATCHING** iff the treatment clears stages 1, 2, 3, 3.5, and 4 **and** beats the control on MAR and Sharpe on the holdout **and** the WF aggregate **and** the lockbox tail. This is the `closed_positive` equivalent and earns forward paper tracking.
- **→ CLOSED NEGATIVE** otherwise (any stage fail, or any failure to dominate the control). No near-miss promotion.

## 8. Kill rule & discipline

- Frozen construction; `n_trials = 2`. One frozen sizing rule (treatment as defined in §5); control is the benchmark, not a selectable trial.
- **No second vol lookback, no fraction grid, no budget relaxation, no entry/exit variation, no per-fold param selection** (WF calibrates the scalar `target_risk` only).
- A near-miss is a reject (the `mom_30` DSR-0.83 and `funding_fade_transfer` precedents).
- Lockbox is one-touch; a second spend raises. `touch_lockbox` is set-once (`src/moonface/research/runner.py:131`).
- Closed-negative ⇒ the vol/risk-targeting lever is terminal for `funding_fade + fixed_bracket`; no v2.

## 9. Build vs reuse

**Reuse unchanged:**
- `funding_fade` entry, `fixed_bracket` exit, `single_trade_r`, `summarize_r`, `deflated_sharpe` — `src/moonface/foundation/{exits,risk,metrics}.py`, `src/moonface/research/edge/funding_signals.py`.
- Control sizing + compounding: `equity_summary(trades, fraction)`.
- Treatment compounding: `equity_summary_from_returns(returns)` (already per-trade-sized).
- One-touch tail discipline: `FencedBundle`, `Store.touch_lockbox` — `src/moonface/research/{lockbox,store,runner}.py`.
- Stage thresholds and DSR: `src/moonface/research/ladder.py`.
- Report writer: `src/moonface/research/report.py`.

**New / extend:**
1. **Vol-targeted sizer + iso-average-risk calibration** — produces `f_i` per trade and the 1-D `target_risk` search (`mean(f_i) = 0.01`).
2. **Paired control/treatment evaluation** — fold both EquitySummaries into a row's stage results; gate on treatment clearing stages *and* dominating control.
3. **`walk_forward_funding_fade`** (stage 3.5) — adapt the `src/moonface/research/walkforward.py` pattern: funding_fade+fixed_bracket via `r_stream`, per-fold `target_risk` calibration, **no param selection**, paired control/treatment per fold, pooled test-window aggregation.
4. **Registration** — `experiments/funding_fade_voltarget/PREREGISTRATION.md` + the `register` command (refuses overwrite, per convention); frozen 2-spec grid.

## 10. Artifacts

- Design spec (this file): `docs/research-log/specs/2026-07-02-funding-fade-voltarget-design.md`
- Pre-registration: `experiments/funding_fade_voltarget/PREREGISTRATION.md` (+ `registration.json`)
- Run + verdict: `experiments/funding_fade_voltarget/<timestamp>/verdict.md`
- Verdict memory: `funding-fade-voltarget-results.md` (project memory)

## 11. Out of scope (explicit)

- BTC (contaminated; reported as in-sample reference only if at all, never counts toward the verdict).
- Re-running the closed ETH/SOL results under fixed-fractional sizing as a rescue — the control is measured for the paired delta, not re-litigated.
- Any signal/exit family other than `funding_fade + fixed_bracket`.
- Portfolio-level / cross-sectional / market-neutral constructions (already exhausted by `drift_basket`).
