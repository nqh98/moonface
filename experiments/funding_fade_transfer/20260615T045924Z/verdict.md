# funding_fade_transfer v1 — verdict

- **Date:** 2026-06-15
- **Status:** CLOSED NEGATIVE (kill rule fired; no v2)
- **Domain:** `funding_fade_transfer` v1 — frozen 4-spec grid (ETH, SOL × `funding_fade {window:60, z_thr:1.5}` × {fixed_bracket, atr_trail} × fraction 0.01)
- **Lockbox:** never touched (`lockbox_touched = False`). Every spec was rejected at stage 2 before any tail was evaluated; the one-touch tail is pristine.
- **Lineage:** successor to the closed profit-maximization program (`experiments/PROGRAM_CONCLUSION.md`, "The one lever deliberately not pulled"). Spec: `docs/research-log/specs/2026-06-15-funding-fade-transfer-design.md`.

## The finding this tested

The closed program's single best OOS construction — `funding_fade {w:60,z:1.5}` + a bounded exit — was rejected on BTC *only* by the fixed absolute −15R drawdown cap; its OOS expectancy was positive (+76.7R, +1.13R/trade). The hypothesis (spec §2): that rejection was a fixed-cap artifact, and the edge clears the standard MAR/sizing/DSR/lockbox ladder on assets the funding probe never touched.

## Decision rule (spec §5, pre-committed)

- **Promotion** requires the frozen construction to clear the full ladder on **BOTH ETH and SOL**.
- **Kill:** if neither clears, the lever is **closed** — the −15R rejection was not a fixed-cap artifact; no v2, no fraction-grid rescue.
- BTC (the contaminated/selected asset) is reported as in-sample reference only and never counts toward the verdict.

## Result — both assets fail at stage 2 (holdout)

| asset | exit | screen n | screen exp R | holdout MAR | holdout DD | research MAR | DSR | status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| ETH/USDT:USDT | fixed_bracket | 166 | +0.147 | **−0.972** | −54.0% | −0.662 | — | rejected |
| ETH/USDT:USDT | atr_trail | 166 | +0.888 | **−0.835** | −48.2% | +2.486 | — | rejected |
| SOL/USDT:USDT | fixed_bracket | 174 | +0.116 | **−0.784** | −37.2% | −0.358 | — | rejected |
| SOL/USDT:USDT | atr_trail | 174 | +0.296 | **−0.750** | −35.1% | +0.277 | — | rejected |

Gate (`research/ladder.py`, unchanged): stage 1 = ≥30 trades & screen expectancy R > 0; stage 2 = holdout MAR > 0 & drawdown ≥ −30%.

- **Stage 1 (screen):** all 4 pass — the entry has positive directional expectancy in-sample on **both** assets (drift is real on the screen window).
- **Stage 2 (holdout):** all 4 **fail on both criteria** — holdout MAR is negative on every spec, and every drawdown breaches the −30% budget. The drift does **not** survive out-of-sample on either independent asset.
- **Stage 3 (DSR) / Stage 4 (lockbox):** never reached. No `oos_pass` row, no corrected survivor, no tail evaluation.

## BTC Q1 reference (in-sample, NOT validation)

Re-expresses the discovery finding under the sizing frame on the contaminated asset. Reported for context only; it cannot and does not change the verdict.

| exit | trades | MAR | Sharpe | netRet | maxDD% |
|---|---:|---:|---:|---:|---:|
| fixed_bracket | 323 | 6.795 | 0.138 | 2.178 | −32.1% |
| atr_trail | 323 | 8.101 | 0.146 | 2.978 | −36.8% |

Under the sizing frame the BTC rejection does flip reject→pass on MAR (6.8 / 8.1) — confirming the lever's premise *in-sample on the asset selection was performed on*. But that in-sample strength (BTC MAR ≈ 7–8, vs ETH/SOL research MAR ≈ −0.7…+2.5) does not transfer: on ETH/SOL the holdout MAR is decisively negative.

## Kill call

**The unpulled lever is closed.** Neither ETH nor SOL cleared stage 2, so promotion was never in reach and DSR/lockbox were never spent. The −15R rejection was **not** purely a fixed-cap artifact: even with the absolute cap swapped for the MAR/sizing frame, the funding_fade construction is **out-of-sample-negative on two independent assets**. The drawdown wall is structural under sizing as well — consistent with every prior single-asset directional family in this program.

No v2, no fraction-grid rescue, no budget-relaxation retry (spec §5 kill rule; spec §8 explicitly out of scope).

## Discipline notes

- **Lockbox pristine.** Rejected at stage 2; `lockbox_touched = False`. No tail was evaluated, so nothing downstream is contaminated by this run.
- **Pre-registration held.** The frozen 4-spec grid was evaluated exactly as registered; no grid widening, no exit/entry variation, no second look.
- **This was the explicit successor** named in the 2026-06-10 conclusion ("the one lever deliberately not pulled"). It has now been pulled, under its own pre-committed discipline, and returned a clean negative. With it, the last data-motivated free-data hypothesis raised by the original program is resolved.

## Artifacts

- Auto-generated leaderboard: `experiments/research/funding_fade_transfer/report_v1.md` (untracked scratch DB at `experiments/research/research.db`).
- BTC reference CLI: `python3 tools/research.py funding-ref`.
- Verdict memory: `funding-fade-transfer-results.md`.
