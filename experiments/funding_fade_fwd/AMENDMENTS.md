# funding_fade_fwd — Amendment Log

> **WINDOW CLOSED PERMANENTLY — 2026-07-14 at human sign-off (spec §7.3).**
> No forward data was observed by any drafting or sign-off phase
> (clamp-enforced; verified at sign-off). Both amendments below were ruled
> and applied while the window was open, before any freeze. No further
> amendments are possible: any verdict-affecting ambiguity discovered after
> forward data is observed VOIDs the cycle (REGISTRATION §10); an unrelated
> repo change forcing a pinned-path edit is a spec §5 escalation, not an
> amendment. Frozen at identity_hash
> `4c481e88f3076bdc18cf198c78ceaeed9ba9db1961234985734bc2d15febd1d0`,
> pipeline commit `0e3fef3a41aa686f9932e94fc0518f2afe438335`.

The amendment window was OPEN until human sign-off (spec §5) and closed
permanently at sign-off, before any forward data was observed.

## Amendment 2 — 2026-07-14 — Null-calibrated success criterion (Escalation-2 ruling: option A)

**Human rationale (verbatim):**

> The guard caught the vol_compression failure mode pre-freeze: the drafted
> criterion cannot distinguish funding information from regime, since the
> −2R/+4R bracket at random entries earns +0.32R/trade in the tail window.
> The funding increment itself is real but narrow (+77.34R vs null p95 67.52R,
> 4/100 nulls above, ~p96). Option (B) is rejected: it would kill the only
> positive lane on evidence that the signal is narrow, not absent, while the
> forward program's cost is near zero and the amendment window is open with no
> forward data observed. Option (A) is the bias-toward-KILL choice among
> continuations: strictly harder, and it tests the correct question — signal
> above same-window regime.

**Binding effects:**

1. **EDGE FOUND requires ALL THREE jointly:** (i) forward cumulative R > 0;
   (ii) expectancy CI excludes 0 at the pre-committed level (95%,
   moving-block bootstrap, block 10, 10,000 resamples, seed 42);
   (iii) forward cumulative R strictly exceeds the null p95 of same-window
   funding-shuffle nulls, frozen pipeline, computed once at verdict.
   Condition (i) explicitly guards against passing (iii) in a bad regime
   where the null p95 is negative.
2. **Percentile convention (pre-specified, stricter reading):** with the
   null net-R values sorted ascending (0-based), the threshold is
   `sorted_nets[min(n-1, ceil(0.95*n))]` — the "higher" order statistic,
   above the nearest-rank value — and the forward result must STRICTLY
   exceed it. **Null set expanded now, before freeze: seeds 0–199
   (n=200).** The seed set and count freeze at sign-off and are never
   revisited. For n=200 the threshold index is 190; at most 9/200 (4.5%)
   nulls can strictly exceed it.
3. **Circularity acknowledgment:** with condition (iii), the guard's ≤5%
   null pass rate holds by construction and is not independent evidence.
   The guard re-run validates machinery, not the criterion.
4. D1 records the downgraded prior verbatim (most of the tail-window return
   is regime-attributable; the funding increment cleared the null narrowly,
   ~p96) and the program's honest power scope (at ~108 trades / 12 months
   it is powered only to confirm a tail-sized ≈+1.1R edge; a
   research-sized ≈+0.25R edge will most likely produce a NO-EDGE verdict,
   and that outcome is expected and acceptable).
5. The random-entry bracket finding gets a dated observation note
   (OBSERVATIONS.md); it does NOT open a new lane — unconditional
   bracket-holding is the closed drawdown-wall question.

## Amendment 1 — 2026-07-14 — Re-baseline on completed candles (§5.2 ruling: option a)

**Human rationale (verbatim):**

> The archived headline (+76.7285R) embeds a mark-to-close against a forming-candle
> snapshot (2026-06-10T06:51:46Z) that no longer exists on any feed and is therefore
> irreproducible in principle. Every in-principle-reproducible figure matched exactly
> (254 / +64.7507R / +0.2549 / −32.0R / 68 OOS trades). The dry-run is judged PASS
> with the reproduction criterion formally amended to: exact match on all
> completed-candle figures. Option (b) is rejected because it would freeze a baseline
> the frozen pipeline can never regenerate; option (c) is rejected because §5.2
> targets undiagnosed pipeline errors, and this discrepancy is fully diagnosed,
> isolated to two open-trade marks, and resolved pre-sign-off within the open
> amendment window.

**Effects:**

1. Pre-cutoff baseline frozen at **+77.3435R OOS net / +1.1374R expectancy**
   (completed-candle regeneration; research fold unchanged: 254 trades,
   +64.7507R, +0.2549R, −32.0R max peak-DD; 68 OOS trades).
2. Forward window opens at the first bar with open time ≥ **2026-06-10T08:00:00Z**.
3. The 04:00–08:00Z bar of 2026-06-10 (whose final OHLC embeds ~69 minutes of
   post-stamp trading) is assigned to the baseline side and thereby excluded
   from forward OOS. This is an accepted, disclosed cost. The §3 hygiene
   disclosure is acknowledged as correctly reported; no further action.
4. D1's citation section states BOTH figures: the archived +76.7285R (verbatim,
   with the snapshot-artifact explanation) and the re-baselined +77.3435R. The
   archived record (`experiments/positioning_exits/20260610T065146Z/`) is not
   altered anywhere.
