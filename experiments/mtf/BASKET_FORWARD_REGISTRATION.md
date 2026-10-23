# MTF Equal-Weight Basket — Forward Paper Registration (frozen)

Registering the equal-weight cross-asset basket of the frozen MTF headline cell
for forward, out-of-sample evaluation. This is the honest resolution of one
in-sample observation: the basket does **not** clear the deployable ECON_BAR (PF
1.13 < 1.2, single-path DD over the fixed-f cap), but it **does** fix the single
thing the BTC-only signal failed — robustness — lifting robust_frac from 0.553 to
0.714 and winning the recent (2024-06+) window on MAR (basket 1.18 vs BTC 0.996,
ETH 0.724, SOL 0.891). The claim under test is narrow and falsifiable: *equal-
weight diversification of this one signal is more robust than the best single
asset, going forward.* Paper only; promotes nothing to live. The frozen 4h
Donchian Slice-3 strategy and the single-asset MTF forward registration are
untouched and resolve independently.

- **asof:** 2026-07-01
- **frozen cell:** `grid.headline_cell()` = `1d:price_vs_sma|rsi_reversion|horizon_wide_stop`
- **construction (frozen, no refit):** equal 1/N risk weight per asset, single
  faithful merged time-ordered equity path (`basket.merge_streams`); N = 3
- **assets (frozen):** BTCUSDT, ETHUSDT, SOLUSDT — each gated by its OWN 1d trend
- **weights (frozen):** equal 0.3333 each. Equal weight is the only non-data-mined
  construction; no per-asset weight, asset selection, or drop-the-weak-leg choice
  is permitted on the same data — that would be the winner's-curse the program has
  repeatedly caught.

## Forward window & resolution

- **forward_start_ms:** 1_782_000_000_000 (end of the registration dataset). Only
  trades whose entry timestamp is >= this boundary count toward resolution.
- **minimum sample:** resolve at the FIRST point where forward basket trades
  n >= 120 AND >= 6 calendar months have elapsed (whichever is later). The basket
  takes ~3x single-asset volume (~450 trades/yr), so ~3-4 months reaches n=120.
- **live-faithful:** bias and trigger use only closed bars (point-in-time by
  construction); no look-ahead; 0.1% round-trip costs applied. Re-run with
  `tools/mtf_basket.py` semantics (`trade_stream` per asset ->
  `basket.merge_streams(1/3)` -> `period_stats(start_ms=forward_start)`).

### Gate (frozen)

| outcome | condition on the forward basket sample |
|---|---|
| **REAFFIRM** (robust-paper-vehicle stands) | basket PF >= 1.10 AND expectancy_r > 0 AND total_r > 0 AND basket MAR >= the median single-asset MAR over the same forward window AND both LONG and SHORT taken |
| **DOWNGRADE / CLOSE** | basket PF < 1.10 OR expectancy_r <= 0 OR total_r <= 0 OR basket MAR < the median single-asset MAR (diversification advantage did not persist) |

Kill rule: a DOWNGRADE closes the basket lineage — no per-asset reweighting, no
leg dropped, no v2 on the same data. A REAFFIRM only earns continued paper
tracking; it does NOT authorise live capital, and it does NOT override the fact
that the basket fails the deployable PF and drawdown-cap bars in-sample.

## In-sample reference (what forward is judged against)

Full 6.5y merged single path: n=2813, balanced 1471L/1342S, PF 1.129, expectancy
+0.102R, MAR 2.684, single-path DD -107.1R, robust_frac 0.714 (5/7 years; only
2022 -1.2R and 2024 -17.8R negative, both mild). Recent window (entries >=
2024-06): n=949, PF 1.106, expectancy +0.087R, MAR 1.180 — above all three
single-asset MARs. De-correlation cut the drawdown 31.2% below the perfect-
correlation reference. The forward basket should look like the recent window if
the diversification advantage is real and not a 2024-25 artifact. Full detail in
`BASKET.md`.

## Caveat (load-bearing)

Crypto majors share beta, so the three assets are correlated confirmations, not
independent ones (the program's breadth-neutral finding showed BTC-hedging this
family turns it negative — the edge is crypto-beta timing, not market-neutral
alpha). The basket therefore diversifies *idiosyncratic loser-clustering and
single-asset survivorship risk*, not market risk. It is a more robust way to hold
one thin directional signal, not a second source of edge.
