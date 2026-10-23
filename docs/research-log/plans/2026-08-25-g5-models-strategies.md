# G5 — `models/` and `strategies/`, and Retiring the v2.2 Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Carve the ~55 reusable files out of `signal/` into two new top-level packages —
`models/` (the signal-combination and mechanism-modelling framework: confluence, MoE, v3
mechanisms, regime/position/discipline, the matrix governor/horizon) and `strategies/` (the
plugin API, registry, and the four reference strategy implementations) — then delete the
genuinely v2.2-only runtime (`cli.py`, `journal.py`'s promotion-gate half, `notify.py`,
`style.py`, `participation_api.py`) so that `signal/` ends this phase empty and removable,
without breaking the one live consumer of two of those "v2.2" files that turns out not to be
v2.2 at all (`feed/`, the Telegram SMC broadcaster).

**Architecture:** The spec's own §1.5 table is a content classification, not a literal target
file tree, and this plan's own research (grepping every `signal/` module's importers before
moving anything, the same discipline G4's Task 2 audit used) found the table's four-file
"genuinely v2.2 runtime" list is **two files short of correct** and **one file too many**:

1. **`notify.py` is not v2.2-only.** Its docstring already says "Outbound Telegram alerts for
   the signal watch daemon... it knows nothing about signals" — and `feed/cli.py` (the separate,
   independently-entry-pointed `moonface-feed` Telegram SMC broadcaster, `pyproject.toml`'s
   second `[project.scripts]` line) imports `TelegramNotifier` from it directly. Deleting it
   with `cli.py` would take `moonface-feed` down. `feed/cli.py` also does a lazy
   `from moonface.signal.cli import _load_env_file` for the same reason. **Both relocate into
   `feed/` in the same commit as `cli.py`'s own deletion (Task 6), not ahead of it.** An earlier
   draft of this plan relocated them in their own task, before `cli.py` was touched — that
   sequencing was tried during execution and immediately failed
   `tests/test_import_boundaries.py::test_signal_does_not_import_research`, which already forbids
   `signal` from importing `moonface.feed` (not just `moonface.research`), because the only way
   to keep `signal/cli.py` working during the commits in between would have been to make it
   reach up into `feed/notify.py` — exactly the forbidden direction. Doing both moves atomically
   in Task 6 means no commit ever exists where anything under `signal/` imports `moonface.feed`.
   Neither file moves into `models/` or `strategies/` — `feed/` is their only remaining consumer,
   and `feed/` itself is untouched by the target architecture in spec §3 (it is not one of
   `core/data/collect/features/models/strategies/kernel/lanes`), so this plan does not invent a
   new shared package for a two-function utility with one consumer.
2. **`journal.py` needs splitting, not a straight delete.** `append_entry`/`read_entries` are a
   generic append-only JSONL log (no v2.2 coupling at all); `tools/engine/engine_ablation.py` —
   which pairs with the *kept* `engine/ablation.py` — imports `read_entries` directly and is not
   going anywhere. Only `forward_report` (the pre-committed paper→live promotion gate, spec §4)
   is genuinely v2.2-specific, with `cli.py` its sole caller. Task 3 splits the file the same way
   G4's Task 6 split `core/bundle.py`: the generic half moves to `models/journal.py` (it pairs
   with `engine/ablation.py`, its one non-CLI consumer, in the same target package); the
   promotion-gate half is deleted in Task 6.
3. **`baseline.py` is used by a kept file.** `engine/regime.py` (staying, moving to `models/`)
   imports it alongside `cli.py`. Its own docstring frames it as CLI-tier ("sits below the
   live/paper/participation tiers in the CLI resolution ladder"), which is what makes it easy to
   misclassify as v2.2-only — but the function itself is a signal model, and `engine/regime.py`
   needs it, so it moves to `models/` in Task 4, not deleted in Task 6.
4. **`participation_api.py`** has exactly one importer in the whole tree (`cli.py` itself) and no
   importer of the research-side advisor it seams to reaches back into it. It is deleted with
   `cli.py` in Task 6 — the spec's four-file list undercounts by naming `style.py` but not this
   file; this plan corrects that in Task 2's audit note.
5. **`strategy_api.py` has zero importers anywhere** — not even the four strategy modules it
   documents itself as "the single import surface for a strategy module" import it; each
   currently imports `core`/`signal.evaluate`/`signal.registry` directly. It still moves to
   `strategies/` per the spec's explicit table entry (it is the intended plugin facade for future
   strategy authors, not dead code to prune under invariant 5's "no lane code deleted until
   re-derivable" — it isn't lane code, it has no history to preserve, and removing a documented
   public facade is a design regression this phase has no mandate to make).

**Internal layout inside `models/`:** the spec's §3 target tree lists `models/` content as prose
("confluence, modules/{trend,revert}, moe/*, mechanisms/{breakout,pullback,reversion}, regime,
governor, horizon, position, discipline") without an explicit full file tree, and the phase's own
boundary tests (`tests/test_import_boundaries.py`) check only top-level package names
(`moonface.models`, `moonface.strategies`), never the internal shape beneath them. This plan
preserves the current `engine/`, `engine/v3/`, `engine/v3/mechanisms/`, `engine/moe/`,
`engine/modules/`, and `matrix/` subdirectory structure verbatim under the new `models/` root
(`git mv src/moonface/signal/engine src/moonface/models/engine`, same for `matrix/`) rather than
flattening every file to match the spec prose's shorthand names. This mirrors G4 Task 6's own
precedent (keeping `core/bundle.py` as one file rather than splitting into funding/metrics
submodules): nothing in the invariants or the boundary tests forces a flatten, and inventing one
here is exactly the kind of unforced restructuring [[restructure-scope-feedback]] flags as
measurably risky. If a human wants the literal flattened names later, that is a follow-up, not
this phase's job.

**What was already pre-wired for this phase (found, not invented):** `tests/test_import_boundaries.py`
already lists `moonface.models` and `moonface.strategies` as forbidden imports for `core`,
`data`, and `collect` — written at G2/G4 in anticipation of this phase, the same pattern G4 found
for `core`'s `data` prohibition. This confirms the target package names and that no shim is
needed at the `core`/`data`/`collect` boundary. It does **not** yet forbid `kernel` from
importing `models`/`strategies` (it still checks the soon-to-be-dead `moonface.signal` path) —
Task 7 fixes this, and it is the one boundary-test edit this phase must make, not inherit.

**Tech Stack:** Python 3.11+ stdlib only. No new dependencies. GitNexus
(`mcp__gitnexus__impact` / `.gitnexus/run.cjs`) for blast-radius confirmation before each
relocation and `detect_changes` after, per this repo's `CLAUDE.md`.

**Spec:** `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (phase G5 in §4, line
474; the `signal/` classification table in §1.5, line 100; target architecture in §3; invariant 1
in §2; the "engine/deriv.py"-style paper-bridge exceptions already codified in
`tests/test_import_boundaries.py`)

## Global Constraints

- **Invariant 1: dependency direction is one-way.** `models ← strategies`; `kernel` must never
  import `models` or `strategies` (verification cannot depend on what it verifies) — Task 7
  makes this a real, enforced test rather than the currently-dead `signal`-path check.
- **Invariant 5: no lane code is deleted until its recorded runs are re-derivable without it.**
  This phase deletes only the confirmed v2.2-only runtime (`cli.py`, `style.py`,
  `participation_api.py`, `journal.py`'s `forward_report` half) and their dedicated tests — no
  lane code, no `experiments/registry/` content, nothing any lane's re-derivation depends on.
- **`signal` must never import `feed`, at any commit.** `tests/test_import_boundaries.py::
  test_signal_does_not_import_research` already forbids `signal` from importing both
  `moonface.research` *and* `moonface.feed` (the module docstring undersells this — it only
  mentions `research` in the exception note, but the forbidden tuple names both). This is why
  Task 6 moves `notify.py`/`_load_env_file` into `feed/` in the same commit it deletes
  `signal/cli.py`, rather than in an earlier task — do not split that move out again.
- **The `signal → research` boundary carries forward as two new rules, not one.** Today's
  `tests/test_import_boundaries.py::test_signal_does_not_import_research` has four scoped
  exceptions (`_PAPER_BRIDGES`): `strategies/playbook.py` → `research.playbook`,
  `strategies/mtf_long.py` → `research.mtf`, `engine/deriv.py` and `engine/deriv_history.py` →
  `research.universe_data`. After the split these become two tests —
  `test_strategies_does_not_import_research` (carrying the first two bridges, paths unchanged
  since `strategies/playbook.py` and `strategies/mtf_long.py` keep their relative filenames) and
  `test_models_does_not_import_research` (carrying the last two, now at `engine/deriv.py` and
  `engine/deriv_history.py` relative to the `models/` root, since Architecture's internal-layout
  decision keeps the `engine/` subdirectory). Task 7 writes both.
- **G1's ruling stays readable.** `experiments/registry/confluence_v2_2/runs/` is untouched by
  this phase (nothing in it references `signal/` file paths); Task 8 confirms this explicitly
  rather than assuming it.
- **Baseline to preserve, captured fresh at Task 1:** `2600 passed, 3 skipped` (`.venv/bin/python
  -m pytest -q -n auto`, ~332s), observed while writing this plan — confirm it is still current at
  Task 1 rather than trusting it silently; it is already lower than G4's own close-out figure of
  2656, so something shifted the count between G4 and now and Task 1 is where that gets noticed,
  not assumed away. **Execution note:** the first full-suite run under this plan reproduced this
  exact gap as a single xdist worker crash (`execnet`/`gateway_base.py` channel-read error) on
  `tests/kernel/test_determinism.py` — confirmed as infra flakiness under concurrent load, not a
  real failure (the same test passes cleanly in isolation, ~247s for 2 tests). If it recurs, isolate
  the named test before assuming a regression; avoid running more than one full `-n auto` suite at
  once — that concurrency is the likely trigger.
- **Commit style:** lowercase conventional prefix with scope `g5`: `refactor(g5):`, `feat(g5):`,
  `test(g5):`, `docs(g5):`, `chore(g5):`. **Never** include `Co-Authored-By` or any
  AI-attribution trailer.
- **Python interpreter:** `.venv/bin/python`. **`git mv` for every move**, never delete-then-create.
- **After any task touching imports, before committing:** run
  `.venv/bin/python -c "import moonface"` and
  `.venv/bin/python -m pytest --collect-only -q | tail -3` — a collection error is the fastest
  signal an import path was missed. `.venv/bin/python tools/ops/phase_guard.py check` runs at the
  end of every task (this phase touches no collector import path, so it should stay `GUARD PASS`
  throughout with no re-baseline needed).
- **The uncommitted `bybit_liquidation`/`bybit_positioning` WIP is out of scope.** Per
  [[g4-data-layer-unification]], `src/moonface/research/exogenous/bybit_liquidation_feed.py`,
  `bybit_positioning.py`, their `tools/bybit_*_collect.py` CLIs, and tests are still uncommitted
  in the working tree as of this plan's writing. They live in `research/exogenous/`, which this
  phase does not touch (G5 only moves `signal/` content), and G4's deferred Tasks 15-16 (moving
  them into `collect/`) are a separate, still-blocked piece of work — not this phase's to commit
  or resolve.

---

### Task 1: Pre-flight — confirm the real baseline

**Files:** none modified; read-only.

- [ ] **Step 1: Confirm the collector guard is green**

Run: `.venv/bin/python tools/ops/phase_guard.py check`
Expected: `GUARD PASS` on both row floors. If not, **stop** — a stalled collector outranks this
phase.

- [ ] **Step 2: Confirm the real pytest baseline**

Run: `.venv/bin/python -m pytest -q -n auto`
Record the exact `N passed, M skipped` line. This plan's own Global Constraints observed `2600
passed, 3 skipped` while being written — 56 fewer than G4's own close-out figure of `2656 passed,
3 skipped`; a re-run during execution reproduced the gap as a single xdist worker crash on
`tests/kernel/test_determinism.py`, confirmed as infra flakiness (isolated run: 2 passed, ~247s)
rather than a real regression, most likely triggered by running more than one full `-n auto`
suite concurrently. If a failure appears here, isolate the named test on its own before treating
it as a real blocker; only stop for real if an isolated re-run also fails. Every later task's
expected count in this plan is written as "baseline ± delta" against whatever real figure this
step confirms — substitute it before trusting any task's "Expected" line.

- [ ] **Step 3: No commit** — this task is pure verification, nothing to stage.

---

### Task 2: Audit — record the spec corrections found while researching this plan

**Files:**
- Modify: `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (append a correction
  note under the G5 section, mirroring G4 Task 2's convention)

**Status: DONE (commit `0a726b8`).** This task's spec-correction commit already landed before the
notify.py/feed boundary issue below was discovered — see the Architecture section's point 1 for
that follow-on correction, folded into Task 6 rather than re-opening this already-committed note.

- [ ] **Step 1: Re-run the importer greps this plan's research used, to catch drift**

```bash
grep -rln "moonface\.signal\.notify\b" --include="*.py" src tools tests | grep -v __pycache__
grep -rln "moonface\.signal\.cli\b" --include="*.py" src tools tests | grep -v __pycache__
grep -rln "moonface\.signal\.journal\b" --include="*.py" src tools tests | grep -v __pycache__
grep -rln "moonface\.signal\.baseline\b" --include="*.py" src tools tests | grep -v __pycache__
grep -rln "moonface\.signal\.participation_api\b" --include="*.py" src tools tests | grep -v __pycache__
grep -rln "strategy_api" --include="*.py" src tools tests | grep -v __pycache__
```
Expected (confirmed at plan-writing time; re-confirm before editing anything): `notify.py` →
`feed/cli.py`, `signal/cli.py`, `tests/signal/test_signal_notify.py`; `cli.py` → `feed/cli.py`
(lazy `_load_env_file` import only), its own tests; `journal.py` → `signal/cli.py`,
`research/practical_full/forward.py` (comment only, not a real import — confirm with
`grep -n "^from moonface.signal.journal\|^import moonface.signal.journal"
src/moonface/research/practical_full/forward.py` returning nothing), `tools/engine/engine_ablation.py`
(`read_entries` only), `tools/lanes/vol_expansion_watch.py` (comment only, same confirmation),
tests; `baseline.py` → `signal/cli.py`, `signal/engine/regime.py`, its own test;
`participation_api.py` → `signal/cli.py` only; `strategy_api` → no hits anywhere.

- [ ] **Step 2: Record the five corrections**

Append under the G5 section of `docs/research-log/specs/2026-08-22-repo-restructure-design.md`:

```markdown
*Correction 2026-08-25 (pre-implementation):* five corrections to this section's "genuinely v2.2
runtime" list, found while researching the implementation plan:

1. `notify.py` is not v2.2-only -- `feed/cli.py` (the separate, independently-entry-pointed
   `moonface-feed` Telegram SMC broadcaster) imports `TelegramNotifier` from it, and lazily
   imports `_load_env_file` from `cli.py`. Both relocate into `feed/` before `cli.py` is deleted,
   rather than being deleted with it.
2. `journal.py` needs a split, not a delete: `append_entry`/`read_entries` are generic
   append-only JSONL I/O with no v2.2 coupling, and `tools/engine/engine_ablation.py` (paired
   with the kept `engine/ablation.py`) imports `read_entries` directly. Only `forward_report`
   (the promotion gate) is v2.2-specific and deletable.
3. `baseline.py` is imported by `engine/regime.py` (kept, moving to `models/`), not just `cli.py`
   -- it moves to `models/` rather than being deleted, despite its CLI-tier framing.
4. `participation_api.py` (one importer: `cli.py` itself) is deletable alongside `cli.py` but was
   not named in the spec's four-file list -- corrected here for completeness.
5. `strategy_api.py` has zero importers anywhere in the tree, including the four strategy modules
   its own docstring describes as importing "only from here". It still moves to `strategies/` per
   this section's explicit table entry (the intended plugin facade for future strategy authors,
   not dead lane code) -- flagged so a future phase does not mistake the zero-importer count for
   a deletion candidate without re-reading this note.
```

- [ ] **Step 3: Commit**

```bash
git add docs/research-log/specs/2026-08-22-repo-restructure-design.md
git commit -m "docs(g5): correct the spec's v2.2-runtime list against the code

notify.py and cli.py's _load_env_file are shared with feed/, not v2.2-only;
journal.py needs a split (engine_ablation.py uses read_entries);
baseline.py is used by the kept engine/regime.py; participation_api.py was
missing from the four-file list; strategy_api.py has zero importers but
stays per the spec's own table. Corrected in place per this repo's
established convention (mirrors G4 Task 2)."
```

---

### Task 3: Split `journal.py` — extract `append_entry`/`read_entries` into `models/journal.py`

**Files:**
- Create: `src/moonface/models/journal.py` (the generic append-only half)
- Modify: `src/moonface/signal/journal.py` (keeps only `forward_report` and its constants until
  Task 6 deletes the whole file)
- Move (split): `tests/test_signal_journal.py`'s three I/O tests → `tests/models/test_journal.py`;
  its two `forward_report` tests stay in `tests/test_signal_journal.py` until Task 6
- Modify: `tools/engine/engine_ablation.py` (repoint `read_entries` import)

**Interfaces:**
- Consumes: nothing (stdlib `json`, `os`, `pathlib` only).
- Produces: `moonface.models.journal.{append_entry, read_entries}`. Task 6's deletion of
  `signal/journal.py` depends on nothing importing the old path for these two names by then.

- [ ] **Step 1: Read `journal.py` in full to confirm it has not drifted**

`cat src/moonface/signal/journal.py` — confirm against the 97-line version this plan's research
read (imports, `append_entry`, `read_entries`, then `FORWARD_MIN_TRADES`/`FORWARD_MIN_WEEKS`/
`_WEEK_MS` constants and `forward_report`) before splitting.

- [ ] **Step 2: Write the failing test for the new location**

Create `tests/models/test_journal.py` by moving these three tests out of
`tests/test_signal_journal.py` verbatim, updating only the import line:
```python
from moonface.models.journal import append_entry, read_entries


def test_append_and_read_roundtrip(tmp_path):
    p = tmp_path / "signals.jsonl"
    append_entry(p, {"a": 1})
    append_entry(p, {"b": 2})
    assert read_entries(p) == [{"a": 1}, {"b": 2}]


def test_missing_journal_reads_empty(tmp_path):
    assert read_entries(tmp_path / "absent.jsonl") == []


def test_corrupt_trailing_line_is_quarantined(tmp_path):
    p = tmp_path / "signals.jsonl"
    append_entry(p, {"a": 1})
    with open(p, "a") as fh:
        fh.write('{"trunc')
    assert read_entries(p) == [{"a": 1}]
    assert (tmp_path / "signals.jsonl.quarantine").exists()
```
Then delete these three functions (and, if now-unused, the `PromotedStrategy`/`strategy_hash`
import line stays — the two remaining `forward_report` tests still use it) from
`tests/test_signal_journal.py`, and fix its `journal` import line, which currently reads
`from moonface.signal.journal import append_entry, forward_report, read_entries`, to
`from moonface.signal.journal import forward_report` only.

- [ ] **Step 3: Run the new test file to verify it fails**

Run: `.venv/bin/python -m pytest tests/models/test_journal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.models'` (the package does not
exist yet; Task 4 creates `models/__init__.py`, but this task needs it now since it is the first
one to write into `models/` — create `src/moonface/models/__init__.py` in this task instead of
waiting for Task 4, since Task 4 depends on this task's ordering anyway).

- [ ] **Step 4: Create `models/__init__.py` and `models/journal.py`**

Create `src/moonface/models/__init__.py`:
```python
"""Signal-model framework: confluence scoring, the MoE combiner, the v3
mechanism-modelling framework, regime/position/discipline research
infrastructure, and generic model-adjacent I/O (journal.py). Moved out of
signal/ at G5 -- see design spec section 3."""
```

Create `src/moonface/models/journal.py`:
```python
"""Append-only JSONL log: one journal entry per line, fsync'd. Generic --
this module has no v2.2 or engine-specific coupling. Split out of
signal/journal.py at G5; the promotion-gate half (forward_report) was
v2.2-specific and was deleted with the rest of the v2.2 runtime, not moved
here."""
from __future__ import annotations

import json
import os
from pathlib import Path


def append_entry(path: str | Path, record: dict) -> None:
    """Append-only with fsync; records are never rewritten in place."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_entries(path: str | Path) -> list[dict]:
    """A corrupt trailing line (torn write) is quarantined to a sidecar file;
    corruption anywhere else is a real error and raises."""
    p = Path(path)
    if not p.exists():
        return []
    lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
    out: list[dict] = []
    for idx, line in enumerate(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            if idx == len(lines) - 1:
                with open(str(p) + ".quarantine", "a") as q:
                    q.write(line + "\n")
                break
            raise ValueError(f"corrupt journal line {idx + 1} in {p}")
    return out
```

- [ ] **Step 5: Trim `signal/journal.py` to the `forward_report` half**

Remove `append_entry`/`read_entries` and the now-unused `json`/`os` imports (keep `Path`,
`Candle`, `PromotedStrategy`, `strategy_hash` — `forward_report` still needs them):
```diff
-import json
-import os
 from pathlib import Path

 from moonface.core.models import Candle
 from moonface.signal.spec import PromotedStrategy, strategy_hash

 FORWARD_MIN_TRADES = 20
 FORWARD_MIN_WEEKS = 12.0
 _WEEK_MS = 7 * 86_400_000


-def append_entry(path: str | Path, record: dict) -> None:
-    ...  # deleted, moved to models/journal.py
-
-
-def read_entries(path: str | Path) -> list[dict]:
-    ...  # deleted, moved to models/journal.py
-
-
 def forward_report(entries: list[dict], candles: list[Candle],
                    strategy: PromotedStrategy) -> dict:
     ...  # unchanged
```
`signal/journal.py` still exists after this task (Task 6 deletes it along with `cli.py`) — it
must still import and run standalone; `forward_report`'s docstring/body reference neither
`append_entry` nor `read_entries`, so no internal call site needs fixing.

- [ ] **Step 6: Repoint `tools/engine/engine_ablation.py`**

```diff
-from moonface.signal.journal import read_entries
+from moonface.models.journal import read_entries
```

- [ ] **Step 7: Confirm `tests/test_signal_journal.py` was trimmed correctly in Step 2**

`test_forward_report_matches_ladder_math` and `test_forward_report_ignores_other_strategy_versions`
are the only two tests left in the file, importing `from moonface.signal.journal import
forward_report` (Step 2 already made this edit) — that import stays valid until Task 6 deletes
the whole file along with `journal.py`'s remaining `forward_report`-only half.

- [ ] **Step 8: Run the new and trimmed test files to verify they pass**

Run: `.venv/bin/python -m pytest tests/models/test_journal.py tests/test_signal_journal.py tests/engine/test_engine_ablation.py -v`
(adjust the last path if `engine_ablation.py`'s test file lives elsewhere — confirm with
`grep -rl "engine_ablation" tests/` first)
Expected: PASS — 3 new + 2 remaining + `engine_ablation`'s own tests unchanged.

- [ ] **Step 9: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: baseline +3 (three tests moved, none added or removed — `git mv`-equivalent split, zero
net change; only the file location differs), `GUARD PASS`.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(g5): split journal.py -- append_entry/read_entries to models/journal.py

Generic append-only JSONL I/O, used by tools/engine/engine_ablation.py
(paired with the kept engine/ablation.py) -- not v2.2-specific despite
living in signal/ alongside the promotion-gate code. forward_report (the
actual v2.2 paper->live gate) stays in signal/journal.py until Task 6
deletes it with the rest of the v2.2 runtime."
```

---

### Task 4: Move `engine/`, `matrix/`, `evaluate.py`, `baseline.py` → `models/`

The bulk move. `engine/` and `matrix/` relocate as whole subtrees (internal structure preserved
per Architecture); `evaluate.py` and `baseline.py` move as loose files at the `models/` root.

**Files:**
- Move: `src/moonface/signal/engine/` → `src/moonface/models/engine/` (44 files, whole subtree)
- Move: `src/moonface/signal/matrix/` → `src/moonface/models/matrix/` (4 files, whole subtree)
- Move: `src/moonface/signal/evaluate.py` → `src/moonface/models/evaluate.py`
- Move: `src/moonface/signal/baseline.py` → `src/moonface/models/baseline.py`
- Move: `tests/signal/engine/` → `tests/models/engine/`
- Move: `tests/signal/matrix/` → `tests/models/matrix/`
- Move: the loose `tests/signal/test_engine_cli.py`, `tests/signal/test_engine_config.py` →
  `tests/models/`
- Move: `tests/test_signal_baseline.py` → `tests/models/test_baseline.py`
- Modify: every internal cross-import inside the moved subtree (`moonface.signal.engine.X` →
  `moonface.models.engine.X`, `moonface.signal.matrix.X` → `moonface.models.matrix.X`,
  `moonface.signal.evaluate` → `moonface.models.evaluate`, `moonface.signal.baseline` →
  `moonface.models.baseline`)
- Modify: every external importer outside `signal/`/`models/` (Step 4 below)

**Interfaces:**
- Consumes: `moonface.core.*` (unchanged), `moonface.data.bundle.load_bundle` (unchanged since
  G4). `moonface.strategies.*` — **not yet** (Task 5 creates `strategies/`; confirm in Step 1
  whether anything in `engine/`/`matrix/`/`evaluate.py`/`baseline.py` currently imports
  `signal.spec`/`signal.registry`/`signal.strategies.*` — if so, those import lines are rewritten
  to the *old* `moonface.signal.spec`/`moonface.signal.registry` paths for now (Task 5 fixes them
  again when `strategies/` is created), not left broken.
- Produces: `moonface.models.{engine.*, matrix.*, evaluate, baseline}` — same names throughout,
  new root. Task 5's `strategies/` files (which do depend on `evaluate.py`'s `Signal`
  re-exports and `registry.py`) consume this task's output.

- [ ] **Step 1: Confirm the exact file set and any forward-referencing imports**

```bash
find src/moonface/signal/engine src/moonface/signal/matrix -name "*.py" | sort
grep -rln "moonface\.signal\.spec\|moonface\.signal\.registry\|moonface\.signal\.strategies" \
  src/moonface/signal/engine src/moonface/signal/matrix \
  src/moonface/signal/evaluate.py src/moonface/signal/baseline.py
```
Record whichever files the second command returns — they need their `moonface.signal.spec`/
`moonface.signal.registry` import lines left untouched in this task (they still resolve, since
`signal/spec.py`/`signal/registry.py` are not moved until Task 5) and revisited in Task 5.

- [ ] **Step 2: `git mv` every file**

```bash
git mv src/moonface/signal/engine src/moonface/models/engine
git mv src/moonface/signal/matrix src/moonface/models/matrix
git mv src/moonface/signal/evaluate.py src/moonface/models/evaluate.py
git mv src/moonface/signal/baseline.py src/moonface/models/baseline.py
git mv tests/signal/engine tests/models/engine
git mv tests/signal/matrix tests/models/matrix
git mv tests/signal/test_engine_cli.py tests/models/test_engine_cli.py
git mv tests/signal/test_engine_config.py tests/models/test_engine_config.py
git mv tests/test_signal_baseline.py tests/models/test_baseline.py
```

- [ ] **Step 3: Rewrite every internal cross-import inside the moved subtree**

```bash
grep -rln "moonface\.signal\.engine\b\|moonface\.signal\.matrix\b\|moonface\.signal\.evaluate\b\|moonface\.signal\.baseline\b" \
  src/moonface/models tests/models | grep -v __pycache__
```
For each hit, replace `moonface.signal.engine` → `moonface.models.engine`,
`moonface.signal.matrix` → `moonface.models.matrix`, `moonface.signal.evaluate` →
`moonface.models.evaluate`, `moonface.signal.baseline` → `moonface.models.baseline`. This is the
large majority of the ~44+4 files' own cross-references (e.g. `engine/confluence.py` importing
`engine/modules/trend_book.py`, `engine/v3/evaluate.py` importing `engine/v3/mechanisms/base.py`,
`matrix/governor.py` importing `engine/position.py`) — expect on the order of 60-90 line edits
across the subtree; this is mechanical, not judgment-requiring, since every name keeps its
relative position, only the `signal` → `models` root segment changes.

- [ ] **Step 4: Rewrite every external importer**

Run, once per module group, to enumerate the remaining external call sites (outside
`src/moonface/models/` and `tests/models/`, which Step 3 already fixed):
```bash
grep -rln "moonface\.signal\.engine\b" --include="*.py" src tools tests \
  | grep -v __pycache__ | grep -v "^src/moonface/models/\|^tests/models/"
grep -rln "moonface\.signal\.matrix\b" --include="*.py" src tools tests \
  | grep -v __pycache__ | grep -v "^src/moonface/models/\|^tests/models/"
grep -rln "moonface\.signal\.evaluate\b" --include="*.py" src tools tests \
  | grep -v __pycache__ | grep -v "^src/moonface/models/\|^tests/models/"
grep -rln "moonface\.signal\.baseline\b" --include="*.py" src tools tests \
  | grep -v __pycache__ | grep -v "^src/moonface/models/\|^tests/models/"
```
This plan's research measured (re-confirm each before editing, since it may have drifted):
`engine.config`: 53 hits — the single largest group, mostly `tools/` lane scripts and their
tests that read `EngineConfig`; `engine.calibration`: 12; `engine.confluence`: 12;
`engine.repair`: 13; `engine.macro`: 10; `engine.deriv`: 10; `engine.engine`: 8; `engine.audit`: 7;
`engine.discipline`: 6; `engine.position`: 5; `engine.scorecard`: 4; `engine.honesty`: 4;
`engine.regime`: 3; `engine.deriv_history`: 3; `engine.resample`: 2; `engine.setupcard`: 2;
`engine.ablation`: 2 (one is `tools/engine/engine_ablation.py`, already touched for its
`journal` import in Task 3 — this is its separate `engine.ablation` import, same file);
`matrix.governor`: 4; `matrix.horizon`: 2; `matrix.signal`: 1; `evaluate`: 16; `baseline`: 3 (down
to 2 external now that `engine/regime.py` moved with the rest of `engine/` in Step 2-3 above —
its own reference was fixed as an internal cross-import).

For every file each command returns, replace the `moonface.signal.` prefix with `moonface.models.`
on the matching import line(s) — `from moonface.signal.engine.confluence import ...`,
`import moonface.signal.engine.config as ...`, etc. all become the `moonface.models.` equivalent,
same submodule path after the root. Do this module group by module group (config first, since it
is largest and touches the most files, down through the smallest) so a mid-way collection check
catches a missed file early rather than after all ~150+ edits are made blind.

- [ ] **Step 5: Verify collection after each module group, not just at the end**

After finishing each `grep` group in Step 4:
```bash
.venv/bin/python -m pytest --collect-only -q 2>&1 | grep -i "error\|ModuleNotFound" | head -20
```
Expected: no output. A non-empty result names the file still on the old import path — fix it
before moving to the next group.

- [ ] **Step 6: Verify no regression in the moved subtree's own tests**

Run: `.venv/bin/python -m pytest tests/models/ -v 2>&1 | tail -20`
Expected: PASS, every test unchanged in assertion.

- [ ] **Step 7: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: baseline unchanged count (pure relocation — tests move, they don't multiply),
`GUARD PASS`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(g5): move engine/, matrix/, evaluate.py, baseline.py from signal/ to models/

The signal-combination and mechanism-modelling framework -- confluence,
MoE, v3 mechanisms, regime/position/discipline, the matrix governor/
horizon -- is not v2.2 runtime (spec section 1.5: only 11 of 66 signal/
files touch promotion/journal/engine.json). Internal engine/, engine/v3/,
engine/v3/mechanisms/, engine/moe/, engine/modules/, and matrix/
subdirectory structure preserved verbatim under models/ -- no boundary
test or invariant forces a flatten, and inventing one is unforced
restructuring risk this phase does not need. baseline.py included: it is
imported by the kept engine/regime.py, not just the retiring cli.py."
```

---

### Task 5: Move `strategy_api.py`, `registry.py`, `spec.py`, `strategies/*` → `strategies/`

**Files:**
- Move: `src/moonface/signal/strategy_api.py` → `src/moonface/strategies/strategy_api.py`
- Move: `src/moonface/signal/registry.py` → `src/moonface/strategies/registry.py`
- Move: `src/moonface/signal/spec.py` → `src/moonface/strategies/spec.py`
- Move: `src/moonface/signal/strategies/` (the 4 implementation files + `__init__.py`) →
  `src/moonface/strategies/strategies/` — **rename to avoid the collision**: the target package
  is itself named `strategies/`, and the existing subdirectory of implementations is also named
  `strategies/`; Step 1 below resolves this before moving anything.
- Move: `tests/signal/test_strategy_registry.py`, `tests/test_signal_strategy_registry.py`,
  `tests/test_signal_strategy_donchian.py`, `tests/test_signal_strategy_stack_path.py`,
  `tests/signal/test_mtf_long_strategy.py`, `tests/signal/test_signal_spec.py`,
  `tests/playbook/test_signal_adapter.py` (repoint only, stays in place — confirm in Step 1
  whether it needs a move) → `tests/strategies/`
- Modify: `src/moonface/strategies/registry.py` (`_FALLBACK_PKG` constant)
- Modify: `pyproject.toml` (`[project.scripts]` drops `moonface-signal`; `[project.entry-points."moonface.strategies"]`
  paths updated)
- Modify: every external importer of `signal.spec`/`signal.registry`/`signal.strategies.*`

**Interfaces:**
- Consumes: `moonface.models.evaluate.{Signal (re-exported), sentinel_extended, wait}`,
  `moonface.core.bundle.DataBundle`, `moonface.core.signal_types.Signal` (the ultimate source,
  per `models/evaluate.py`'s own import).
- Produces: `moonface.strategies.{strategy_api, registry, spec}` and
  `moonface.strategies.strategies.{donchian, mtf_long, playbook, stack_path}` — the entry-point
  target paths `pyproject.toml` now names.

- [ ] **Step 1: Resolve the `strategies/strategies/` naming collision**

The target package is `strategies/` (plugin API + registry + implementations, per spec §3: "
`strategies/ plugin API + registry + implementations (donchian, mtf_long, playbook,
stack_path)`" — one flat package, not a package containing a same-named subpackage. Rename the
implementations subdirectory to `strategies/impls/` on the move (not `strategies/strategies/`):
```bash
git mv src/moonface/signal/strategies src/moonface/strategies_impls_tmp   # staging name, avoids
                                                                            # colliding with the
                                                                            # not-yet-created
                                                                            # src/moonface/strategies/
```
(The two-step staging move is necessary because `git mv src/moonface/signal/strategies
src/moonface/strategies/impls` fails — `src/moonface/strategies/` does not exist yet as a
directory for `git mv` to move *into*.) Finish the rename once `src/moonface/strategies/` exists
in Step 2.

- [ ] **Step 2: `git mv` the three loose files, then settle the staged implementations directory**

```bash
git mv src/moonface/signal/strategy_api.py src/moonface/strategies/strategy_api.py
git mv src/moonface/signal/registry.py src/moonface/strategies/registry.py
git mv src/moonface/signal/spec.py src/moonface/strategies/spec.py
git mv src/moonface/strategies_impls_tmp src/moonface/strategies/impls
```
Create `src/moonface/strategies/__init__.py`:
```python
"""Strategy plugin API, registry, and reference implementations. Moved out
of signal/ at G5 -- see design spec section 3. strategy_api.py is the
single documented import surface for a strategy module (though, per this
plan's own audit, none of the four reference implementations currently
import it -- each imports moonface.core/moonface.models.evaluate directly;
kept as the intended facade for future strategy authors regardless)."""
```
`src/moonface/strategies/impls/__init__.py` already exists (moved with the directory) — leave its
content as-is unless Step 3 finds it needs an import fix.

- [ ] **Step 3: Rewrite internal cross-imports inside the moved files**

```bash
grep -rln "moonface\.signal\.spec\|moonface\.signal\.registry\|moonface\.signal\.strategy_api\|moonface\.signal\.strategies\b\|moonface\.signal\.evaluate\|moonface\.signal\.baseline" \
  src/moonface/strategies | grep -v __pycache__
```
Replace each: `moonface.signal.spec` → `moonface.strategies.spec`, `moonface.signal.registry` →
`moonface.strategies.registry`, `moonface.signal.strategy_api` → `moonface.strategies.strategy_api`,
`moonface.signal.strategies` → `moonface.strategies.impls`, `moonface.signal.evaluate` →
`moonface.models.evaluate` (Task 4's new path), `moonface.signal.baseline` → `moonface.models.baseline`
(Task 4's new path — confirm which of the 4 implementation files, if any, import `baseline.py`;
this plan's research found only `cli.py` and `engine/regime.py` do, so this may be a no-op here).

- [ ] **Step 4: Fix `registry.py`'s `_FALLBACK_PKG` constant**

```diff
-_FALLBACK_PKG = "moonface.signal.strategies"
+_FALLBACK_PKG = "moonface.strategies.impls"
```
This is the one line that makes `pkgutil.iter_modules` find the four implementation modules when
entry-point metadata is unavailable (the source-checkout fallback path) — get it wrong and
`_from_fallback()` silently returns an empty dict instead of raising.

- [ ] **Step 5: Fix `pyproject.toml`**

```diff
 [project.scripts]
-moonface-signal = "moonface.signal.cli:main"
 moonface-feed = "moonface.feed.cli:main"

 [project.entry-points."moonface.strategies"]
-donchian_break = "moonface.signal.strategies.donchian:DonchianStrategy"
-stack_path = "moonface.signal.strategies.stack_path:StackPathStrategy"
+donchian_break = "moonface.strategies.impls.donchian:DonchianStrategy"
+stack_path = "moonface.strategies.impls.stack_path:StackPathStrategy"
```
`moonface-signal`'s removal is Task 6's deletion of `cli.py` landing early here rather than
there, because the entry point can't point at a target this task already knows is about to not
exist under its old name — leaving it dangling for one extra commit is worse than removing it a
task early. `mtf_long`/`playbook` were never in the entry-points table (only discoverable via the
fallback scan) — this plan does not add them; that would be a scope decision beyond "move the
files", left for a human.

- [ ] **Step 6: Reinstall the package so the entry-point change takes effect**

Run: `.venv/bin/python -m pip install -e . --no-deps -q`
Expected: no output (quiet reinstall); confirms `pyproject.toml`'s edit is picked up before any
test exercises `entry_points(group="moonface.strategies")`.

- [ ] **Step 7: Rewrite every external importer**

```bash
grep -rln "moonface\.signal\.spec\b" --include="*.py" src tools tests | grep -v __pycache__ \
  | grep -v "^src/moonface/strategies/"
grep -rln "moonface\.signal\.registry\b" --include="*.py" src tools tests | grep -v __pycache__ \
  | grep -v "^src/moonface/strategies/"
grep -rln "moonface\.signal\.strategies\b" --include="*.py" src tools tests | grep -v __pycache__ \
  | grep -v "^src/moonface/strategies/"
```
This plan's research measured 12 `spec` importers, 12 `registry` importers, and a handful of
direct `signal.strategies.<name>` importers (`tools/`'s Donchian/stack_path/mtf_long-specific
scripts, plus `tests/playbook/test_signal_adapter.py` for `playbook.py`) — re-confirm the exact
list before editing (it drifts as lanes get touched by other in-flight work) and rewrite each hit:
`moonface.signal.spec` → `moonface.strategies.spec`, `moonface.signal.registry` →
`moonface.strategies.registry`, `moonface.signal.strategies.<name>` →
`moonface.strategies.impls.<name>`.

- [ ] **Step 8: Move the strategy-specific test files**

```bash
git mv tests/signal/test_strategy_registry.py tests/strategies/test_strategy_registry.py
git mv tests/test_signal_strategy_registry.py tests/strategies/test_signal_strategy_registry.py
git mv tests/test_signal_strategy_donchian.py tests/strategies/test_signal_strategy_donchian.py
git mv tests/test_signal_strategy_stack_path.py tests/strategies/test_signal_strategy_stack_path.py
git mv tests/signal/test_mtf_long_strategy.py tests/strategies/test_mtf_long_strategy.py
git mv tests/signal/test_signal_spec.py tests/strategies/test_signal_spec.py
```
(`tests/strategies/` does not exist yet — these `git mv` calls create it. Leave
`tests/playbook/test_signal_adapter.py` in place; it lives in a domain-named test directory, not
a `signal`-named one, so this task's rename scope does not reach it — only fix its import line if
Step 7's grep names it.) Repoint each moved file's import lines the same way as Step 7.

- [ ] **Step 9: Verify no regression, per group**

Run:
```bash
.venv/bin/python -m pytest tests/strategies/ -v
.venv/bin/python -c "from importlib.metadata import entry_points; print(sorted(e.name for e in entry_points(group='moonface.strategies')))"
```
Expected: PASS; the second command prints `['donchian_break', 'stack_path']` (entry-point-visible
names — `mtf_long`/`playbook` are fallback-only, unchanged from before this task).

- [ ] **Step 10: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: baseline unchanged count, `GUARD PASS`.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "refactor(g5): move strategy_api.py, registry.py, spec.py, strategies/ to strategies/

The plugin API and registry (spec section 1.5: 'the extension point for
new strategies'), not v2.2 runtime. Implementations subdirectory renamed
signal/strategies/ -> strategies/impls/ to avoid colliding with the new
strategies/ package name itself. registry.py's _FALLBACK_PKG and
pyproject.toml's entry-point paths updated to match; moonface-signal
script entry removed a task early since its target (signal/cli.py) is
retiring in Task 6 and a dangling entry point for one extra commit is
worse than removing it here."
```

---

### Task 6: Delete the v2.2 runtime, relocating `notify.py`/`_load_env_file` into `feed/` atomically

**This task does two things in one commit, deliberately.** Deleting `cli.py`, `style.py`,
`participation_api.py`, and `journal.py`'s remainder is what makes `signal/` empty. Relocating
`notify.py`/`_load_env_file` into `feed/` must happen in the *same* commit — see Global
Constraints and Architecture point 1: `tests/test_import_boundaries.py::
test_signal_does_not_import_research` already forbids anything under `signal/` from importing
`moonface.feed`, so there is no earlier commit where `notify.py` could move to `feed/` while
`signal/cli.py` still needs it without creating that exact violation. Doing both here means
`signal/cli.py` (which still imports the *old* `signal/notify.py` path right up until this
commit) is deleted in the same breath that `notify.py` moves out from under it — no transitional
state, no violation.

**Files:**
- Delete: `src/moonface/signal/cli.py`, `src/moonface/signal/style.py`,
  `src/moonface/signal/participation_api.py`, `src/moonface/signal/journal.py` (its remaining
  `forward_report`-only half)
- Delete: `tests/test_signal_cli.py`, `tests/signal/test_signal_style.py`,
  `tests/test_signal_journal.py` (its remaining two `forward_report` tests)
- Delete: `promotion/` (the root-level JSON config directory — `strategy.json`, `styles.json`,
  `participation.json`, `engine.json`, `baseline.json`, `archive/`; confirm nothing outside the
  files just deleted reads from it before removing)
- Move: `src/moonface/signal/notify.py` → `src/moonface/feed/notify.py`
- Move: `tests/signal/test_signal_notify.py` → `tests/feed/test_feed_notify.py`
- Modify: `src/moonface/feed/cli.py` (repoint the `TelegramNotifier` import to `feed.notify`;
  inline `_load_env_file` — copied verbatim from `signal/cli.py` before it is deleted — in place
  of the lazy cross-package import)

**Interfaces:**
- Consumes: nothing new.
- Produces: `moonface.feed.notify.{TelegramNotifier, notifier_from_env}` — `feed/`'s only
  remaining consumer from this commit forward. Nothing — pure deletion for the other four files,
  permitted under invariant 5 since none is lane code and none has a recorded run depending on it
  (confirmed by Task 2's audit: their only importers, other than each other, were `feed/cli.py`
  for two functions this task itself relocates, and `tools/engine/engine_ablation.py` for
  `read_entries` already relocated in Task 3).

- [ ] **Step 1: Confirm nothing else imports any of the four v2.2-only files**

```bash
grep -rln "moonface\.signal\.cli\b\|moonface\.signal\.style\b\|moonface\.signal\.participation_api\b\|moonface\.signal\.journal\b" \
  --include="*.py" src tools tests | grep -v __pycache__
```
Expected: only `feed/cli.py` (for `_load_env_file`, fixed in Step 5 below) and the four files'
own dedicated test files (about to be deleted in Step 6) — nothing else. **If anything else
appears, stop** — it means Task 2's audit missed an importer; resolve it (relocate, don't delete)
before proceeding.

- [ ] **Step 2: Confirm nothing reads `promotion/` outside what's being deleted**

```bash
grep -rln "\"promotion/\|'promotion/" --include="*.py" src tools tests | grep -v __pycache__
```
Expected: only `signal/cli.py` and `signal/style.py` (both about to be deleted) — default
argument values (`--strategy default="promotion/strategy.json"`, etc.). If any other file
appears, stop and investigate before deleting `promotion/`.

- [ ] **Step 3: Read the exact lines needed before their source files disappear**

```bash
grep -n "notify\|_load_env_file" src/moonface/signal/cli.py src/moonface/feed/cli.py
sed -n '43,72p' src/moonface/signal/cli.py   # _load_env_file's body, re-confirm the range first
```
Copy `_load_env_file`'s current body verbatim in Step 5 below — do not retype it from memory.

- [ ] **Step 4: `git mv` `notify.py` and its test into `feed/`**

```bash
git mv src/moonface/signal/notify.py src/moonface/feed/notify.py
git mv tests/signal/test_signal_notify.py tests/feed/test_feed_notify.py
```
Edit `src/moonface/feed/notify.py`'s docstring: replace "Outbound Telegram alerts for the signal
watch daemon" with "Outbound Telegram alerts for the moonface-feed broadcaster (and,
historically, the retired v2.2 signal CLI)." Edit `tests/feed/test_feed_notify.py`'s import line:
`from moonface.signal.notify import ...` → `from moonface.feed.notify import ...`.

- [ ] **Step 5: Fix `feed/cli.py` — repoint the notify import, inline `_load_env_file`**

```diff
 from moonface.data.bundle import load_bundle
 from moonface.feed.loop import run_once, run_watch
+from moonface.feed.notify import TelegramNotifier
 from moonface.feed.universe import select_top_volume
-from moonface.signal.notify import TelegramNotifier
```
Add `from pathlib import Path` to the import block (`_load_env_file` needs it; `feed/cli.py`
already imports `os`). Replace the lazy-import call site with the function itself, copied
verbatim from Step 3's read:
```diff
+def _load_env_file(path: str = ".env",
+                   env: dict[str, str] | None = None) -> None:
+    """Best-effort .env loader: parse KEY=VALUE lines into `env` (default the
+    process environment) without overriding values already present, so a real
+    shell export always wins. Stdlib-only on purpose -- this repo keeps
+    python-dotenv out of its deps. Called once from main() so `notifier_from_env()`
+    sees the TELEGRAM_* / MOONFACE_TELEGRAM_* keys a developer keeps in .env and
+    --watch actually mirrors every candle to Telegram instead of idling silent."""
+    if env is None:
+        env = os.environ
+    try:
+        text = Path(path).read_text()
+    except OSError:
+        return                       # no .env -> silent noop, env untouched
+    for raw in text.splitlines():
+        line = raw.strip()
+        if not line or line.startswith("#"):
+            continue
+        if line.startswith("export "):
+            line = line[len("export "):].lstrip()
+        if "=" not in line:
+            continue
+        key, _, value = line.partition("=")
+        key = key.strip()
+        if not key:
+            continue
+        value = value.strip()
+        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
+            value = value[1:-1]      # strip one surrounding quote pair
+        env.setdefault(key, value)
+
+
 def main() -> None:
-    # Best-effort .env load, mirroring signal.cli (stdlib-only).
-    from moonface.signal.cli import _load_env_file
     _load_env_file()
     raise SystemExit(run())
```

- [ ] **Step 6: Delete the four v2.2-only source files and their tests**

```bash
git rm src/moonface/signal/cli.py src/moonface/signal/style.py \
  src/moonface/signal/participation_api.py src/moonface/signal/journal.py
git rm tests/test_signal_cli.py tests/signal/test_signal_style.py tests/test_signal_journal.py
```

- [ ] **Step 7: Delete `promotion/`**

```bash
git rm -r promotion/
```

- [ ] **Step 8: Confirm `signal/` is now empty and remove what's left**

```bash
find src/moonface/signal -type f
find tests/signal -type f
```
Expected: only `src/moonface/signal/__init__.py` remains under `src/`, and `tests/signal/` is
empty (Tasks 3-5 moved every file out of it). Remove the now-pointless package:
```bash
git rm src/moonface/signal/__init__.py
rmdir src/moonface/signal tests/signal 2>/dev/null || true
```
If either `find` returns anything unexpected, **stop** — a file was missed in an earlier task;
find it and relocate it properly rather than force-deleting it here.

- [ ] **Step 9: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: baseline minus the deleted tests' count (record the exact delta: `test_signal_cli.py`'s
test count + `test_signal_style.py`'s test count + 2 remaining `forward_report` tests — count
each file's `def test_` lines before deleting in Step 6 if the exact number matters for the
commit message), `GUARD PASS`.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(g5): delete the v2.2 runtime, relocating notify.py/_load_env_file into feed/ atomically

signal/cli.py (the v2.2 advisory CLI), style.py (its per-style config
loader), participation_api.py (its live-CLI/research-advisor seam, one
importer, cli.py itself), and journal.py's promotion-gate half
(forward_report) are the confirmed v2.2-only remainder after Tasks 3-5
relocated everything with a surviving consumer (models/'s baseline.py and
journal.py's I/O half; strategies/'s plugin API). notify.py and
_load_env_file move into feed/ -- their only remaining consumer -- in this
same commit rather than an earlier one: test_import_boundaries.py already
forbids signal/ from importing moonface.feed, so no commit before this one
could have moved them without signal/cli.py briefly reaching into feed/ to
keep working. promotion/'s JSON configs had no other reader. signal/
package removed -- empty after this commit."
```

---

### Task 7: Fix `tests/test_import_boundaries.py` for the new layering

**Files:**
- Modify: `tests/test_import_boundaries.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: the enforced version of invariant 1 for this phase — `kernel` forbidden from
  importing `models` or `strategies`; `models` and `strategies` each forbidden from importing
  `research`, with the four paper-bridge exceptions re-scoped to their new relative paths.

- [ ] **Step 1: Read the current file in full to confirm it has not drifted**

`cat tests/test_import_boundaries.py` — confirm against the version this plan's research read
(reproduced in the Architecture section above) before editing.

- [ ] **Step 2: Replace the module docstring and the two bridge dicts**

```diff
 """Architecture guard: dependencies point only downward.
-core <- signal, core <- research; signal must NOT import research.
+core <- data <- features <- {models, kernel}; models <- strategies;
+kernel must never import models or strategies; models and strategies must
+NOT import research.

 Exception: signal/strategies/playbook.py is a PAPER-ONLY adapter (Signal tier
-"paper"; never the live execution path) that bridges to research.playbook to run
-the research engine and emit paper signals. It is allow-listed in _PAPER_BRIDGES
-as a scoped paper bridge. Live strategies such as donchian remain pure
-core+signal and are NOT allow-listed."""
+"paper"; never the live execution path) that bridges to research.playbook to run
+the research engine and emit paper signals. It is allow-listed in
+_STRATEGIES_RESEARCH_BRIDGES as a scoped paper bridge. Live strategies such as
+donchian remain pure core+models and are NOT allow-listed."""
 import ast
 import pathlib

 SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "moonface"

-# PAPER-ONLY adapters that deliberately bridge signal -> research to emit paper
+# PAPER-ONLY adapters that deliberately bridge strategies -> research to emit paper
 # signals. Scoped per-file: only the named research submodule (and its children)
-# is permitted for the listed adapter; every other signal file stays forbidden.
-_PAPER_BRIDGES: dict[str, tuple[str, ...]] = {
-    "strategies/playbook.py": ("moonface.research.playbook",),
-    # mtf_long is a paper-only adapter (Signal tier "paper", never live/executed)
+# is permitted for the listed adapter; every other strategies file stays forbidden.
+_STRATEGIES_RESEARCH_BRIDGES: dict[str, tuple[str, ...]] = {
+    "impls/playbook.py": ("moonface.research.playbook",),
+    # mtf_long is a paper-only adapter (Signal tier "paper", never live/executed)
     # that bridges to research.mtf to run the frozen broaden_best LONG-only entry
     # byte-identically to its registered backtest. (research.mtf's own transitive
     # research imports stay within the research layer and need no scoping here.)
-    "strategies/mtf_long.py": ("moonface.research.mtf",),
-    # engine/deriv.py is the confluence v2 derivatives adapter for the PAPER-ONLY
+    "impls/mtf_long.py": ("moonface.research.mtf",),
+}
+
+# models/ -> research bridges: engine/deriv.py is the confluence v2 derivatives
+# adapter for the PAPER-ONLY engine tier (ships disabled, NO_CLAIM).
+_MODELS_RESEARCH_BRIDGES: dict[str, tuple[str, ...]] = {
     # engine tier (ships disabled, NO_CLAIM). It reuses the funding-rate fetcher
     # from research.universe_data (spec Tech Stack: "deriv adapter only"); scoped
-    # to that one module so the rest of the signal layer stays research-free.
+    # to that one module so the rest of the models layer stays research-free.
     "engine/deriv.py": ("moonface.research.universe_data",),
     # engine/deriv_history.py is the scoring audit's historical counterpart of
     # deriv.py (read-only diagnostic, never the live engine path). It reuses the
     # same funding-rate fetcher, scoped identically.
     "engine/deriv_history.py": ("moonface.research.universe_data",),
 }
```
(Re-derive the exact hunk against Step 1's fresh read rather than applying this diff blind — the
line numbers and surrounding context may have shifted.) Note `_STRATEGIES_RESEARCH_BRIDGES`'
keys change from `strategies/playbook.py` to `impls/playbook.py` — Task 5 renamed the
implementations subdirectory to `strategies/impls/`, so a path *relative to the `strategies/`
layer root* is now `impls/playbook.py`, not `strategies/playbook.py` (that would now mean
`strategies/strategies/playbook.py`, which does not exist).

- [ ] **Step 3: Fix `_violations`' default argument**

```diff
 def _violations(layer: str, forbidden: tuple[str, ...],
-                bridges: dict[str, tuple[str, ...]] = _PAPER_BRIDGES) -> list[str]:
+                bridges: dict[str, tuple[str, ...]] | None = None) -> list[str]:
+    bridges = bridges or {}
     bad: list[str] = []
```
The old default silently assumed every caller wanted the (now strategies-specific) paper bridges;
make every caller pass its own bridges dict explicitly instead (Step 4's rewritten test functions
do this) so a future new layer added here can't accidentally inherit strategies' exceptions.

- [ ] **Step 4: Rewrite the test functions**

```diff
 def test_core_imports_nothing_above_it():
     assert _violations("core",
                        ("moonface.data", "moonface.features", "moonface.models",
                         "moonface.kernel", "moonface.strategies",
                         "moonface.signal", "moonface.research", "moonface.feed")) == []


-def test_kernel_imports_neither_signal_nor_a_lane():
-    assert _violations("kernel", ("moonface.signal", "moonface.research"),
+def test_kernel_imports_neither_models_strategies_nor_a_lane():
+    assert _violations("kernel",
+                       ("moonface.models", "moonface.strategies", "moonface.research"),
                        bridges=_KERNEL_RESEARCH_BRIDGES) == []
```
(`"moonface.signal"` drops from this test's forbidden tuple entirely — the package no longer
exists after Task 6, and a forbidden-import check against a nonexistent package name is not
protecting anything.)
```diff
 def test_data_imports_nothing_above_it():
     assert _violations("data",
                        ("moonface.features", "moonface.models", "moonface.kernel",
-                        "moonface.strategies", "moonface.signal", "moonface.research",
+                        "moonface.strategies", "moonface.research",
                         "moonface.feed", "moonface.collect", "moonface.lanes")) == []


 def test_collect_imports_nothing_above_it():
     assert _violations("collect",
                        ("moonface.features", "moonface.models", "moonface.kernel",
-                        "moonface.strategies", "moonface.signal", "moonface.research",
+                        "moonface.strategies", "moonface.research",
                         "moonface.feed", "moonface.lanes")) == []


-def test_signal_does_not_import_research():
-    assert _violations("signal", ("moonface.research", "moonface.feed")) == []
+def test_models_does_not_import_research():
+    assert _violations("models", ("moonface.research", "moonface.feed"),
+                       bridges=_MODELS_RESEARCH_BRIDGES) == []
+
+
+def test_strategies_does_not_import_research():
+    assert _violations("strategies", ("moonface.research", "moonface.feed"),
+                       bridges=_STRATEGIES_RESEARCH_BRIDGES) == []


 def test_feed_does_not_import_research():
     assert _violations("feed", ("moonface.research",)) == []
```
Also remove `"moonface.signal"` from `test_core_imports_nothing_above_it`'s forbidden tuple
(same reasoning: `moonface.signal` no longer exists) — leave `"moonface.strategies"` and
`"moonface.models"` in place, they are the real ongoing invariant.

- [ ] **Step 5: Run this test file alone first**

Run: `.venv/bin/python -m pytest tests/test_import_boundaries.py -v`
Expected: PASS — 7 tests (`core`, `kernel`, `data`, `collect`, `models`, `strategies`, `feed`),
each green. A failure here names the exact file+import still crossing a forbidden boundary —
fix that file, don't loosen the test.

- [ ] **Step 6: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: baseline unchanged count (no test added or removed, only rewritten), `GUARD PASS`.

- [ ] **Step 7: Commit**

```bash
git add tests/test_import_boundaries.py
git commit -m "test(g5): codify the models/ and strategies/ layering invariants

Replaces the dead signal-path checks (signal/ no longer exists after this
phase) with real enforcement of invariant 1: kernel must never import
models or strategies; models and strategies must not import research,
except the four already-scoped paper bridges (playbook.py, mtf_long.py
under strategies/impls/; deriv.py, deriv_history.py under models/engine/),
re-pathed to match Tasks 4-5's moves."
```

---

### Task 8: Close-out — confirm G1's ruling stays readable, record the phase-complete note

**Files:**
- Modify: `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (append the "Done" note
  under the G5 section, matching G0-G4's convention)

- [ ] **Step 1: Confirm G1's ruling is untouched**

```bash
ls experiments/registry/confluence_v2_2/runs/
cat experiments/registry/confluence_v2_2/runs/*/result.json 2>/dev/null | head -5
grep -rl "signal\." experiments/registry/confluence_v2_2/ 2>/dev/null
```
Expected: the run directory from G1 (`2026-07-05T09-00-00Z__b4924f8e/` per
[[g4-data-layer-unification]]'s sibling memory) still present with its `result.json`; the third
command returns nothing (the ledger records numbers and provenance, not source file paths, so
this phase's file moves cannot have touched it — confirm rather than assume).

- [ ] **Step 2: Confirm the four reference strategies still load through the registry**

```bash
.venv/bin/python -c "
from moonface.strategies.registry import get_strategy_module
for fam in ('donchian_break', 'mtf_long', 'playbook', 'stack_path'):
    mod = get_strategy_module(fam)
    print(fam, '->', 'OK' if mod is not None else 'MISSING')
"
```
Expected: all four print `OK`. (Family names must match each strategy class's own `.family`
attribute — if any prints `MISSING`, read that strategy's source to confirm the family string
used in `pyproject.toml`/the fallback registration matches what this check queries, and fix the
check or the registration, not silently skip it.)

- [ ] **Step 3: Confirm `models`/`strategies` import no `kernel`**

```bash
grep -rln "moonface\.kernel" --include="*.py" src/moonface/models src/moonface/strategies
```
Expected: no output — the reverse direction (models/strategies importing kernel) was never
forbidden by name in `test_import_boundaries.py` (only the kernel→models/strategies direction
is), but the spec's green-when criterion states it explicitly ("models/strategies import no
kernel") — confirm it directly rather than relying on the absence of a dedicated test.

- [ ] **Step 4: Full-suite final confirmation**

Run:
```bash
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: green, matching Task 7's count exactly (no drift since).

- [ ] **Step 5: Append the phase-complete note**

Append under the G5 section of `docs/research-log/specs/2026-08-22-repo-restructure-design.md`,
matching G0-G4's `*Done YYYY-MM-DD:* ...` convention:
```markdown
*Done 2026-08-25:* `models/` (engine/, matrix/, evaluate.py, baseline.py, journal.py's
append-only I/O half) and `strategies/` (strategy_api.py, registry.py, spec.py, impls/{donchian,
mtf_long, playbook, stack_path}) stood up; v2.2 runtime retired (cli.py, style.py,
participation_api.py, journal.py's forward_report half, promotion/); signal/ package removed.
Two of the spec's four "genuinely v2.2 runtime" files turned out to be shared with feed/ (the
separate moonface-feed Telegram broadcaster) and relocated there instead of being deleted --
correction recorded in this section pre-implementation, with a second execution-time correction
(notify.py/_load_env_file had to move atomically with cli.py's deletion, not ahead of it, because
test_import_boundaries.py already forbade signal/ from importing feed/) folded into Task 6.
tests/test_import_boundaries.py now enforces the real invariant-1 boundary (kernel forbidden from
models/strategies) in place of a dead signal-path check.
```

- [ ] **Step 6: Commit**

```bash
git add docs/research-log/specs/2026-08-22-repo-restructure-design.md
git commit -m "docs(g5): phase complete -- models/ and strategies/ stood up, v2.2 runtime retired

G1 ruling confirmed still readable (experiments/registry/confluence_v2_2/
untouched by this phase's file moves); all four reference strategies
confirmed loading through the registry; models/strategies confirmed
importing no kernel. Full suite green, collector guard PASS."
```
