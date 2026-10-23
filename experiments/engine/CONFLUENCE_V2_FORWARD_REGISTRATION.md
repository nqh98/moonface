# Confluence Engine v2 — Forward-Paper Pre-Registration

**STATUS: FROZEN (2026-07-04, human-approved v2-only refocus mandate).**
Frozen per the approved spec docs/research-log/specs/2026-07-03-v2-only-refocus-design.md.
No frozen value below may change until the horizon; any change is a new
ENGINE_VERSION → new hash → new registration.

Spec: `docs/research-log/specs/2026-07-03-confluence-engine-v2-design.md` (§6).
Plan: `docs/research-log/plans/2026-07-03-confluence-engine-v2.md` (Task 9).

## Posture (binding)

Paper only. Disciplined heuristic, **no validated-edge claim** — the `NO_CLAIM` banner rides on
every emitted signal and card. The program record says the components have no individual edge
(liqladder, funding, macro-filter, ensemble lanes all closed negative). The engine's proposition
is **selectivity + risk discipline + an auditable evidence trail**; this forward paper record is
the only test. This is NOT a backtest and MUST NOT be tuned against history.

## Frozen identity

- `ENGINE_VERSION = "2.0"`, folded into `engine_hash`. Every journal entry carries
  `strategy_version = engine_hash(cfg)`. Any change to a frozen constant (weights, thresholds,
  gate table, panel-param constants, risk lookup) changes the hash → **the paper record restarts
  from zero** and this registration is void until re-frozen.
- Weights / thresholds / gate table / panel params are frozen constants in code, excluded from
  `EngineConfig`. No config knob can drift them.
- Frozen at freeze time: `engine_hash = 10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf`,
  `enable_date_utc = 2026-07-04`, `journal_path = journal/signals.jsonl`,
  `symbol/timeframe = BTC/USDT:USDT 1h`.

## Horizon (pre-committed)

Evaluate at the LATER of:
- **6 months** from `enable_date_utc`, OR
- **≥ 30 completed setups** (closed engine trades, `action == "EXIT"` at the frozen hash).

No interim peeking-to-decide. A verdict is written once, at the horizon.

## Success bar (all must hold — practical, NOT DSR)

1. **Net R > 0** over all completed setups at the frozen hash.
2. **MaxDD within the discipline budget** — peak-to-trough realized-R drawdown over the trailing
   `drawdown_window_days` (90d) stays within the 15R window budget (the layered kill-switch's
   routine pause threshold); the 30R hard latch must never have tripped.
3. **CT and WT sub-books each ≥ 0 R** *separately*. A positive aggregate that is entirely one
   profile carrying a losing other profile fails. (Split by journal `profile` field.)

If any of 1–3 fails → the engine is DOWNGRADED (back to `enabled=False`, no re-tune on this hash).

## Mandatory gate-ablation report (part of the verdict)

Every REJECT is journaled as a WAIT with `veto` + `shadow_score`. The verdict MUST report, from the
journal:
- how many setups the macro gate vetoed, and the distribution of their `shadow_score`s;
- the counterfactual: what the record would look like had the vetoed setups been taken at their
  shadow scores (did the gate save or cost R?).
This is the whole point of journaling shadow scores — the gate is the one macro filter kept, and its
value must be measurable from the forward record, not assumed.

## Kill rule (binding)

**One cycle.** If the horizon verdict is DOWNGRADE, the lineage does not get a "re-tune and rerun".
Any change to a frozen constant to chase the result is a **new version** (`ENGINE_VERSION` bump →
new `engine_hash` → new registration → fresh clock). No silent re-fits on the same identity.

## Pre-freeze checklist (whole-branch review, 2026-07-03)

The final whole-branch review returned Ready-to-merge YES (0 Critical). Two of its
Important items were fixed on the branch before merge and are recorded here for the
freeze audit; one remains a human decision at freeze time.

- **RESOLVED — example config no longer neuters the gate.** `promotion/engine.json.example`
  shipped `lookback_bars: 1500` (~8 weekly closes) plus dead keys; that starves
  `classify_macro` (needs 31 weekly closes) → macro permanently NEUTRAL → the 1W Gating
  Matrix inert. Fixed to `lookback_bars: 6000`, dead keys dropped. **At freeze, confirm the
  actual enabled config (`promotion/engine.json`) carries `lookback_bars` ≥ ~5300** so the
  macro gate is live, and sanity-check that the journal shows non-`ALLOW` policies occur.
- **RESOLVED — M1 is now pure 1W macro (spec §2).** M1 previously required 4h SMA alignment
  (M2's condition), which muted it and double-counted 4h structure against `BREADTH_MIN`.
  Corrected so a confirmed weekly bias scores +20 in its direction regardless of 4h; the gate
  handles opposition. This changes the frozen scoring — it is the intended spec behavior and
  was fixed pre-clock (no forward record existed), so no version reset is owed.
- **RESOLVED (2026-07-04) — hash now auto-covers the module constants.**
  `engine_hash` folds a digest of the frozen weight/threshold/gate/panel/risk
  constants (`_frozen_constants_payload` in
  `src/moonface/signal/engine/config.py`), so editing any frozen constant
  mechanically resets the paper record. The ENGINE_VERSION-bump convention
  remains as a second, human-visible layer.

## What "enable" means (human runbook, informational)

1. Freeze this file (STATUS → FROZEN, fill the blanks above, commit).
2. Set `"enabled": true` in the engine config JSON (`promotion/engine.json` or the configured path).
   The default `EngineConfig().enabled` stays `False` in code — enabling is only ever via the
   user config file, never a code default.
3. Start the watch loop; the journal accrues `status="engine"` entries at the frozen hash.
4. Do not touch frozen constants until the horizon. At the horizon, write the verdict (with the
   gate-ablation report) and apply the success bar / kill rule.

## Freeze record (2026-07-04)

- Pre-freeze sanity: journal/signals.jsonl contained 0 `status="engine"` rows;
  promotion/ carries only the engine-tier configs (all other lineages archived
  under promotion/archive/2026-07-03-v2-refocus/, registrations withdrawn).
- promotion/engine.json differs from EngineConfig() defaults only in
  `enabled: true`; verified engine_hash(load_engine_config(...)) ==
  engine_hash(EngineConfig()) == the frozen hash above. lookback_bars 6000
  (~35 weekly closes) keeps the 1W macro gate live (needs ≥31).
- Gate-ablation tooling for the horizon verdict:
  tools/engine_ablation.py (read-only) + moonface.signal.engine.ablation.
- Forward-operation sanity (first weeks, non-binding observation only —
  NOT a peek at performance): confirm journal entries show non-`ALLOW`
  policies occurring, i.e. the macro gate is actually live.

## SUPERSEDED — WITHDRAWN (2026-07-04)

Human-approved v2.1 mandate 2026-07-04
(spec `docs/research-log/specs/2026-07-04-confluence-engine-v21-design.md`):
v2.1 supersedes this registration before any setup accrued. Record at
withdrawal: 6 journal rows at the frozen hash, all WAIT, 0 setups,
0 completed trades. Forward clock VOID. The v2 identity
(ENGINE_VERSION "2.0", engine_hash 10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf)
is retired; resuming it would require a NEW registration with a fresh clock.
Design evidence for the supersession:
`experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md` (verdict UNCALIBRATED —
CT book negative at every score level; Tier-A bucket inverts; short trend
side negative). Successor registration:
`experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md`.
No text above this addendum was edited or removed.
