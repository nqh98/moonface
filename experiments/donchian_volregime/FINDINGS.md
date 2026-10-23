# Donchian × Volatility-Regime Filter — Findings (2026-07-02)

**Verdict: NEGATIVE — no forward-paper-watch candidate.** Decided at the **explore
(train) stage**: 0 of 5 pre-registered regime cells passed the train qualifier, so
`--select` froze `null` and the sealed holdout was **never opened** (mirrors
`regime_overlay`). Paper-only. The deployed 4h Donchian is unchanged.

Spec (frozen before run): `docs/research-log/specs/2026-07-02-donchian-volregime-design.md`.
Code: `src/moonface/research/donchian_volregime/`, `tools/donchian_volregime.py`.
Reproduce: `--register → --explore → --select → --validate` (`.venv/bin/python -m
tools.donchian_volregime --<stage> --out-dir experiments/donchian_volregime`).

## Hypothesis

The frozen BTC 4h Donchian 40/20 (long-only) should not trade in all environments;
its edge should concentrate in **High-Volatility + Expansion / Trending** regimes,
and default to WAIT in range-bound / low-vol / compressed regimes. Gate = strict
subset of the base trade stream, keyed on the **entry bar's** regime label; the
engine (entries/exits/costs) is byte-frozen and unchanged.

## What was tested — 5 pre-registered cells (n_trials=5)

ATR percentile≥0.60 · HV percentile≥0.60 · ATR(14)/ATR(100)≥1.0 (expansion) ·
Donchian-width/ATR ≥ trailing median (not compressed) · composite (ATR-pct≥0.60 AND
expansion≥1.0). All features point-in-time, no look-ahead. Windows identical to the
control lanes (train 2020-01→2023-11, validate →2025-03, sealed →~2026-06).

## Correctness anchor

Base Donchian train reproduces `donchian_filter` **exactly**: n=76, net +74.79R,
maxDD −8.77R, robust_frac 0.833, PF 2.75 — confirming the frozen spine is
byte-identical to the ADX-gate control.

## Result — explore (train 2020-01 → 2023-11)

| cell | n | net R | expectancy | PF | maxDD | robust_frac | qualifies |
|------|---|-------|-----------|----|-------|-------------|-----------|
| **base (no gate)** | **76** | **+74.79** | +0.984 | 2.75 | −8.77 | 0.833 | — |
| hv_pct | 29 | +9.52 | +0.328 | 1.68 | −3.54 | 0.833 | ❌ |
| expansion | 28 | +9.23 | +0.330 | 1.75 | −3.79 | 0.833 | ❌ |
| hivol_expansion | 20 | +1.27 | +0.063 | 1.12 | −3.54 | 0.667 | ❌ |
| atr_pct | 23 | −1.30 | −0.057 | 0.90 | −4.48 | 0.583 | ❌ |
| not_compressed | 11 | −4.67 | −0.425 | 0.52 | −6.69 | 0.333 | ❌ |

**Every cell fails the train qualifier** (net_r ≥ 0.90×base AND maxDD strictly
better AND robust_frac ≥ base AND n ≥ 0.50×base). All 5 fail **trend-capture**
(best cell keeps only ~13% of base net_r) and **activity** (best keeps ~38% of
trades); most also fail robustness. → `frozen = null`; sealed slice untouched;
`--validate` → `verdict: negative`.

## Honest interpretation — the gate removes the profitable trades

The hypothesis is **falsified**, and in an informative way. Restricting Donchian to
already-high-volatility / already-expanded / already-non-compressed bars **removes
the bulk of the trend-follower's edge**:

- The best regime cells (HV-pct, expansion) capture only **~+9.5R of the base
  +74.8R** — ~13% of the profit — while cutting trade count by ~62%.
- The composite "High-Vol + Expansion / Trending" cell nets **+1.27R** (near
  breakeven): the specific regime the hypothesis bets on is where Donchian barely
  makes money.
- `atr_pct` and `not_compressed` go **negative** in-sample.

Mechanistically this is the **mirror image of the `donchian_filter` (ADX) result**:
- `donchian_filter` showed the 2025–26 drawdown is high-ADX (high trend-strength)
  breakout *failures*, not low-vol chop.
- This lane shows that conditioning *into* high-vol/expansion regimes strips out the
  trades that actually pay. A Donchian breakout **earns by being early into an
  expansion** (breaking a compressed range), not by waiting until volatility is
  already elevated — by which point the move is largely spent.

Together with `regime_overlay` (macro risk-on/off, also 0-of-12 in-sample), the
**volatility-regime and macro-regime filter families are now definitively closed**
for this Donchian spine. No selectable regime filter improves it.

## LLM narrative veto gate (optional layer) — forward-only, not backtested

Pre-registered as a **permission/veto layer only** (schema + decision rule +
tested pure `combine`): labels {allow, veto, reduce_risk, uncertain}; the LLM never
sets direction/entry/exit/stop/target. It cannot be honestly backtested (an LLM's
knowledge cutoff bakes hindsight into historical scoring — spec §11.1), so it is
registered **disabled** for forward paper validation only
(`LLM_FORWARD_REGISTRATION.json`, t0=1782300000000). No historical numbers claimed.
Given the quantitative regime family is closed negative, enabling it is human-gated
and low-priority — a veto layer cannot rescue an engine whose in-regime trades are
themselves near-breakeven.

## Comparison summary (Donchian alone vs regime filters)

| approach | outcome |
|----------|---------|
| Donchian alone (frozen 4h 40/20) | the reference; already-active paper, unchanged |
| Quant vol-regime filter (this lane) | **NEGATIVE** — removes the profitable trades |
| ADX trend-strength gate (`donchian_filter`) | NEGATIVE — DD is high-ADX failures |
| Macro risk-on/off overlay (`regime_overlay`) | NEGATIVE — 0/12 in-sample |
| LLM narrative veto (this lane) | forward-only scaffold, disabled, not run |

## Kill rule / status

Closed negative per §9: no threshold re-tuning, no new features, no long/short flip,
no exit change, no v2 regime rule. `promotion/`, `journal/`, `EXIT_REGISTRY`, and the
Donchian Slice-3 forward registration are untouched. No promotion, no paper-watch
started. **This path is closed negative.**
</content>
