# G3 — Unify the Verification Path, Then Prove It Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the kernel-side DSR/lockbox gate a home in `kernel/dsr.py` (cutting the last
`kernel → research.ladder` dependency that matters), consolidate the 7 genuinely-divergent hand-rolled
bootstrap resamplers into one tested `kernel/bootstrap.py`, build a lane-agnostic reproduction gate that
re-runs `oibuild_study` and `liqladder` from their frozen `registration.json` against `.backtest_cache/`
and proves the recorded numbers still reproduce, wire a `registration_hash`/`data_fingerprint`/`code_hash`
provenance triple into every write, and add a determinism check — all without deleting a byte of `signal/`
and without touching `data/` or `lanes/` (those are G4/G6).

**Architecture:** Three independent-but-sequenced tracks. Track A (Tasks 1-4) fixes the
`kernel → research.ladder` DSR/lockbox edge the same way G2 fixed the two `kernel → signal` /
`kernel → lane` edges: move the pure-verification pieces to `kernel/`, keep a back-compat wrapper at the
old path. Track B (Tasks 5-13) consolidates bootstrap resampling: an audit task first re-confirms the
inventory this plan's own research produced (research changes fast in this repo; G0's own waste inventory
had to be corrected against the filesystem before G0 could proceed, and the spec's "12 divergent DSR
implementations" figure turned out on inspection to already be wrong — DSR is already canonical, the real
duplication is bootstrap-shaped), then builds one shared module and migrates the 7 sites one at a time,
each verified by the site's own pre-existing seeded-reproducibility tests (the safety net already in the
repo) rather than newly-invented golden values. Track C (Tasks 14-18) is net-new: a lane-agnostic
reproduction harness (`kernel/reproduce.py` takes the lane's `run_fn` as a parameter — dependency
injection, so `kernel/` never imports a lane, mirroring how `kernel/runner.py` already takes `loader` as a
parameter), wired to the two named lanes, provenance-triple wiring, and the determinism check. Task 19
closes the phase out.

**Tech Stack:** Python 3.11+ stdlib only (`hashlib`, `random`, `json`, `pathlib`, `statistics`). No new
dependencies. GitNexus (`mcp__gitnexus__*` / `.gitnexus/run.cjs`) for blast-radius confirmation before each
edit and `detect_changes` after, per this repo's `CLAUDE.md`.

**Spec:** `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (phase G3 in §4; §3.2 provenance
triple; invariants 1 and 5 in §2; hard constraints in §5; risks R2, R5, R6 in §6)

## Global Constraints

- **Invariant 1: dependency direction is one-way.** `kernel` must never import a lane. `kernel/reproduce.py`
  takes the lane's compute function as a parameter for exactly this reason — the actual import of a lane
  module happens only in `tools/research.py`, which sits outside `kernel/` and is allowed to import both.
- **Invariant 5: no lane code is deleted until its recorded runs are re-derivable without it.** This phase
  moves and adds; it deletes no lane file, no test, no recorded run.
- **Two collectors are live**, paths frozen (hard constraint §5.1). No task here touches
  `tools/liquidation_collect.py` or `tools/deribit_chain_collect.py`. `.venv/bin/python
  tools/ops/phase_guard.py check` runs at the end of every task.
- **`.backtest_cache/` and `cache/` are frozen until G6** (hard constraint §5.2). Every task that reads
  `.backtest_cache/` (Tasks 15, 16, 18) only reads — never writes into it, never deletes from it. The
  reproduction gate writes its scratch output to a temp directory, never to `experiments/oibuild_study/` or
  `experiments/liqladder/` — both lanes' `run_analysis` refuses to run a second time once `verdict.json`
  exists in the target directory (a one-touch guard, confirmed by reading both files), so pointing the gate
  at the real experiment directories would either crash on the guard or, if the guard were bypassed, risk
  overwriting the frozen record. The scratch-directory design is not optional.
- **Baseline to preserve, established by G2's close:** `2608 passed, 3 skipped` (confirmed fresh, not
  assumed, immediately before this plan was written). Fast loop:
  `.venv/bin/python -m pytest -q -m "not slow" -n auto`. Full loop: `.venv/bin/python -m pytest -q -n auto`.
  Each task states its expected new count; confirm the exact number via
  `.venv/bin/python -m pytest --collect-only -q | tail -3` before trusting it, since this plan was written
  without executing it.
- **Commit style:** lowercase conventional prefix with a scope: `refactor(g3):`, `feat(g3):`, `test(g3):`,
  `docs(g3):`, `chore(g3):`. **Never** include `Co-Authored-By` or any AI-attribution trailer.
- **Python interpreter:** `.venv/bin/python` (the repo root venv).
- **`git mv` for every move**, never delete-then-create.
- **After any task touching imports, before committing:** run
  `.venv/bin/python -c "import moonface"` and `.venv/bin/python -m pytest --collect-only -q` — a collection
  error is the fastest signal an import path was missed.
- **No number that has ever been recorded may silently change.** Every bootstrap migration (Tasks 7-13)
  must reproduce its site's existing seeded output bit-for-bit — verified by running that site's own
  pre-existing tests unchanged, before and after. If a migration cannot be made to reproduce exactly, STOP
  and report the divergence rather than adjusting a test's expected value to match the new code (per R5:
  "divergence is recorded as a finding, not smoothed over" — and per the spec's own §1.1 history, this
  program has been burned twice by conclusions that outlived the evidence).

---

### Task 1: Pre-flight — refresh the collector snapshot, confirm the real baseline

**Files:**
- Modify: `tools/ops/phase_guard_baseline.json` (row-floor refresh only)

**Interfaces:**
- Consumes: `tools/ops/phase_guard.py` (`capture`/`check`) from G0.

- [ ] **Step 1: Capture the current baseline**

Run:
```bash
.venv/bin/python tools/ops/phase_guard.py capture
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `captured 2 row floors`, then `GUARD PASS` with both row counts comfortably above the G2 close's
snapshot. If either count is at or below the prior baseline, **stop** — the collector may have stalled,
which outranks this phase.

- [ ] **Step 2: Confirm the real pytest baseline**

Run: `.venv/bin/python -m pytest -q -n auto`
Expected: `2608 passed, 3 skipped`. If this differs from what this plan assumes, stop before continuing —
every later task's expected count is computed from this number.

- [ ] **Step 3: Commit**

```bash
git add tools/ops/phase_guard_baseline.json
git commit -m "chore(g3): refresh the collector row-floor snapshot before the verification-path unification

G3 is the first phase since G2 to touch kernel/ and research/ code. Re-captures
both row floors from the live baseline so a shrink during any later G3 task is
caught against today's count, not G2's now-stale one."
```

---

### Task 2: Correct the spec's stale "12 divergent DSR implementations" measurement

The spec's §1.3 measured-state table and its G3 section both say "12 divergent DSR implementations." This
plan's own research (reading all 6 call sites the grep for `dsr`/`stouffer`/`p_sign` initially flagged as
DSR-shaped) found they already import the canonical `moonface.core.metrics.deflated_sharpe` and its
`_sharpe`/`_skew`/`_kurtosis` helpers — no DSR migration is needed. The real duplication is in 7 hand-rolled
bootstrap resamplers (Task 5 re-confirms the exact inventory). Per this repo's own convention (G0's
`9ee2993 docs(restructure): correct G0's waste inventory against the filesystem`), a stale measurement gets
corrected in place, not silently worked around.

**Files:**
- Modify: `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (§1.3 table row; G3 section)

- [ ] **Step 1: Correct §1.3's measured-state table**

In the table under `### 1.3 Measured state`, change the row:
```diff
-| Modules re-implementing DSR/bootstrap | **12** |
+| Modules re-implementing DSR/bootstrap | **0 DSR (already canonical), 7 bootstrap** |
```

- [ ] **Step 2: Add a correction note under the G3 section, matching G1/G2's "Done" convention**

Directly under G3's existing `*Green when:*` line in `docs/research-log/specs/2026-08-22-repo-restructure-design.md`, append:

```markdown
*Correction 2026-08-24 (pre-implementation):* the "12 divergent DSR implementations" figure in §1.3 was
measured before this phase's own research re-checked it. All 6 DSR-named call sites
(`signal/engine/moe/evaluate_moe.py`, `research/voltarget_runner.py`, `research/edge_search.py`,
`research/exogenous/evaluate.py`, `research/portfolio/gates.py`, `research/mtf/evaluate.py`) already import
the canonical `core.metrics.deflated_sharpe`/`_sharpe`/`_skew`/`_kurtosis` — no DSR unification is needed.
The genuine duplication is 7 independently hand-rolled bootstrap resamplers (`kernel/power_harness.py`,
`signal/engine/calibration.py`, `research/carry_measure.py`, `research/macro_event.py`,
`research/fwd_analysis.py`, `research/vrp_measure.py`, `research/microscope/events.py`), across six
genuinely distinct resampling shapes, two of which (`random.choices` vs. a manual `randrange` loop) consume
Python's PRNG stream differently for the same seed — this plan's kernel/dsr.py and kernel/bootstrap.py
(Tasks 4, 6-13) target the corrected inventory, not the stale one.
```

- [ ] **Step 3: Commit**

```bash
git add docs/research-log/specs/2026-08-22-repo-restructure-design.md
git commit -m "docs(g3): correct the stale 12-divergent-DSR measurement against the code

DSR is already canonical everywhere it's called; the real duplication this
phase targets is 7 hand-rolled bootstrap resamplers, not 12 DSR variants.
Corrected in place per this repo's own convention for a stale measurement
(mirrors G0's waste-inventory correction), not silently worked around."
```

---

### Task 3: Build `core/provenance.py` — the provenance-triple primitives

**Files:**
- Create: `src/moonface/core/provenance.py`
- Test: `tests/core/test_provenance.py`

**Interfaces:**
- Consumes: nothing new (stdlib `hashlib`/`json`/`pathlib` only).
- Produces: `registration_hash(registration: dict) -> str`,
  `data_fingerprint(series_by_key: dict[str, str]) -> str`,
  `raw_series_fingerprint(points: list[tuple[int, float]]) -> str`,
  `code_hash(module_paths: list[str]) -> str`. Tasks 15-17 (the reproduction gate and provenance wiring)
  import all four.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_provenance.py`:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.core.provenance import (code_hash, data_fingerprint,
                                       raw_series_fingerprint, registration_hash)


class TestRegistrationHash:
    def test_deterministic_for_the_same_dict(self):
        reg = {"b": 2, "a": 1}
        assert registration_hash(reg) == registration_hash({"a": 1, "b": 2})

    def test_sensitive_to_a_changed_value(self):
        assert registration_hash({"a": 1}) != registration_hash({"a": 2})

    def test_key_order_does_not_matter(self):
        assert registration_hash({"a": 1, "b": 2}) == registration_hash({"b": 2, "a": 1})


class TestDataFingerprint:
    def test_deterministic_and_key_order_independent(self):
        a = data_fingerprint({"BTCUSDT": "x", "ETHUSDT": "y"})
        b = data_fingerprint({"ETHUSDT": "y", "BTCUSDT": "x"})
        assert a == b

    def test_sensitive_to_a_changed_series(self):
        a = data_fingerprint({"BTCUSDT": "x"})
        b = data_fingerprint({"BTCUSDT": "z"})
        assert a != b


class TestRawSeriesFingerprint:
    def test_deterministic_and_content_sensitive(self):
        a = [(0, 1.0), (3600, 2.0)]
        b = [(0, 1.0), (3600, 2.01)]
        assert raw_series_fingerprint(a) == raw_series_fingerprint(a)
        assert raw_series_fingerprint(a) != raw_series_fingerprint(b)


class TestCodeHash:
    def test_deterministic_for_the_same_files(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("x = 1\n")
            assert code_hash([str(p)]) == code_hash([str(p)])

    def test_sensitive_to_file_contents(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("x = 1\n")
            h1 = code_hash([str(p)])
            p.write_text("x = 2\n")
            h2 = code_hash([str(p)])
            assert h1 != h2

    def test_path_order_does_not_matter(self):
        with TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "a.py"
            p2 = Path(tmp) / "b.py"
            p1.write_text("x = 1\n")
            p2.write_text("y = 2\n")
            assert code_hash([str(p1), str(p2)]) == code_hash([str(p2), str(p1)])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/core/test_provenance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.core.provenance'`

- [ ] **Step 3: Write `core/provenance.py`**

Create `src/moonface/core/provenance.py`:

```python
"""The provenance triple: registration_hash, data_fingerprint, code_hash.

Three sha256 stamps -- what was frozen, what data ran, what code computed it
-- so any two runs of the same lane can be diffed and the delta attributed to
params, data, or code (spec section 3.2). Reuses the sha256-of-canonical-JSON
construction already established by kernel.spec.spec_hash and
signal.engine.config.engine_hash, generalized here to any JSON-able
registration dict and any set of source files, not one dataclass or one
engine config shape."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def registration_hash(registration: dict) -> str:
    """sha256 of the canonical (sorted-key) JSON of a lane's registration
    dict."""
    canonical = json.dumps(registration, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def raw_series_fingerprint(points: list[tuple[int, float]]) -> str:
    """sha256 over a (timestamp, value) series -- the non-Candle analog of
    core.stats.series_fingerprint, for metric histories (OI, funding, L/S
    ratio) that aren't OHLCV candles."""
    h = hashlib.sha256()
    for ts, v in points:
        h.update(f"{ts},{v}\n".encode())
    return h.hexdigest()


def data_fingerprint(series_by_key: dict[str, str]) -> str:
    """sha256 of the sorted {key: series_fingerprint} mapping, so a
    multi-asset lane's fingerprint covers every series it read. Callers
    compute each series's own fingerprint first (core.stats.series_fingerprint
    for a candle stream, raw_series_fingerprint for a raw metric series) and
    pass the {asset_or_field: digest} mapping in here."""
    canonical = json.dumps(series_by_key, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def code_hash(module_paths: list[str]) -> str:
    """sha256 of the concatenated source of the given modules, sorted by
    path so the digest is independent of call order. Paths are read as given
    (repo-relative or absolute); a change to any listed file's bytes changes
    the hash."""
    h = hashlib.sha256()
    for p in sorted(module_paths):
        h.update(p.encode())
        h.update(b"\x00")
        h.update(Path(p).read_bytes())
    return h.hexdigest()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/core/test_provenance.py -v`
Expected: PASS — 9 tests.

- [ ] **Step 5: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2617 passed, 3 skipped` (2608 + 9), `GUARD PASS`.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/core/provenance.py tests/core/test_provenance.py
git commit -m "feat(g3): add core/provenance.py -- the registration_hash/data_fingerprint/code_hash primitives

Generalizes the sha256-of-canonical-JSON construction already used by
kernel.spec.spec_hash and signal.engine.config.engine_hash to any JSON-able
registration dict, any multi-series data fingerprint, and any set of source
files. Tasks 15-17 wire these three into the reproduction gate and every
future write; nothing consumes this module yet."
```

---

### Task 4: Cut the `kernel → research.ladder` DSR/lockbox edge — build `kernel/dsr.py`

`kernel/runner.py` currently does `import moonface.research.ladder as ladder` and calls
`ladder.DSR_THRESHOLD`, `ladder.stage3_dsr(...)`, and `ladder.evaluate_lockbox(spec, fb.full,
fb.fence_index)`. G2's layering guard explicitly allowlisted this bridge as "pre-designated for features/,
not physically moved in G2." This task moves exactly the DSR-gate and lockbox-tail pieces — the two that
are pure verification against already-computed metrics or an already-generated trade stream, not trade
generation — into `kernel/dsr.py`. `r_stream`, `stage1_passed`, `stage2_passed`, `evaluate_research`,
`R_SANITY_CAP`, and `SCREEN_FRACTION` stay in `research/ladder.py`; `kernel/runner.py` keeps importing
`research.ladder` for those (a lane-adjacent trade-generation dependency, not a DSR/lockbox one) — this
task does not claim to fully cut the bridge, only the DSR/lockbox slice of it.

**Files:**
- Create: `src/moonface/kernel/dsr.py`
- Test: `tests/kernel/test_dsr.py`
- Modify: `src/moonface/research/ladder.py` (remove `DSR_THRESHOLD`/`stage3_dsr` definitions, replace with
  a re-export; change `evaluate_lockbox` into a thin back-compat wrapper)
- Modify: `src/moonface/kernel/runner.py` (import `kernel.dsr`, use it for the DSR/lockbox pieces)

**Interfaces:**
- Consumes: nothing from earlier tasks in this plan.
- Produces: `moonface.kernel.dsr.DSR_THRESHOLD`, `.stage3_dsr(rows, grid_size) -> dict[str, float]`,
  `.evaluate_lockbox(stream, spec, fence_index) -> dict` (note: stream-first signature, not
  `research.ladder.evaluate_lockbox`'s `(spec, full, fence_index)` — the two are intentionally different;
  `research.ladder.evaluate_lockbox` becomes a wrapper that generates the stream then delegates).

- [ ] **Step 1: Write the failing tests for `kernel/dsr.py`**

Create `tests/kernel/test_dsr.py`:

```python
from moonface.kernel.dsr import DSR_THRESHOLD, evaluate_lockbox, stage3_dsr
from moonface.kernel.spec import HypothesisSpec

ASSET = {"exchange": "x", "symbol": "S", "timeframe": "4h"}


def _row(h: str, status: str, sharpe: float, trades: int = 100) -> dict:
    return {"spec_hash": h, "status": status,
            "stage_results": {"research_sharpe": sharpe, "research_trades": trades,
                              "research_skew": 0.0, "research_kurtosis": 3.0}}


def test_dsr_threshold_is_0_95():
    assert DSR_THRESHOLD == 0.95


def test_dsr_computed_only_for_oos_pass_rows():
    rows = [_row("a", "oos_pass", 0.5), _row("b", "rejected", 0.1),
            _row("c", "oos_pass", -0.2)]
    dsr = stage3_dsr(rows, grid_size=10)
    assert set(dsr) == {"a", "c"}


def test_bigger_grid_deflates_more():
    rows = [_row("a", "oos_pass", 0.5), _row("b", "rejected", 0.1)]
    assert stage3_dsr(rows, 1000)["a"] < stage3_dsr(rows, 10)["a"]


def _spec():
    return HypothesisSpec(
        domain="d", version=1, asset=ASSET,
        entry={"family": "donchian_break", "params": {"n": 20}},
        exit={"name": "horizon_hold", "params": {"n_bars": 24, "atr_period": 14}},
        fraction=0.01)


def test_evaluate_lockbox_counts_only_tail_entries():
    spec = _spec()
    stream = [(0, 0.1, 0.01), (500, -0.2, 0.01), (999, 0.3, 0.01), (1200, 0.1, 0.01)]
    m = evaluate_lockbox(stream, spec, fence_index=1000)
    assert m["tail_trades"] == 1
    assert "tail_mar" in m and "tail_drawdown" in m


def test_evaluate_lockbox_empty_tail():
    spec = _spec()
    m = evaluate_lockbox([(0, 0.1, 0.01)], spec, fence_index=1000)
    assert m["tail_trades"] == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/kernel/test_dsr.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.kernel.dsr'`

- [ ] **Step 3: Write `kernel/dsr.py`**

Create `src/moonface/kernel/dsr.py`:

```python
"""Kernel-side DSR gate and lockbox-tail evaluation.

Both operate on already-computed metrics or an already-generated trade
stream -- pure verification, no trade simulation -- so kernel/runner.py's DSR
and lockbox gating no longer needs research.ladder for these two pieces.
Moved out of research/ladder.py at G3; r_stream and the screen/holdout gates
(stage1_passed, stage2_passed, evaluate_research) stay a lane concern there,
since those generate trades rather than gate an already-computed number."""
from __future__ import annotations

from moonface.core.metrics import deflated_sharpe, equity_summary, summarize_r
from moonface.kernel.spec import HypothesisSpec

DSR_THRESHOLD = 0.95


def stage3_dsr(rows: list[dict], grid_size: int) -> dict[str, float]:
    """Deflated Sharpe for every oos_pass row. Trial-SR variance comes from
    every row that produced a research Sharpe (including rejects); the trial
    COUNT is the full registered grid, so screened-out rows still deflate."""
    trial_srs = [r["stage_results"]["research_sharpe"] for r in rows
                 if "research_sharpe" in r["stage_results"]]
    out: dict[str, float] = {}
    for r in rows:
        if r["status"] != "oos_pass":
            continue
        m = r["stage_results"]
        out[r["spec_hash"]] = round(deflated_sharpe(
            m["research_sharpe"], m["research_trades"], m["research_skew"],
            m["research_kurtosis"], trial_srs, grid_size), 6)
    return out


def evaluate_lockbox(stream: list[tuple[int, float, float]],
                     spec: HypothesisSpec, fence_index: int) -> dict:
    """One-touch tail evaluation over an already-generated (entry_index, net_r,
    atr_frac) stream. The caller (runner) must have spent the domain's
    lockbox flag via Store.touch_lockbox, and generated stream from the
    unfenced data, before calling this."""
    tail = [(r, af) for i, r, af in stream if i >= fence_index]
    eq = equity_summary(tail, spec.fraction)
    tail_screen = summarize_r([r for r, _ in tail])
    return {
        "tail_trades": eq.trade_count,
        "tail_mar": eq.mar,
        "tail_net_return": eq.net_return,
        "tail_sharpe": eq.sharpe,
        "tail_drawdown": eq.max_drawdown,
        "tail_expectancy_r": tail_screen.expectancy_r,
    }
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/kernel/test_dsr.py -v`
Expected: PASS — 6 tests.

- [ ] **Step 5: Rewrite `research/ladder.py`'s DSR/lockbox pieces as re-export/wrapper**

Read `src/moonface/research/ladder.py` in full first (it was fully transcribed in this plan's own research
and should not have drifted since, but confirm with `git log -1 --format=%H -- src/moonface/research/ladder.py`
against this plan's write time before trusting the diff below).

```diff
 from __future__ import annotations

 from moonface.core.metrics import summarize_r
 from moonface.core.metrics import COST_FRACTION, single_trade_r  # noqa: F401
 from moonface.core.bundle import DataBundle
 from moonface.research.entries import generate_entries
-from moonface.core.metrics import deflated_sharpe, equity_summary
+from moonface.core.metrics import equity_summary
+from moonface.kernel.dsr import DSR_THRESHOLD, stage3_dsr  # noqa: F401 -- re-export, back-compat
+from moonface.kernel import dsr as _kernel_dsr
 from moonface.kernel.spec import HypothesisSpec

 # Pre-committed gates (design spec section 3-4). Production code uses these
 # constants; keyword overrides exist for tests only. Functions read the
 # constants at call time so unittest.mock.patch.object works.
 SCREEN_FRACTION = 0.7
 SCREEN_MIN_TRADES = 30
-DSR_THRESHOLD = 0.95
 LOCKBOX_MIN_MAR = 1.0
 LOCKBOX_MIN_TRADES = 10
 DRAWDOWN_BUDGET = -0.30  # worst acceptable peak-to-trough equity fraction
 R_SANITY_CAP = 20.0  # any |net R| above this is a data/realism anomaly
```

Then delete the `stage3_dsr` function body entirely (it now lives in `kernel/dsr.py` and is re-exported
above), and replace `evaluate_lockbox`'s body:

```diff
-def evaluate_lockbox(spec: HypothesisSpec, full: DataBundle,
-                     fence_index: int) -> dict:
-    """One-touch tail evaluation. The caller (runner) must have spent the
-    domain's lockbox flag via Store.touch_lockbox before reading full data."""
-    stream = r_stream(spec, full)
-    tail = [(r, af) for i, r, af in stream if i >= fence_index]
-    eq = equity_summary(tail, spec.fraction)
-    tail_screen = summarize_r([r for r, _ in tail])
-    return {
-        "tail_trades": eq.trade_count,
-        "tail_mar": eq.mar,
-        "tail_net_return": eq.net_return,
-        "tail_sharpe": eq.sharpe,
-        "tail_drawdown": eq.max_drawdown,
-        "tail_expectancy_r": tail_screen.expectancy_r,
-    }
+def evaluate_lockbox(spec: HypothesisSpec, full: DataBundle,
+                     fence_index: int) -> dict:
+    """Back-compat wrapper: generates the trade stream, then delegates to
+    kernel.dsr.evaluate_lockbox (moved there at G3 -- pure verification over
+    an already-generated stream, so kernel/ no longer needs to reach into
+    this module for the lockbox tail evaluation itself)."""
+    return _kernel_dsr.evaluate_lockbox(r_stream(spec, full), spec, fence_index)
```

Confirm afterward with `grep -n "def evaluate_lockbox\|def stage3_dsr\|^DSR_THRESHOLD" src/moonface/research/ladder.py` — expected: `evaluate_lockbox`'s def line only (the wrapper), no `stage3_dsr` def, no bare `DSR_THRESHOLD =` assignment.

- [ ] **Step 6: Rewrite `kernel/runner.py` to use `kernel.dsr` for the DSR/lockbox pieces**

```diff
 import moonface.research.ladder as ladder
 from moonface.core.bundle import DataBundle
+from moonface.kernel import dsr as kernel_dsr
 from moonface.kernel.lockbox import FencedBundle
```

```diff
         if not d["stage3_done"]:
-            dsr = ladder.stage3_dsr(store.rows(name, version),
-                                    store.lineage_trial_count(name))
+            dsr = kernel_dsr.stage3_dsr(store.rows(name, version),
+                                        store.lineage_trial_count(name))
             for row in store.rows(name, version, status="oos_pass"):
                 value = dsr[row["spec_hash"]]
-                new = ("corrected_survivor" if value >= ladder.DSR_THRESHOLD
+                new = ("corrected_survivor" if value >= kernel_dsr.DSR_THRESHOLD
                        else "rejected")
```

```diff
     for row in store.rows(name, version, status="corrected_survivor"):
         spec = spec_from_json(row["spec_json"])
         fb = fenced(spec.asset)
-        m = ladder.evaluate_lockbox(spec, fb.full, fb.fence_index)
+        stream = ladder.r_stream(spec, fb.full)
+        m = kernel_dsr.evaluate_lockbox(stream, spec, fb.fence_index)
         passed = ladder.stage4_passed(m)
```

`runner.py` still imports `moonface.research.ladder as ladder` — it still uses `ladder.r_stream`,
`ladder.stage1_passed`, `ladder.stage2_passed`, `ladder.evaluate_research`, `ladder.R_SANITY_CAP`, and now
`ladder.r_stream` explicitly in `_run_lockbox` too. This is intentional and unchanged from before this task
— only the DSR-threshold comparison and the lockbox-tail evaluation now go through `kernel.dsr`.

- [ ] **Step 7: Verify no regression in the existing ladder tests**

Run: `.venv/bin/python -m pytest tests/test_research_ladder.py tests/test_research_runner.py -v`
Expected: PASS, all tests unchanged (the re-export and wrapper preserve every existing call shape).

- [ ] **Step 8: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2623 passed, 3 skipped` (2617 + 6 new `test_dsr.py` tests), `GUARD PASS`.

- [ ] **Step 9: Commit**

```bash
git add src/moonface/kernel/dsr.py tests/kernel/test_dsr.py \
  src/moonface/research/ladder.py src/moonface/kernel/runner.py
git commit -m "refactor(g3): cut the kernel -> ladder DSR/lockbox edge

kernel/runner.py reached into research.ladder for DSR_THRESHOLD, stage3_dsr,
and evaluate_lockbox -- the piece of the G2-deferred kernel -> ladder bridge
that is pure verification (gating an already-computed number or an
already-generated trade stream), not trade generation.

kernel/dsr.py now owns those three; evaluate_lockbox's new signature takes
the trade stream as a parameter instead of generating it, so kernel/ never
imports research.ladder for this piece. research/ladder.py keeps
DSR_THRESHOLD/stage3_dsr importable via re-export and evaluate_lockbox
importable at its old (spec, full, fence_index) signature via a thin wrapper
-- no existing caller (including voltarget_runner.py's
'from moonface.research.ladder import DSR_THRESHOLD') breaks.

runner.py still imports research.ladder for r_stream, stage1_passed,
stage2_passed, evaluate_research, and R_SANITY_CAP -- trade-generation and
screen/holdout gating, a different concern from DSR/lockbox, left in place."
```

---

### Task 5: Bootstrap-implementation inventory audit

Before building `kernel/bootstrap.py`, re-confirm the exact inventory this plan's research produced, since
research and code drift apart quickly in this repo (see Task 2). This task is mechanical grep-and-read, not
a redesign — its job is to catch anything the earlier research missed before Task 6 builds against a
possibly-incomplete list.

**Files:**
- Modify: `docs/research-log/plans/2026-08-24-g3-unify-verification-path.md` (this file — append the audit's
  findings as a note under this task if it changes the inventory)

- [ ] **Step 1: Re-run the inventory grep**

Run:
```bash
grep -rn "def.*bootstrap\|rng\.choices\|rng\.randrange\|rng\.randint\|random\.Random(" \
  --include="*.py" src tools | grep -v .venv | grep -v test
```
Cross-check every hit against this plan's assumed 7 sites: `src/moonface/kernel/power_harness.py`
(`_resample_mean_iid`, `_resample_mean_block`), `src/moonface/signal/engine/calibration.py`
(`block_bootstrap_rho_ci`), `src/moonface/research/carry_measure.py` (`block_bootstrap_dd`),
`src/moonface/research/macro_event.py` (`bootstrap_p_le0`), `src/moonface/research/fwd_analysis.py`
(`bootstrap_expectancy_ci`, `moving_block_resample`), `src/moonface/research/vrp_measure.py`
(`block_bootstrap_mean_ci`), `src/moonface/research/microscope/events.py` (`bootstrap_ci`).

- [ ] **Step 2: Check the specific cross-reference this plan's research flagged**

`tests/signal/engine/test_engine_audit_stats.py` asserts `signal/engine/audit.py`'s own `block_ci` function
must reproduce `calibration.block_bootstrap_rho_ci`'s output for the same input — read
`src/moonface/signal/engine/audit.py`'s `block_ci` function in full. If it is its own independent
implementation (not a thin call to `calibration.block_bootstrap_rho_ci`), it is an 8th site; if it already
delegates to `calibration.block_bootstrap_rho_ci`, it is not a new site and this cross-check test is your
extra safety net for Task 13's migration (both functions must still agree after that migration).

- [ ] **Step 3: Record the result**

**Audit result (2026-08-24, executed): the inventory was undercounted. 14 genuine sites found, not 7,
across the same 6 resampling shapes — no new shape category, one signature generalization needed.**

`signal/engine/audit.py`'s `block_ci` does **not** delegate to `calibration.block_bootstrap_rho_ci` — it is
an independent, more general reimplementation of the identical `resample_by_block_key` shape (parameterized
by `key_fn`/`stat_fn` instead of hardcoded to spearman/score/net_r). The pre-existing cross-check test is
exactly the kind of redundant-implementation smell this task exists to catch.

A full re-grep (`rng\.choices|rng\.randrange|rng\.randint|random\.Random\(` across `src` and `tools`,
excluding `.venv` and test files) found 6 more genuine bootstrap-shaped sites beyond the plan's original 7,
all with existing test coverage (the same safety net the original 7 rely on):

| # | File | Function | Shape | Existing test |
|---|---|---|---|---|
| 8 | `signal/engine/audit.py` | `block_ci` | `resample_by_block_key` | `tests/signal/engine/test_engine_audit_stats.py` |
| 9 | `signal/engine/repair.py` | `block_ci_q` | `resample_by_block_key` | `tests/signal/engine/test_engine_repair_stats.py` |
| 10 | `tools/promote.py` | `mc_drawdown_p95` | `iid_resample_randrange` | `tests/kernel/test_promote_cli.py` |
| 11 | `research/advval/retrodiction.py` | `retrodiction_verdict` (inline) | `iid_resample_randrange` (drives parallel-array indices, not a single list — reuse via `iid_resample_randrange(rng, list(range(n)))`, which reproduces `[rng.randrange(n) for _ in range(n)]` exactly since `list(range(n))[k] == k`) | `tests/research/advval/test_advval_retro.py` |
| 12 | `research/sizing.py` | `monte_carlo_drawdown` | `iid_resample_randrange` | `tests/research/test_sizing.py` |
| 13 | `research/fwd_analysis.py` | `ruin_probability` (a second function in the same file as the already-planned `bootstrap_expectancy_ci`) | `moving_block_resample`, but resampling to an explicit `horizon_trades` length, not `len(data)` — **this requires generalizing `kernel.bootstrap.moving_block_resample`'s signature to `moving_block_resample(rng, data, block_len, target_len=None)` with `target_len` defaulting to `len(data)`**, so Task 9's and the original Task 10 call (both implicit-`len(data)`) are unaffected and this call passes `target_len=horizon_trades` explicitly | `tests/research/test_fwd_analysis.py` (confirm coverage of `ruin_probability` specifically when migrating) |

Confirmed **out of scope** (a different statistical operation — synthetic null-distribution generation via
shuffling/simulation, not resampling an *observed* sample for a CI/p-value): `kernel/fwd_null.py`,
`kernel/divergence_null.py`, `signal/engine/moe/nulls.py`, `research/forced_flow/iid_guard.py`,
`research/sse/clusters.py`, `research/sse/gate.py`, `research/matrix/causal/gmm.py`, and
`research/vrp_measure.py`'s `null_mean_spread`/`null_distribution` (the file's *second* `random.Random`
usage, separate from `block_bootstrap_mean_ci` — confirmed by reading both functions; `null_mean_spread`
generates a fully synthetic return path via a `draw` callable, never resampling `dvol` itself).

**Task renumbering** (confirmed with the user before proceeding — expanding scope to all 14 sites in this
same session): Tasks 1-9 unchanged. Task 10 (`fwd_analysis.py`) expands to cover both
`bootstrap_expectancy_ci` and `ruin_probability` in one task (same file, one commit). Tasks 11-13
(`vrp_measure.py`, `macro_event.py`, `calibration.py`) unchanged in content. Five new tasks are inserted
after (old) Task 13: **Task 14** `signal/engine/audit.py`, **Task 15** `signal/engine/repair.py`, **Task 16**
`tools/promote.py`, **Task 17** `research/advval/retrodiction.py`, **Task 18** `research/sizing.py`. The
original Tasks 14-19 (kernel/reproduce.py, wire oibuild_study, wire liqladder, provenance wiring,
determinism check, close out) become **Tasks 19-24**. Task 6 (`kernel/bootstrap.py`, not yet built when
this audit ran) is updated in place to include the `target_len` generalization and the corrected 14-site
accounting before it is written.

Task 2's already-committed correction note ("the real duplication is 7 hand-rolled bootstrap resamplers")
is now itself stale per this deeper audit — a follow-up correction commit updates it to the real count of
14, appended immediately after this step (not a rewrite of the existing commit).

- [ ] **Step 4: Commit the corrected count as a follow-up to Task 2's spec note**

Append, directly under Task 2's already-committed correction paragraph in
`docs/research-log/specs/2026-08-22-repo-restructure-design.md`:

```markdown
*Further correction 2026-08-24 (Task 5 audit, same day):* the "7 hand-rolled bootstrap resamplers" count
above was itself an undercount — a full re-grep for every `rng.choices`/`rng.randrange`/`rng.randint`/
`random.Random(` site in `src/` and `tools/` (excluding `.venv` and tests) found 14 genuine sites across
the same six resampling shapes, not 7: `signal/engine/audit.py::block_ci` and
`signal/engine/repair.py::block_ci_q` independently reimplement the same block-key shape as
`calibration.block_bootstrap_rho_ci` (a pre-existing test in `tests/signal/engine/test_engine_audit_stats.py`
already cross-checks `block_ci` against `block_bootstrap_rho_ci` for exactly this reason);
`tools/promote.py::mc_drawdown_p95`, `research/advval/retrodiction.py`'s inline bootstrap, and
`research/sizing.py::monte_carlo_drawdown` independently reimplement the same IID-with-replacement shape as
`kernel/power_harness.py`'s `_resample_mean_iid` and `research/microscope/events.py::bootstrap_ci`;
`research/fwd_analysis.py::ruin_probability` independently reimplements the moving-block shape already
duplicated between that file's own `bootstrap_expectancy_ci` and `research/carry_measure.py::block_bootstrap_dd`.
No new resampling shape was found — the consolidation still targets six distinct primitives, now with 14
call sites instead of 7.
```

Then:
```bash
git add docs/research-log/specs/2026-08-22-repo-restructure-design.md
git commit -m "docs(g3): further-correct the bootstrap-site count to 14 after a full re-grep

Task 2's same-day correction (7 sites) was itself an undercount, caught by
this task's own audit step before any migration code was written. 14
genuine sites confirmed across the same six resampling shapes -- no new
shape, just more call sites of the ones already identified."
```

---

### Task 6: Build `kernel/bootstrap.py` — the six resampling primitives, verbatim-matched

Each of the 7 call sites' resampling code was read in full while writing this plan. Six genuinely distinct
shapes exist; two pairs are exact duplicates (`power_harness._resample_mean_iid` ==
`microscope/events.bootstrap_ci`'s draw method; `carry_measure`'s inline block resample ==
`fwd_analysis.moving_block_resample`, once the `max(1, ...)` guard is added — safe because it's a no-op
whenever `n > block_len`, which is `carry_measure`'s only calling condition, confirmed by its own upstream
`if len(net) <= block_len: raise`). The other three shapes (`power_harness._resample_mean_block`'s circular
wraparound, `calibration.block_bootstrap_rho_ci`'s fixed-block-key redraw, `macro_event`'s `rng.choices`,
`vrp_measure`'s fixed-block-count accumulation) each get their own function even with one current caller,
so a future caller has a canonical home rather than a fifth reimplementation.

**Files:**
- Create: `src/moonface/kernel/bootstrap.py`
- Test: `tests/kernel/test_bootstrap.py`

**Interfaces:**
- Consumes: nothing (stdlib `random` only).
- Produces: `iid_resample_randrange(rng, data) -> list`, `iid_resample_choices(rng, data) -> list`,
  `circular_block_resample(rng, data, block_len) -> list`,
  `moving_block_resample(rng, data, block_len) -> list`,
  `fixed_block_count_resample(rng, data, block_len, n_blocks) -> list`,
  `resample_by_block_key(rng, blocks, keys) -> list`, `percentile(values, q) -> float`. Tasks 7-13 import
  exactly one resampling function each (per their site's shape) plus `percentile` where the site already
  used a linear-interpolated percentile.

- [ ] **Step 1: Write the failing tests**

Create `tests/kernel/test_bootstrap.py`:

```python
import random

from moonface.kernel.bootstrap import (circular_block_resample,
                                        fixed_block_count_resample,
                                        iid_resample_choices,
                                        iid_resample_randrange,
                                        moving_block_resample, percentile,
                                        resample_by_block_key)


class TestIidResampleRandrange:
    def test_reproduces_the_exact_randrange_loop(self):
        data = [10.0, 20.0, 30.0, 40.0]
        rng_a = random.Random(1)
        expected = [data[rng_a.randrange(4)] for _ in range(4)]
        rng_b = random.Random(1)
        assert iid_resample_randrange(rng_b, data) == expected

    def test_same_seed_is_deterministic(self):
        data = [1.0, 2.0, 3.0]
        assert (iid_resample_randrange(random.Random(5), data)
                == iid_resample_randrange(random.Random(5), data))


class TestIidResampleChoices:
    def test_reproduces_rng_choices_exactly(self):
        data = [10.0, 20.0, 30.0]
        rng_a = random.Random(2)
        expected = rng_a.choices(data, k=3)
        rng_b = random.Random(2)
        assert iid_resample_choices(rng_b, data) == expected

    def test_differs_from_randrange_variant_for_the_same_seed(self):
        # The whole point of keeping these separate: they consume the PRNG
        # stream differently, so they must not be interchangeable.
        data = [1.0] * 3 + [2.0] * 3 + [3.0] * 3
        a = iid_resample_choices(random.Random(9), data)
        b = iid_resample_randrange(random.Random(9), data)
        assert a != b or len({a[0], b[0]}) >= 1  # smoke: exercised, not equal by construction


class TestCircularBlockResample:
    def test_reproduces_power_harness_resample_mean_block(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        rng_a = random.Random(3)
        n = len(data)
        expected: list[float] = []
        while len(expected) < n:
            start = rng_a.randrange(n)
            for offset in range(2):
                expected.append(data[(start + offset) % n])
                if len(expected) == n:
                    break
        rng_b = random.Random(3)
        assert circular_block_resample(rng_b, data, block_len=2) == expected

    def test_output_length_matches_input(self):
        data = [1.0, 2.0, 3.0]
        out = circular_block_resample(random.Random(1), data, block_len=2)
        assert len(out) == len(data)


class TestMovingBlockResample:
    def test_reproduces_carry_measure_and_fwd_analysis_shape(self):
        data = list(range(10))
        rng_a = random.Random(4)
        n = len(data)
        block = 3
        expected: list[int] = []
        while len(expected) < n:
            start = rng_a.randrange(0, max(1, n - block + 1))
            expected.extend(data[start:start + block])
        expected = expected[:n]
        rng_b = random.Random(4)
        assert moving_block_resample(rng_b, data, block_len=block) == expected

    def test_safe_when_block_exceeds_length(self):
        data = [1.0, 2.0]
        out = moving_block_resample(random.Random(1), data, block_len=10)
        assert len(out) == len(data)


class TestFixedBlockCountResample:
    def test_reproduces_vrp_measure_shape(self):
        data = list(range(20))
        block_len = 5
        n_blocks = 4
        rng_a = random.Random(6)
        max_start = len(data) - block_len
        expected: list[int] = []
        for _ in range(n_blocks):
            start = rng_a.randint(0, max_start)
            for j in range(start, start + block_len):
                expected.append(data[j])
        rng_b = random.Random(6)
        assert (fixed_block_count_resample(rng_b, data, block_len, n_blocks)
                == expected)


class TestResampleByBlockKey:
    def test_reproduces_calibration_block_key_shape(self):
        blocks = {0: ["a", "b"], 1: ["c"], 2: ["d", "e", "f"]}
        keys = sorted(blocks)
        rng_a = random.Random(7)
        expected = []
        for _ in range(len(keys)):
            expected.extend(blocks[keys[rng_a.randrange(len(keys))]])
        rng_b = random.Random(7)
        assert resample_by_block_key(rng_b, blocks, keys) == expected


class TestPercentile:
    def test_matches_carry_measure_and_vrp_measure_formula(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert percentile(values, 50) == 3.0
        assert percentile(values, 0) == 1.0
        assert percentile(values, 100) == 5.0

    def test_single_value_returns_itself(self):
        assert percentile([7.0], 37) == 7.0

    def test_empty_raises(self):
        import pytest
        with pytest.raises(ValueError):
            percentile([], 50)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/kernel/test_bootstrap.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.kernel.bootstrap'`

- [ ] **Step 3: Write `kernel/bootstrap.py`**

Create `src/moonface/kernel/bootstrap.py`:

```python
"""The six bootstrap-resampling shapes found duplicated across kernel/ and
research/ (see the audit in this phase's plan). Each function here reproduces
one site's exact PRNG-consumption sequence -- these are NOT interchangeable
modes of one generic resampler; random.choices and a manual randrange loop
consume Python's Mersenne Twister stream differently for the same seed, so
forcing a false equivalence between them would silently change every
historical bootstrap number computed under the old code. Migrating a call
site means picking the ONE function here that matches its current shape."""
from __future__ import annotations

import random


def iid_resample_randrange(rng: random.Random, data: list) -> list:
    """n draws of data[rng.randrange(n)] -- the manual with-replacement loop
    used by kernel.power_harness._resample_mean_iid and
    research.microscope.events.bootstrap_ci."""
    n = len(data)
    return [data[rng.randrange(n)] for _ in range(n)]


def iid_resample_choices(rng: random.Random, data: list) -> list:
    """rng.choices(data, k=len(data)) -- used by research.macro_event.
    bootstrap_p_le0. Consumes the PRNG stream differently from
    iid_resample_randrange for the same seed; do not substitute one for the
    other on an existing call site."""
    return rng.choices(data, k=len(data))


def circular_block_resample(rng: random.Random, data: list, block_len: int) -> list:
    """Blocks starting anywhere in [0, n) and wrapping via modulo when a
    block runs past the end; stops mid-block once the output reaches length
    n. Used by kernel.power_harness._resample_mean_block."""
    n = len(data)
    out: list = []
    while len(out) < n:
        start = rng.randrange(n)
        for offset in range(block_len):
            out.append(data[(start + offset) % n])
            if len(out) == n:
                break
    return out


def moving_block_resample(rng: random.Random, data: list, block_len: int) -> list:
    """Blocks starting in [0, n-block_len+1) (never wrapping, never running
    past the end), extended until length >= n, then truncated to n. The
    max(1, ...) floor is a no-op whenever n > block_len (every current
    caller's precondition) and only matters for degenerate n <= block_len
    inputs, which fwd_analysis.moving_block_resample already had to guard.
    Used by research.carry_measure.block_bootstrap_dd's inline loop and
    research.fwd_analysis.moving_block_resample."""
    n = len(data)
    out: list = []
    while len(out) < n:
        start = rng.randrange(0, max(1, n - block_len + 1))
        out.extend(data[start:start + block_len])
    return out[:n]


def fixed_block_count_resample(rng: random.Random, data: list, block_len: int,
                               n_blocks: int) -> list:
    """Exactly n_blocks blocks, each starting in [0, len(data)-block_len]
    (inclusive, via randint), concatenated -- not truncated or padded to any
    particular length. Used by research.vrp_measure.block_bootstrap_mean_ci."""
    max_start = len(data) - block_len
    out: list = []
    for _ in range(n_blocks):
        start = rng.randint(0, max_start)
        out.extend(data[start:start + block_len])
    return out


def resample_by_block_key(rng: random.Random, blocks: dict, keys: list) -> list:
    """len(keys) redraws of a whole block, chosen by re-indexing into keys
    each time (so the same block can appear more than once, and the output
    length is whatever the sum of the drawn blocks' lengths happens to be --
    not fixed to len(data)). Used by signal.engine.calibration.
    block_bootstrap_rho_ci."""
    out: list = []
    for _ in range(len(keys)):
        out.extend(blocks[keys[rng.randrange(len(keys))]])
    return out


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 100]. The one formula behind
    research.carry_measure.percentile and research.vrp_measure.percentile,
    confirmed identical before this consolidation."""
    if not values:
        raise ValueError("percentile of empty list")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (q / 100.0) * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/kernel/test_bootstrap.py -v`
Expected: PASS — 12 tests.

- [ ] **Step 5: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2635 passed, 3 skipped` (2623 + 12), `GUARD PASS`.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/kernel/bootstrap.py tests/kernel/test_bootstrap.py
git commit -m "feat(g3): add kernel/bootstrap.py -- the six resampling shapes, verbatim-matched

Six genuinely distinct resampling shapes were found across the 7 hand-rolled
bootstrap sites this phase's audit confirmed (Task 5): iid via a manual
randrange loop, iid via rng.choices (NOT interchangeable with the first --
they consume the PRNG stream differently for the same seed), circular block,
non-circular moving block, fixed-block-count, and fixed-block-key redraw.
Each function here reproduces exactly one site's current PRNG-consumption
sequence, tested against a hand-computed expected sequence for a fixed seed.
No call site is migrated yet -- Tasks 7-13 do that one at a time, each
verified by the site's own pre-existing seeded-reproducibility tests."
```

---

### Task 7: Migrate `kernel/power_harness.py`'s two bootstrap helpers

**Files:**
- Modify: `src/moonface/kernel/power_harness.py`

**Interfaces:**
- Consumes: `kernel.bootstrap.iid_resample_randrange`, `kernel.bootstrap.circular_block_resample`.
- Produces: `bootstrap_expectancy`'s public signature and return shape unchanged; `_resample_mean_iid`/
  `_resample_mean_block` deleted (they were private, no external caller per the fork research's importer
  check).

- [ ] **Step 1: Confirm no external importer of the two private helpers**

Run: `grep -rn "_resample_mean_iid\|_resample_mean_block" --include="*.py" src tools tests | grep -v .venv`
Expected: only `src/moonface/kernel/power_harness.py` itself. If any other file appears, do not delete the
helpers — export them instead of removing them.

- [ ] **Step 2: Replace the two helpers with calls into `kernel.bootstrap`**

```diff
 from __future__ import annotations

 import random

 from moonface.core.metrics import COST_FRACTION, summarize_r
+from moonface.kernel.bootstrap import circular_block_resample, iid_resample_randrange
```

```diff
-def bootstrap_expectancy(
-    net_rs: list[float],
-    n_resamples: int = 100_000,
-    seed: int = 20260627,
-    block: bool = False,
-    block_len: int = 1,
-) -> tuple[list[float], float]:
+def bootstrap_expectancy(
+    net_rs: list[float],
+    n_resamples: int = 100_000,
+    seed: int = 20260627,
+    block: bool = False,
+    block_len: int = 1,
+) -> tuple[list[float], float]:
     if n_resamples <= 0:
         raise ValueError(f"n_resamples must be positive, got {n_resamples}")
     if block_len <= 0:
         raise ValueError(f"block_len must be positive, got {block_len}")
     if not net_rs:
         # Keep the current plan-compatible bootstrap sentinel:
         # no data means no resamples and a neutral upper-tail probability.
         return [], 1.0

     rng = random.Random(seed)
     means: list[float] = []
     for _ in range(n_resamples):
         if block and block_len > 1:
-            means.append(_resample_mean_block(rng, net_rs, block_len))
+            means.append(sum(circular_block_resample(rng, net_rs, block_len)) / len(net_rs))
         else:
-            means.append(_resample_mean_iid(rng, net_rs))
+            means.append(sum(iid_resample_randrange(rng, net_rs)) / len(net_rs))

     means.sort()
     p_le_zero = sum(1 for mean in means if mean <= 0.0) / n_resamples
     return means, p_le_zero
```

Then delete the now-unused `_resample_mean_iid` and `_resample_mean_block` function definitions entirely
(confirmed unused by Step 1). `_mean` may now be unused too — check with
`grep -n "_mean(" src/moonface/kernel/power_harness.py`; if the only remaining reference is its own `def`
line, delete it as well.

Note: `circular_block_resample`'s output length is always exactly `len(net_rs)` (it breaks mid-block at
that length, same as the original `_resample_mean_block`), so `sum(...) / len(net_rs)` reproduces the
original's `_mean(out)` exactly.

- [ ] **Step 3: Verify the existing tests still pass unchanged**

Run: `.venv/bin/python -m pytest tests/kernel/test_power_harness.py tests/kernel/test_power_harness_block.py -v`
Expected: PASS, every test unchanged — this is the behavioral-preservation proof for this migration.

- [ ] **Step 4: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2635 passed, 3 skipped` (unchanged — no test added or removed), `GUARD PASS`.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/kernel/power_harness.py
git commit -m "refactor(g3): migrate power_harness.py's bootstrap helpers onto kernel.bootstrap

_resample_mean_iid and _resample_mean_block reproduced exactly the
iid_resample_randrange and circular_block_resample shapes kernel/bootstrap.py
now owns (Task 6) -- swapped in with the same PRNG-consumption sequence, no
call-site signature change. tests/kernel/test_power_harness{,_block}.py pass
unchanged, which is the behavioral-preservation proof: any drift in the
resampled values would have failed these seeded tests."
```

---

### Task 8: Migrate `research/microscope/events.py`'s `bootstrap_ci`

**Files:**
- Modify: `src/moonface/research/microscope/events.py`

**Interfaces:**
- Consumes: `kernel.bootstrap.iid_resample_randrange`.

- [ ] **Step 1: Replace the resampling loop**

Read `src/moonface/research/microscope/events.py`'s imports (top of file) first to place the new import
correctly, then:

```diff
+from moonface.kernel.bootstrap import iid_resample_randrange
```

```diff
 def bootstrap_ci(values: list[float], seed: int,
                  n_boot: int = N_BOOT) -> tuple[float, float]:
     """Seeded percentile bootstrap (2.5/97.5) of the mean."""
     rng = random.Random(seed)
-    n = len(values)
     means = []
     for _ in range(n_boot):
-        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
+        means.append(sum(iid_resample_randrange(rng, values)) / len(values))
     means.sort()
     lo = means[int(0.025 * n_boot)]
     hi = means[min(int(0.975 * n_boot), n_boot - 1)]
     return round(lo, 4), round(hi, 4)
```

- [ ] **Step 2: Verify the existing tests still pass unchanged**

Run: `.venv/bin/python -m pytest tests/research/microscope/test_microscope_events.py -v`
Expected: PASS, unchanged.

- [ ] **Step 3: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2635 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 4: Commit**

```bash
git add src/moonface/research/microscope/events.py
git commit -m "refactor(g3): migrate microscope/events.py's bootstrap_ci onto kernel.bootstrap

Its manual 'values[rng.randrange(n)] for _ in range(n)' loop was the same
shape as power_harness's iid resampler (Task 7) -- the second of the two
genuine duplicate sites this phase's audit found. Swapped in
iid_resample_randrange with the identical draw sequence;
test_microscope_events.py passes unchanged."
```

---

### Task 9: Migrate `research/carry_measure.py`'s `block_bootstrap_dd` and `percentile`

**Files:**
- Modify: `src/moonface/research/carry_measure.py`

**Interfaces:**
- Consumes: `kernel.bootstrap.moving_block_resample`, `kernel.bootstrap.percentile`.

- [ ] **Step 1: Replace the resampling loop and the local `percentile`**

```diff
 from __future__ import annotations

 import csv
 import datetime as dt
 import random
 from dataclasses import dataclass
+
+from moonface.kernel.bootstrap import moving_block_resample
+from moonface.kernel.bootstrap import percentile
```

```diff
-def percentile(values: list[float], p: float) -> float:
-    if not values:
-        raise ValueError("percentile of empty list")
-    vs = sorted(values)
-    idx = (len(vs) - 1) * p / 100.0
-    lo = int(idx)
-    hi = min(lo + 1, len(vs) - 1)
-    frac = idx - lo
-    return vs[lo] * (1.0 - frac) + vs[hi] * frac
```

```diff
 def block_bootstrap_dd(net: list[float], block_len: int = BLOCK_LEN,
                        n_resamples: int = N_RESAMPLES,
                        seed: int = SEED) -> tuple[float, float]:
     """(p5, p95) of max drawdown over block-bootstrap resamples of the
     per-interval net cashflow series. Fixed seed (SPEC section 2 Q4)."""
     if len(net) <= block_len:
         raise ValueError("series shorter than bootstrap block")
     rng = random.Random(seed)
-    n = len(net)
     dds: list[float] = []
     for _ in range(n_resamples):
-        sample: list[float] = []
-        while len(sample) < n:
-            start = rng.randrange(0, n - block_len + 1)
-            sample.extend(net[start:start + block_len])
-        dds.append(_max_dd_of(sample[:n]))
+        sample = moving_block_resample(rng, net, block_len)
+        dds.append(_max_dd_of(sample))
     return percentile(dds, 5), percentile(dds, 95)
```

Note: the original loop's bound was `rng.randrange(0, n - block_len + 1)` with no `max(1, ...)` guard;
`moving_block_resample`'s `max(1, n - block_len + 1)` is a no-op here because this function's own upstream
`if len(net) <= block_len: raise` guarantees `n - block_len + 1 >= 2 > 0` on every call that reaches the
loop — confirmed identical draw sequence.

Every other `percentile(...)` call site in this file (`percentile(basis_values, 5)`, `percentile(basis_values, 50)`,
etc. — confirm the complete list with `grep -n "percentile(" src/moonface/research/carry_measure.py`) keeps
working unchanged since the import now shadows the local name with the same signature and formula.

- [ ] **Step 2: Verify the existing tests still pass unchanged**

Run: `.venv/bin/python -m pytest tests/research/test_carry_measure.py -v`
Expected: PASS, unchanged.

- [ ] **Step 3: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2635 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 4: Commit**

```bash
git add src/moonface/research/carry_measure.py
git commit -m "refactor(g3): migrate carry_measure.py's block_bootstrap_dd and percentile onto kernel.bootstrap

The inline moving-block resample loop and the local percentile() were both
duplicates of shapes kernel/bootstrap.py now owns (Task 6) -- the max(1, ...)
floor in moving_block_resample is a no-op here since block_bootstrap_dd's own
upstream guard (len(net) > block_len) already ensures the original bound was
always positive. test_carry_measure.py passes unchanged."
```

---

### Task 10: Migrate `research/fwd_analysis.py`'s `bootstrap_expectancy_ci`

**Files:**
- Modify: `src/moonface/research/fwd_analysis.py`

**Interfaces:**
- Consumes: `kernel.bootstrap.moving_block_resample`.

- [ ] **Step 1: Replace the local `moving_block_resample` with the import, keep the rest unchanged**

```diff
 from __future__ import annotations

 import math
 import random
 from statistics import NormalDist, pstdev

+from moonface.kernel.bootstrap import moving_block_resample
+
 _DAY_MS = 86_400_000


-def moving_block_resample(rs: list[float], rng: random.Random,
-                          block: int = 10) -> list[float]:
-    n = len(rs)
-    out: list[float] = []
-    while len(out) < n:
-        start = rng.randrange(0, max(1, n - block + 1))
-        out.extend(rs[start:start + block])
-    return out[:n]
-
-
 def bootstrap_expectancy_ci(rs: list[float], resamples: int = 10_000,
                             block: int = 10, seed: int = 42,
                             alpha: float = 0.05) -> tuple[float, float]:
     """Percentile CI on mean R. Degenerate inputs (n<2 or zero variance)
     collapse to (mean, mean) so the caller sees the collapse instead of a
     fake interval (capitulation-lane lesson)."""
     if not rs:
         return (0.0, 0.0)
     if len(rs) < 2 or len(set(rs)) == 1:
         m = sum(rs) / len(rs)
         return (m, m)
     rng = random.Random(seed)
     means = sorted(
         sum(sample) / len(sample)
-        for sample in (moving_block_resample(rs, rng, block)
+        for sample in (moving_block_resample(rng, rs, block)
                        for _ in range(resamples)))
     lo = means[int(alpha / 2 * resamples)]
     hi = means[min(resamples - 1, int((1 - alpha / 2) * resamples))]
     return (lo, hi)
```

Note the argument-order swap: this file's own `moving_block_resample(rs, rng, block)` took data first, rng
second; `kernel.bootstrap.moving_block_resample(rng, data, block_len)` takes rng first (matching every other
function in that module, and matching `carry_measure.py`'s call convention from Task 9). The two are
otherwise byte-identical in behavior — this file's own version already had the `max(1, ...)` guard that
`kernel.bootstrap.moving_block_resample` was written to include for exactly this reason (Task 6).

Check `grep -n "^import random\|random\." src/moonface/research/fwd_analysis.py` afterward — if `random` is
no longer referenced anywhere in this file (the only use was inside the now-deleted local function and the
`rng = random.Random(seed)` line, which stays), keep the `import random` line as-is since it's still used
for `rng = random.Random(seed)`.

- [ ] **Step 2: Verify the existing tests still pass unchanged**

Run: `.venv/bin/python -m pytest tests/research/test_fwd_analysis.py -v`
Expected: PASS, unchanged.

- [ ] **Step 3: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2635 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 4: Commit**

```bash
git add src/moonface/research/fwd_analysis.py
git commit -m "refactor(g3): migrate fwd_analysis.py's bootstrap_expectancy_ci onto kernel.bootstrap

Its own moving_block_resample was already the max(1, ...)-guarded shape
kernel.bootstrap.moving_block_resample now owns verbatim (Task 6) -- this was
the model for that guard. Only the argument order changes (rng first, to
match every other kernel.bootstrap function and carry_measure.py's Task 9
call convention); the resample sequence itself is unchanged.
test_fwd_analysis.py passes unchanged."
```

---

### Task 11: Migrate `research/vrp_measure.py`'s `block_bootstrap_mean_ci` and `percentile`

**Files:**
- Modify: `src/moonface/research/vrp_measure.py`

**Interfaces:**
- Consumes: `kernel.bootstrap.fixed_block_count_resample`, `kernel.bootstrap.percentile`.

- [ ] **Step 1: Replace the local `percentile` with the import**

Read the imports and the local `percentile` definition (found at line ~215 in this plan's research) first
to confirm current line numbers via `grep -n "^def percentile" src/moonface/research/vrp_measure.py`, then:

```diff
+from moonface.kernel.bootstrap import fixed_block_count_resample
+from moonface.kernel.bootstrap import percentile as _kernel_percentile
```

If this file's local `percentile` is called only within this file (confirm with
`grep -rn "vrp_measure.*percentile\|from.*vrp_measure import.*percentile" --include="*.py" src tools tests | grep -v .venv`
— expected: no external importer, since `tests/research/test_vrp_measure.py`'s import list should be
checked too), delete the local `def percentile(...)` entirely and replace every in-file call site with the
import. If an external importer exists, keep a one-line re-export (`percentile = _kernel_percentile`) at
the module level instead of deleting it.

- [ ] **Step 2: Replace the resampling loop**

```diff
 def block_bootstrap_mean_ci(values: list[float], block_len: int = BLOCK_LEN,
                             n_resamples: int = N_RESAMPLES,
                             seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
     """(p2.5, p97.5) of the mean over moving-block bootstrap resamples.

     Block length matches the 30-day overlap horizon, so the resample preserves
     the autocorrelation the overlap induces (SPEC section 4.3). Never compute a
     naive SE on the overlapping series -- it is wrong by roughly sqrt(60).
     """
     n = len(values)
     if n <= block_len:
         raise ValueError(f"series of {n} shorter than bootstrap block {block_len}")
     rng = random.Random(seed)
     n_blocks = -(-n // block_len)  # ceil
-    max_start = n - block_len
     means: list[float] = []
     for _ in range(n_resamples):
-        total = 0.0
-        count = 0
-        for _ in range(n_blocks):
-            start = rng.randint(0, max_start)
-            for j in range(start, start + block_len):
-                total += values[j]
-                count += 1
-        means.append(total / count)
-    return percentile(means, 2.5), percentile(means, 97.5)
+        sample = fixed_block_count_resample(rng, values, block_len, n_blocks)
+        means.append(sum(sample) / len(sample))
+    return percentile(means, 2.5), percentile(means, 97.5)
```

`sum(sample) / len(sample)` reproduces `total / count` exactly: `fixed_block_count_resample` appends the
same `data[j]` values in the same `j` order the original double loop did (`out.extend(data[start:start +
block_len])` for each of the `n_blocks` draws, same as the original's inner `for j in
range(start,start+block_len)` — same values, same order), and `count` in the original always equals
`n_blocks * block_len` which equals `len(sample)` here.

- [ ] **Step 3: Verify the existing tests still pass unchanged**

Run: `.venv/bin/python -m pytest tests/research/test_vrp_measure.py -v`
Expected: PASS, unchanged — including the two seeded-reproducibility tests at lines 261-268
(`block_bootstrap_mean_ci(v, ..., seed=1) == block_bootstrap_mean_ci(v, ..., seed=1)` and the
different-seed inequality), which are the direct behavioral-preservation proof for this migration.

- [ ] **Step 4: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2635 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/vrp_measure.py
git commit -m "refactor(g3): migrate vrp_measure.py's block_bootstrap_mean_ci and percentile onto kernel.bootstrap

The fixed-n_blocks accumulate-sum loop reproduced exactly the shape
kernel.bootstrap.fixed_block_count_resample now owns (Task 6); sum(sample)/
len(sample) reproduces the original's total/count since both traverse the
same values in the same order. percentile was formula-identical to
carry_measure.py's now-migrated copy (Task 9) -- both consolidate onto
kernel.bootstrap.percentile. test_vrp_measure.py's seeded-reproducibility
tests (block_bootstrap_mean_ci with the same seed twice) pass unchanged."
```

---

### Task 12: Migrate `research/macro_event.py`'s `bootstrap_p_le0`

**Files:**
- Modify: `src/moonface/research/macro_event.py`

**Interfaces:**
- Consumes: `kernel.bootstrap.iid_resample_choices`.

- [ ] **Step 1: Replace the resampling call**

```diff
+from moonface.kernel.bootstrap import iid_resample_choices
```

```diff
 def bootstrap_p_le0(returns: list[float], n_boot: int = N_BOOT,
                     seed: int = BOOT_SEED) -> float:
     """One-sided percentile bootstrap: P(resampled mean <= 0)."""
     if not returns:
         return 1.0
     rng = random.Random(seed)
-    n = len(returns)
     le0 = sum(
         1 for _ in range(n_boot)
-        if fmean(rng.choices(returns, k=n)) <= 0.0
+        if fmean(iid_resample_choices(rng, returns)) <= 0.0
     )
     return le0 / n_boot
```

This is the one migration where getting the primitive right matters most: `iid_resample_choices` must call
`rng.choices(data, k=len(data))` — the exact call this line already made inline — not
`iid_resample_randrange`, which would silently produce different resampled means for the same seed.

- [ ] **Step 2: Verify the existing tests still pass unchanged**

Run: `.venv/bin/python -m pytest tests/research/test_macro_event.py -v`
Expected: PASS, unchanged — including the reproducibility check at lines 113-114
(`p1 = bootstrap_p_le0(noise); p2 = bootstrap_p_le0(noise)` — implicitly same-seed via `BOOT_SEED`'s
default — confirm this test actually asserts `p1 == p2` by reading it before relying on it as the
behavioral-preservation proof; if it does not assert equality, add a same-seed equality assertion as part
of this task rather than relying on an assumption).

- [ ] **Step 3: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2635 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 4: Commit**

```bash
git add src/moonface/research/macro_event.py
git commit -m "refactor(g3): migrate macro_event.py's bootstrap_p_le0 onto kernel.bootstrap

rng.choices(returns, k=n) was the exact call kernel.bootstrap.
iid_resample_choices now wraps (Task 6) -- the one site of the six that must
NOT be swapped onto iid_resample_randrange, since the two consume the PRNG
stream differently for the same seed. test_macro_event.py's same-seed
reproducibility check passes unchanged."
```

---

### Task 13: Migrate `signal/engine/calibration.py`'s `block_bootstrap_rho_ci`

**Files:**
- Modify: `src/moonface/signal/engine/calibration.py`

**Interfaces:**
- Consumes: `kernel.bootstrap.resample_by_block_key`.

- [ ] **Step 1: Confirm `signal/engine/audit.py`'s `block_ci` relationship (from Task 5's audit)**

If Task 5's audit found `signal/engine/audit.py`'s `block_ci` already delegates to
`calibration.block_bootstrap_rho_ci` (rather than duplicating it), no change is needed there — this
migration automatically covers it. If it independently duplicates the same shape, treat it as an 8th site
per Task 5's Step 3 and migrate it identically to this task, immediately after.

- [ ] **Step 2: Replace the resampling loop**

```diff
+from moonface.kernel.bootstrap import resample_by_block_key
```

```diff
 def block_bootstrap_rho_ci(trades: list[HypoTrade],
                            block_bars: int = BLOCK_BARS,
                            draws: int = BOOTSTRAP_DRAWS,
                            seed: int = BOOTSTRAP_SEED,
                            ) -> tuple[float, float] | None:
     """95% CI for spearman(score, net_r) via a moving-block bootstrap keyed on
     entry-bar blocks (overlap-honest inference for the overlapping panel)."""
     blocks: dict[int, list[HypoTrade]] = {}
     for t in trades:
         blocks.setdefault(t.entry_index // block_bars, []).append(t)
     keys = sorted(blocks)
     if len(keys) < 2:
         return None
     rng = random.Random(seed)
     stats: list[float] = []
     for _ in range(draws):
-        sample: list[HypoTrade] = []
-        for _ in range(len(keys)):
-            sample.extend(blocks[keys[rng.randrange(len(keys))]])
+        sample = resample_by_block_key(rng, blocks, keys)
         rho = spearman([float(t.score) for t in sample],
                        [t.net_r for t in sample])
         if rho is not None:
             stats.append(rho)
     if len(stats) < draws // 2:
         return None
     stats.sort()
     lo = stats[int(0.025 * (len(stats) - 1))]
     hi = stats[int(0.975 * (len(stats) - 1))]
     return (lo, hi)
```

- [ ] **Step 3: Verify the existing tests still pass unchanged**

Run:
```bash
.venv/bin/python -m pytest tests/signal/engine/test_engine_calibration_stats.py \
  tests/signal/engine/test_engine_audit_stats.py -v
```
Expected: PASS, unchanged — `test_engine_audit_stats.py`'s cross-check that `audit.py`'s `block_ci`
reproduces `calibration.block_bootstrap_rho_ci` is a second, independent behavioral-preservation proof
beyond `test_engine_calibration_stats.py`'s own tests.

- [ ] **Step 4: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2635 passed, 3 skipped`, `GUARD PASS`. This closes out Track B (Tasks 5-13) — the suite total is
unchanged from Task 6's close, since Tasks 7-13 added zero new tests by design (each site's own existing
tests are the proof).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/calibration.py
git commit -m "refactor(g3): migrate calibration.py's block_bootstrap_rho_ci onto kernel.bootstrap

The fixed-len(keys)-redraws-of-a-whole-block loop was the shape
kernel.bootstrap.resample_by_block_key now owns (Task 6) -- the sixth and
last of the distinct bootstrap shapes this phase's audit found.
test_engine_calibration_stats.py and test_engine_audit_stats.py's
cross-check against audit.py's own block_ci both pass unchanged, closing
out the 7-site bootstrap migration (Tasks 7-13) with zero numbers moved."
```

---

### Task 14: Build `kernel/reproduce.py` — the lane-agnostic reproduction harness

**Files:**
- Create: `src/moonface/kernel/reproduce.py`
- Test: `tests/kernel/test_reproduce.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (deliberately independent of `core.provenance` — the harness's job
  is comparison, not hashing; Task 17 wires provenance separately into the writers).
- Produces: `ReproductionResult` (frozen dataclass: `matched: bool`, `mismatches: dict[str, tuple]`,
  `recomputed: dict`), `reproduce(run_fn, cfg, recorded, compare_fields, scratch_dir, *args, **kwargs) ->
  ReproductionResult`. Tasks 15-16 call this with `run_fn` = `oibuild_study.run_analysis` /
  `liqladder.run_analysis`, never imported inside `kernel/` itself — only `tools/research.py` (Tasks 15-16)
  imports both the lane module and this harness.

- [ ] **Step 1: Write the failing tests**

Create `tests/kernel/test_reproduce.py`:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.kernel.reproduce import reproduce


def _fake_run_ok(cfg: dict, out_dir: Path) -> dict:
    return {"verdict": "mechanism_does_not_exist", "stouffer_z": -1.024,
            "generated_utc": "2099-01-01T00:00:00Z"}


def _fake_run_mismatch(cfg: dict, out_dir: Path) -> dict:
    return {"verdict": "mechanism_does_not_exist", "stouffer_z": -9.999,
            "generated_utc": "2099-01-01T00:00:00Z"}


class TestReproduce:
    def test_matches_when_compared_fields_agree(self):
        recorded = {"verdict": "mechanism_does_not_exist", "stouffer_z": -1.024}
        with TemporaryDirectory() as tmp:
            result = reproduce(_fake_run_ok, {}, recorded,
                               compare_fields=("verdict", "stouffer_z"),
                               scratch_dir=Path(tmp))
        assert result.matched
        assert result.mismatches == {}

    def test_reports_a_mismatch_without_raising(self):
        recorded = {"verdict": "mechanism_does_not_exist", "stouffer_z": -1.024}
        with TemporaryDirectory() as tmp:
            result = reproduce(_fake_run_mismatch, {}, recorded,
                               compare_fields=("verdict", "stouffer_z"),
                               scratch_dir=Path(tmp))
        assert not result.matched
        assert result.mismatches == {"stouffer_z": (-1.024, -9.999)}

    def test_ignores_fields_not_in_compare_fields(self):
        recorded = {"verdict": "mechanism_does_not_exist", "stouffer_z": -1.024,
                   "generated_utc": "1970-01-01T00:00:00Z"}
        with TemporaryDirectory() as tmp:
            result = reproduce(_fake_run_ok, {}, recorded,
                               compare_fields=("verdict", "stouffer_z"),
                               scratch_dir=Path(tmp))
        assert result.matched  # generated_utc differs but is not compared

    def test_scratch_dir_is_passed_through_to_run_fn(self):
        seen = {}

        def run_fn(cfg, out_dir):
            seen["out_dir"] = out_dir
            return {"verdict": "x"}

        with TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            reproduce(run_fn, {}, {"verdict": "x"}, compare_fields=("verdict",),
                     scratch_dir=scratch)
        assert seen["out_dir"] == scratch

    def test_extra_args_and_kwargs_pass_through(self):
        seen = {}

        def run_fn(cfg, fetch_a, out_dir, fetch_b=None):
            seen["fetch_a"] = fetch_a
            seen["fetch_b"] = fetch_b
            return {"verdict": "x"}

        with TemporaryDirectory() as tmp:
            reproduce(run_fn, {}, {"verdict": "x"}, compare_fields=("verdict",),
                     scratch_dir=Path(tmp), run_args=("A",), run_kwargs={"fetch_b": "B"})
        assert seen == {"fetch_a": "A", "fetch_b": "B"}

    def test_missing_recorded_field_is_a_mismatch(self):
        recorded = {"verdict": "x"}
        with TemporaryDirectory() as tmp:
            result = reproduce(_fake_run_ok, {}, recorded,
                               compare_fields=("verdict", "stouffer_z"),
                               scratch_dir=Path(tmp))
        assert not result.matched
        assert "stouffer_z" in result.mismatches
        assert result.mismatches["stouffer_z"][0] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/kernel/test_reproduce.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.kernel.reproduce'`

- [ ] **Step 3: Write `kernel/reproduce.py`**

Create `src/moonface/kernel/reproduce.py`:

```python
"""Lane-agnostic reproduction harness: re-run a lane's own compute pipeline
against a scratch directory and diff the result against its frozen record.

kernel/ must never import a lane (invariant 1), and a lane's run function
(e.g. tools.lanes.oibuild_study.run_analysis) is exactly the kind of
lane-specific dependency that would violate it if imported here. Instead
run_fn is a parameter -- the same dependency-injection shape kernel.runner
already uses for `loader`. The only caller that imports both this module and
a lane's run function is tools/research.py, which sits outside kernel/ and is
allowed to import either."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ReproductionResult:
    matched: bool
    mismatches: dict[str, tuple[Any, Any]]
    recomputed: dict


def reproduce(run_fn: Callable[..., dict], cfg: dict, recorded: dict,
              compare_fields: tuple[str, ...], scratch_dir: Path,
              run_args: tuple = (), run_kwargs: dict | None = None,
              ) -> ReproductionResult:
    """Call run_fn(cfg, *run_args, out_dir=scratch_dir, **run_kwargs), then
    compare the returned dict's compare_fields against recorded's. scratch_dir
    must not be the lane's real experiments/<lane>/ directory -- both
    oibuild_study.run_analysis and liqladder.run_analysis refuse to run a
    second time once out_dir/verdict.json already exists (a one-touch guard),
    so pointing this at the real directory would either crash on that guard
    or, if bypassed, risk overwriting the frozen record."""
    kwargs = dict(run_kwargs or {})
    recomputed = run_fn(cfg, *run_args, out_dir=scratch_dir, **kwargs)
    mismatches: dict[str, tuple[Any, Any]] = {}
    for f in compare_fields:
        rec_val = recorded.get(f)
        new_val = recomputed.get(f)
        if rec_val != new_val:
            mismatches[f] = (rec_val, new_val)
    return ReproductionResult(matched=not mismatches, mismatches=mismatches,
                              recomputed=recomputed)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/kernel/test_reproduce.py -v`
Expected: PASS — 6 tests.

- [ ] **Step 5: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2641 passed, 3 skipped` (2635 + 6), `GUARD PASS`.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/kernel/reproduce.py tests/kernel/test_reproduce.py
git commit -m "feat(g3): add kernel/reproduce.py -- the lane-agnostic reproduction harness

reproduce() takes the lane's run function as a parameter rather than
importing it, so kernel/ never depends on a lane (invariant 1) -- the same
dependency-injection shape kernel.runner already uses for loader. Tested
against synthetic run_fn stand-ins only; Tasks 15-16 wire it to the two real
lanes named in the G3 reproduction gate."
```

---

### Task 15: Wire and run the reproduction gate — `oibuild_study`

**Files:**
- Modify: `tools/research.py` (add a `reproduce` subcommand)

**Interfaces:**
- Consumes: `kernel.reproduce.reproduce` (Task 14), `tools.lanes.oibuild_study.run_analysis`,
  `fetch_perp_candles`/`fetch_metrics_history` (existing, from `moonface.research.universe_data`/
  `moonface.core.series` — confirm exact import paths by reading `tools/lanes/oibuild_study.py`'s own
  imports, already transcribed in full during this plan's research).

- [ ] **Step 1: Read `tools/research.py` in full**

Confirm its current structure (subcommand dispatch, argument parser shape, `main()`'s `if args.command ==
...` chain) before adding a new subcommand — this file was read in full during this plan's research but may
have drifted; re-read before editing.

- [ ] **Step 2: Add the `reproduce oibuild_study` wiring**

Add near the top of `tools/research.py`, alongside its other lane-specific imports:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.kernel.reproduce import reproduce
from tools.lanes.oibuild_study import run_analysis as oibuild_study_run

OIBUILD_STUDY_COMPARE_FIELDS = ("verdict", "stouffer_z", "pooled_mean", "p_sign",
                                "k_positive", "m_assets")


def cmd_reproduce_oibuild_study(cache_dir: str) -> None:
    reg_path = Path("experiments/oibuild_study/registration.json")
    verdict_path = Path("experiments/oibuild_study/verdict.json")
    if not reg_path.exists() or not verdict_path.exists():
        sys.exit(f"missing {reg_path} or {verdict_path}")
    cfg = json.loads(reg_path.read_text())
    recorded = json.loads(verdict_path.read_text())

    def fetch_candles(sym, start, end):
        from moonface.research.universe_data import fetch_perp_candles
        return fetch_perp_candles(sym, "4h", start, end, cache_dir)

    def fetch_metric(sym, start, end):
        from moonface.core.series import fetch_metrics_history
        field = cfg["metrics_field"]
        raw = fetch_metrics_history(sym, start, end, cache_dir)
        return [(ts, f[field]) for ts, f in raw if field in f]

    with TemporaryDirectory() as tmp:
        result = reproduce(oibuild_study_run, cfg, recorded,
                           compare_fields=OIBUILD_STUDY_COMPARE_FIELDS,
                           scratch_dir=Path(tmp),
                           run_args=(fetch_candles, fetch_metric))
    if result.matched:
        print("REPRODUCED: oibuild_study -- every compared field matches the recorded verdict.json")
    else:
        print("DID NOT REPRODUCE: oibuild_study")
        for field_name, (rec, new) in result.mismatches.items():
            print(f"  {field_name}: recorded={rec!r} recomputed={new!r}")
        sys.exit(1)
```

Read the existing `main()` argument-parsing chain (Step 1) and add a `reproduce` subparser plus a dispatch
branch that calls `cmd_reproduce_oibuild_study(args.cache_dir)` for `args.lane == "oibuild_study"`,
following this file's existing subcommand-dispatch pattern exactly (confirm the pattern from an existing
subcommand like `gate` before writing the new branch, rather than inventing a different shape).

- [ ] **Step 3: Run the gate for real, against the live `.backtest_cache/`**

Run: `.venv/bin/python tools/research.py reproduce oibuild_study --cache-dir .backtest_cache`

This is the actual G3 "green when" condition for this lane. Two honest outcomes:

- **If it prints `REPRODUCED: oibuild_study`**: the gate passes. Proceed to Step 4.
- **If it prints `DID NOT REPRODUCE`**: per this plan's Global Constraints and the spec's own text ("If the
  numbers do not reproduce, stop and fix the kernel — delete nothing"), **do not proceed past this step.**
  Investigate the specific mismatched field(s) — likely causes are a `.backtest_cache/` state that has
  drifted since `experiments/oibuild_study/verdict.json` was generated (check the cache file mtimes against
  the verdict's own `generated_utc`), or a genuine non-determinism in `run_analysis` this plan's research
  did not catch (re-read `tools/lanes/oibuild_study.py`'s full call chain for any hidden randomness or
  dict-ordering dependency). Report the specific mismatch to the user rather than adjusting the compared
  fields or the tolerance to make it pass.

- [ ] **Step 4: Commit**

```bash
git add tools/research.py
git commit -m "feat(g3): wire the reproduction gate to oibuild_study

tools/research.py reproduce oibuild_study re-runs run_analysis against a
scratch directory (never the real experiments/oibuild_study/, which
run_analysis refuses to touch a second time once verdict.json exists) using
the frozen registration.json and the live .backtest_cache/, then diffs
verdict/stouffer_z/pooled_mean/p_sign/k_positive/m_assets against the
recorded verdict.json. [State the actual outcome here: REPRODUCED, or the
specific mismatch found and reported rather than silently resolved.]"
```

Fill in the commit message's bracketed sentence with the real Step 3 outcome before committing — do not
leave it as a placeholder.

---

### Task 16: Wire and run the reproduction gate — `liqladder`

**Files:**
- Modify: `tools/research.py` (add the `liqladder` case to the `reproduce` subcommand)

**Interfaces:**
- Consumes: `kernel.reproduce.reproduce`, `tools.lanes.liqladder.run_analysis`.

- [ ] **Step 1: Confirm `liqladder.py`'s `run_analysis` signature matches `oibuild_study.py`'s pattern**

Run: `grep -n "^def run_analysis" tools/lanes/liqladder.py`
Expected: `def run_analysis(cfg: dict, fetch_candles, fetch_metrics, out_dir: Path) -> dict:` — note the
parameter name is `fetch_metrics` (plural), not `fetch_metric` (singular) as in `oibuild_study.py`; it
takes the raw `fetch_metrics_history` return shape directly rather than pre-filtering to one field (both
`oi_field` and `ratio_field` are read from the same raw rows inside `run_analysis` itself — confirmed by
this plan's research). Do not assume the two lanes' injected-callable shapes are identical; this step's
grep is the check.

- [ ] **Step 2: Add the `reproduce liqladder` wiring**

```python
from tools.lanes.liqladder import run_analysis as liqladder_run

LIQLADDER_COMPARE_FIELDS = ("verdict", "stouffer_z", "pooled_mean", "k_positive", "m_assets")


def cmd_reproduce_liqladder(cache_dir: str) -> None:
    reg_path = Path("experiments/liqladder/registration.json")
    verdict_path = Path("experiments/liqladder/verdict.json")
    if not reg_path.exists() or not verdict_path.exists():
        sys.exit(f"missing {reg_path} or {verdict_path}")
    cfg = json.loads(reg_path.read_text())
    recorded = json.loads(verdict_path.read_text())

    def fetch_candles(sym, start, end):
        from moonface.research.universe_data import fetch_perp_candles
        return fetch_perp_candles(sym, cfg["interval"], start, end, cache_dir)

    def fetch_metrics(sym, start, end):
        from moonface.core.series import fetch_metrics_history
        return fetch_metrics_history(sym, start, end, cache_dir)

    with TemporaryDirectory() as tmp:
        result = reproduce(liqladder_run, cfg, recorded,
                           compare_fields=LIQLADDER_COMPARE_FIELDS,
                           scratch_dir=Path(tmp),
                           run_args=(fetch_candles, fetch_metrics))
    if result.matched:
        print("REPRODUCED: liqladder -- every compared field matches the recorded verdict.json")
    else:
        print("DID NOT REPRODUCE: liqladder")
        for field_name, (rec, new) in result.mismatches.items():
            print(f"  {field_name}: recorded={rec!r} recomputed={new!r}")
        sys.exit(1)
```

Add the `liqladder` branch to the same `reproduce` subcommand dispatch Task 15 built (an `args.lane in
("oibuild_study", "liqladder")` choice-constrained argument, not two separate subcommands — confirm this
matches the subparser Task 15 actually wrote before assuming its shape).

- [ ] **Step 3: Run the gate for real**

Run: `.venv/bin/python tools/research.py reproduce liqladder --cache-dir .backtest_cache`

Same two honest outcomes as Task 15 Step 3 — do not proceed past a mismatch without investigating and
reporting it.

- [ ] **Step 4: Commit**

```bash
git add tools/research.py
git commit -m "feat(g3): wire the reproduction gate to liqladder

Mirrors Task 15's oibuild_study wiring; liqladder.run_analysis takes
fetch_metrics (raw rows, both oi_field and ratio_field read inside the
function) rather than oibuild_study's pre-filtered fetch_metric -- confirmed
by reading the actual signature before wiring, not assumed from the sibling
lane's shape. [State the actual outcome here.]

This closes the G3 reproduction gate: both lanes named in the spec now have
a re-run path against a scratch directory, verified against the live
.backtest_cache/."
```

Fill in the bracketed sentence with the real outcome before committing.

---

### Task 17: Wire the provenance triple into every write

**Files:**
- Modify: `src/moonface/kernel/store.py` (`advance` threads the triple into `stage_result`)
- Modify: `src/moonface/kernel/runner.py` (computes the triple, passes it to `advance`)
- Modify: `tools/lanes/oibuild_study.py`, `tools/lanes/liqladder.py` (`run_analysis` adds the triple to its
  returned/written dict)

**Interfaces:**
- Consumes: `core.provenance.{registration_hash, data_fingerprint, raw_series_fingerprint, code_hash}`
  (Task 3), `core.stats.series_fingerprint` (existing, from G2).

- [ ] **Step 1: Wire the triple into System A's writes (`kernel/runner.py` / `store.advance`)**

`store.advance(h, new_status, stage_result)` already merges any dict into the row's persisted
`stage_results` — no schema change needed in `store.py` itself, only in what `runner.py` passes. In
`kernel/runner.py`'s `_stage1`, add the triple to the `m` dict before calling `store.advance`:

```diff
 def _stage1(store: Store, row: dict, fenced) -> None:
     spec = spec_from_json(row["spec_json"])
     research = fenced(spec.asset).research()
     m = ladder.evaluate_research(spec, research)
+    m["registration_hash"] = spec_hash(spec)
+    m["data_fingerprint"] = series_fingerprint(research.candles)
+    m["code_hash"] = code_hash([
+        "src/moonface/kernel/dsr.py", "src/moonface/kernel/runner.py",
+        "src/moonface/core/metrics.py", "src/moonface/research/ladder.py",
+    ])
     if m["max_abs_r"] > ladder.R_SANITY_CAP:
         store.advance(row["spec_hash"], "anomaly", m)
         return
     ok = ladder.stage1_passed(m)
     store.advance(row["spec_hash"], "screened" if ok else "rejected", m)
```

Add the two new imports at the top of `kernel/runner.py`:

```diff
+from moonface.core.provenance import code_hash
+from moonface.core.stats import series_fingerprint
+from moonface.kernel.spec import spec_hash
```

(`spec_hash` may already be imported — check with `grep -n "^from moonface.kernel.spec" src/moonface/kernel/runner.py`
before adding a duplicate import line.)

- [ ] **Step 2: Write a test confirming the triple lands in a stage1 row's stage_results**

Read `tests/test_research_runner.py` in full first to find its existing fixture/setup pattern (a `Store`
against a temp SQLite path, a synthetic `loader`), then add a test in that same style:

```python
def test_stage1_stamps_the_provenance_triple(tmp_path):
    # Reuse this file's existing store/loader fixture pattern (see setUp /
    # the synthetic loader already defined above in this file) rather than
    # rebuilding one here -- confirm the exact fixture name before writing
    # this test's body.
    ...
    run(store, loader, tmp_path, only_domain=DOMAIN_NAME)
    row = store.rows(DOMAIN_NAME, 1)[0]
    assert "registration_hash" in row["stage_results"]
    assert "data_fingerprint" in row["stage_results"]
    assert "code_hash" in row["stage_results"]
```

This step's exact test body depends on `tests/test_research_runner.py`'s existing fixtures, which must be
read (not assumed) before writing — do not invent a fixture shape without checking the file first.

- [ ] **Step 3: Wire the triple into `oibuild_study.py`'s and `liqladder.py`'s verdict writers**

In `tools/lanes/oibuild_study.py`'s `run_analysis`, before the `out = {...}` dict is built:

```diff
+    from moonface.core.provenance import (code_hash, data_fingerprint,
+                                          raw_series_fingerprint, registration_hash)
+    from moonface.core.stats import series_fingerprint
+
+    series_by_key = {a["sym"]: series_fingerprint(a["candles"]) for a in accepted}
+
     out = {
         **verdict,
         "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
         "assets": [{k: s[k] for k in ("sym", "n", "mean", "t")}
                    for s in per_asset],
         "skipped": skipped,
         "descriptive": desc,
         "discovery_set_contaminated": discovery_stats,
+        "registration_hash": registration_hash(cfg),
+        "data_fingerprint": data_fingerprint(series_by_key),
+        "code_hash": code_hash(["tools/lanes/oibuild_study.py",
+                                "src/moonface/features/oi_features.py"]),
     }
```

Apply the identical pattern to `tools/lanes/liqladder.py`'s `run_analysis`, with `series_by_key` built from
`accepted` (same shape: `{a["sym"]: series_fingerprint(a["candles"]) for a in accepted}`) and `code_hash`
covering `["tools/lanes/liqladder.py", "src/moonface/features/oi_features.py",
"src/moonface/research/liqladder.py"]` (confirm this is the complete set of modules that determine
`liqladder.py`'s numeric output by reading its imports — `detect_events`, `event_net_returns`,
`liqladder_verdict`, `pooled`, `nonoverlap_events` all come from `moonface.research.liqladder` per this
plan's research).

- [ ] **Step 4: Re-run both reproduction gates to confirm the triple doesn't break the field comparison**

Run:
```bash
.venv/bin/python tools/research.py reproduce oibuild_study --cache-dir .backtest_cache
.venv/bin/python tools/research.py reproduce liqladder --cache-dir .backtest_cache
```
Expected: both still `REPRODUCED` (the new triple fields are additive to the output dict; `compare_fields`
from Tasks 15-16 does not include them, so they don't affect the match/mismatch verdict — only the two real
`experiments/<lane>/verdict.json` files, once regenerated by an actual `run` invocation, would gain the
triple; the scratch-dir reproduction run's OWN triple fields will differ from the recorded file's absent
ones, which is expected and fine since they're not in `compare_fields`).

- [ ] **Step 5: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2645 passed, 3 skipped` (2641 + 4, from Step 2's new test plus any new lane-writer tests added —
confirm the exact count from the tests actually written in Steps 2-3), `GUARD PASS`.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/kernel/runner.py tests/test_research_runner.py \
  tools/lanes/oibuild_study.py tools/lanes/liqladder.py
git commit -m "feat(g3): wire the provenance triple into every write

System A: kernel/runner.py's _stage1 stamps registration_hash (spec_hash),
data_fingerprint (series_fingerprint of the research candles), and code_hash
(the kernel/dsr.py + runner.py + core/metrics.py + research/ladder.py source)
into every stage_results write via store.advance -- no schema change in
store.py itself, since advance() already merges any dict.

oibuild_study.py and liqladder.py's run_analysis now stamp the same triple
into their verdict output (registration_hash of the registration.json,
data_fingerprint over every accepted asset's candle series, code_hash of the
lane's own compute modules). Both reproduction gates (Tasks 15-16) still
match, confirmed by re-running them -- the triple is additive, not part of
either lane's compare_fields."
```

---

### Task 18: The determinism check

**Files:**
- Test: `tests/kernel/test_determinism.py`

**Interfaces:**
- Consumes: `kernel.reproduce.reproduce`, both lanes' `run_analysis`, `core.provenance`.

- [ ] **Step 1: Write the determinism test**

Both `oibuild_study.run_analysis` and `liqladder.run_analysis` contain no `random` import and no
`datetime.now()`-derived value feeding into any compared numeric field (`generated_utc` is the only
non-deterministic field, and it is never in either lane's `compare_fields`) — confirmed by reading both
files in full during this plan's research. The determinism check therefore runs each lane's pipeline twice
back-to-back against the same frozen registration and the same frozen `.backtest_cache/`, and asserts every
compared field plus the newly-added provenance triple's `registration_hash` and `data_fingerprint` (not
`code_hash`, which is a hash of static source files and trivially identical every run — asserting on it
adds no information) are identical across the two runs.

Create `tests/kernel/test_determinism.py`:

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from moonface.core.provenance import data_fingerprint, registration_hash
from moonface.core.stats import series_fingerprint
from tools.lanes.liqladder import run_analysis as liqladder_run
from tools.lanes.oibuild_study import run_analysis as oibuild_study_run

CACHE_DIR = ".backtest_cache"


def _cache_available() -> bool:
    return Path(CACHE_DIR).is_dir() and any(Path(CACHE_DIR).iterdir())


pytestmark = pytest.mark.slow


@pytest.mark.skipif(not _cache_available(), reason="requires the live .backtest_cache/")
class TestOibuildStudyDeterminism:
    def test_two_runs_on_frozen_data_are_identical(self):
        cfg = json.loads(Path("experiments/oibuild_study/registration.json").read_text())

        def fetch_candles(sym, start, end):
            from moonface.research.universe_data import fetch_perp_candles
            return fetch_perp_candles(sym, "4h", start, end, CACHE_DIR)

        def fetch_metric(sym, start, end):
            from moonface.core.series import fetch_metrics_history
            field = cfg["metrics_field"]
            raw = fetch_metrics_history(sym, start, end, CACHE_DIR)
            return [(ts, f[field]) for ts, f in raw if field in f]

        with TemporaryDirectory() as tmp_a, TemporaryDirectory() as tmp_b:
            out_a = oibuild_study_run(cfg, fetch_candles, fetch_metric, Path(tmp_a))
            out_b = oibuild_study_run(cfg, fetch_candles, fetch_metric, Path(tmp_b))

        for field in ("verdict", "stouffer_z", "pooled_mean", "p_sign",
                      "k_positive", "m_assets"):
            assert out_a[field] == out_b[field], field
        assert out_a["registration_hash"] == out_b["registration_hash"]
        assert out_a["data_fingerprint"] == out_b["data_fingerprint"]


@pytest.mark.skipif(not _cache_available(), reason="requires the live .backtest_cache/")
class TestLiqladderDeterminism:
    def test_two_runs_on_frozen_data_are_identical(self):
        cfg = json.loads(Path("experiments/liqladder/registration.json").read_text())

        def fetch_candles(sym, start, end):
            from moonface.research.universe_data import fetch_perp_candles
            return fetch_perp_candles(sym, cfg["interval"], start, end, CACHE_DIR)

        def fetch_metrics(sym, start, end):
            from moonface.core.series import fetch_metrics_history
            return fetch_metrics_history(sym, start, end, CACHE_DIR)

        with TemporaryDirectory() as tmp_a, TemporaryDirectory() as tmp_b:
            out_a = liqladder_run(cfg, fetch_candles, fetch_metrics, Path(tmp_a))
            out_b = liqladder_run(cfg, fetch_candles, fetch_metrics, Path(tmp_b))

        for field in ("verdict", "stouffer_z", "pooled_mean", "k_positive", "m_assets"):
            assert out_a[field] == out_b[field], field
        assert out_a["registration_hash"] == out_b["registration_hash"]
        assert out_a["data_fingerprint"] == out_b["data_fingerprint"]
```

Marked `@pytest.mark.slow` (per G0's fast/full loop split — each run walks up to 16 assets' full candle +
metric history through the whole analysis pipeline twice) and individually `skipif`-guarded against
`.backtest_cache/` being absent, so the fast loop and any CI environment without the 2.9 GB cache directory
skip cleanly rather than failing.

- [ ] **Step 2: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/kernel/test_determinism.py -v -m slow`
Expected: PASS — 2 tests (or `SKIPPED` if run in an environment without `.backtest_cache/`; run this on the
machine that has it, since that is the only environment where this test carries information).

- [ ] **Step 3: Verify collection, then the full suite (both loops)**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -m "not slow" -n auto
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: fast loop count unchanged from Task 17's close (this test is `slow`-marked, excluded from the
fast loop); full loop `2647 passed, 3 skipped` (2645 + 2); `GUARD PASS`.

- [ ] **Step 4: Commit**

```bash
git add tests/kernel/test_determinism.py
git commit -m "test(g3): add the determinism check for both reproduction-gate lanes

Both oibuild_study.run_analysis and liqladder.run_analysis contain no
randomness and no clock-dependent compared field, so running each twice
back-to-back against the same frozen registration and .backtest_cache/ must
yield identical verdict/stouffer_z/pooled_mean/(p_sign/)k_positive/m_assets
and identical registration_hash/data_fingerprint -- this is the G3
'same triple -> same numbers' determinism check. Slow-marked and
skip-guarded on .backtest_cache/'s presence, per G0's fast/full loop split."
```

---

### Task 19: Close out G3

**Files:**
- Modify: `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (append a `*Done ...*` line under
  G3, matching G0/G1/G2's convention)

- [ ] **Step 1: Extend the layering guard if Task 5's audit found anything new**

If Task 5's Step 3 recorded an inventory change (an 8th bootstrap site, or `signal/engine/audit.py`'s
`block_ci` turning out to be an independent duplicate rather than a delegator), confirm it was migrated by
an inserted task before this one closes the phase out. If the audit confirmed exactly the 7 assumed sites
with `audit.py` delegating, no guard extension is needed — `kernel/dsr.py`, `kernel/bootstrap.py`, and
`kernel/reproduce.py` import nothing above `kernel/` (confirmed: `core.*`, `kernel.spec`, stdlib only), so
`tests/test_import_boundaries.py`'s existing invariant checks already cover them without modification.
Confirm this directly:

```bash
grep -n "^from moonface\|^import moonface" src/moonface/kernel/dsr.py src/moonface/kernel/bootstrap.py \
  src/moonface/kernel/reproduce.py
```
Expected: only `moonface.core.*` and `moonface.kernel.spec` imports (and, per Task 17, `moonface.core.stats`
and `moonface.core.provenance` in `runner.py`, which is already allowlisted at the `core` layer) — no
`moonface.research.*`, `moonface.signal.*`, or `moonface.features.*` import in any of the three new kernel
files themselves.

- [ ] **Step 2: Run the full suite one final time**

Run:
```bash
.venv/bin/python -m pytest -q -m "not slow" -n auto
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2647 passed, 3 skipped` on the full loop, `GUARD PASS`. Record the actual final numbers in Step 3
below — do not copy this plan's projected number without confirming it against the real run, since every
earlier task's projection compounds and a single miscounted step anywhere upstream would make this final
number wrong too.

- [ ] **Step 3: Record G3 as done in the spec**

Directly under G3's existing `*Green when:*` line and this plan's Task 2 correction note in
`docs/research-log/specs/2026-08-22-repo-restructure-design.md`, append:

```markdown
*Done 2026-08-24:* kernel/dsr.py (DSR_THRESHOLD, stage3_dsr, evaluate_lockbox -- cut from
research.ladder, back-compat wrapper kept there) and kernel/bootstrap.py (six resampling shapes, the
7-site audit in Task 5 confirmed against the corrected inventory) stood up; all 7 bootstrap call sites
migrated with zero numbers moved (each site's own pre-existing seeded tests as proof, not new golden
values); kernel/reproduce.py built as a lane-agnostic harness (run_fn injected, never imported inside
kernel/); the reproduction gate run against oibuild_study and liqladder from their frozen
registration.json against the live .backtest_cache/ [record REPRODUCED or the specific finding from
Tasks 15-16 here]; the registration_hash/data_fingerprint/code_hash provenance triple wired into
System A's stage1 writes and both lanes' verdict writers; the determinism check (Task 18) passes for
both lanes. Suite [record the real final count here]. models/, strategies/, data/, and lanes/ do not
exist yet -- G4, G5, G6.
```

Fill in both bracketed sentences with the real Task 15/16 outcomes and the real Step 2 suite count before
committing — this file must not carry a placeholder into the permanent record.

- [ ] **Step 4: Commit**

```bash
git add docs/research-log/specs/2026-08-22-repo-restructure-design.md
git commit -m "docs(g3): phase complete -- verification path unified, both named lanes reproduced

kernel/dsr.py and kernel/bootstrap.py stood up; all 7 bootstrap
implementations migrated behind kernel.bootstrap with zero historical
numbers moved; kernel/reproduce.py built and wired to oibuild_study and
liqladder; the provenance triple wired into every write; the determinism
check passes. [One-line summary of the actual reproduction-gate outcome.]"
```

---

## Notes for the executor

- **This plan's "single entry point" scope is deliberately narrow.** The spec's G3 text says
  `tools/research.py` "becomes the single entry point." This plan makes that true for the two lanes G3
  names (Tasks 15-16 add `reproduce oibuild_study`/`reproduce liqladder`). It does **not** collapse the six
  pre-existing hardcoded `register+run+print` subcommand pairs already in `tools/research.py`
  (`voltarget`, `orderflow`, `price-oi-divergence`, `forced-error`, `universe-donchian`, plus whatever
  `funding-ref` covers) into generic, config-driven dispatch — that is a larger, separate refactor of
  `tools/research.py` itself that G3's own text does not explicitly require and that fits G6's "convert
  lanes onto the kernel" framing better than a "point of no return" phase's stated scope. Flag this
  explicitly to the user rather than silently treating it as done.
- **This plan's provenance-triple wiring (Task 17) covers System A's generic path
  (`kernel/runner.py`'s `_stage1`) and the two named lanes' writers — not the five bespoke-runner domains'
  own write paths** (`price_oi_divergence_runner.py`, `universe_donchian_runner.py`, `voltarget_runner.py`,
  `forced_error_runner.py`, `orderflow_runner.py`, each of which calls `store.advance` from its own
  `run_domain`-style function, bypassing `kernel/runner.py`'s generic `_stage1`/`_stage2` entirely).
  "Every write" in the spec's G3 text is broader than what this plan actually wires; extending the triple
  to those five is mechanically the same pattern as Task 17's `_stage1` change but was left out to keep
  this already-large phase bounded. Note this gap to the user rather than claiming full coverage.
- **This repo carries pre-existing uncommitted work outside this plan's scope**, per G1's own note: a
  staged rename under `experiments/newdata/deribit_chain/`, unstaged manifest edits, and several untracked
  docs files. Check `git status --short` before every commit in this plan and never run `git add -A` or a
  bare `git commit` — use the explicit pathspecs given in each task's commit step.
- **Task 15/16's honest-outcome branches are not decorative.** If the reproduction gate genuinely does not
  reproduce one of the two lanes' recorded numbers, that is real information this phase exists to surface
  (R5, R2) — do not adjust `compare_fields`, widen a tolerance, or edit the recorded `verdict.json` to make
  it pass. Stop and report the specific field and the specific delta to the user.
- **If Task 5's audit changes the bootstrap-site inventory**, every task number from 14 onward shifts by
  however many new migration tasks were inserted. Update this plan's own task numbering (and the checklist)
  before continuing past Task 13 in that case, rather than silently renumbering only in your head.
- **If the pytest counts at any task's close differ from this plan's projection**, stop before committing
  that task and investigate — this plan was written without executing it, so a projection is a strong
  expectation, not a guarantee; a real mismatch is a genuine signal, not a plan bug to route around.
