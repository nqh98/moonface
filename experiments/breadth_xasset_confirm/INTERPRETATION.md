# Cross-asset transfer — honest interpretation (2026-06-28)

The auto-generated `FINDINGS.md` reports the mechanical verdict
(`MECHANISM_UNCONFIRMED`). This note records the nuance, because the result is
**not** the clean negative that was pre-committed as expected.

## What actually happened

`anchor_ok=True` — both leads reproduce the BTC discovery byte-for-byte
(net_new_highs val 0.5323/n34, seal 0.2588/n32; breadth_momentum val 0.1652/n327,
seal 0.1424/n326), so the wiring is proven before any ETH/SOL number is read.

All four (lead × asset) cells came back **`forward_candidate`**: positive pooled
OOS expectancy, same sign across validate and sealed. None reached the
family-wise significance gate (α/K = 0.0125), so nothing is confirmed. But the
sign evidence is uniform:

| asset | lead | pooled exp | PF | maxDD | practical | cost | p(≤0) |
|---|---|---|---|---|---|---|---|
| ETH | net_new_highs | +0.474 | 1.73 | −10.6R | ✅ | ✅ | 0.040 |
| SOL | net_new_highs | +0.407 | 1.69 | −7.4R | ✅ | ✅ | 0.059 |
| ETH | breadth_momentum | +0.193 | 1.27 | −43.2R | ❌ (DD) | ✅ | 0.045 |
| SOL | breadth_momentum | +0.093 | 1.13 | −43.1R | ❌ (DD) | ✅ | 0.184 |

`net_new_highs` passes **practical + cost** robustness on *both* independent
traded legs and misses only strict significance — its best cross-asset showing
in the program. The leads are positive in sign on BTC, ETH, and SOL.

## Why this is NOT a confirmation (the decisive caveat)

**The three "assets" are not three independent experiments.** Every cell's OOS
window is the *same calendar period* (~2023.5–2026, the recent 40% of each
asset's bars), and BTC/ETH/SOL are highly cross-correlated. "Positive on BTC,
ETH, and SOL in the same up-trending window" is largely **one** piece of
evidence — a breadth signal catching crypto beta in a favorable regime — viewed
through three correlated lenses. The effective independent sample is far smaller
than the nominal n, so the per-cell p-values (0.04–0.18) overstate the evidence,
and family-wise significance is correctly *not* reached.

Two more yellow flags:
- **The cleaner cells are the least powered.** The practical-passing cells are
  the small-n net_new_highs ones (n≈60–66); the high-frequency breadth_momentum
  (n≈600) fails practical on a −43R drawdown. Small n is where noise wins.
- **Period dependence.** On the in-sample train window (~2020–2023.5) both leads
  are *negative/flat* on ETH/SOL (net_new_highs −0.20/−0.14); they only turn
  positive in the recent OOS regime. The edge, if any, is regime-conditional.

## Reconciling with the disjoint-universe failure

The disjoint-universe lanes killed the leads when the breadth was recomputed on
rank-20–60 coins. Cross-asset keeps the **top-20** breadth and varies only the
traded leg — and the leads survive. Read together, this is consistent with a
mechanism that is *specifically top-20-market-leader breadth timing crypto beta*:
fragile to universe composition (tail coins don't carry it), shared across the
major assets, and concentrated in the recent regime. That is a coherent story —
but coherent is not confirmed, and the cross-correlation caveat means it is still
underpowered, not significant.

## Verdict and next falsification

**No promotion.** `net_new_highs` remains the program's most persistent
underpowered lead; it now refuses to die on an independent-asset axis but still
will not reach significance. The binding confound is no longer *asset* — it is
**time** (one OOS regime) and **crypto-beta correlation**. The honest resolutions
are therefore:
1. the frozen forward-paper registrations (time-disjoint, resolve slowly); and
2. a **market-neutral** framing — does top-20 breadth predict each asset's
   *beta-residual*, or is it just "long crypto beta in an up market"? That test
   would separate a real timing edge from regime exposure.

Paper-only. Nothing here authorizes live capital.
