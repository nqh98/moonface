# Matrix Step-A Slice-1 — Regime Router Floor Comparison Results

**Date:** 2026-07-07
**Lane:** AI-Assisted Smart Matrix (v2.2), Module A — regime→mode Router, Slice 1.
**Verdict:** `CLOSED_NEGATIVE (read-only, power-checked)` — no sealed-lockbox spend.
**Report:** `experiments/engine/matrix_router_20260707T120926Z.json`
**Predecessors:** Step B causal pipeline (`bae90f2`), Step C ablation floors (`d07afb0`).
**Router code:** `src/moonface/research/matrix/router/` (`b50ed20`→`685deda`).

## Thesis tested (read-only, descriptive — no verdict/gate by design)

Does AI-regime conditioning of the Step C Donchian baseline beat **both** deterministic
floors after realistic costs — B1 (raw stop-and-reverse) and B2 (Donchian + ATR-freeze)?
Modes: 1 = trend 1.0×, 2 = quarantine 0.25×, 3 = freeze. State→mode map is per-window,
train-only (label-switching safe); entropy>0.90 forces freeze.

## Descriptive floor comparison (SEALED segment, the OOS-honest read)

| sealed | n | net_R | maxDD | ev/trade | MAR 1× | MAR 2× |
|---|---|---|---|---|---|---|
| Router     | 36 | +0.161 | −0.232 | +0.0057 | 0.73 |  0.56 |
| Baseline 1 | 43 | +0.047 | −0.359 | +0.0028 | 0.13 |  0.008 |
| Baseline 2 | 41 | +0.002 | −0.359 | +0.0017 | 0.006 | −0.105 |

On the raw descriptive read the router beat **both** floors on every axis (net, drawdown
depth, per-trade expectancy, cost-robustness) — the first overlay in the whole program to
improve rather than subtract from the floor. Absolute economics were already trivial
(+0.16R over the entire sealed span; ev +0.0057R/trade, an order of magnitude under the
0.05R economic bar).

## Power check (read-only bootstrap, n=36, 20k resamples, seed 12345) — DECISIVE

| sealed 1× | ev/trade | 95% CI | P(ev>0) | ≥0.05R bar? |
|---|---|---|---|---|
| Router     | +0.00570 | [−0.01188, +0.02537] | 0.710 | no |
| Baseline 1 | +0.00276 | [−0.01427, +0.02155] | 0.603 | no |
| Baseline 2 | +0.00173 | [−0.01555, +0.02093] | 0.553 | no |
| router−B2  | +0.00397 | [−0.02191, +0.02996] | 0.618 | — |
| router−B1  | +0.00294 | [−0.02288, +0.02861] | 0.586 | — |

(2× cost identical story; ev/trade reconciles exactly with the JSON report's `ev_per_trade`.)

**The descriptive win does not survive an honest CI:**
1. The router's own OOS per-trade edge is indistinguishable from zero (P=0.71, a coin).
2. The "router beats B2" gap is a 62% coin flip — difference CI straddles zero.
3. No strategy's ev CI comes within 2× of the 0.05R economic bar.

This reproduces the `signal-matrix-horizon-harvest` n=8→n=106 collapse without spending
the lockbox: the encouraging descriptive ranking was an underpowered (n=36) artifact.

## Conclusion & stop

The AI regime router does **not** reliably beat the deterministic ATR-freeze floor (B2) OOS.
Same structural drawdown wall every prior regime overlay hit (regime-overlay, regime-selector,
donchian-adx-filter, donchian-volregime — all CLOSED NEGATIVE). **Slice 2 (Gate 1 verdict) is
not justified** — nothing is statistically powered to gate; registering it would spend the
sealed BTC tail to confirm a null already established for free. Sealed tail **preserved,
unspent**. Slice 3 (15m Sniper) remains free-data-blocked (aggressor-trades infeasible).

## Known defect (unfixed)

`tools/matrix_router.py` imports sibling `tools.matrix_baselines` but only puts `src/` on
`sys.path`, so `python tools/matrix_router.py` crashes (`ModuleNotFoundError: tools`); it runs
only as `python -m tools.matrix_router` from repo root (tests pass because pytest adds rootdir).
Fix if the instrument is re-used.
