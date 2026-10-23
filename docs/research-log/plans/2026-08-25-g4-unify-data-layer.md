# G4 — Unify the Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate every fetch/cache implementation in the repo into one `data/` package (invariant 3:
"no lane fetches or caches on its own"), give the two live cron collectors and two dormant forward
collectors a real home in `collect/` per its own G2-written scaffold docstring, and re-run the G3
reproduction gate afterward to prove the move changed no historical number (risk R6) — without deleting a
byte of `research/`'s lane code (invariant 5) and without converting a single lane onto the kernel (that is
G6).

**Architecture:** Two invariant-driven tracks, forced by a fact this plan's own research found:
`tests/test_import_boundaries.py::test_core_imports_nothing_above_it` already forbids `core` from importing
`moonface.data` (it was written at G2, in anticipation of this phase). That means the three fetch/cache
modules currently living in `core/` (`core/data.py`, `core/series.py`, and `core/bundle.py`'s `load_bundle`
function) cannot leave a re-export shim behind at their old path the way G3's `research/ladder.py` did for
`kernel.dsr` — a shim would make `core` import `data`, which the test already forbids. **Track A** (Tasks
3-6) therefore relocates those three out of `core/` and directly rewrites every one of their ~60-70 call
sites (mechanical import-line edits, grep-verified) — the DSR/lockbox playbook does not apply here.
**Track B** (Tasks 7-12) relocates the ten fetch/cache modules currently living in `research/` (universe
data, aggtrades, orderbook depth, DVOL, FRED, Vision-archive minute klines): `research/` sits *above*
`data/` in the target layering with no test forbidding the dependency, so a thin re-export shim at the old
path is both safe and correct here — it is what keeps this phase from having to touch ~150 lane-script
importers that G6 will convert one at a time anyway. **Track C** (Tasks 13-16) gives the four "live
collector" domains (`deribit_chain`, `liquidation`, `bybit_liquidation`, `bybit_positioning`) real homes in
`collect/`, replacing the empty G2 scaffold; two of the four are the live cron paths (hard constraint §5.1)
and get a hand-run + row-count check after their commit, exactly like G3's Task 1 pattern. Track D (Tasks
17-19) closes the phase: an import-boundary test extension, the G3 reproduction-gate re-run (risk R6), and
the close-out commit.

**Tech Stack:** Python 3.11+ stdlib only (`csv`, `json`, `pathlib`, `urllib.request`, `zipfile`). No new
dependencies. GitNexus (`mcp__gitnexus__*` / `.gitnexus/run.cjs`) for blast-radius confirmation before each
relocation and `detect_changes` after, per this repo's `CLAUDE.md`.

**Spec:** `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (phase G4 in §4; target layout §3;
invariants 1 and 3 in §2; hard constraints §5; risk R6 in §6)

## Global Constraints

- **Invariant 1: dependency direction is one-way** — `core ← data ← features ← {models, kernel}`,
  `collect` an independent branch off `core`+`data`. Concretely: `data/` may import `core/` and nothing
  else in this repo; `collect/` may import `core/` and `data/` and nothing else. `core/` must import
  neither `data/` nor `collect/` — already enforced by `tests/test_import_boundaries.py::
  test_core_imports_nothing_above_it`, which is *why* Track A cannot use a back-compat shim (see
  Architecture above).
- **Invariant 3: after G4 no lane fetches or caches on its own.** Green-when for this whole phase: every
  network `urlopen`/`ccxt` call and every CSV cache read/write in `src/` lives under `data/` or `collect/`.
  Verified per task by re-running `grep -rln "urlopen\|urllib.request\|import ccxt" --include="*.py" src
  tools | grep -v .venv` against a maintained exclusion list (this plan's Task 2 audit).
- **Invariant 5: no lane code is deleted until its recorded runs are re-derivable without it.** This phase
  moves and re-exports; it deletes no lane file, no test, no recorded run, no `experiments/registry/`
  content.
- **Two collectors are live**, paths frozen (hard constraint §5.1): `tools/liquidation_collect.py` and
  `tools/deribit_chain_collect.py`, cron every minute. Tasks 13 and 14 touch their imports — the only two
  tasks in this phase that do — and each is followed by a manual `collect`/`status` run plus a row-count
  check against the Task 1 snapshot, per the same pattern G3's Task 1 used for its own collector refresh.
  `.venv/bin/python tools/ops/phase_guard.py check` runs at the end of every task.
- **`.backtest_cache/` and `cache/` are frozen until G6** (hard constraint §5.2). Every relocation in this
  plan moves *code*, never touches a byte inside either cache directory — the cache file-naming functions
  (`OhlcvCache.path`, `FundingCache.path`, `_cache_path` in each module) move verbatim, so every existing
  cache file is still found at the same path by the same logic after its owning code moves.
- **The monkeypatch-by-module-alias gotcha, found in this plan's own research:** a handful of tests do
  `import moonface.core.bundle as bundle_mod` (or similar) then `monkeypatch.setattr(bundle_mod,
  "fetch_history", ...)` — this only works because the *target* module (`core/bundle.py`, in that example)
  imports `fetch_history` at module level and calls it unqualified. When a function moves to `data/`, any
  test patching it this way must update BOTH the `import ... as mod` line AND, if the call site's own
  internal unqualified reference also moved, nothing else — but if only the *test's* patch target needs
  correcting, do exactly that and no more. `patch("tools.research.load_bundle", ...)`-style calls that name
  the *using* module (not the definition module) never need changing. Task 6 hits this concretely; check
  for the same pattern (`import moonface\.(core|research)\.\S+ as \w+` followed by `monkeypatch.setattr` on
  that alias) before treating any other test file's move as a pure `git mv`.
- **A relocated module's own test file moves with it** (`git mv`, not a copy) into `tests/data/` or
  `tests/collect/`, importing the new path directly — the shim exists for external consumers, not as the
  module's primary test coverage. `tests/data/` and `tests/collect/` do not exist yet; create them with an
  empty `__init__.py`-free `conftest.py`-free directory (this repo's existing `tests/core/`, `tests/kernel/`
  subdirectories have no `__init__.py` either — confirm with `ls tests/core/__init__.py` before assuming
  otherwise, and mirror whatever that check shows).
- **Baseline to preserve, confirmed fresh immediately before this plan was written:** `2652 passed, 3
  skipped` (`.venv/bin/python -m pytest -q -n auto`, 320s). Fast loop:
  `.venv/bin/python -m pytest -q -m "not slow" -n auto`. Each task states its expected new count; a pure
  relocation task changes the count by 0 (tests move, they don't multiply) — only Task 3 (new `data/http.py`
  tests) and Task 17 (new boundary-test cases) add tests.
- **Commit style:** lowercase conventional prefix with scope `g4`: `refactor(g4):`, `feat(g4):`,
  `test(g4):`, `docs(g4):`, `chore(g4):`. **Never** include `Co-Authored-By` or any AI-attribution trailer.
- **Python interpreter:** `.venv/bin/python`. **`git mv` for every move**, never delete-then-create.
- **After any task touching imports, before committing:** run `.venv/bin/python -c "import moonface"` and
  `.venv/bin/python -m pytest --collect-only -q | tail -3` — a collection error is the fastest signal an
  import path was missed.
- **No number that has ever been recorded may silently change.** Task 18 (the G3 reproduction-gate re-run)
  is this phase's proof: `oibuild_study` must still reproduce exactly as at G3's close, and `liqladder`
  must still fail to reproduce in exactly the same six compared fields, for exactly the same
  already-recorded reason (the pre-G3 cache-mutation incident) — not a new, different divergence introduced
  by this phase's own file moves.

---

### Task 1: Pre-flight — refresh the collector snapshot, confirm the real baseline

**Files:**
- Modify: `tools/ops/phase_guard_baseline.json` (row-floor refresh only)

**Interfaces:**
- Consumes: `tools/ops/phase_guard.py` (`capture`/`check`) from G0, unchanged since G3.

- [ ] **Step 1: Capture the current baseline**

Run:
```bash
.venv/bin/python tools/ops/phase_guard.py capture
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `captured 2 row floors`, then `GUARD PASS` with both row counts comfortably above G3's close
snapshot. If either count is at or below the prior baseline, **stop** — the collector may have stalled,
which outranks this phase.

- [ ] **Step 2: Confirm the real pytest baseline**

Run: `.venv/bin/python -m pytest -q -n auto`
Expected: `2652 passed, 3 skipped`. If this differs, stop before continuing — every later task's expected
count is computed from this number.

- [ ] **Step 3: Commit**

```bash
git add tools/ops/phase_guard_baseline.json
git commit -m "chore(g4): refresh the collector row-floor snapshot before the data-layer unification

G4 is the first phase since G3 to touch the two live collectors' import
paths (Tasks 13-14). Re-captures both row floors from the live baseline so
a shrink during either task is caught against today's count, not G3's
now-stale one."
```

---

### Task 2: Audit — correct the spec's G4 module inventory against the code

The spec's §4 G4 paragraph lists what it absorbs: "universe_data (98 importers), aggtrades_data,
orderbook_features' loader, newdata, exogenous/*, eventtime/vision_klines, forced_flow/coinm_archive,
multifamily_loader, regime_{selector,overlay}/data, foundation/{series,bundle} loaders." Reading every
module this plan's own research found four corrections, following this repo's own convention (G3 Tasks 2
and 5) of correcting a stale spec measurement in place rather than silently working around it.

**Files:**
- Modify: `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (append a correction note under
  the G4 section)

- [ ] **Step 1: Re-run the importer-count greps and record the corrected inventory**

Run (each confirmed during this plan's research; re-run to catch drift since):
```bash
grep -rl "universe_data" --include="*.py" src tools tests | grep -v __pycache__ | wc -l   # 100, not 98
grep -rl "from moonface.core.bundle import\|moonface\.core\.bundle" --include="*.py" src tools tests | grep -v __pycache__ | wc -l  # 103 total; only 16 files import load_bundle directly (Task 6)
grep -rln "load_bundle" --include="*.py" src tools tests | grep -v __pycache__ | wc -l    # 25
```

- [ ] **Step 2: Record the four corrections**

Append under the G4 section of `docs/research-log/specs/2026-08-22-repo-restructure-design.md`:

```markdown
*Correction 2026-08-25 (pre-implementation):* four corrections to this section's module list, found while
researching the implementation plan:

1. `foundation/{series,bundle}` (now `core/{series,bundle}` after G2's rename) cannot leave a back-compat
   re-export shim at the old path the way G3's `research/ladder.py` did for `kernel.dsr` --
   `tests/test_import_boundaries.py::test_core_imports_nothing_above_it` already forbids `core` from
   importing `moonface.data` (written at G2, in anticipation of this phase). `core/data.py` and
   `core/series.py` relocate wholesale with every call site rewritten directly (no shim); `core/bundle.py`
   splits -- `DataBundle`/`align_feature`/`_check_coverage`/`FEATURE_COVERAGE_MIN` stay in `core/bundle.py`
   as pure types (matching the spec's own description of `core/` as holding "primitives"; 78 of 103
   importers use only these and are untouched), while `load_bundle` (the one function that actually calls
   the fetch layer) moves to `data/bundle.py` with its 25 importers rewritten directly.
2. `research/newdata.py` is not a fetch/cache module -- it is the readiness-gate *reader*
   (`load_manifest`/`assess_manifest`), consumed by `tools/collect/newdata.py`. It performs no network
   fetch and owns no cache; it stays in `research/` untouched by this phase.
3. `research/regime_selector/data.py` and `research/regime_overlay/data.py` are not independent fetch/cache
   implementations -- each is a 14-17 line pass-through (`load_macro`/`load_btc` calling
   `exogenous.fred_data.fetch_fred_series` and `universe_data.fetch_perp_candles`/`fetch_funding_rates`
   directly). They need only their own three import lines updated to the new `data/` paths (folded into
   Tasks 7 and 11), not a dedicated migration task.
4. `research/forced_flow/coinm_archive.py` (a strict loader over a *frozen*, already-downloaded Binance
   Vision COIN-M archive -- no live fetch, no cache write, the archive window is hard-coded
   2023-06-25..2024-10-14) and `tools/collect/{carry_measure_fetch_spot,vrp_fetch_dvol}.py` (one-time,
   already-executed, human-gated scripts for the FROZEN `carry_measure` and `vrp_measure` lanes -- per
   memory, both lanes closed/frozen months before this phase) are explicitly OUT OF SCOPE: none of the
   three performs a repeatable live fetch or owns an ongoing cache in the sense invariant 3 targets, and
   `forced_flow` is itself terminal (COIN-M KILL, 2026-07-14). Moving them would touch closed-lane code for
   no invariant-3 benefit -- left exactly where they are, per invariant 5.
```

- [ ] **Step 3: Commit**

```bash
git add docs/research-log/specs/2026-08-22-repo-restructure-design.md
git commit -m "docs(g4): correct the spec's G4 module inventory against the code

core/bundle.py splits rather than fully relocating (its own boundary test
forbids a back-compat shim); newdata.py, regime_selector/overlay's data.py,
forced_flow/coinm_archive.py, and the two one-time frozen-lane collect
scripts are out of scope. Corrected in place per this repo's established
convention (mirrors G3 Tasks 2 and 5), not silently worked around."
```

---

### Task 3: Build `data/http.py` — extract the shared `retrying` HTTP wrapper

`research/universe_data.py` defines `retrying(get, attempts=4, sleep=None)`, a generic transient-failure
retry wrapper (retries `URLError`/`OSError`/`TimeoutError`, re-raises `HTTPError` immediately since an HTTP
error response is a real answer, not a transport failure). `features/orderbook_features.py` already imports
it from `universe_data` for its own `_get_bytes`. Both this call site and the eventual `data/universe.py`
(Task 7) and `data/orderbook.py` (Task 8) need it, so it gets a shared home *before* either of those tasks,
avoiding a `data/orderbook.py -> data/universe.py` cross-import that would otherwise be the only
inter-domain dependency inside `data/`.

**Files:**
- Create: `src/moonface/data/http.py`
- Test: `tests/data/test_http.py`
- Modify: `src/moonface/research/universe_data.py` (import `retrying` from the new module instead of
  defining it)
- Modify: `src/moonface/features/orderbook_features.py` (import `retrying` from the new module instead of
  `universe_data`)

**Interfaces:**
- Consumes: nothing (stdlib `urllib.error`, `time` only).
- Produces: `moonface.data.http.retrying(get, attempts=4, sleep=None) -> Callable[[str], Any]`. Tasks 7
  and 8 import it from here; Task 2's shim-writing convention does not apply (this function never had
  external importers other than the two updated in this task).

- [ ] **Step 1: Confirm no other importer of `retrying`**

Run: `grep -rln "\bretrying\b" --include="*.py" src tools tests | grep -v __pycache__`
Expected: `src/moonface/research/universe_data.py` (definition), `src/moonface/features/orderbook_features.py`
(the one external importer). If a third file appears, add it to Step 3/4 below.

- [ ] **Step 2: Write the failing tests**

Create `tests/data/test_http.py`:

```python
import urllib.error

from moonface.data.http import retrying


def test_returns_the_wrapped_result_on_success():
    wrapped = retrying(lambda url: f"ok:{url}")
    assert wrapped("http://x") == "ok:http://x"


def test_retries_on_transient_url_error_then_succeeds():
    calls = []

    def flaky(url):
        calls.append(url)
        if len(calls) < 3:
            raise urllib.error.URLError("boom")
        return "recovered"

    wrapped = retrying(flaky, attempts=4, sleep=lambda _: None)
    assert wrapped("http://x") == "recovered"
    assert len(calls) == 3


def test_reraises_after_exhausting_attempts():
    def always_fails(url):
        raise urllib.error.URLError("boom")

    wrapped = retrying(always_fails, attempts=2, sleep=lambda _: None)
    try:
        wrapped("http://x")
        assert False, "expected URLError"
    except urllib.error.URLError:
        pass


def test_http_error_is_not_retried():
    calls = []

    def bad_response(url):
        calls.append(url)
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)

    wrapped = retrying(bad_response, attempts=4, sleep=lambda _: None)
    try:
        wrapped("http://x")
        assert False, "expected HTTPError"
    except urllib.error.HTTPError:
        pass
    assert len(calls) == 1  # no retry -- a served response, not a transport failure
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/data/test_http.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.data'`

- [ ] **Step 4: Create `data/__init__.py` and `data/http.py`**

Create `src/moonface/data/__init__.py`:
```python
"""One access layer: OHLCV, perp candles, funding, OI/positioning, orderbook
depth, options/DVOL, macro, aggregate trades, and Vision-archive minute
klines -- each domain in its own module, all under one cache-directory
convention. See design spec section 3, phase G4."""
```

Create `src/moonface/data/http.py`:
```python
"""Shared HTTP-retry wrapper for every data/ fetcher that hits a raw URL.

Moved out of research.universe_data at G4 -- data/universe.py and
data/orderbook.py both need it, and this is a data/-internal utility with no
domain of its own, not one more file each domain would otherwise duplicate."""
from __future__ import annotations

import time
import urllib.error
from typing import Any, Callable


def retrying(get: Callable[[str], Any], attempts: int = 4,
            sleep: Callable[[float], None] | None = None) -> Callable[[str], Any]:
    """Wrap a get(url) callable with retries on transient network failures
    (URLError covers timeouts/handshakes/resets; OSError the rest). HTTP
    error responses pass through -- the callers interpret those."""
    do_sleep = time.sleep if sleep is None else sleep

    def wrapped(url: str):
        for attempt in range(attempts):
            try:
                return get(url)
            except urllib.error.HTTPError:
                raise  # a served response, not a transient transport failure
            except (urllib.error.URLError, OSError, TimeoutError):
                if attempt == attempts - 1:
                    raise
                do_sleep(2.0 * (attempt + 1))
    return wrapped
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/data/test_http.py -v`
Expected: PASS — 4 tests.

- [ ] **Step 6: Point the two existing definitions/importers at the new module**

In `src/moonface/research/universe_data.py`, replace the `retrying` function definition (currently right
after the `_PERP_RE` constant) with an import, and delete the old `def retrying(...)` body entirely:
```diff
 from dataclasses import dataclass
 from pathlib import Path
+
+from moonface.data.http import retrying
```

In `src/moonface/features/orderbook_features.py`:
```diff
-from moonface.research.universe_data import retrying
+from moonface.data.http import retrying
```

- [ ] **Step 7: Verify no regression in the two files' existing tests**

Run: `.venv/bin/python -m pytest tests/research/test_universe_data.py tests/features/test_bookdepth_data.py -v`
Expected: PASS, every test unchanged.

- [ ] **Step 8: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped` (2652 + 4), `GUARD PASS`.

- [ ] **Step 9: Commit**

```bash
git add src/moonface/data/__init__.py src/moonface/data/http.py tests/data/test_http.py \
  src/moonface/research/universe_data.py src/moonface/features/orderbook_features.py
git commit -m "feat(g4): add data/http.py -- the shared retrying HTTP wrapper, moved out of universe_data

Both data/universe.py (Task 7) and data/orderbook.py (Task 8) need this
generic transient-failure retry wrapper. Extracted first so neither later
task creates a data/orderbook.py -> data/universe.py cross-import for a
utility that belongs to neither domain. universe_data.py and
orderbook_features.py now both import it from here; no external importer of
retrying existed beyond these two (confirmed by grep before this move)."
```

---

### Task 4: Relocate `core/data.py` → `data/ohlcv.py`

The first Track A move: `OhlcvCache`, `fetch_history`, `TIMEFRAME_MS`, `TF_MS`, `paginate_ranges`,
`align_to_h1` all perform or support a network fetch/cache — `core/` cannot hold them once `data/` exists
(§ Global Constraints, invariant 1). This is a pure `git mv` — file content is unchanged; only the ~28
importers' import lines change, mechanically.

**Files:**
- Move: `src/moonface/core/data.py` → `src/moonface/data/ohlcv.py`
- Move: `tests/core/test_backtest_data.py` → `tests/data/test_ohlcv.py`
- Modify: every file listed in Step 2 (import-line rewrite only)

**Interfaces:**
- Consumes: `moonface.core.models.Candle` (unchanged import, `core` stays below `data`).
- Produces: `moonface.data.ohlcv.{OhlcvCache, fetch_history, TIMEFRAME_MS, TF_MS, paginate_ranges,
  align_to_h1}` — same names, new module path. Task 6 (`data/bundle.py`) and Task 18's reproduction-gate
  re-run both depend on this path.

- [ ] **Step 1: `git mv` the module and its test**

```bash
git mv src/moonface/core/data.py src/moonface/data/ohlcv.py
git mv tests/core/test_backtest_data.py tests/data/test_ohlcv.py
```

- [ ] **Step 2: Rewrite every importer's import line**

Run this to find every remaining reference after the move:
```bash
grep -rln "moonface\.core\.data\b" --include="*.py" src tools tests | grep -v __pycache__
```
For each hit, replace `moonface.core.data` with `moonface.data.ohlcv` in that file's import line(s) —
`from moonface.core.data import ...`, `import moonface.core.data as ...`, and any `from moonface.core
import data` all become the `moonface.data.ohlcv` equivalent. This plan's research found these exact sites
(re-confirm the list with the grep above before editing, since it may have drifted):

`src/moonface/core/bundle.py` (module-level `from moonface.core.data import OhlcvCache, fetch_history` —
Task 6 further edits this file, but fix this line now), `src/moonface/kernel/reproduce.py` (a lazy import
inside `offline_fetch_perp_candles`), `src/moonface/research/universe_data.py` (its own `fetch_perp_candles`
imports `Candle` from `core.models`, not `core.data` — confirm no false hit), plus every file the grep
above actually returns — expect roughly 28 files including `tests/core/test_metrics_data.py` (a
module-alias import, see Task 6's gotcha note if this file also touches `load_bundle`), `tools/` engine and
lane scripts, and several `tests/` files exercising `OhlcvCache` directly.

- [ ] **Step 3: Update `data/ohlcv.py`'s own module docstring reference (if any) and confirm no self-import**

`core/data.py` had no module docstring; none to update. Confirm the moved file compiles standalone:
`.venv/bin/python -c "import moonface.data.ohlcv"`.

- [ ] **Step 4: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped` (unchanged from Task 3 — a relocation moves tests, it doesn't add them),
`GUARD PASS`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(g4): relocate core/data.py to data/ohlcv.py

OhlcvCache and fetch_history perform a live ccxt fetch and own a CSV cache
-- core/ cannot hold them once data/ exists (test_core_imports_nothing_above_it
already forbids the reverse dependency this would require for a back-compat
shim, so every importer's import line is rewritten directly instead; no
shim left behind). Pure git mv: file content unchanged, ~28 call sites'
import paths updated mechanically, zero test count change."
```

---

### Task 5: Relocate `core/series.py` → `data/series.py`

`FundingCache`, `fetch_funding_history`, `align_funding`, `align_basis`, `METRICS_FIELDS`,
`fetch_metrics_history`, `align_metric`, `parse_metrics_csv`, plus the private `_cache_path`/`_read_cache`/
`_write_cache` helpers `kernel/reproduce.py` already reaches into. Kept as **one file** (not split into
funding/metrics submodules) — several tests import these private helpers directly
(`tests/core/test_metrics_data.py`, `kernel/reproduce.py`'s lazy import), and a same-file move preserves
every one of those references exactly; a split would require re-deriving which private helper belongs to
which half without full visibility into every caller, which is unjustified risk for a phase whose job is
consolidation, not redesign.

**Files:**
- Move: `src/moonface/core/series.py` → `src/moonface/data/series.py`
- Move: `tests/core/test_funding.py` → `tests/data/test_funding.py`
- Move: `tests/core/test_basis.py` → `tests/data/test_basis.py`
- Modify: every file listed in Step 2 (import-line rewrite only)

**Interfaces:**
- Consumes: `moonface.core.models.Candle` (unchanged).
- Produces: `moonface.data.series.{FundingCache, fetch_funding_history, align_funding, align_basis,
  METRICS_FIELDS, fetch_metrics_history, align_metric, parse_metrics_csv, _cache_path, _read_cache,
  _write_cache}` — same names, new module path. Task 6 depends on this path.

- [ ] **Step 1: `git mv` the module and its two dedicated test files**

```bash
git mv src/moonface/core/series.py src/moonface/data/series.py
git mv tests/core/test_funding.py tests/data/test_funding.py
git mv tests/core/test_basis.py tests/data/test_basis.py
```

`tests/core/test_metrics_data.py` also tests this module (the metrics/OI half) — leave it in place for now,
Task 6 moves it (it also tests `load_bundle`, which Task 6 relocates, so both fixes belong together).

- [ ] **Step 2: Rewrite every importer's import line**

Run:
```bash
grep -rln "moonface\.core\.series\b" --include="*.py" src tools tests | grep -v __pycache__
```
For each hit, replace `moonface.core.series` with `moonface.data.series`. This plan's research found ~23
sites including `src/moonface/core/bundle.py` (module-level `from moonface.core.series import ...` — Task 6
further edits this file), `src/moonface/kernel/reproduce.py` (lazy import of `_cache_path`/`_read_cache`),
`src/moonface/research/regime_selector/data.py` and `regime_overlay/data.py` (do **not** touch these here —
they import `exogenous.fred_data`, handled in Task 11, and `universe_data`, handled in Task 7; confirm
neither imports `core.series` directly before skipping), plus `tests/core/test_metrics_data.py` (leave this
one's `moonface.core.series` import lines for Task 6, which handles the whole file at once — do not
half-edit it here), and the remaining `tools/`/`tests/` sites the grep returns.

- [ ] **Step 3: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped`, `GUARD PASS`. (`tests/core/test_metrics_data.py` still imports the old
`moonface.core.series` path at this point for its metrics-half assertions — it still passes because Task 6,
not yet run, hasn't moved `data/series.py` away from anywhere `test_metrics_data.py` can't already reach;
confirm this explicitly by running it: `.venv/bin/python -m pytest tests/core/test_metrics_data.py -v`
should still PASS here, since only its `load_bundle` half is stale until Task 6.)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(g4): relocate core/series.py to data/series.py

FundingCache/fetch_funding_history/align_funding/align_basis and the
metrics-archive (OI/positioning) fetch_metrics_history/align_metric/
parse_metrics_csv all perform a live ccxt or Binance Vision fetch and own a
CSV cache -- same invariant-1 reasoning as Task 4's core/data.py move.
Kept as one file rather than split into funding/metrics submodules: several
callers (kernel/reproduce.py, tests/core/test_metrics_data.py) reach into
the module's private cache helpers directly, and a same-file move preserves
every one of those references without having to re-derive which private
helper belongs to which half. ~23 call sites' import paths updated
mechanically; tests/core/test_metrics_data.py deliberately left for Task 6,
which also relocates load_bundle out of the same file."
```

---

### Task 6: Split `core/bundle.py` — extract `load_bundle` into `data/bundle.py`

The one genuinely non-mechanical Track A task. `core/bundle.py` currently holds `DataBundle` (a pure
dataclass — the shape of "everything a hypothesis can see"), `align_feature`/`_check_coverage` (pure
alignment/validation, no I/O), and `load_bundle` (the one function that actually calls `fetch_history`/
`fetch_funding_history`/`fetch_metrics_history`). 78 of 103 importers use only `DataBundle` (and, in one
test, `align_feature`) — moving the whole file would force 78 unnecessary changes and contradicts the
spec's own description of `core/` as holding "primitives: series, metrics, models, indicators, signal
types" (`DataBundle` is exactly such a primitive shape). Only `load_bundle` — the fetch orchestrator — moves.

**Files:**
- Modify: `src/moonface/core/bundle.py` (remove `load_bundle`, its two now-unused fetch-layer imports)
- Create: `src/moonface/data/bundle.py` (new home for `load_bundle`)
- Move: `tests/core/test_metrics_data.py` → `tests/data/test_metrics_and_bundle.py`
- Modify: the 16 direct-import files listed in Step 3 below
- Modify: 8 test files that patch `load_bundle` by target-module string (Step 4) — no change needed, listed
  for completeness/verification only

**Interfaces:**
- Consumes: `moonface.core.bundle.{DataBundle, align_feature, _check_coverage, FEATURE_COVERAGE_MIN}`
  (unchanged location — `data` may import `core`), `moonface.data.ohlcv.{OhlcvCache, fetch_history}`,
  `moonface.data.series.{FundingCache, fetch_funding_history, align_funding, align_basis, METRICS_FIELDS,
  fetch_metrics_history, align_metric}`.
- Produces: `moonface.data.bundle.load_bundle(asset: dict, start_ms: int, end_ms: int, cache_dir: str) ->
  DataBundle` — same signature, new module. Task 18's reproduction-gate re-run and every remaining
  `tools/engine/*` script depend on this path.

- [ ] **Step 1: Read `core/bundle.py` in full to confirm it has not drifted**

`git log -1 --format=%H -- src/moonface/core/bundle.py` then `cat src/moonface/core/bundle.py` — confirm
against the version transcribed in this plan's research (81 lines: `DataBundle`, `align_feature`,
`load_bundle`, `_check_coverage`, all in one file) before editing.

- [ ] **Step 2: Split the file**

Rewrite `src/moonface/core/bundle.py` to remove `load_bundle` and its two fetch-layer imports:
```diff
 from __future__ import annotations

 from dataclasses import dataclass

-from moonface.core.data import OhlcvCache, fetch_history
-from moonface.core.series import (
-    FundingCache, METRICS_FIELDS, align_basis, align_funding, align_metric,
-    fetch_funding_history, fetch_metrics_history,
-)
 from moonface.core.models import Candle


 FEATURE_COVERAGE_MIN = 0.8  # aligned feature series must be >=80% non-None


 @dataclass(frozen=True)
 class DataBundle:
     """Everything a hypothesis can see for one asset. funding/basis/feature/
     bookdepth are aligned 1:1 with candles (as-of joins, no lookahead) or None
     when not loaded. `feature` is a cross-asset close series (e.g. ETH for
     lead-lag) or a metrics series; `bookdepth` is the per-bar mean ±1% depth
     imbalance."""

     candles: list[Candle]
     funding: list[float | None] | None = None
     basis: list[float | None] | None = None
     feature: list[float | None] | None = None
     bookdepth: list[float | None] | None = None


 def align_feature(candles: list[Candle],
                   feat_candles: list[Candle]) -> list[float | None]:
     """Exact close-time join: both series share the timeframe, so the feature
     candle closing at the same timestamp is fully closed — no lookahead."""
     closes = {c.timestamp_ms: c.close for c in feat_candles}
     return [closes.get(c.timestamp_ms) for c in candles]


-def load_bundle(asset: dict, start_ms: int, end_ms: int, cache_dir: str) -> DataBundle:
-    ...  # entire function body deleted, moved verbatim to data/bundle.py
-
-
 def _check_coverage(feature: list[float | None], label: str) -> None:
     filled = sum(1 for v in feature if v is not None)
     if not feature or filled / len(feature) < FEATURE_COVERAGE_MIN:
         raise ValueError(
             f"feature {label} coverage {filled}/{len(feature)} below"
             f" {FEATURE_COVERAGE_MIN:.0%}; refusing to run with a gappy"
             " feature series")
```

- [ ] **Step 3: Create `data/bundle.py` with `load_bundle` moved in verbatim, imports repointed**

Create `src/moonface/data/bundle.py`:
```python
from __future__ import annotations

from moonface.core.bundle import DataBundle, _check_coverage
from moonface.data.ohlcv import OhlcvCache, fetch_history
from moonface.data.series import (
    METRICS_FIELDS, align_basis, align_funding, align_metric,
    fetch_funding_history, fetch_metrics_history,
)


def align_feature(candles, feat_candles) -> list[float | None]:
    """Re-exported from core.bundle for this module's own use below --
    load_bundle calls it unqualified, same as before the split."""
    from moonface.core.bundle import align_feature as _align_feature
    return _align_feature(candles, feat_candles)


def load_bundle(asset: dict, start_ms: int, end_ms: int, cache_dir: str) -> DataBundle:
    """Full (unfenced) bundle for one asset. Mirrors the wiring of the
    bespoke probe CLIs; network access only through the existing CSV caches.
    Tests inject synthetic bundles instead of calling this.

    Moved out of core.bundle at G4 -- this is the one function in that
    module that actually calls the fetch layer (fetch_history,
    fetch_funding_history, fetch_metrics_history), which core/ can no
    longer hold once data/ exists. DataBundle itself and its pure
    alignment/validation helpers stay in core.bundle -- they are a shape,
    not a fetch."""
    candles = fetch_history(asset["exchange"], asset["symbol"], asset["timeframe"],
                            start_ms, end_ms, OhlcvCache(cache_dir))
    funding = None
    if "funding_symbol" in asset:
        points = fetch_funding_history(asset["exchange"], asset["funding_symbol"],
                                       start_ms, end_ms, moonface_data_series_FundingCache(cache_dir))
        funding = align_funding(candles, points)
    basis = None
    if "spot_symbol" in asset:
        spot = fetch_history(asset["exchange"], asset["spot_symbol"],
                             asset["timeframe"], start_ms, end_ms,
                             OhlcvCache(cache_dir))
        basis = align_basis(candles, spot)
    feature = None
    if "feature_symbol" in asset:
        feat = fetch_history(asset["exchange"], asset["feature_symbol"],
                             asset["timeframe"], start_ms, end_ms,
                             OhlcvCache(cache_dir))
        feature = align_feature(candles, feat)
        _check_coverage(feature, asset["feature_symbol"])
    elif "metrics_field" in asset:
        field = asset["metrics_field"]
        if field not in METRICS_FIELDS:
            raise ValueError(f"unknown metrics field {field!r}")
        archive_symbol = asset["symbol"].split(":")[0].replace("/", "")
        raw = fetch_metrics_history(archive_symbol, start_ms, end_ms, cache_dir)
        feature = align_metric(candles, [(ts, f[field]) for ts, f in raw
                                         if field in f])
        _check_coverage(feature, f"{archive_symbol} metrics {field}")
    return DataBundle(candles=candles, funding=funding, basis=basis, feature=feature)
```

Fix the `moonface_data_series_FundingCache` placeholder above — that name does not exist; it is a
reminder to import `FundingCache` from `moonface.data.series` at the top of the file alongside the other
five names already listed in the `from moonface.data.series import (...)` block, then use the plain name
`FundingCache(cache_dir)` in the body. Also drop the redundant local re-import inside `align_feature`
above — import `align_feature` directly at module level from `moonface.core.bundle` instead of
re-wrapping it:
```diff
-from moonface.core.bundle import DataBundle, _check_coverage
+from moonface.core.bundle import DataBundle, _check_coverage, align_feature
 from moonface.data.ohlcv import OhlcvCache, fetch_history
 from moonface.data.series import (
-    METRICS_FIELDS, align_basis, align_funding, align_metric,
+    FundingCache, METRICS_FIELDS, align_basis, align_funding, align_metric,
     fetch_funding_history, fetch_metrics_history,
 )
-
-
-def align_feature(candles, feat_candles) -> list[float | None]:
-    """Re-exported from core.bundle for this module's own use below --
-    load_bundle calls it unqualified, same as before the split."""
-    from moonface.core.bundle import align_feature as _align_feature
-    return _align_feature(candles, feat_candles)
```
And inside `load_bundle`'s body, replace the placeholder call with `FundingCache(cache_dir)`. Re-read the
finished file once assembled to confirm it is self-consistent before moving on — this step's diff-on-a-diff
is intentionally shown as a first draft then a correction, mirroring how a careful engineer catches their
own placeholder before committing it; the finished `data/bundle.py` must contain a clean single set of
imports and a `load_bundle` body identical in logic to the original, with `FundingCache(cache_dir)` (not
the placeholder name) as its only textual difference from `core/bundle.py`'s pre-split version.

- [ ] **Step 4: Rewrite the 16 direct-import source lines**

Run: `grep -rn "from moonface.core.bundle import.*load_bundle" --include="*.py" src tools tests | grep -v __pycache__`
Expected 16 hits (confirmed by this plan's research; re-confirm before editing):
`src/moonface/feed/cli.py`, `src/moonface/signal/cli.py` (imports `DataBundle, load_bundle` together —
split into two import lines, one per module), `tools/research.py`, `tools/engine/v3_evaluate.py`,
`tools/engine/engine_calibration.py`, `tools/reconfirm.py`, `tools/promote.py`, `tools/engine/engine_audit.py`,
`tools/engine/engine_repair.py`, `tools/engine/v3_replay.py`, `tools/engine/engine_honest_report.py`,
`tools/engine/engine_backtest.py` (also `DataBundle, load_bundle` together — split),
`tools/engine/engine_ablation.py`, `tools/liq_twap/liq_twap_screen.py`, `tools/engine/moe_evaluate.py`,
`tests/test_leadlag_signals.py` (imports `DataBundle, align_feature, load_bundle` together — split into a
`core.bundle` line for `DataBundle, align_feature` and a `data.bundle` line for `load_bundle`).

For each single-name hit: `from moonface.core.bundle import load_bundle` →
`from moonface.data.bundle import load_bundle`. For each combined hit, split into two lines as shown for
`signal/cli.py`:
```diff
-from moonface.core.bundle import DataBundle, load_bundle
+from moonface.core.bundle import DataBundle
+from moonface.data.bundle import load_bundle
```

- [ ] **Step 5: Fix the monkeypatch-by-module-alias test, then move it**

`tests/core/test_metrics_data.py` does `import moonface.core.bundle as bundle_mod` three times (in
`test_load_bundle_attaches_metrics_feature`, `test_load_bundle_rejects_thin_metrics_coverage`,
`test_load_bundle_skips_rows_missing_the_field`), then `monkeypatch.setattr(bundle_mod, "fetch_history",
...)` / `monkeypatch.setattr(bundle_mod, "fetch_metrics_history", ...)` and calls `bundle_mod.load_bundle(...)`.
This only works because `fetch_history`/`fetch_metrics_history` were imported into `core/bundle.py`'s own
namespace and `load_bundle` called them unqualified — both facts are now false (they moved to
`data/bundle.py`). Change all three `import moonface.core.bundle as bundle_mod` lines to
`import moonface.data.bundle as bundle_mod`. The file's other imports
(`from moonface.core.series import (METRICS_FIELDS, align_metric, ...)`) already got rewritten to
`moonface.data.series` in Task 5's mass edit — confirm that landed (`grep -n "core.series"
tests/core/test_metrics_data.py` should return nothing).

Then:
```bash
git mv tests/core/test_metrics_data.py tests/data/test_metrics_and_bundle.py
```

- [ ] **Step 6: Verify no regression**

Run: `.venv/bin/python -m pytest tests/data/test_metrics_and_bundle.py tests/test_leadlag_signals.py -v`
Expected: PASS, every test unchanged in assertion, only import/alias targets moved.

- [ ] **Step 7: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(g4): split load_bundle out of core/bundle.py into data/bundle.py

DataBundle, align_feature, and _check_coverage are pure shape/validation --
core/ keeps them (78 of 103 importers use only these, untouched here).
load_bundle is the one function that calls the fetch layer
(fetch_history/fetch_funding_history/fetch_metrics_history), which core/
cannot hold once data/ exists (same invariant-1 reasoning as Tasks 4-5).
16 direct-import call sites rewritten; tests/core/test_metrics_data.py's
three 'import moonface.core.bundle as bundle_mod' monkeypatch targets fixed
to moonface.data.bundle (the function-alias gotcha this plan's Global
Constraints flagged) and the file moved to tests/data/test_metrics_and_bundle.py."
```

---

### Task 7: Relocate `research/universe_data.py` → `data/universe.py`, shim the old path

First Track B task. Unlike Track A, `research/` sits *above* `data/` — no test forbids `research` from
importing `data`, so the old path becomes a thin re-export shim rather than forcing ~100 importers to
change. `regime_selector/data.py`, `regime_overlay/data.py`, and `multifamily_loader.py` (Task 2's audit
corrections 3) get their own three-line internal updates in this same task since they are the only
"central" call sites cheap enough to modernize now.

**Files:**
- Move: `src/moonface/research/universe_data.py`'s content → `src/moonface/data/universe.py` (new file)
- Modify: `src/moonface/research/universe_data.py` (becomes a re-export shim)
- Move: `tests/research/test_universe_data.py` → `tests/data/test_universe.py`
- Modify: `src/moonface/research/regime_selector/data.py`, `src/moonface/research/regime_overlay/data.py`,
  `src/moonface/research/multifamily_loader.py` (repoint the 5 total import lines that name
  `universe_data` directly at `data.universe`)

**Interfaces:**
- Consumes: `moonface.core.models.Candle`, `moonface.data.ohlcv.OhlcvCache`, `moonface.data.http.retrying`.
- Produces: `moonface.data.universe.{DailyRow, parse_symbol_listing, parse_klines_payload,
  list_um_perp_symbols, save_daily_cache, load_daily_cache, fetch_daily_klines, fetch_perp_candles,
  fetch_funding_rates, _INTERVAL_MS}` at the new path; the same names remain importable at
  `moonface.research.universe_data` via the shim for the ~95 remaining importers this task does not touch.

- [ ] **Step 1: Create `data/universe.py` with the file's content, imports repointed**

```bash
git mv src/moonface/research/universe_data.py src/moonface/data/universe.py
```

Edit `src/moonface/data/universe.py`: replace `from moonface.core.data import OhlcvCache` (inside
`fetch_perp_candles`, currently a lazy import) with `from moonface.data.ohlcv import OhlcvCache`, and
replace whatever `retrying` import remains from Task 3's edit
(`from moonface.data.http import retrying` — already correct if Task 3 landed; verify, don't re-add).

- [ ] **Step 2: Write the re-export shim at the old path**

Create `src/moonface/research/universe_data.py`:
```python
"""Moved to moonface.data.universe at G4 (repo restructure design spec,
phase G4). Re-exported here for the ~95 existing importers across
research/, signal/, and tools/ that this phase deliberately does not touch
-- each is a lane G6 converts individually. New code should import
moonface.data.universe directly."""
from moonface.data.universe import (  # noqa: F401
    DailyRow, fetch_daily_klines, fetch_funding_rates, fetch_perp_candles,
    list_um_perp_symbols, load_daily_cache, parse_klines_payload,
    parse_symbol_listing, save_daily_cache,
)
from moonface.data.universe import _INTERVAL_MS  # noqa: F401 -- one test imports this private name
```

- [ ] **Step 3: Move the module's own test file, repoint its imports**

```bash
git mv tests/research/test_universe_data.py tests/data/test_universe.py
```
Edit `tests/data/test_universe.py`: replace every `from moonface.research.universe_data import ...` with
`from moonface.data.universe import ...`.

- [ ] **Step 4: Update the three central pass-through wrappers**

`src/moonface/research/regime_selector/data.py`:
```diff
-from moonface.research.universe_data import fetch_perp_candles
+from moonface.data.universe import fetch_perp_candles
```

`src/moonface/research/regime_overlay/data.py`:
```diff
-from moonface.research.universe_data import (fetch_funding_rates,
-                                             fetch_perp_candles)
+from moonface.data.universe import fetch_funding_rates, fetch_perp_candles
```

`src/moonface/research/multifamily_loader.py` — this file's `default_readers` function imports
`fetch_bookdepth_history`/`imbalance_points` together too (Task 8 handles that pair); for this task, fix
only the `universe_data`-named import inside the same function if present, and the module-level one if
present. Run `grep -n "universe_data" src/moonface/research/multifamily_loader.py` first to see the exact
current line(s), then replace `moonface.research.universe_data` with `moonface.data.universe` in each.

- [ ] **Step 5: Verify no regression in the four touched files' own tests**

Run:
```bash
.venv/bin/python -m pytest tests/data/test_universe.py tests/research/regime_selector/ \
  tests/research/regime_overlay/ tests/research/test_multifamily_loader.py -v
```
Expected: PASS, every test unchanged.

- [ ] **Step 6: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 7: Confirm invariant 3 for this module**

Run: `grep -n "urlopen\|ccxt\." src/moonface/research/universe_data.py`
Expected: no output — the shim performs no fetch of its own.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(g4): relocate universe_data.py to data/universe.py, shim the old path

data/ may be imported from research/ without violating any layering test
(unlike core/, Track A), so the ~95 remaining importers across research/,
signal/, and tools/ -- each a lane G6 will convert individually -- are left
on the old moonface.research.universe_data path via a thin re-export shim
rather than rewritten now. regime_selector/data.py, regime_overlay/data.py,
and multifamily_loader.py -- the only central, cheap-to-modernize call
sites -- import moonface.data.universe directly. Zero fetch/cache code
remains at the old path (confirmed: no urlopen/ccxt reference in the shim)."
```

---

### Task 8: Split `features/orderbook_features.py` — extract fetch/cache into `data/orderbook.py`

`fetch_bookdepth_history`, `parse_bookdepth_csv`, and their cache helpers perform the fetch; `imbalance_points`
is a pure feature computation (bid/ask notional → imbalance ratio) with no I/O — it belongs in `features/`
per the target layout (`features ← data`), not `data/`. Only 2 non-test call sites import
`fetch_bookdepth_history` directly (`tools/lanes/bookdepth_study.py`,
`research/multifamily_loader.py::default_readers`) — small enough to update directly rather than shim.

**Files:**
- Modify: `src/moonface/features/orderbook_features.py` (keeps `imbalance_points`, `Row` type; loses
  `fetch_bookdepth_history`, `parse_bookdepth_csv`, `_get_bytes*`, `_cache_path`, `_read_cache`,
  `_write_cache`, `_URL`, `_DAY_MS`, `_FLUSH_EVERY_DAYS`)
- Create: `src/moonface/data/orderbook.py` (new home for the fetch/cache half)
- Move: `tests/features/test_bookdepth_data.py` → `tests/data/test_orderbook.py`
- Modify: `tools/lanes/bookdepth_study.py`, `src/moonface/research/multifamily_loader.py` (repoint
  `fetch_bookdepth_history` import; leave `imbalance_points` import as-is, now a separate line)

**Interfaces:**
- Consumes: `moonface.data.http.retrying`.
- Produces: `moonface.data.orderbook.{Row, parse_bookdepth_csv, fetch_bookdepth_history}`. `features/
  orderbook_features.py` imports `Row` from here for `imbalance_points`'s signature.

- [ ] **Step 1: Create `data/orderbook.py` with the fetch half, verbatim**

Create `src/moonface/data/orderbook.py` with `Row`, `parse_bookdepth_csv`, `_get_bytes_once`, `_get_bytes =
retrying(_get_bytes_once)` (importing `retrying` from `moonface.data.http`), `_cache_path`, `_read_cache`,
`_write_cache`, `fetch_bookdepth_history`, `_URL`, `_DAY_MS`, `_FLUSH_EVERY_DAYS` — copied verbatim from the
current `features/orderbook_features.py` (this plan's research read the full 122-line file; re-read it
fresh before copying, in case it drifted). Module docstring: reuse the existing one (the "Binance Vision UM
`bookDepth` archive..." paragraph) since it describes the fetch behavior, not the feature.

- [ ] **Step 2: Trim `features/orderbook_features.py` to the feature half**

Rewrite it to keep only:
```python
"""Order-book depth imbalance feature: (bid-ask)/(bid+ask) at the ±1% band,
from data.orderbook's fetched snapshots. The fetch/cache logic itself moved
to data/orderbook.py at G4 (invariant 3: no module outside data/ performs a
network fetch or writes a cache) -- this module now holds only the pure
feature computation."""
from __future__ import annotations

from moonface.data.orderbook import Row


def imbalance_points(rows: list[Row]) -> list[tuple[int, float]]:
    """(ts, (bid-ask)/(bid+ask)); zero-liquidity snapshots dropped."""
    return [(ts, (b - a) / (b + a)) for ts, b, a in rows if b + a > 0.0]
```

- [ ] **Step 3: Move the test file, split its imports**

```bash
git mv tests/features/test_bookdepth_data.py tests/data/test_orderbook.py
```
Edit `tests/data/test_orderbook.py`: `from moonface.features.orderbook_features import
(fetch_bookdepth_history, ...)` becomes two lines — `fetch_bookdepth_history`, `parse_bookdepth_csv`, `Row`
(if imported) from `moonface.data.orderbook`; `imbalance_points` (if this file tests it too — check) stays
imported from `moonface.features.orderbook_features`.

- [ ] **Step 4: Update the two direct-import call sites**

`tools/lanes/bookdepth_study.py`:
```diff
-from moonface.features.orderbook_features import (fetch_bookdepth_history,
-                                              imbalance_points)
+from moonface.data.orderbook import fetch_bookdepth_history
+from moonface.features.orderbook_features import imbalance_points
```

`src/moonface/research/multifamily_loader.py` (inside `default_readers`, per this plan's research at line
~50):
```diff
-    from moonface.features.orderbook_features import (fetch_bookdepth_history,
-                                                  imbalance_points)
+    from moonface.data.orderbook import fetch_bookdepth_history
+    from moonface.features.orderbook_features import imbalance_points
```

- [ ] **Step 5: Verify no regression**

Run:
```bash
.venv/bin/python -m pytest tests/data/test_orderbook.py tests/research/test_multifamily_loader.py -v
```
Expected: PASS. `tools/lanes/bookdepth_study.py` has no dedicated test file per this plan's research —
confirm with `grep -rl "bookdepth_study" tests/`; if a test exists, run it too.

- [ ] **Step 6: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(g4): split orderbook fetch/cache out of features/orderbook_features.py into data/orderbook.py

fetch_bookdepth_history and parse_bookdepth_csv perform a live Binance
Vision fetch and own a CSV cache -- invariant 3 moves them to data/.
imbalance_points is pure feature computation (no I/O) and stays in
features/, now importing the Row type from data.orderbook. Only 2
non-test call sites (tools/lanes/bookdepth_study.py, multifamily_loader.py)
imported fetch_bookdepth_history directly -- updated in place, no shim
needed at this importer count."
```

---

### Task 9: Relocate `research/aggtrades_data.py` → `data/aggtrades.py`

Only 2 non-definition importers (`tools/collect/aggtrades_fetch.py`, its own test) — small enough for a
direct update, no shim.

**Files:**
- Move: `src/moonface/research/aggtrades_data.py` → `src/moonface/data/aggtrades.py`
- Move: `tests/research/test_aggtrades_data.py` → `tests/data/test_aggtrades.py`
- Modify: `tools/collect/aggtrades_fetch.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (stdlib only, self-contained — confirmed by this plan's full read of
  the file).
- Produces: `moonface.data.aggtrades.{SecondRow, parse_aggtrades_day, fetch_aggsec_history, export_window}`.

- [ ] **Step 1: `git mv` the module and its test**

```bash
git mv src/moonface/research/aggtrades_data.py src/moonface/data/aggtrades.py
git mv tests/research/test_aggtrades_data.py tests/data/test_aggtrades.py
```

- [ ] **Step 2: Rewrite the two importers**

Run: `grep -rln "moonface\.research\.aggtrades_data\|aggtrades_data" --include="*.py" src tools tests | grep -v __pycache__`
Expected: `tools/collect/aggtrades_fetch.py` and `tests/data/test_aggtrades.py` (just moved). In
`tools/collect/aggtrades_fetch.py`:
```diff
-from moonface.research.aggtrades_data import export_window, fetch_aggsec_history
+from moonface.data.aggtrades import export_window, fetch_aggsec_history
```
In `tests/data/test_aggtrades.py`, replace every `moonface.research.aggtrades_data` reference with
`moonface.data.aggtrades`.

- [ ] **Step 3: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(g4): relocate aggtrades_data.py to data/aggtrades.py

Only 2 non-definition importers (tools/collect/aggtrades_fetch.py, its own
test) -- updated directly, no shim needed at this count."
```

---

### Task 10: Relocate `research/exogenous/deribit_dvol.py` → `data/options.py`, shim the old path

4 importers across `research/`, `tools/`, and `tests/` — shimmed, matching Track B's Task 7 pattern.

**Files:**
- Move: `src/moonface/research/exogenous/deribit_dvol.py` → `src/moonface/data/options.py`
- Modify: `src/moonface/research/exogenous/deribit_dvol.py` (becomes a re-export shim)
- Move: `tests/research/exogenous/test_deribit_dvol.py` → `tests/data/test_options.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (stdlib only).
- Produces: `moonface.data.options.{DvolPoint, parse_dvol_payload, fetch_dvol}` at the new path; same names
  remain importable at `moonface.research.exogenous.deribit_dvol` via the shim.

- [ ] **Step 1: `git mv`, write the shim**

```bash
git mv src/moonface/research/exogenous/deribit_dvol.py src/moonface/data/options.py
```
Create `src/moonface/research/exogenous/deribit_dvol.py`:
```python
"""Moved to moonface.data.options at G4. Re-exported here for existing
importers (research/exogenous, tools/exogenous/exogenous_btc.py,
tools/collect/vrp_fetch_dvol.py); new code should import
moonface.data.options directly."""
from moonface.data.options import DvolPoint, fetch_dvol, parse_dvol_payload  # noqa: F401
```

- [ ] **Step 2: Move the test file, repoint its imports**

```bash
git mv tests/research/exogenous/test_deribit_dvol.py tests/data/test_options.py
```
Replace every `from moonface.research.exogenous.deribit_dvol import ...` with
`from moonface.data.options import ...`.

- [ ] **Step 3: Confirm the 3 remaining importers are unaffected (shim absorbs them)**

Run: `grep -rln "exogenous.deribit_dvol\|exogenous import deribit_dvol" --include="*.py" src tools tests | grep -v __pycache__`
Expected: `tools/exogenous/exogenous_btc.py`, `tools/collect/vrp_fetch_dvol.py`,
`tests/research/test_vrp_measure.py` — none need editing (the shim covers them).

- [ ] **Step 4: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(g4): relocate deribit_dvol.py to data/options.py, shim the old path

fetch_dvol performs a live Deribit fetch and owns a CSV cache -- invariant
3 moves it to data/. 3 remaining importers (tools/exogenous/exogenous_btc.py,
tools/collect/vrp_fetch_dvol.py -- a one-time frozen-lane script, out of
scope per Task 2 but its import still resolves via the shim --
tests/research/test_vrp_measure.py) left on the old path via a thin
re-export shim."
```

---

### Task 11: Relocate `research/exogenous/fred_data.py` → `data/macro.py`, shim the old path, fix `regime_overlay`/`regime_selector`

10 importers — the widest Track B shim target after `universe_data`. Also finishes Task 2's audit
correction 3 by repointing `regime_selector/data.py` and `regime_overlay/data.py`'s `fred_data` import
(their `universe_data` import was already fixed in Task 7).

**Files:**
- Move: `src/moonface/research/exogenous/fred_data.py` → `src/moonface/data/macro.py`
- Modify: `src/moonface/research/exogenous/fred_data.py` (becomes a re-export shim)
- Move: `tests/research/exogenous/test_fred_data.py` → `tests/data/test_macro.py`
- Modify: `src/moonface/research/regime_selector/data.py`, `src/moonface/research/regime_overlay/data.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (stdlib only).
- Produces: `moonface.data.macro.{MacroPoint, parse_fred_csv, fetch_fred_series}` at the new path; same
  names remain importable at `moonface.research.exogenous.fred_data` via the shim.

- [ ] **Step 1: `git mv`, write the shim**

```bash
git mv src/moonface/research/exogenous/fred_data.py src/moonface/data/macro.py
```
Create `src/moonface/research/exogenous/fred_data.py`:
```python
"""Moved to moonface.data.macro at G4. Re-exported here for existing
importers (exogenous/*, regime_selector, regime_overlay's own historical
importers if any remain, tools/exogenous/exogenous_btc.py,
tools/ls_tournament/ls_tournament.py); new code should import
moonface.data.macro directly."""
from moonface.data.macro import MacroPoint, fetch_fred_series, parse_fred_csv  # noqa: F401
```

- [ ] **Step 2: Move the test file, repoint its imports**

```bash
git mv tests/research/exogenous/test_fred_data.py tests/data/test_macro.py
```
Replace every `from moonface.research.exogenous.fred_data import ...` with `from moonface.data.macro import
...`.

- [ ] **Step 3: Repoint `regime_selector/data.py` and `regime_overlay/data.py`**

```diff
-from moonface.research.exogenous.fred_data import fetch_fred_series
+from moonface.data.macro import fetch_fred_series
```
in both files.

- [ ] **Step 4: Confirm the remaining importers are unaffected (shim absorbs them)**

Run: `grep -rln "exogenous.fred_data\|exogenous import fred_data" --include="*.py" src tools tests | grep -v __pycache__`
Expected the 7 remaining sites this plan's research found (`tools/exogenous/exogenous_btc.py`,
`tools/ls_tournament/ls_tournament.py`, `tests/research/regime_overlay/test_regime.py`,
`tests/research/regime_selector/test_selector.py`, `tests/research/exogenous/test_exo_features.py`,
`tests/research/exogenous/test_evaluate.py`, `tests/research/exogenous/test_conditioning.py`) — none need
editing.

- [ ] **Step 5: Verify no regression, then collection, then the full suite**

Run:
```bash
.venv/bin/python -m pytest tests/data/test_macro.py tests/research/regime_selector/ tests/research/regime_overlay/ -v
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: everything PASS; `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(g4): relocate fred_data.py to data/macro.py, shim the old path

fetch_fred_series performs a live FRED fetch and owns a CSV cache --
invariant 3 moves it to data/. regime_selector/data.py and
regime_overlay/data.py (Task 2 audit correction 3's pass-through wrappers)
now import moonface.data.macro directly, finishing both files' migration
started in Task 7. 7 remaining importers left on the old
research.exogenous.fred_data path via a thin re-export shim."
```

---

### Task 12: Relocate `research/eventtime/vision_klines.py` → `data/vision.py`, shim the old path

5 importers, including `research/eventtime/__init__.py`'s own relative re-export and
`research/eventtime/dollar_bars.py`'s type-only import — both keep working unchanged through the shim
since `eventtime/__init__.py`'s `from .vision_klines import ...` still resolves.

**Files:**
- Move: `src/moonface/research/eventtime/vision_klines.py` → `src/moonface/data/vision.py`
- Modify: `src/moonface/research/eventtime/vision_klines.py` (becomes a re-export shim)
- Move: `tests/research/eventtime/test_eventtime_vision.py` → `tests/data/test_vision.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (stdlib only).
- Produces: `moonface.data.vision.{MinuteBar, parse_vision_klines_csv, fetch_vision_1m}` at the new path;
  same names remain importable at `moonface.research.eventtime.vision_klines` via the shim.

- [ ] **Step 1: `git mv`, write the shim**

```bash
git mv src/moonface/research/eventtime/vision_klines.py src/moonface/data/vision.py
```
Create `src/moonface/research/eventtime/vision_klines.py`:
```python
"""Moved to moonface.data.vision at G4. Re-exported here for
research/eventtime/__init__.py's own relative import and dollar_bars.py's
MinuteBar type import; new code should import moonface.data.vision
directly."""
from moonface.data.vision import MinuteBar, fetch_vision_1m, parse_vision_klines_csv  # noqa: F401
```

- [ ] **Step 2: Move the test file, repoint its imports**

```bash
git mv tests/research/eventtime/test_eventtime_vision.py tests/data/test_vision.py
```
Replace every `from moonface.research.eventtime.vision_klines import ...` with `from moonface.data.vision
import ...`.

- [ ] **Step 3: Confirm `eventtime/__init__.py` and `dollar_bars.py` still resolve unchanged**

`src/moonface/research/eventtime/__init__.py` does `from .vision_klines import MinuteBar, fetch_vision_1m,
parse_vision_klines_csv` — a relative import against the shim file, which now re-exports exactly those
three names. No edit needed; confirm with
`.venv/bin/python -c "from moonface.research.eventtime import MinuteBar, fetch_vision_1m, parse_vision_klines_csv"`.
`src/moonface/research/eventtime/dollar_bars.py` imports `MinuteBar` from `.vision_klines` directly — same,
no edit needed.

- [ ] **Step 4: Verify no regression, then collection, then the full suite**

Run:
```bash
.venv/bin/python -m pytest tests/data/test_vision.py tests/research/eventtime/ -v
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: everything PASS; `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(g4): relocate vision_klines.py to data/vision.py, shim the old path

fetch_vision_1m performs a live Binance Vision fetch and owns a CSV cache --
invariant 3 moves it to data/. eventtime/__init__.py's relative import and
dollar_bars.py's MinuteBar import both resolve unchanged through the shim.
5 importers total, none touched beyond the shim itself."
```

---

### Task 13: Give `deribit_chain` a real home in `collect/` — the first LIVE collector move

First Track C task, and the first to touch a live cron path (hard constraint §5.1). Moves the pure
parse/append/manifest logic; `tools/deribit_chain_collect.py`'s own async/CLI shell is untouched beyond its
import line. Followed by a mandatory hand-run and row-count check — no automated test can substitute for
confirming the live path still writes.

**Files:**
- Move: `src/moonface/research/exogenous/deribit_chain.py` → `src/moonface/collect/deribit_chain.py`
- Modify: `tools/deribit_chain_collect.py` (import line only)
- Move: `tests/research/test_deribit_chain.py` → `tests/collect/test_deribit_chain.py`
- Modify: `src/moonface/collect/__init__.py` (docstring — this domain is no longer "empty until then")

**Interfaces:**
- Consumes: nothing from earlier tasks (stdlib only — `research/exogenous/deribit_chain.py` has no
  cross-module dependency per this plan's full read of the file).
- Produces: `moonface.collect.deribit_chain.{ChainRow, parse_instrument_name, parse_book_summary, csv_path,
  bucket_of, snapshot_stats, collected_dates, collected_buckets, append_snapshot, write_manifest,
  collect_once, DEFAULT_CADENCE_MS, HOUR_MS, DAY_MS, CSV_FIELDS}`. No shim at the old path — only
  `tools/deribit_chain_collect.py` and its own test imported it (confirmed: 2 importers total in this
  plan's research), both updated in this same task.

- [ ] **Step 1: `git mv` the module and its test**

```bash
git mv src/moonface/research/exogenous/deribit_chain.py src/moonface/collect/deribit_chain.py
git mv tests/research/test_deribit_chain.py tests/collect/test_deribit_chain.py
```
Edit the moved test's imports: `from moonface.research.exogenous.deribit_chain import ...` →
`from moonface.collect.deribit_chain import ...`.

- [ ] **Step 2: Update `tools/deribit_chain_collect.py`'s import line**

```diff
-from moonface.research.exogenous.deribit_chain import (DEFAULT_CADENCE_MS, HOUR_MS,
+from moonface.collect.deribit_chain import (DEFAULT_CADENCE_MS, HOUR_MS,
```
(match whatever the rest of that multi-line import lists — read the file's current import block before
editing, do not guess the trailing names).

- [ ] **Step 3: Update `collect/__init__.py`'s docstring**

```diff
-"""Live collectors writing through data/ (G4). Empty until then.
-
-tools/liquidation_collect.py and tools/deribit_chain_collect.py still call
-moonface.research.exogenous.{liquidation_feed,deribit_chain} directly -- G4
-moves that logic here once data/ exists for it to write through. Moving it
-before then would touch the two live cron paths (hard constraint SS5.1) for
-no benefit this phase can use.
-"""
+"""Live collectors: deribit_chain, liquidation, bybit_liquidation,
+bybit_positioning (G4). Each holds the pure parse/append/manifest logic;
+the async/WS shell for each stays in its tools/*_collect.py CLI, which
+imports from here."""
```

- [ ] **Step 4: Verify no regression**

Run: `.venv/bin/python -m pytest tests/collect/test_deribit_chain.py -v`
Expected: PASS, every test unchanged.

- [ ] **Step 5: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(g4): give deribit_chain a real home in collect/ -- LIVE cron path

The G2-scaffolded collect/__init__.py named this exact move. Only
tools/deribit_chain_collect.py and its own test imported the old
research.exogenous.deribit_chain path -- both updated directly, no shim.
Hard constraint SS5.1: this touches the live cron path; the next step is
the mandatory hand-run + row-count check before this commit is trusted."
```

- [ ] **Step 7: Mandatory hand-run + row-count check (do not skip)**

Run:
```bash
.venv/bin/python tools/deribit_chain_collect.py status
```
Expected: prints the current collection stats (rows/days/coverage) without error — confirms the CLI's
import path resolves and the collector's read path against the live CSV is intact. Then run one live
collection cycle by hand (the same operation cron performs every minute):
```bash
.venv/bin/python tools/deribit_chain_collect.py collect
```
Expected: exits 0, either `{"status": "already_collected", ...}` (if inside the same cadence bucket as
cron's last run) or `{"status": "collected", "appended": N, ...}` with `N > 0`. Compare
`experiments/newdata/deribit_chain/chain_BTC.csv` row count against Task 1's snapshot
(`tools/ops/phase_guard_baseline.json`'s `csv_row_floor` entry) — it must be `>=` that floor, not lower.
If either command errors or the row count regressed, **stop and revert this task's commit** — the live
clock (150-day gate, per memory) cannot silently break.

---

### Task 14: Give `liquidation` a real home in `collect/` — the second LIVE collector move

Same shape as Task 13, for the other live cron path.

**Files:**
- Move: `src/moonface/research/exogenous/liquidation_feed.py` → `src/moonface/collect/liquidation.py`
- Modify: `tools/liquidation_collect.py` (import line only)
- Move: `tests/research/exogenous/test_liquidation_feed.py` → `tests/collect/test_liquidation.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (stdlib only).
- Produces: `moonface.collect.liquidation.{LiquidationRow, parse_force_order, rows_from_liquidations,
  append_rows, snapshot_stats, write_manifest, CSV_FIELDS, CLUSTER_GAP_MS}`. No shim — 3 importers total per
  this plan's research (`tools/liquidation_collect.py`, its own test, and confirm no third via the grep
  below), all updated here.

- [ ] **Step 1: `git mv` the module and its test**

```bash
git mv src/moonface/research/exogenous/liquidation_feed.py src/moonface/collect/liquidation.py
git mv tests/research/exogenous/test_liquidation_feed.py tests/collect/test_liquidation.py
```
Edit the moved test's imports: `from moonface.research.exogenous.liquidation_feed import ...` →
`from moonface.collect.liquidation import ...`.

- [ ] **Step 2: Confirm the exact importer set, then update `tools/liquidation_collect.py`**

Run: `grep -rln "exogenous.liquidation_feed\|exogenous import liquidation_feed" --include="*.py" src tools tests | grep -v __pycache__`
Expected exactly `tools/liquidation_collect.py` and the just-moved test (already fixed). Update
`tools/liquidation_collect.py`:
```diff
-from moonface.research.exogenous.liquidation_feed import (
+from moonface.collect.liquidation import (
     append_rows, rows_from_liquidations, snapshot_stats, write_manifest)
```

- [ ] **Step 3: Verify no regression**

Run: `.venv/bin/python -m pytest tests/collect/test_liquidation.py -v`
Expected: PASS, every test unchanged.

- [ ] **Step 4: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(g4): give liquidation a real home in collect/ -- LIVE cron path

Same shape as Task 13 for the other live cron collector. Only
tools/liquidation_collect.py and its own test imported the old
research.exogenous.liquidation_feed path -- both updated directly, no
shim. Next step is the mandatory hand-run + row-count check."
```

- [ ] **Step 6: Mandatory hand-run + row-count check (do not skip)**

Run:
```bash
.venv/bin/python tools/liquidation_collect.py status
```
Expected: prints current collection stats without error. This collector is event-driven (WebSocket
liquidations, not a poll), so a short live `collect` run cannot be timed to guarantee a new row inside a
test window the way `deribit_chain`'s cadence-bucket check can — instead, confirm the import path end to
end with a short supervised run:
```bash
timeout 20 .venv/bin/python tools/liquidation_collect.py collect; echo "exit: $?"
```
Expected: runs for ~20s without a traceback, then is killed by `timeout` (exit 124) or exits 0 on
`KeyboardInterrupt`/`CancelledError` per the script's own `finally` block, which always calls
`write_manifest` on the way out — confirm `experiments/newdata/liquidations/manifest.json`'s
`generated`/timestamp-bearing field (read the file to see its exact key) advanced past its Task-1 value.
Row count itself may legitimately stay flat for 20s (liquidations are sparse) — that is not a failure
signal here; a traceback or an import error is. If either appears, **stop and revert this task's commit**.

---

### Task 15: Give `bybit_liquidation` a real home in `collect/`

Not a live cron path (confirmed via `crontab -l` in this plan's research: only `liquidation_collect.py` and
`deribit_chain_collect.py` are scheduled) — lower risk than Tasks 13-14, no mandatory hand-run, but still
verified by its own tests.

**Files:**
- Move: `src/moonface/research/exogenous/bybit_liquidation_feed.py` → `src/moonface/collect/bybit_liquidation.py`
- Modify: `tools/bybit_liquidation_collect.py` (import line only)
- Move: `tests/test_bybit_liquidation_feed.py` → `tests/collect/test_bybit_liquidation.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (stdlib only).
- Produces: `moonface.collect.bybit_liquidation.{LiquidationRow, row_from_liquidation,
  rows_from_liquidations, csv_path, append_rows, snapshot_stats, write_manifest}`. No shim — confirmed 1
  importer beyond its own test (`tools/bybit_liquidation_collect.py`).

- [ ] **Step 1: `git mv` the module and its test**

```bash
git mv src/moonface/research/exogenous/bybit_liquidation_feed.py src/moonface/collect/bybit_liquidation.py
git mv tests/test_bybit_liquidation_feed.py tests/collect/test_bybit_liquidation.py
```
Edit the moved test's imports to the new path.

- [ ] **Step 2: Update `tools/bybit_liquidation_collect.py`**

Read its current import block first (this plan's research confirmed it is a multi-line `from
moonface.research.exogenous.bybit_liquidation_feed import (  # noqa: E402` — copy the exact name list from
the file rather than guessing), then change only the module path:
```diff
-from moonface.research.exogenous.bybit_liquidation_feed import (  # noqa: E402
+from moonface.collect.bybit_liquidation import (  # noqa: E402
```

- [ ] **Step 3: Verify no regression, then collection, then the full suite**

Run:
```bash
.venv/bin/python -m pytest tests/collect/test_bybit_liquidation.py -v
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: everything PASS; `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(g4): give bybit_liquidation a real home in collect/

Not a live cron path (confirmed via crontab -l: only liquidation_collect.py
and deribit_chain_collect.py are scheduled) -- lower risk than Tasks 13-14,
no mandatory hand-run. Only tools/bybit_liquidation_collect.py and its own
test imported the old path -- both updated directly, no shim."
```

---

### Task 16: Give `bybit_positioning` a real home in `collect/`

Same shape as Task 15, closing out the four-domain `collect/` package.

**Files:**
- Move: `src/moonface/research/exogenous/bybit_positioning.py` → `src/moonface/collect/bybit_positioning.py`
- Modify: `tools/bybit_positioning_collect.py` (import line only)
- Move: `tests/test_bybit_positioning.py` → `tests/collect/test_bybit_positioning.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (stdlib only).
- Produces: `moonface.collect.bybit_positioning.{PositioningRow (if defined — confirm exact name via the
  file's dataclass), period_ms, build_url, unwrap, parse_account_ratio, fetch_window, csv_path, append_rows,
  collection_stats, write_manifest, collect}`. No shim — `tools/bybit_positioning_collect.py` imports it as
  `from moonface.research.exogenous import bybit_positioning as bp` (a module-alias import, not a
  from-import of individual names) — the whole-module alias form, simpler to fix than the per-name shims
  above.

- [ ] **Step 1: `git mv` the module and its test**

```bash
git mv src/moonface/research/exogenous/bybit_positioning.py src/moonface/collect/bybit_positioning.py
git mv tests/test_bybit_positioning.py tests/collect/test_bybit_positioning.py
```
Edit the moved test's imports to the new path.

- [ ] **Step 2: Update `tools/bybit_positioning_collect.py`**

```diff
-from moonface.research.exogenous import bybit_positioning as bp  # noqa: E402
+from moonface.collect import bybit_positioning as bp  # noqa: E402
```
Every `bp.<name>` call site in the rest of the file needs no further change — the alias name is unchanged,
only what it points at.

- [ ] **Step 3: Verify no regression, then collection, then the full suite**

Run:
```bash
.venv/bin/python -m pytest tests/collect/test_bybit_positioning.py -v
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: everything PASS; `2656 passed, 3 skipped`, `GUARD PASS`.

- [ ] **Step 4: Confirm invariant 3 across all of `research/` now**

Run:
```bash
grep -rln "urlopen\|urllib.request\|import ccxt\|ccxt\." --include="*.py" src/moonface/research | grep -v __pycache__
```
Expected: only `src/moonface/research/forced_flow/coinm_archive.py` (reads a frozen local archive, not a
live URL — confirm no `urlopen`/`ccxt` call inside it, only `zipfile`/local `Path` reads, per Task 2's
audit) and the thin shims from Tasks 7/10/11/12 (each of which imports, but does not itself call,
`urlopen`/`ccxt` — confirm each shim file has zero such calls, only import statements). Any other hit is a
missed relocation — stop and investigate before committing.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(g4): give bybit_positioning a real home in collect/

Closes out the four-domain collect/ package (deribit_chain, liquidation,
bybit_liquidation, bybit_positioning -- exactly the list collect/__init__.py
named at G2). tools/bybit_positioning_collect.py's module-alias import
updated in place. Confirmed: no remaining urlopen/ccxt call anywhere in
research/ outside forced_flow/coinm_archive.py (a frozen local-archive
reader, explicitly out of scope per Task 2) and the four Track-B shims."
```

---

### Task 17: Extend `tests/test_import_boundaries.py` with `data`/`collect` layering rules

Codifies invariant 1 for the two packages this phase built, the same way G2 codified it for `core`/
`kernel`/`signal`/`feed`.

**Files:**
- Modify: `tests/test_import_boundaries.py`

**Interfaces:**
- Consumes: the existing `_violations`/`_imports` helpers, unchanged.
- Produces: two new test functions; no new production code.

- [ ] **Step 1: Write the two new test functions**

Add to `tests/test_import_boundaries.py`, after `test_kernel_imports_neither_signal_nor_a_lane`:

```python
def test_data_imports_nothing_above_it():
    assert _violations("data",
                       ("moonface.features", "moonface.models", "moonface.kernel",
                        "moonface.strategies", "moonface.signal", "moonface.research",
                        "moonface.feed", "moonface.collect", "moonface.lanes")) == []


def test_collect_imports_nothing_above_it():
    assert _violations("collect",
                       ("moonface.features", "moonface.models", "moonface.kernel",
                        "moonface.strategies", "moonface.signal", "moonface.research",
                        "moonface.feed", "moonface.lanes")) == []
```

- [ ] **Step 2: Run the two new tests**

Run: `.venv/bin/python -m pytest tests/test_import_boundaries.py -v`
Expected: PASS, including the two new tests — every prior task in this plan already enforced the
constraint by construction (Track A had no choice; Track B's shims only ever import `moonface.data.*`;
Track C's collect modules are self-contained or import only `moonface.data.http`), so this task is a
codification, not a fix. If either new test fails, find which file the failure names and fix its import
before proceeding — do not weaken the test to pass.

- [ ] **Step 3: Verify collection, then the full suite**

Run:
```bash
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `2658 passed, 3 skipped` (2656 + 2), `GUARD PASS`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_import_boundaries.py
git commit -m "test(g4): codify the data/ and collect/ layering invariants

Mirrors G2's core/kernel/signal/feed boundary tests for the two packages
this phase built: data/ may import only core/; collect/ may import only
core/ and data/. Every prior task already satisfied this by construction --
this task turns the invariant into a standing regression guard."
```

---

### Task 18: Re-run the G3 reproduction gate — prove the data-layer move changed no number (risk R6)

The spec names this explicitly: "G4 runs the G3 gate again afterwards; the recorded runs must still
reproduce" (§6, risk R6's control). `oibuild_study` and `liqladder`'s frozen `registration.json` files, and
their recorded `verdict.json` files, are untouched by this phase (invariant 5) — only the *code path* that
recomputes their numbers moved (`kernel/reproduce.py`'s `offline_fetch_perp_candles`/
`offline_fetch_metrics_history` now import `OhlcvCache` from `data.ohlcv` and `_cache_path`/`_read_cache`
from `data.series`, per Tasks 4-5's mass edits). This task confirms that move was numerically silent.

**Files:**
- None modified — this task runs the existing `tools/research.py reproduce` CLI (built at G3) and records
  the result in this plan, no code change.

**Interfaces:**
- Consumes: `moonface.kernel.reproduce.reproduce`, `tools/research.py`'s `cmd_reproduce_oibuild_study`/
  `cmd_reproduce_liqladder` (both already migrated onto `moonface.data.*` by Tasks 4-6's mass edits, since
  `tools/research.py` was one of the direct `load_bundle` importers in Task 6 and `kernel/reproduce.py` was
  one of the `core.data`/`core.series` importers in Tasks 4-5).

- [ ] **Step 1: Confirm `kernel/reproduce.py`'s imports actually moved**

Run: `grep -n "moonface.core.data\|moonface.core.series" src/moonface/kernel/reproduce.py`
Expected: no output — both lazy imports were rewritten to `moonface.data.ohlcv`/`moonface.data.series` in
Tasks 4-5. If either old path still appears, stop and fix it before running the gate (the gate would
otherwise "pass" without actually exercising this phase's own change).

- [ ] **Step 2: Run the reproduction gate for both lanes**

Run:
```bash
.venv/bin/python tools/research.py reproduce oibuild_study --cache-dir .backtest_cache
.venv/bin/python tools/research.py reproduce liqladder --cache-dir .backtest_cache
```
Expected, matching G3's close exactly: `oibuild_study` prints `REPRODUCED: oibuild_study -- every compared
field matches the recorded verdict.json` and exits 0. `liqladder` prints `DID NOT REPRODUCE: liqladder`
with mismatches on `stouffer_z` and `pooled_mean` only (`k_positive`, `m_assets`, `verdict` must still
match) and exits 1 — the exact same divergence G3 already attributed to the pre-G3 cache-mutation incident
(`docs/findings/BACKTEST_CACHE_MUTATION_2026-08-24.md`), not a new one this phase introduced. **If
`oibuild_study` fails to reproduce, or `liqladder`'s mismatch set differs from exactly `{stouffer_z,
pooled_mean}`, stop** — that is a real regression from this phase's file moves, not the known incident, and
must be root-caused before this task closes.

- [ ] **Step 3: Confirm `.backtest_cache/` was not written to**

Run: `git status .backtest_cache/ cache/` (both are gitignored per G0, so this checks nothing is newly
present that `git status --ignored` would reveal) and, more directly, compare a file listing snapshot taken
before Step 2 against one taken after:
```bash
find .backtest_cache -type f -newer tools/ops/phase_guard_baseline.json
```
Expected: empty output — no cache file was modified by the reproduction run (hard constraint §5.2, and the
exact defect class the pre-G3 incident was).

- [x] **Step 4: Record the result in this plan**

**Executed 2026-08-25** against the worktree's symlinked `.backtest_cache/` (pointing at the main
checkout's frozen cache, read-only for this run):

`oibuild_study`:
```
REPRODUCED: oibuild_study -- every compared field matches the recorded verdict.json
```

`liqladder`:
```
DID NOT REPRODUCE: liqladder
  stouffer_z: recorded=-1.9004349960975828 recomputed=-2.0627555747046387
  pooled_mean: recorded=-0.0006388059072359321 recomputed=-0.0006849522792324151
```
`k_positive`, `m_assets`, and `verdict` were not listed as mismatches, confirming they still match — exactly
the two-field divergence pattern G3's close already attributed to the pre-G3 `.backtest_cache/` mutation
incident, not a new one introduced by this phase's ~150 mechanical import-path edits.
`find .backtest_cache -type f -newer tools/ops/phase_guard_baseline.json` returned empty both before and
after both runs — zero cache writes.

- [ ] **Step 5: Commit**

```bash
git commit --allow-empty -m "test(g4): re-run the G3 reproduction gate after the data-layer move -- risk R6

oibuild_study still reproduces exactly (all six compared fields match).
liqladder still fails to reproduce in exactly the same two fields
(stouffer_z, pooled_mean) for exactly the same already-recorded reason (the
pre-G3 .backtest_cache/ mutation incident) -- not a new divergence
introduced by this phase's file moves. .backtest_cache/ confirmed
untouched by the gate run itself. No code changed in this commit; it
records the gate's post-G4 result as this phase's own evidence."
```

---

### Task 19: Close out — spec doc update, final full-suite verification

**Files:**
- Modify: `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (G4 section — append a "Done"
  note, matching G0-G3's convention)

- [ ] **Step 1: Append the "Done" note under G4's `*Green when:*` line**

```markdown
*Done <run date>:* `data/` stood up with nine domain modules (`ohlcv`, `series`, `bundle`, `http`,
`universe`, `orderbook`, `aggtrades`, `options`, `macro`, `vision` -- ten, correcting this count if it
drifted while writing) consolidating every fetch/cache implementation the spec's G4 paragraph named, plus
the four corrections Task 2 recorded. `core/data.py` and `core/series.py` relocated wholesale (no shim
possible -- test_core_imports_nothing_above_it already forbade it); `core/bundle.py` split, keeping
`DataBundle` as a pure type and moving only `load_bundle`. `research/`'s six remaining fetch/cache modules
(`universe_data`, `aggtrades_data`, orderbook's fetch half, `deribit_dvol`, `fred_data`, `vision_klines`)
kept thin re-export shims at their old paths for their combined ~120 remaining importers, deferring their
rewrite to G6's lane-by-lane conversion. `collect/` filled in with all four domains its G2 scaffold named
(`deribit_chain`, `liquidation`, `bybit_liquidation`, `bybit_positioning`); the two live cron paths
(`tools/deribit_chain_collect.py`, `tools/liquidation_collect.py`) each got a hand-run + row-count check
after their commit, per hard constraint SS5.1. `research/forced_flow/coinm_archive.py` and the two
one-time frozen-lane `tools/collect/` scripts stayed untouched, out of scope per Task 2. The import-boundary
test suite gained two new cases enforcing `data`/`collect`'s one-way dependency on `core` (and, for
`collect`, on `data`). The G3 reproduction gate re-ran clean: `oibuild_study` still reproduces exactly;
`liqladder` still fails to reproduce in exactly the same two fields for exactly the same already-recorded
reason -- confirming this phase's ~150 mechanical import-path edits changed no historical number. Suite
`<final count>`. `models/`, `strategies/`, and `lanes/` do not exist yet -- G5 and G6.
```
Fill in `<run date>` and `<final count>` from the actual execution, not from this plan's estimate.

- [ ] **Step 2: Final full-suite verification**

Run:
```bash
.venv/bin/python -c "import moonface"
.venv/bin/python -m pytest -q -n auto
.venv/bin/python tools/ops/phase_guard.py check
.venv/bin/python tools/deribit_chain_collect.py status
.venv/bin/python tools/liquidation_collect.py status
```
Expected: `2658 passed, 3 skipped`, `GUARD PASS`, both collector `status` calls print without error and
show row counts at or above Task 1's snapshot.

- [ ] **Step 3: Commit**

```bash
git add docs/research-log/specs/2026-08-22-repo-restructure-design.md
git commit -m "docs(g4): phase complete -- data/ and collect/ stood up, reproduction gate re-confirmed clean

data/ consolidates every measured fetch/cache implementation (ten domain
modules); collect/ filled in with all four G2-scaffolded collector
domains, both live cron paths hand-verified. G3's reproduction gate re-ran
identical to its G3 result, closing risk R6. models/, strategies/, and
lanes/ remain for G5 and G6."
```

---

## Self-Review Notes

**Spec coverage:** §4 G4's paragraph ("Consolidate ~20 fetch/cache implementations into data/... OHLCV,
perp candles, funding, OI, orderbook, options/DVOL, liquidations, macro... collect/ writes through the same
layer. Absorbs universe_data, aggtrades_data, orderbook_features' loader, newdata, exogenous/*,
eventtime/vision_klines, forced_flow/coinm_archive, multifamily_loader, regime_{selector,overlay}/data,
foundation/{series,bundle} loaders") — every named module is covered by a task or explicitly scoped out in
Task 2 with a stated reason. "Green when: suite green; no module outside data/ performs a network fetch or
writes a cache; collectors verified by hand; .backtest_cache/ still readable by the G3 gate" — suite-green
checked after every task; the no-fetch-outside-data/collect invariant checked explicitly in Task 16 Step 4
and codified permanently in Task 17; collectors hand-verified in Tasks 13-14 (the two live ones) and
smoke-tested in Task 19; `.backtest_cache/` readability proven by Task 18's gate re-run succeeding at all
(a broken read path would show as a gate crash, not a clean non-reproduction). Risk R6 ("G4 runs the G3
gate again afterwards") is Task 18 directly.

**Placeholder scan:** the one literal placeholder text (`moonface_data_series_FundingCache`) in Task 6 Step
3 is deliberately shown mid-correction, with the very next paragraph replacing it with the real fix and
instructing the executor to produce a clean final file — flagged here so a reviewer does not mistake it for
an oversight; every other task's code blocks are either the actual verbatim content this plan's research
already read in full, or a mechanical grep/sed-verify procedure in the same style G3's own plan used for
its lower-risk migrations (e.g. G3 Task 7's "confirm no external importer" step).

**Type consistency:** `moonface.data.ohlcv.OhlcvCache`/`fetch_history` (Task 4) are the exact names Task 6's
`data/bundle.py` and Task 7's `data/universe.py` import; `moonface.data.series.FundingCache`/
`fetch_funding_history`/`align_funding`/`align_basis`/`METRICS_FIELDS`/`fetch_metrics_history`/
`align_metric` (Task 5) match Task 6's `data/bundle.py` import list exactly; `moonface.data.http.retrying`
(Task 3) matches Task 7's and Task 8's consumption; `moonface.core.bundle.{DataBundle, align_feature,
_check_coverage, FEATURE_COVERAGE_MIN}` (Task 6) match what stays behind for the 78 untouched importers.
