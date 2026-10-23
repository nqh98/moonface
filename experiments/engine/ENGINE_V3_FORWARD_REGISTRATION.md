# Engine v3 - Regime-Mechanism - Forward Registration (FROZEN)

**Engine:** v3 (regime-mechanism matrix). Spec:
`docs/research-log/specs/2026-07-06-regime-mechanism-engine-v3-design.md`.
**Pinned hash (`engine_hash_v3(EngineConfigV3())`):** `dccc879a51939ea02394f26ef944276b642089a88cbbab0803a478ece4e02893`
**Registered:** 2026-07-06. **Status:** paper, disabled by default.

## Architecture under test

Regime (`trend/range × volatility`) selects exactly one specialist mechanism
(`BREAKOUT` / `PULLBACK` / `REVERSION`); the mechanism trigger is the sole
trade decision; a size-only quality score scales the position and vetoes
degenerate cases. No trade is created by summing confirmations. `RANGING×HIGH`
and `EXTREME` vol stand flat by design.

## The falsifiable bet (spec §11)

Prior regime work (regime-selector, regime-overlay) failed because regime
filtered an additive score. Here regime is a selector that restricts trading
to where one specialist has edge, and empty cells are first-class. Bet:
selection-not-summation with size-only scoring survives a forward window where
confluence did not.

## Frozen evaluation protocol

- Horizon / sample: verdict at the earlier of 6 months of paper or >= 30
  closed setups.
- Baseline: frozen v2.2 (hash `b4924f8e...`) over the same forward window.
- Promotion bar (all required): net-R > 0 after 3x cost stress; max
  drawdown-R no worse than v2.2; >= 1 mechanism contributes > 0 net-R on its
  own cells. Failing any -> CLOSED NEGATIVE on the selection architecture.
- Discipline: no constant changes after this freeze. Any change = new
  ENGINE_VERSION + new hash + new registration. Starting the paper clock and
  swapping the daemon from v2.2 is a human step, out of scope for this build.
