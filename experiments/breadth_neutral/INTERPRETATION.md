# Market-neutral falsification — honest interpretation (2026-06-28)

## Headline: the cross-asset confirmation was crypto beta

The cross-asset lane showed the breadth leads positive on BTC, ETH, and SOL in
the same window, but warned the three assets are not independent (crypto
cross-correlation). This lane removes the BTC-beta component of each ETH/SOL
trade's PnL over its actual holding window (rolling trailing beta, no
look-ahead) and re-judges the residual.

`anchor_ok=True` — beta=0 reproduces the cross-asset raw expectancy
bit-for-bit (0.4737/0.1929/0.4071/0.0926), so the trade set and exit are
identical; only the beta component is stripped.

| asset | lead | raw exp | hedged exp | β-contribution | mean β | hedged verdict |
|---|---|---|---|---|---|---|
| ETH | net_new_highs | +0.474 | **−0.049** | +0.523 | 1.15 | negative (sign-flip) |
| SOL | net_new_highs | +0.407 | **−0.020** | +0.427 | 1.35 | negative (sign-flip) |
| SOL | breadth_momentum | +0.093 | **−0.044** | +0.136 | 1.36 | negative |
| ETH | breadth_momentum | +0.193 | +0.043 | +0.150 | 1.16 | forward_candidate (p=0.29) |

**The β-contribution accounts for essentially the entire raw edge.** Strip crypto
beta and `net_new_highs` — the program's strongest, most persistent lead — has
*no* independent edge on ETH/SOL: it goes negative on both, with sign-flip across
windows. `breadth_momentum` goes negative on SOL.

## The lane verdict label overstates the result

The pre-registered rule prints `RESIDUAL_SURVIVES` because **one** cell
(ETH × breadth_momentum) is `residual_positive`. That cell is hedged **+0.043R
at p=0.29** — statistically indistinguishable from zero, a noise residual on an
n=653 high-frequency signal. The verdict was computed honestly per the frozen
rule and is left unchanged, but the correct economic read is **beta_explained**:
the cross-asset "breadth of evidence" was a single crypto-beta bet seen through
three correlated assets, exactly as the cross-asset caveat suspected.

## What this resolves (and what it does not)

Three independent perturbations of the breadth-internal leads:
1. **Universe (disjoint slices):** both leads wash to ~0 → fail.
2. **Asset (ETH/SOL traded leg):** survive in sign — *but*
3. **Market-neutral (BTC-hedged):** the asset survival is **entirely crypto
   beta**; no residual edge.

Together: the breadth signal is a **crypto-beta timing overlay** that looked like
an edge in the recent up-regime, not a market-neutral alpha. Its apparent
strength was inflated by winner's-curse on the universe and by beta in an up
market.

**What it does NOT kill:** BTC cannot be hedged against itself, so this lane does
not touch the original BTC directional lead. `net_new_highs` on BTC remains the
underpowered `forward_candidate` it always was (pooled n=66), now stripped of the
cross-asset support that made it look stronger. Its only honest resolution is the
frozen forward-paper journal over real time. As a *market-neutral* strategy the
breadth family is closed; as an underpowered *directional BTC* lead it is
unchanged — alive only on paper, never significant.

Paper-only. Nothing here authorizes live capital.
