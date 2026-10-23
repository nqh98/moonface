# V2-Only Refocus — Design Spec (2026-07-03)

**Mandate (human, 2026-07-03):** Refocus MoonFace on the Confluence engine v2 only.
Suspend all other active paper strategies from watch, promotion, and signal routing —
without deleting their historical journals, registrations, or audit records. Complete
the v2 freeze runbook (fix `lookback_bars`, close the hash open item, freeze the
registration), then start a clean forward-paper record evaluated by the registered
6-month / ≥30-setup gate with the mandatory gate-ablation report. **Do NOT live-enable
anything** — "enable" here means paper-forward journaling only; live remains a separate
human decision that no part of this work unlocks.

Related documents:
- v2 registration: `experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md` (DRAFT → to be FROZEN)
- v2 spec/plan: `docs/research-log/specs/2026-07-03-confluence-engine-v2-design.md`,
  `docs/research-log/plans/2026-07-03-confluence-engine-v2.md`
- Suspended registrations: `experiments/deployable/DONCHIAN_SLICE3_FORWARD_REGISTRATION.md`,
  `experiments/mtf/LONG_ONLY_FORWARD_REGISTRATION.md`

## Decisions (approved 2026-07-03)

1. **Suspended strategies' frozen forward registrations → administrative WITHDRAWAL.**
   Dated append-only addendum on each: *SUSPENDED UNRESOLVED by human refocus mandate
   2026-07-03; forward clock void; resuming the lineage later requires a NEW registration
   with a fresh clock.* Rationale: Donchian's 12-week clock is wall-clock and would
   ambiguously keep ticking under a "paused" state; selective resumption invites peeking.
2. **v2 journal stays `journal/signals.jsonl`.** Engine scorecard, kill-switch, and
   position state already filter strictly by `engine_hash`; a fresh hash gives a clean
   forward record in the shared file. Verified 2026-07-03: the journal contains zero
   `status="engine"` entries, so the v2 record starts clean. A separate file would risk
   split-brain via a forgotten `--journal` flag.
3. **Hash defense-in-depth: yes.** Fold a digest of the frozen module constants
   (module weights/thresholds, gating matrix, panel params, risk/tier lookup) into
   `engine_hash` before freezing. Editing any frozen constant then mechanically resets
   the paper record instead of relying on the ENGINE_VERSION-bump convention. This
   closes the registration's OPEN pre-freeze item. `ENGINE_VERSION` stays `"2.0"`.
4. **Starting the watch daemon is human ops**, out of scope here (consistent with the
   Donchian Slice-3 registration). The deliverable ends at "frozen and armed".

## Current state (verified 2026-07-03)

- Tier order per style in `src/moonface/signal/cli.py::_load_style` / `_emit_for_style`:
  **strategy → engine → participation → baseline**, where baseline is *on-by-default*
  (absent/invalid baseline config = heuristic tier).
- `promotion/styles.json` routes two styles: `swing` (Donchian 4h paper strategy) and
  `day` (disabled baseline). `promotion/mtf_long/styles.json` routes the MTF long-only
  paper strategy. `promotion/participation.json` is `enabled=false`.
- `promotion/engine.json` (git-ignored, local) is **`enabled: true` with
  `lookback_bars: 1500`** — enabled under a DRAFT registration, and 1500 bars starves
  `classify_macro` (needs ~5300+ 1h bars for 31 weekly closes), leaving the 1W macro
  gate permanently NEUTRAL. Both are freeze blockers. No watch daemon is running; no
  engine entries have reached the journal (no contamination).
- Journal `journal/signals.jsonl`: 68 rows (2026-06-15 → 2026-07-01), 66 WAIT / 2
  baseline LONGs; Donchian (df7cc856…) 23 rows all WAIT; MTF (df023c2…) 39 rows all WAIT.
- Engine journaling (`cli.py::_emit_engine`) writes `status="engine"`,
  `strategy_version=engine_hash(cfg)`, plus per-entry `veto` and `shadow_score` — the
  raw material for the gate-ablation report exists; the aggregation/report tool does not.
- Stray 0-byte artifact at repo root: `paper signal: LONG @ 100.0, invalidation 95.0, f=0.01`
  (untracked, accidental alert-cmd/redirect artifact).

## Design

### 1. Suspension & routing (only v2 can emit)

Create `promotion/archive/2026-07-03-v2-refocus/` and `git mv` the tracked configs of
every non-engine lineage into it:

- `promotion/strategy.json` (Donchian 4h paper)
- `promotion/mtf_long/` (strategy + its styles manifest)
- `promotion/day/` (disabled day-slot baseline)
- `promotion/participation.json` (disabled participation advisor)

Add a short `README.md` inside the archive folder stating what was archived, why
(this spec), and that nothing here may be re-pointed at by a styles manifest without a
new registration.

Rewrite `promotion/styles.json` to exactly one style:

```json
{
  "styles": [
    {"name": "engine",
     "strategy": "promotion/none.json",
     "policy": "promotion/none.json",
     "baseline": "promotion/baseline.json",
     "engine": "promotion/engine.json"}
  ]
}
```

- `promotion/none.json` does not exist → `load_strategy` / `load_policy_if_enabled`
  return None, so the strategy and participation tiers can never fire.
- `promotion/baseline.json` is **written as `{"enabled": false}`** (defense-in-depth):
  if a human later sets `engine.enabled=false`, the style falls through to a disabled
  baseline and prints `WAIT (no validated strategy)` — it does NOT revive the
  on-by-default heuristic and does not journal.
- Result: the only journal-writing path in the manifest is the engine tier
  (`status="engine"`). One-shot CLI default flags reach the same outcome: default
  `--strategy promotion/strategy.json` no longer exists → falls to the engine config.

Suspension does not delete anything: journals, experiment results, and registration
documents are untouched; archived configs remain in git history and in the archive dir.

### 2. Registration addenda (governance, append-only)

Append a dated section to each of:

- `experiments/deployable/DONCHIAN_SLICE3_FORWARD_REGISTRATION.md`
- `experiments/mtf/LONG_ONLY_FORWARD_REGISTRATION.md`

Content: **WITHDRAWN — SUSPENDED UNRESOLVED (2026-07-03)** by human refocus mandate;
state at withdrawal (Donchian: 0 closed trades, ~1.9 of 12 weeks, all-WAIT journal;
MTF: frozen 2026-07-01, 0 closed trades); forward clock void; archive location of the
config; resuming requires a NEW registration with a fresh clock. No existing text is
edited or removed.

### 3. Freeze-blocker code changes (pre-freeze; legal because no forward record exists)

**3a. `engine_hash` module-constants digest.** `engine_hash(cfg)` additionally folds a
deterministic digest of the frozen constant tables (module weights/thresholds, the 1W
gating matrix, panel params, the risk/tier sizing lookup). Constants are serialized
canonically (sorted keys, stable float repr) from their single source-of-truth
definitions in `moonface.signal.engine` modules — no duplication of values in the hash
code. Property: editing any frozen constant changes `engine_hash` → the journal's
version filter isolates the old record and the registration is void, mechanically.

**3b. Gate-ablation reporter (read-only).** A pure function (beside
`engine_scorecard`) plus a small CLI entry point that, given journal entries and the
frozen config, reports for the frozen hash:

- number of macro-vetoed setups (`veto` non-null) and their `shadow_score` distribution
  (count, min/median/max, per-tier breakdown);
- the counterfactual: estimated R had the vetoed setups been taken at their shadow
  scores' implied tier sizing — i.e. did the gate save or cost R. The counterfactual
  replays each vetoed setup's entry/stop per the engine's standard exit discipline on
  the candle series; assumptions are printed with the report.
- clearly labeled DIAGNOSTIC — the reporter never gates and never mutates state.

Built now, before any forward data exists (no peeking risk; guaranteed availability at
the horizon, where the registration makes this report mandatory).

### 4. Freeze runbook execution (config + docs)

1. Write the real `promotion/engine.json` (git-ignored) from the example:
   `enabled=true`, `lookback_bars=6000`, no dead keys. 6000 1h bars ≈ 35 weekly closes
   ≥ the ~5300-bar minimum for a live macro gate.
2. Fill and freeze `experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md`:
   STATUS → FROZEN; `engine_hash` = value computed **after** 3a;
   `enable_date_utc` = the freeze date; `journal_path = journal/signals.jsonl`;
   `symbol/timeframe = BTC/USDT:USDT 1h`; note that the hash now folds the module
   constants (open item resolved); commit.
3. Delete the stray 0-byte root artifact file.
4. Sanity checks recorded in the freeze commit message or registration: config parses
   `enabled=true` / `lookback_bars=6000`; the frozen config differs from
   `EngineConfig()` defaults **only** in `enabled` (which the hash excludes), so
   `engine_hash(load_engine_config("promotion/engine.json")) ==
   engine_hash(EngineConfig())` — the registration's fill-in formula and the hash the
   journal will actually carry are the same value; zero pre-existing `status="engine"`
   journal rows.

Ordering constraint: 3a (hash change) → 4.2 (freeze fills the hash) → nothing frozen
may change afterward.

### 5. Forward record & horizon (unchanged from the registration)

Human starts `moonface-signal --watch`. The engine journals `status="engine"` entries
at the frozen hash. Verdict written **once**, at the later of 6 months from
`enable_date_utc` or ≥30 completed setups, using `engine_scorecard` + the ablation
reporter. Success bar (net R > 0; windowed DD within 15R/90d and 30R hard latch never
tripped; CT and WT sub-books each ≥ 0 separately) and the one-cycle kill rule are
exactly as registered — this spec changes none of them.

### 6. Testing

- Routing: with the new manifest fixture, only the engine tier can emit; missing
  `promotion/none.json` paths resolve to None tiers; disabled baseline stub prints
  WAIT-no-strategy and journals nothing.
- Hash: digest is stable across runs; changes when any single module constant changes;
  `enabled` stays excluded from the hash.
- Ablation reporter: synthetic journal fixtures with vetoed/taken/mixed setups produce
  correct counts, distributions, and counterfactual sign; empty journal → empty report,
  no crash.
- Full suite stays green.

## Out of scope

Live-enabling anything; tuning any frozen constant or threshold; editing or deleting
journal history, experiment results, or registration text (append-only addenda only);
reopening any closed research lane; starting/managing the watch daemon.
