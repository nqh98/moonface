# .backtest_cache/ — mutation during the G3 liqladder reproduction gate

Attaches to `docs/research-log/plans/2026-08-24-g3-unify-verification-path.md` (Tasks 20-21) and
`experiments/liqladder/verdict.json` (2026-07-02, unmodified). Neither is edited by this record; this is
the incident report the G3 reproduction-gate result needs in order to be interpretable.

## What happened

G3's reproduction gate (`tools/research.py reproduce <lane>`, per the spec: "Run offline against
`.backtest_cache/` so the comparison is deterministic") was first wired using
`moonface.research.universe_data.fetch_perp_candles` and `moonface.core.series.fetch_metrics_history` as
the injected fetch callables. Both functions fall back to a live network fetch on a cache miss or a
coverage gap, and **write the result back into `cache_dir`** — they are cache-through fetchers, not
read-only cache accessors. This was not caught before the first `reproduce liqladder --cache-dir
.backtest_cache` run.

That run (2026-08-24, ~22:18 local time) reached the network for candidates whose 1h cache had gaps and
wrote the results into `.backtest_cache/`, which hard constraint §5.2 of
`docs/research-log/specs/2026-08-22-repo-restructure-design.md` requires to stay frozen until G6.

## What was touched (measured, not estimated)

`find .backtest_cache -newermt "2026-08-24 21:00:00" -type f`, run after the mutation, split by whether the
underlying candle/metric **data** changed or only the coverage-sidecar (`.cov`) bookkeeping file did:

**Data rewritten (11 files)** — `1000FLOKIUSDT_1h.csv`, `1000PEPEUSDT_1h.csv`, `1000SHIBUSDT_1h.csv`,
`BNBUSDT_1h.csv`, `DOGEUSDT_1h.csv`, `FILUSDT_1h.csv`, `HIGHUSDT_1h.csv`, `JASMYUSDT_1h.csv`,
`PEOPLEUSDT_1h.csv`, `XRPUSDT_1h.csv`, `metrics_HIGHUSDT.csv`. All eleven are 1h-interval or metrics files
for `liqladder` candidate symbols. No `*_4h.csv` data file was touched.

**Coverage-sidecar only (`~36` `.cov` files)** — includes both 1h siblings of the eleven above and a set of
`*_4h.csv.cov` files (`1000FLOKIUSDT`, `1000PEPEUSDT`, `1000SHIBUSDT`, `ARBUSDT`, `AVAXUSDT`, `BNBUSDT`,
`DOGEUSDT`, `ETCUSDT`, `ETHUSDT`, `FILUSDT`, `FTMUSDT`, `HIGHUSDT`, `JASMYUSDT`, `LINKUSDT`, `NEARUSDT`,
`PEOPLEUSDT`, `SOLUSDT`, `TRBUSDT`, `XRPUSDT`). The `.cov` sidecar records the known-covered timestamp
range, written whenever it changes even if the candle list itself did not (`_write_cov` fires independent
of whether `cache.save` did) — a metadata write, not a numeric one, and it does not feed
`stouffer_z`/`pooled_mean`/any compared field.

No backup of `.backtest_cache/` exists (it is git-ignored, confirmed via `git check-ignore -v
.backtest_cache`, and no snapshot mechanism was found anywhere on this machine). The original bytes for the
eleven data-rewritten files are not recoverable through any means available in this session.

## Which reproduction-gate results this affects

**`oibuild_study`: unaffected.** It fetches only `*_4h.csv` data; zero 4h data files were touched (some 4h
`.cov` sidecars were, but those carry no numeric content). Its `REPRODUCED` result was confirmed twice —
once before this mutation was discovered, once after switching to the strictly offline fetchers built in
response (`kernel.reproduce.offline_fetch_perp_candles` / `offline_fetch_metrics_history`, which read
`OhlcvCache.load()` / the metrics cache file directly and never fall back to network or write) — both runs
produced the identical `stouffer_z=-1.0240920214752438` etc. and touched zero new files.

**`liqladder`: `DID NOT REPRODUCE`, and the cause is this mutation, not organic data drift or a kernel
defect.** Proof: after switching to the offline fetchers, `liqladder`'s gate was re-run and touched **zero**
new cache files (confirmed: the touched-file count stayed at 47, unchanged from immediately after the first
run) — yet reproduced the exact same mismatched numbers
(`stouffer_z: recorded=-1.9004349960975828 recomputed=-2.0627555747046387`,
`pooled_mean: recorded=-0.0006388059072359321 recomputed=-0.0006849522792324151`). `k_positive`, `m_assets`,
and `verdict` all still match. If the mismatch were caused by live network calls happening *during* the
gate, an offline re-run touching zero files would have reproduced the *original* (July) numbers, not the
same shifted ones. It didn't — proving the eleven data files' new content, written by the first (buggy) run,
is now simply what `.backtest_cache/` contains, and both the buggy and the fixed run read the same (already
mutated) state.

## Ruling

**Record as an honest `DID NOT REPRODUCE` finding for `liqladder`, attributed to this incident, not to a
kernel or bootstrap-migration defect. `experiments/liqladder/verdict.json` (2026-07-02) is not amended,
retracted, or superseded — it remains the authoritative record of what that run measured, per invariant 5
("the ledger records runs, never closes a lane") and this repo's own precedent (`oi_build` was ruled
untestable, then a later data release proved otherwise; the original record was never edited, only the
interpretation attached to it changed).**

Reasoning:

1. **The mismatch is real and measured, not assumed.** Two independent runs (network-capable, then
   strictly offline) against the current cache state produce bit-identical recomputed numbers, both
   differing from the recorded verdict in the same two fields, by a modest amount, same sign.
2. **The cause is now understood and attributable to this session's tooling defect**, not to the kernel
   unification work (Tasks 4-19) — `liqladder` does not call any of the fourteen migrated bootstrap sites;
   its methodology is pure Stouffer-Z / binomial arithmetic with no randomness.
3. **The fix (offline-only fetchers) is real and verified**: zero cache writes on re-run, confirmed by file
   count before and after.
4. **Reprocessing the eleven files is not attempted.** There is nothing to revert to — no prior version of
   the bytes exists to restore. Re-fetching from the network again would only add a third, equally
   unverifiable version, not recover the original.
5. **`oibuild_study`'s result stands as fully offline-reproduced**, unaffected by this incident.
