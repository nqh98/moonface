# Confluence Engine v2.1 — Evidence-Guided Simplification (Design Spec, 2026-07-04)

**Mandate (human, 2026-07-04):** Build v2.1 of the confluence engine from the
calibration diagnostic's evidence (`experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md`,
verdict UNCALIBRATED, one-run rule stands). v2.1 is a **simplification** — it removes
the components the diagnostic condemned and adds nothing:

1. **Drop counter-trend entries.** Every MEAN_REVERT score bucket lost −0.17 to
   −0.24 R/event over 31,801 panel events under its own CT exit discipline.
2. **Flatten tiers.** The Tier-A bucket (score ≥75) was the *worst* trend bucket
   (−0.15, n=36): full module alignment means late entry. One threshold, one size.
3. **Long-only trend.** LONG +0.068 R/event (n=26,933) vs SHORT −0.14 (n=19,596),
   consistent with every prior L/S lane in the program record.

Explicitly **descoped** (post-hoc knob-turns, rejected): removing high-vol size
damping; re-weighting modules from the IC table; inverting the revert book;
re-running the calibration diagnostic.

Related documents:
- Diagnostic evidence: `experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md` +
  `experiments/engine/calibration_report_2026-07.json`
- v2 registration (to be superseded): `experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md`
- v2 spec: `docs/research-log/specs/2026-07-03-confluence-engine-v2-design.md`

## 1. Version & governance

- `ENGINE_VERSION = "2.1"` in `src/moonface/signal/engine/config.py`. The
  frozen-constants digest changes with the tier table and new policy constants,
  so `engine_hash` moves mechanically; a test pins that the new default-config
  hash ≠ v2's frozen `10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf`.
- **v2 superseded (human-approved 2026-07-04):** append-only dated addendum to
  `CONFLUENCE_V2_FORWARD_REGISTRATION.md` — *SUPERSEDED by v2.1; record at
  withdrawal: 5 WAIT rows, 0 setups, 0 trades; forward clock void; resuming the
  v2 identity would require a new registration.* No existing text edited or removed.
- **New registration** `experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md`,
  frozen LAST (code merged → hash computed → registration filled → nothing frozen
  changes afterward). Paper-only, `NO_CLAIM` posture unchanged.
- The diagnostic is design evidence only. v2.1 gets **no new historical calibration
  run**: the trend book's scoring function is unchanged, so the existing report
  already characterizes it; the one-run rule is not reopened.
- Implementation approach: constant surgery inside the existing engine package
  (no parallel package, no config-driven mode flags — weights/policy stay frozen
  constants in code, outside `EngineConfig`).

## 2. Decision semantics

Both books keep scoring every bar exactly as in v2 (module code untouched).
A v2.1 policy layer inside `decide()` (`src/moonface/signal/engine/confluence.py`)
applies after book contexts are computed:

1. **MEAN_REVERT candidates never trade.** A revert-book setup that would have
   been valid under v2 rules (breadth ≥ `BREADTH_MIN`, score ≥ its gate-adjusted
   threshold, gate policy ≠ REJECT) returns action WAIT with
   `veto = "v2.1 no counter-trend entries"` and `shadow_score`/`shadow_direction`
   set from that candidate.
2. **SHORT trend candidates never trade.** Same treatment with
   `veto = "v2.1 long-only"`. LONG trend setups trade exactly as v2:
   threshold `BASE_THRESHOLD = 60`, breadth ≥ 3, macro gate unchanged
   (BEAR macro still REJECTs TREND LONG with its own macro-veto shadow).
3. **Reversal exits survive long-only.** A would-be SHORT trend setup (valid but
   for the long-only rule) still CLOSES an open long position; it never opens a
   short. Rationale: the calibration's reversal-sensitivity block showed reversal
   exits added +116R on the triggered trend subset — the exit lever is kept,
   scoped to the trusted book. Shadowed MEAN_REVERT setups do NOT drive exits.
   Mechanically: `evaluate_engine` derives `signal_dir` for `manage_position`
   from the trend book's would-be-valid direction (long-only veto included),
   not from `decision.direction` alone.
4. **Untouched:** macro gating matrix, extreme-vol standdown, post-loss cooldown,
   layered kill-switch (15R/90d window + 30R hard latch), position management
   (`position.py` — the CT machinery stays in code and in the hash payload;
   it simply becomes unreachable for entries).
5. **Shadow precedence** when multiple veto families could fire on one bar:
   the trend-book shadow wins the single shadow slot (matching v2's existing
   `trend or revert` veto handling, and required by the reversal rule); the
   veto reason string identifies the family. Known limitation carried over
   from v2: a same-bar revert shadow is not journaled when a trend shadow
   exists — acceptable, since the schema is unchanged and the CT question is
   answered by the bars where the CT shadow does land.

## 3. Tiers & sizing

- One threshold (60), one size. The Tier-A branch leaves `decide()`'s valid
  logic; `tier` journals as `"B"` for schema continuity. The `TIER_A` and
  `CT_SURCHARGE` constants STAY DEFINED in `confluence.py` as vestigial —
  removing them would break `calibration.py` (which imports `CT_SURCHARGE`)
  and churn the drift guard's field lists for no benefit. They are simply no
  longer read by `decide()`'s valid path (nothing `ALLOW_CT` can trade, and no
  score maps to a bigger size). The hash still changes via `ENGINE_VERSION`
  and the flattened discipline table.
- `_TIER_PROFILE_FRACTION` in `discipline.py` flattens to the single surviving
  cell `("B", "WT"): 0.005` — the conservative Tier-B/base fraction; Tier-A's
  0.010 upsize was attached to the bucket that inverted. High-vol halving in
  `tier_size_fraction` stays; the function keeps its signature.

## 4. Shadows & journal

- **No journal schema change.** The existing `veto`, `shadow_score`,
  `shadow_direction` fields carry the two new families; reason strings
  distinguish them: `"macro …"`, `"v2.1 no counter-trend entries"`,
  `"v2.1 long-only"`.
- The ablation module (`src/moonface/signal/engine/ablation.py` +
  `tools/engine_ablation.py`) gains per-family grouping so the horizon report
  answers, from forward data, each question separately: did the macro gate, the
  CT drop, and the long-only rule save or cost R. Read-only, never gates.

## 5. Registration & success bar (frozen at freeze time)

- **Horizon:** later of 6 months from `enable_date_utc` or ≥ 30 completed
  setups (closed trades at the frozen v2.1 hash). One verdict, written once.
- **Success bar:** (1) net R > 0 over all completed setups at the frozen hash;
  (2) drawdown within the layered discipline budgets — trailing 15R/90d window
  never latching beyond routine pause, 30R hard latch never tripped;
  (3) the mandatory ablation report covering all three veto families is part of
  the verdict — REPORTED, none of it gates (shadows are diagnostics, not targets).
  The v2 CT/WT sub-book clause is dropped with the CT entries themselves.
- **Kill rule:** one cycle. DOWNGRADE → `enabled=false`, no re-tune on this hash;
  any constant change is v2.2 → new hash → new registration → fresh clock.
- **Deploy note (human ops):** restarting the watch daemon picks up v2.1; the
  first journal row at the new hash starts the record. Journal stays
  `journal/signals.jsonl` (hash filtering isolates records, as verified for v2).

## 6. Testing & sanity

- Engine behavior tests (updates to existing engine test files + new cases):
  - revert-book valid setup → WAIT, veto `"v2.1 no counter-trend entries"`,
    shadow fields populated;
  - short trend setup → WAIT, veto `"v2.1 long-only"`, shadow fields populated;
  - a would-be short trend setup closes an open long (reversal exit) and opens
    nothing; a shadowed revert setup does not close positions;
  - LONG trend setup at score ≥ 60/breadth ≥ 3 opens WT at fraction 0.005;
    journaled tier is `"B"`; no path yields fraction 0.010;
  - macro BEAR still vetoes trend longs with the macro shadow;
  - extreme vol still stands down everything.
- Hash/identity tests: `ENGINE_VERSION == "2.1"`;
  `engine_hash(EngineConfig())` ≠ the v2 frozen hash; the frozen-constants
  drift guard (`_frozen_constants_payload`) passes with the updated
  confluence/discipline field lists.
- Ablation reporter: per-family grouping correct on synthetic journals mixing
  all three veto families; empty journal safe.
- Existing v2-pinned tests updated deliberately (the calibration pass test that
  pins `10bb5a44…` moves to pinning "≠ v2 hash" + the new computed value at
  freeze time; every such change is called out in review as an intentional
  version-bump edit, never silent).
- One **non-gating** sanity replay over full history via `tools/engine_backtest.py`
  / `tools/engine_honest_report.py`, recorded in the registration as house-convention
  sanity — NOT an edge claim, NOT a gate; expected outcome "disciplined,
  DD-bounded" only.

## Out of scope

Any new signal, weight change, or threshold move beyond the three listed
removals; touching module scorers, macro, regime, resample, or position
management logic; changing `EngineConfig` fields; re-running the calibration
diagnostic; live-enabling anything (paper only; live remains a separate human
decision this work does not unlock); starting/stopping the watch daemon
(human ops).
