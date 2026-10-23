# Findings Index

One row per research lane. Every lane was **pre-registered** (design frozen in its
`PREREGISTRATION.md` / `registration.json` before results were seen) and judged by fixed
gates: walk-forward OOS, deflated Sharpe (DSR), iid/block nulls, and a sealed holdout
("lockbox") opened at most once.

**Headline:** across ~60 lanes, **no price/flow *prediction* signal survived** (0/58).
The only things that held up are **risk-premium measurements** (3/3): variance risk
premium, funding carry and a deferred ETF-rebalance study — and even the strongest of
those (VRP) decays toward zero by 2026. Read [`PROGRAM_CONCLUSION.md`](PROGRAM_CONCLUSION.md)
and [`MANDATE_ASSESSMENT_2026-07.md`](MANDATE_ASSESSMENT_2026-07.md) first.

Verdict legend: **CLOSED** = failed its gate, terminal · **FROZEN** = measurement done,
frozen · **FORWARD** = only a frozen forward (paper) registration remains · **DEFER** =
waiting for data · **KILL** = failed a Stage-0/feasibility or mechanism check.

## Risk-premium measurements (the survivors)

| Lane | Verdict | Key result | Artifacts |
|---|---|---|---|
| vrp_measure | FROZEN 2026-07-24 | BTC implied-vs-realized spread mean +0.095, clears both nulls ~9×; decays to ~0 by 2026 | [`vrp_measure`](vrp_measure/), [`vrp_stage1`](vrp_stage1/) |
| carry_measure | FROZEN 2026-07-16 | Funding-carry measurement; Binance spot gap (31h) spliced from Coinbase | [`carry_measure`](carry_measure/) |
| etf_rebalance | DEFER → 2029-04-01 | Stage-0 A/B pass, C underpowered; hypothesis window untouched | [`etf_rebalance`](etf_rebalance/) |

## Directional / trend families

| Lane | Verdict | Key result | Artifacts |
|---|---|---|---|
| Edge probe (SMC advisor) | CLOSED | No OOS-valid signal under ATR bracket; SMC flip dead | [`edge`](edge/), [`smc_decompose`](smc_decompose/) |
| H4 edge / exit probes | CLOSED | H4 drift exists (Donchian break dominates) but drawdown kills every row | [`exit_probe`](exit_probe/), [`exits`](exits/) |
| Sizing | CLOSED | All 3 H4 entries unsizable (optimal f = 0) | [`sizing`](sizing/) |
| Exit ablation | CLOSED | 0/14 exits clear; failure is the entry, not the trailing stop | [`ls_exit_ablation`](ls_exit_ablation/) |
| Drift screen (price, 16 assets 4h) | CLOSED | All 7 price signals dead | [`drift_screen`](drift_screen/) |
| Drift screen (funding/OI/book) | CLOSED | 8/9 dead | [`drift_screen_multifamily`](drift_screen_multifamily/) |
| stack_path screen | CLOSED | Well-powered; 5/16 sign below a coin flip | [`drift_screen_stack_path`](drift_screen_stack_path/) |
| Dual-timeframe edge search | CLOSED | All 9 cells die at stage 1 | [`edge_search*`](edge_search/) |
| System-level search | CLOSED | All 72 cells fail DSR at stage 1 | [`system_search`](system_search/) |
| Practical signal discovery | CLOSED | 0/72 survivors | [`practical_search`](practical_search/), [`practical`](practical/) |
| Practical-full re-eval | CLOSED | 3/132 pass, all reverse in sealed window | [`practical_full`](practical_full/) |
| Playbook signal engine | CLOSED | 0/12 clear the battery; lockbox never opened | [`playbook`](playbook/) |
| Portfolio tournament | CLOSED | 0/8 ensembles clear DSR | [`portfolio`](portfolio/) |
| L/S tournament | CLOSED | Sole survivor reverses in sealed holdout | [`ls_tournament`](ls_tournament/) |
| Cross-section momentum | CLOSED | mom_30 rejected; sealed tail −91.6% DD | [`xsection`](xsection/) |
| Betting-against-beta | CLOSED | In-sample anomaly reverses OOS | [`bab`](bab/) |
| Residual reversal | CLOSED | Fails gross pre-screen (coin flip) | [`resrev`](resrev/) |
| Calendar seasonality | CLOSED | No cell clears \|Z\|>3 | [`calseason`](calseason/) |
| BTC-specialized (3 slices) | CLOSED | All negative; edge decays as timeframe shrinks | [`btc_specialized`](btc_specialized/), [`btcspec*`](btcspec/) |
| BTC classic | FORWARD | Forward candidate only; no paper promotion | [`btc_classic`](btc_classic/) |
| Donchian revalidation / ADX filter / vol-regime | CLOSED | Filters target the wrong trades; vol gate removes the profitable ones | [`donchian_revalidate`](donchian_revalidate/), [`donchian_filter`](donchian_filter/), [`donchian_volregime`](donchian_volregime/) |
| Universe Donchian | CLOSED | v1 verdict negative | [`universe_donchian`](universe_donchian/) |
| Bollinger breakout / revert / harvest | CLOSED | Fails gross Z floor once OOS-aware | [`bb_breakout`](bb_breakout/), [`bb_revert`](bb_revert/), [`bb_harvest`](bb_harvest/) |
| Multi-timeframe (MTF) lanes | FORWARD | Strongest live family, thin & large DD; 3 frozen forward registrations (winner's-curse caveat) | [`mtf*`](mtf/) |
| Signal-matrix horizon harvest | CLOSED | Clean, well-powered; "harvest the drift" falsified | [`matrix`](matrix/) |
| Vol compression | CLOSED | Selection-bias tautology: a valid gate must fail on an iid null | [`vol_compression`](vol_compression/) |
| Session sweeps | CLOSED | Well-powered clean fail | [`session_sweeps`](session_sweeps/) |
| Capitulation fade | CLOSED (inconclusive) | OOS underpowered (n=4) | [`capitulation`](capitulation/) |
| Euphoria fade | CLOSED | Microscope texture = noise | [`euphoria_fade`](euphoria_fade/) |

## Breadth family

| Lane | Verdict | Key result | Artifacts |
|---|---|---|---|
| Breadth thrust | FORWARD | DSR kill was a false negative; OOS underpowered | [`breadth`](breadth/) |
| Breadth internal (lanes 2–3, v2, HF) | FORWARD/diagnostic | 0 paper; net_new_highs fails family gate | [`breadth_internal`](breadth_internal/), [`breadth_internal_hf`](breadth_internal_hf/) |
| Breadth confirm / momentum-confirm / x-asset | CLOSED | Edges were universe-selection artifacts / regime confound | [`breadth_confirm`](breadth_confirm/), [`breadth_momentum_confirm`](breadth_momentum_confirm/), [`breadth_xasset_confirm`](breadth_xasset_confirm/) |
| Breadth neutral | CLOSED (decisive) | Transfer was entirely crypto beta | [`breadth_neutral`](breadth_neutral/) |
| Drift basket | CLOSED | Basket fails ladder | [`drift_basket`](drift_basket/) |

## Positioning, funding, flow & microstructure

| Lane | Verdict | Key result | Artifacts |
|---|---|---|---|
| Funding probe / fade transfer / vol-target | CLOSED | Fade drift exists but bracket-invalid; ETH/SOL fail OOS | [`funding`](funding/), [`funding_fade_transfer`](funding_fade_transfer/), [`funding_fade_voltarget`](funding_fade_voltarget/) |
| funding_fade_fwd | FORWARD (terminal) | One forward run at trigger ~mid-2027 | [`funding_fade_fwd`](funding_fade_fwd/) |
| Spot-perp basis | CLOSED | All 4 cells fail OOS bracket gate | [`basis`](basis/) |
| Positioning domain / transfer / exits | CLOSED | oi_build DSR 0.30 (strongest ever) still noise; ETH 0.933 vs 0.95 gate | [`positioning_exits`](positioning_exits/) |
| OI-build mechanism | CLOSED | Mechanism does not exist | [`oibuild_study`](oibuild_study/) |
| Price/OI divergence, liq ladder, liq reversal | CLOSED | OI datasource dead in both directions | [`price_oi_divergence`](price_oi_divergence/), [`liqladder`](liqladder/), [`liqrev`](liqrev/) |
| Liquidation premium | CLOSED | \|Z\|=0.28: no effect detectable (not a reversal) | [`liqprem`](liqprem/) |
| Liquidation TWAP | CLOSED | Floor uncleared (max effect-Z 1.03) | [`lane1_twap`](lane1_twap/), [`liq_twap`](liq_twap/) |
| Book-depth study | CLOSED | h=1 effect real but ~10× under cost | [`bookdepth_study`](bookdepth_study/) |
| Aggressor trades (Hawkes) | KILL | Free aggTrades fails feasibility; lane closed | [`orderflow_microstructure`](orderflow_microstructure/), [`newdata`](newdata/) |
| Forced flow (COIN-M) | KILL | Terminal pilot kill | [`forced_flow`](forced_flow/) |
| Forced-error harvesting | CLOSED | All 8 cells die at stage 1 | [`forced_error`](forced_error/) |

## Regime, macro & structure

| Lane | Verdict | Key result | Artifacts |
|---|---|---|---|
| Exogenous (FRED + DVOL) | CLOSED | Dies at DSR 0.0 | [`exogenous`](exogenous/) |
| Regime overlay / selector | CLOSED | Macro filter subtracts; nothing beats always-trend | [`regime_overlay`](regime_overlay/), [`regime_selector`](regime_selector/) |
| Macro event windows (FOMC/CPI) | CLOSED | No cell near gate | [`macro_event`](macro_event/) |
| Macro-regime instrument | CLOSED (fragile) | GMM classifier rank-flips across eras | [`macro_regime`](macro_regime/) |
| Market-state microscope | CLOSED | Forward-R does not stratify by regime (explains ~8 dead regime lanes) | [`microscope`](microscope/) |
| Regime-mechanism engine v3 / MoE combiner | CLOSED | Selection architecture hits the same wall | [`engine`](engine/) |
| Calibration / scoring audit / score repair | CLOSED | v2 score uncalibrated; all 3 repairs fail Gate 1 | [`engine`](engine/) |
| Path signatures (rungs 0–2) | CLOSED | Distributional-path thesis falsified | [`path_signal`](path_signal/) |
| TDA topology | CLOSED | Indistinguishable from null | [`tda_topology`](tda_topology/) |
| State-space (SSE) | CLOSED | Fails both Gate-0 cells | [`sse`](sse/) |
| Event-time (dollar bars) | KILL | Dollar-bar twin misses the bar | [`eventtime`](eventtime/) |
| Adverse-validation instrument | KILL | Fails retrodiction (rho = −0.18) | [`advval`](advval/) |
| Reconfirmation cycle 1 | DEGRADED | 4h degraded, anchor intact | [`reconfirmation`](reconfirmation/) |

## Lessons worth stealing

- **A valid gate must fail on an iid null.** If your filter "passes" on shuffled data, it is
  measuring selection, not edge (vol_compression).
- **Check power before spending the lockbox.** Several lanes were inconclusive only because
  the sealed window had n < 10 events.
- **Regime conditioning rarely helps** here: forward returns of the anchor strategy do not
  stratify by regime at all (microscope), which is why ~8 regime lanes died.
- **Cross-asset "transfer" is often beta.** Neutralize before claiming a signal generalizes.
- **Report DSR, then gate on it.** Lanes that reported DSR without gating produced artifacts.
