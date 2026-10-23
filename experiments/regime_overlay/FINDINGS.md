# Donchian × Macro-Regime Overlay — Findings (2026-06-26)

**Verdict: NEGATIVE — no forward-paper-watch candidate.** The pre-registered
practical bar (DSR reported, *not* gated) decided the outcome at the **explore
(train) stage**: zero of 12 overlay cells beat the base Donchian where selection
is legitimately allowed. The sealed/recent slice was **never opened for
selection** (no train+validate survivor). The deployed 4h Donchian remains the
program's only active-paper artifact, **unchanged**.

## Hypothesis tested

The Donchian 4h trend-follower's recent decay is risk-regime-driven; conditioning
the *frozen, byte-identical deployed* Donchian spine (`entry_n=40, trail_n=20,
k_stop=2.0, atr_period=14`, **long-only**, `f=0.01`) on a macro risk-on/off regime
— as a filter/sizer (and, for the long-only base, sourcing shorts in risk-off) —
should improve recent performance and tame drawdown without destroying trend
capture. Information sets combined: **BTC 4h price (Donchian) × FRED macro
(SP500, VIX, broad USD)**.

## What this run is

Frozen 12-cell grid = 4 regime defs × 3 application modes, base **not re-tuned**
(the only searched degree of freedom is the overlay). No-lookahead enforced by the
tested `exogenous` publication-lag aligner. Train → validate → one-touch sealed.

- Regimes: **R1** equity_riskon (SP500 20d mom>0), **R2** equity_trend (SP500
  100d>0), **R3** riskon_calm (mom>0 & VIX<30), **R4** dollar_weak (USD 20d<0).
- Modes: **directional** (longs in risk-on, shorts in risk-off), **derisk**
  (WAIT in risk-off), **size** (½ size in risk-off).
- Windows (ms): train 2020-01-01→2023-11-01, validate →2025-03-01, sealed
  →~2026-06-24. n_trials=12 (DSR reported, never gated).

## Result — explore (train 2020-01 → 2023-11)

Base Donchian (train): **76 trades, net +74.79R, maxDD −8.77R, trailing-365d
+35.60R**, robust to 3× cost (+64.50R). The in-sample base is already strong.

**Every overlay cell strictly degrades it.** `beats_recent` (cell trailing-365d >
base) is **False for all 12 cells**; net R is lower for all 12. Best cell on the
selection criterion (R2-size) still loses −9.59R of trailing-365d vs base. The
macro conditioning only removes net-profitable trades.

→ Per the pre-registered rule (advance iff `all_pass AND beats_recent` on train),
**0 cells advance**. `--select` → `frozen: null`. `--validate` → `verdict:
negative`, **sealed slice untouched**.

## Post-hoc diagnostic (NOT selection, NOT a rescue — lane already closed)

To answer the practical question "would *any* overlay have helped in the recent
chop?", the cells were scored on the sealed window **after** the verdict. This is
reported for honesty only; it cannot and does not change the verdict.

Base Donchian (sealed 2025-03 → 2026-06): **30 trades, −10.24R, maxDD −14.75R** —
the documented bleed.

| sealed cell | trades | net R | maxDD | Δnet vs base | beats_recent |
|---|---|---|---|---|---|
| **R4-directional** | 31 | **+1.39** | −6.60 | **+11.63** | yes |
| R4-derisk | 18 | −3.13 | −7.64 | +7.11 | yes |
| R4-size | 30 | −6.68 | −11.19 | +3.56 | yes |
| (R1/R3 derisk/size) | 23–30 | ≈−9 to −10 | ≈−11 to −13 | +0.1 to +0.6 | yes |
| R1/R3-directional | 33 | −19.37 | −19.37 | −9.13 | no |

**One cell — R4-directional (dollar-weak + shorts-in-risk-off) — genuinely
reverses the recent bleed** (−10.24R → +1.39R) and halves drawdown. That is a
real, mechanism-consistent signal: when the broad USD is strengthening (risk-off),
BTC Donchian **shorts** earned in the 2025-26 downtrend while the long-only base
bled.

**But that exact cell is the worst over full history and was un-selectable:**
- Full 2020-26: R4-directional net **+28.11R vs base +86.00R** (Δ −57.89R), maxDD
  −28.10R.
- On **train** it was the **only** cell to fail the practical bar:
  maxDD −28.10R and **outlier-dependent** (net_r_ex_best1 = **−2.05**).

The shorts that rescue 2025-26 bled badly through the 2020-24 bull. The
recent-helpful cell could only be identified by looking at the held-out answer —
exactly what the holdout discipline forbids. **The recent winner is
regime-specific selection noise, not a robust edge.** The diagnostic *validates*
the protocol: the cell that wins out-of-sample is the one that loses worst
in-sample.

## Honest reading

1. **NEGATIVE is correct.** Macro risk-on/off conditioning does not improve a
   Donchian that is already trending well in-sample; it removes profitable trades.
   The structural finding stands: there is no robust, *selectable* macro overlay
   that beats the base.
2. **The base Donchian's recent drawdown is normal trend-follower chop**, not
   something a macro filter fixes in a generalizable way.
3. **One research breadcrumb (not promotable, not WAIT-forever):** a *dollar-/
   risk-off-conditioned SHORT* strategy (its own engine, not a filter on the long
   base) is the only thing that monetized the recent downtrend. It would need its
   own honest pre-registration and would have to survive its catastrophic 2020-24
   behavior — i.e., it is a *different* hypothesis (regime-gated shorts), not a
   rescue of this one. Left to the human.

## Status / isolation

PAPER-only research. `promotion/`, `journal/signals.jsonl`, `EXIT_REGISTRY`, and
the Donchian Slice-3 forward registration are **untouched**. No promotion, no
paper-watch start. Lane CLOSED NEGATIVE; no v2 in this session.

## Reproduce (committed code only)

```
.venv/bin/python -m tools.regime_overlay_btc --register --out-dir experiments/regime_overlay
.venv/bin/python -m tools.regime_overlay_btc --explore  --out-dir experiments/regime_overlay
.venv/bin/python -m tools.regime_overlay_btc --select   --out-dir experiments/regime_overlay
.venv/bin/python -m tools.regime_overlay_btc --validate --out-dir experiments/regime_overlay
```
(FRED series SP500/VIXCLS/DTWEXBGS and BTCUSDT 4h candles/funding are read from
`cache/swing`; the post-hoc diagnostic re-uses `evaluate.base_vector`/`cell_vector`
over the sealed and full windows.)
