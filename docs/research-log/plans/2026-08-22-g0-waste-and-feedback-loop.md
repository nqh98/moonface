# G0 — Waste and Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reclaim 1.30 GB of nested virtualenvs, protect the three things that look like waste but are evidence, and cut the verification loop from 10 m 52 s to under 60 s — without touching a single import.

**Architecture:** G0 is the only phase of the restructure that changes no Python imports. It does three separable things: builds a reusable guard that asserts the protected assets are intact (every later phase reuses it), removes verified waste, and splits the test suite into a fast loop and a full loop. Nothing here is irreversible beyond `git revert`.

**Tech Stack:** Python 3.11+, stdlib only for the guard (`json`, `pathlib`, `argparse`, `subprocess`). pytest 9.0.3 plus a new `pytest-timeout` dev dependency. No numpy, no pandas.

**Spec:** `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (phase G0, §5 hard constraints)

## Global Constraints

- **Two collectors are live.** `crontab` runs `tools/liquidation_collect.py` and `tools/deribit_chain_collect.py` every minute with hard-coded paths. Their paths must not change. Deribit is ~24 days into a ~150-day clock toward a 2027-01-25 gate; a silent break costs the clock.
- **`.backtest_cache/` and `cache/` are frozen until G6 completes.** They are the deterministic substrate of the G3 reproduction gate. G0 does not touch them despite their size (3.3 GB and 927 MB).
- **Invariant 5: no evidence is deleted.** `recon_hl.py` is a recorded research artifact (named by `docs/research-log/specs/2026-07-07-hyperliquid-aggressor-delta-recon-design.md`). `experiments/microscope/` (186 MB) is research output. `.claude/worktrees/vrp-measure` (220 MB) is a live git worktree on branch `worktree-vrp-measure` at `1be2563`. None may be deleted.
- **Every task ends on a green suite.** Baseline to preserve: `2579 passed, 3 skipped` (652.4 s serial, measured 2026-08-22). From Task 6 onward the full loop is `-n auto` at roughly 2 minutes.
- **Commit style:** lowercase conventional prefix with a scope, e.g. `chore(g0): ...`. **Never** include `Co-Authored-By` or any AI-attribution trailer.
- **Python interpreter:** `.venv/bin/python` (the repo root venv). Never the nested experiment venvs.

---

### Task 1: Phase guard — assert the protected assets are intact

Every later phase's "green when" clause requires proving the collectors still run and the protected paths still exist. Build that check once, here, as a reusable script.

**Files:**
- Create: `tools/ops/__init__.py`
- Create: `tools/ops/phase_guard.py`
- Create: `tools/ops/phase_guard_baseline.json`
- Test: `tests/tools/test_phase_guard.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `missing_paths(root: Path, required: list[str]) -> list[str]` — returns the subset of `required` that does not exist under `root`.
  - `row_count(path: Path) -> int` — number of lines in a CSV, 0 if absent.
  - `check(root: Path, baseline: dict) -> dict` — returns `{"missing": list[str], "shrunk": list[str], "counts": dict[str, int]}`. `shrunk` lists any CSV whose row count is **below** its baseline (growth is expected; shrinkage means data loss).
  - CLI: `python tools/ops/phase_guard.py check` exits 0 when `missing` and `shrunk` are both empty, 1 otherwise. `python tools/ops/phase_guard.py capture` rewrites the baseline.

- [ ] **Step 1: Write the failing test**

Create `tests/tools/test_phase_guard.py`:

```python
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.ops.phase_guard import check, missing_paths, row_count


class TestMissingPaths(unittest.TestCase):
    def test_reports_only_absent_paths(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "present.txt").write_text("x")
            self.assertEqual(
                missing_paths(root, ["present.txt", "gone.txt"]), ["gone.txt"]
            )

    def test_empty_when_all_present(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").mkdir()
            self.assertEqual(missing_paths(root, ["a"]), [])


class TestRowCount(unittest.TestCase):
    def test_counts_lines(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.csv"
            p.write_text("h\n1\n2\n")
            self.assertEqual(row_count(p), 3)

    def test_absent_file_is_zero(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(row_count(Path(tmp) / "nope.csv"), 0)


class TestCheck(unittest.TestCase):
    def _baseline(self, counts=None):
        return {
            "required_paths": ["keep.txt"],
            "csv_row_floor": counts or {},
        }

    def test_passes_when_intact(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "keep.txt").write_text("x")
            (root / "data.csv").write_text("a\nb\n")
            result = check(root, self._baseline({"data.csv": 2}))
            self.assertEqual(result["missing"], [])
            self.assertEqual(result["shrunk"], [])

    def test_flags_deleted_protected_path(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = check(root, self._baseline())
            self.assertEqual(result["missing"], ["keep.txt"])

    def test_growth_is_not_shrinkage(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "keep.txt").write_text("x")
            (root / "data.csv").write_text("a\nb\nc\n")
            result = check(root, self._baseline({"data.csv": 2}))
            self.assertEqual(result["shrunk"], [])
            self.assertEqual(result["counts"]["data.csv"], 3)

    def test_flags_shrunk_csv(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "keep.txt").write_text("x")
            (root / "data.csv").write_text("a\n")
            result = check(root, self._baseline({"data.csv": 2}))
            self.assertEqual(result["shrunk"], ["data.csv"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/tools/test_phase_guard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.ops'`

- [ ] **Step 3: Create the package and implementation**

Create `tools/ops/__init__.py` as an empty file.

Create `tools/ops/phase_guard.py`:

```python
"""Assert that assets the restructure must not damage are still intact.

Every phase of the restructure ends with a "green when" clause that requires
proving the live collectors still append and the protected paths still exist.
This is that check, in one place, so each phase reuses it instead of
reinventing it.

Growth in a collector CSV is expected -- cron appends every minute. Only
shrinkage is a failure, because it means data was lost.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASELINE_PATH = Path(__file__).resolve().parent / "phase_guard_baseline.json"
REPO_ROOT = Path(__file__).resolve().parents[2]


def missing_paths(root: Path, required: list[str]) -> list[str]:
    """Return the subset of ``required`` that does not exist under ``root``."""
    return [rel for rel in required if not (root / rel).exists()]


def row_count(path: Path) -> int:
    """Line count of a CSV; 0 when the file is absent."""
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def check(root: Path, baseline: dict) -> dict:
    """Compare the tree at ``root`` against ``baseline``.

    Returns ``{"missing": [...], "shrunk": [...], "counts": {...}}``.
    """
    missing = missing_paths(root, baseline.get("required_paths", []))
    counts: dict[str, int] = {}
    shrunk: list[str] = []
    for rel, floor in baseline.get("csv_row_floor", {}).items():
        n = row_count(root / rel)
        counts[rel] = n
        if n < floor:
            shrunk.append(rel)
    return {"missing": missing, "shrunk": shrunk, "counts": counts}


def _load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text())


def _cmd_check(_args) -> int:
    result = check(REPO_ROOT, _load_baseline())
    for rel in result["missing"]:
        print(f"MISSING  {rel}", file=sys.stderr)
    for rel in result["shrunk"]:
        print(f"SHRUNK   {rel} -> {result['counts'][rel]} rows", file=sys.stderr)
    for rel, n in sorted(result["counts"].items()):
        print(f"ok       {rel} {n} rows")
    failed = bool(result["missing"] or result["shrunk"])
    print("GUARD FAIL" if failed else "GUARD PASS")
    return 1 if failed else 0


def _cmd_capture(_args) -> int:
    baseline = _load_baseline()
    counts = {
        rel: row_count(REPO_ROOT / rel)
        for rel in baseline.get("csv_row_floor", {})
    }
    baseline["csv_row_floor"] = counts
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    print(f"captured {len(counts)} row floors")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify protected assets").set_defaults(fn=_cmd_check)
    sub.add_parser("capture", help="rewrite row floors from disk").set_defaults(fn=_cmd_capture)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `tools/ops/phase_guard_baseline.json`:

```json
{
  "required_paths": [
    ".backtest_cache",
    "cache",
    "experiments/microscope/features.csv",
    "experiments/microscope/states.csv",
    "experiments/newdata/deribit_chain/chain_BTC.csv",
    "experiments/newdata/liquidations/liq_BTCUSDT.csv",
    "docs/research-log/specs/2026-08-22-repo-restructure-design.md",
    "tools/liquidation_collect.py",
    "tools/deribit_chain_collect.py"
  ],
  "csv_row_floor": {
    "experiments/newdata/deribit_chain/chain_BTC.csv": 0,
    "experiments/newdata/liquidations/liq_BTCUSDT.csv": 0
  }
}
```

Note `recon_hl.py` is deliberately absent from `required_paths` — Task 4 moves it, and Task 4 adds it back at its new path.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/tools/test_phase_guard.py -v`
Expected: PASS — 8 tests

- [ ] **Step 5: Capture the real baseline and confirm the guard passes**

Run:
```bash
.venv/bin/python tools/ops/phase_guard.py capture
.venv/bin/python tools/ops/phase_guard.py check
```
Expected: `captured 2 row floors`, then a list of `ok` lines and `GUARD PASS`, exit 0.

Sanity-check the captured numbers are non-trivial — Deribit should be in the hundreds of thousands of rows, liquidations in the thousands. If either is 0, **stop**: the collectors are not writing and that is a live incident, not a restructure problem.

- [ ] **Step 6: Commit**

```bash
git add tools/ops/__init__.py tools/ops/phase_guard.py tools/ops/phase_guard_baseline.json tests/tools/test_phase_guard.py
git commit -m "chore(g0): phase guard asserts protected assets survive each phase

Every phase of the restructure has to prove the live collectors still append
and the protected paths still exist. This is that check in one place.

Growth in a collector CSV is expected -- cron appends every minute -- so only
shrinkage fails. The baseline records row floors, not exact counts."
```

---

### Task 2: Stop nested virtualenvs from being tracked, then delete them

Order matters: the ignore rule lands first so nothing re-enters the index while the deletion is in flight.

**Files:**
- Modify: `.gitignore`
- Delete: `experiments/{vol_compression,macro_regime,tda_topology,session_sweeps,capitulation}/.venv`

**Interfaces:**
- Consumes: `tools/ops/phase_guard.py` from Task 1.
- Produces: nothing importable.

- [ ] **Step 1: Confirm none of the five venvs is tracked**

Run: `git ls-files experiments | grep '\.venv/' | head`
Expected: no output. If there **is** output, stop — tracked venv files change the deletion from a filesystem operation into a history question, which is out of scope for G0.

- [ ] **Step 2: Record the exact reclaim figure before deleting**

Run:
```bash
find experiments -maxdepth 2 -type d -name .venv -exec du -sb {} \; \
  | awk '{s+=$1} END {printf "%.2f GB across %d venvs\n", s/1024/1024/1024, NR}'
```
Expected: `1.30 GB across 5 venvs`. If the count is not 5, re-read the spec's G0 section — the inventory was already corrected once.

- [ ] **Step 3: Add the ignore rule**

In `.gitignore`, the existing `.venv/` entry only matches at the root. Replace that line:

```diff
-.venv/
+.venv/
+# nested per-experiment venvs (1.30 GB reclaimed in G0); never track, never commit
+**/.venv/
```

- [ ] **Step 4: Verify the rule covers all five before deleting anything**

Run:
```bash
for d in vol_compression macro_regime tda_topology session_sweeps capitulation; do
  git check-ignore -q "experiments/$d/.venv" && echo "ignored: $d" || echo "NOT IGNORED: $d"
done
```
Expected: five `ignored:` lines. Any `NOT IGNORED` line means stop and fix the pattern first.

- [ ] **Step 5: Delete the five virtualenvs**

Run:
```bash
find experiments -maxdepth 2 -type d -name .venv -print -exec rm -rf {} +
```
Expected: five paths printed.

- [ ] **Step 6: Verify nothing protected was touched and the suite is green**

Run:
```bash
.venv/bin/python tools/ops/phase_guard.py check
.venv/bin/python -m pytest -q
```
Expected: `GUARD PASS`, then `2579 passed, 3 skipped`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore
git commit -m "chore(g0): drop five nested experiment virtualenvs, 1.30 GB

experiments/{vol_compression,macro_regime,tda_topology,session_sweeps,
capitulation} each carried its own .venv. None was tracked. The root .gitignore
only matched .venv/ at the top level, so **/.venv/ now covers the nested case
and they cannot come back.

Deliberately untouched: experiments/microscope (186 MB) is research output, not
a venv -- an earlier draft of the spec miscounted it as the sixth."
```

---

### Task 3: Remove the root bytecode cache and two empty agent directories

**Files:**
- Delete: `__pycache__/`, `.agents/`, `.codex/`

**Interfaces:**
- Consumes: `tools/ops/phase_guard.py` from Task 1.
- Produces: nothing importable.

- [ ] **Step 1: Confirm the two directories are genuinely empty**

Run: `find .agents .codex -mindepth 1 | wc -l`
Expected: `0`. Any non-zero result means they hold configuration — stop and inspect rather than delete.

- [ ] **Step 2: Confirm the root `__pycache__` holds only conftest bytecode**

Run: `ls __pycache__/`
Expected: only `conftest.cpython-*.pyc` entries. Anything else, inspect first.

- [ ] **Step 3: Delete**

Run: `rm -rf __pycache__ .agents .codex`

- [ ] **Step 4: Verify**

Run:
```bash
.venv/bin/python tools/ops/phase_guard.py check
.venv/bin/python -m pytest -q
```
Expected: `GUARD PASS`, then `2579 passed, 3 skipped`.

`__pycache__/` is already in `.gitignore`, so `git status` should show no change from its removal.

- [ ] **Step 5: Commit**

```bash
git commit --allow-empty -m "chore(g0): remove root bytecode cache and two empty agent directories

.agents/ and .codex/ were verified empty (find -mindepth 1 returned nothing).
__pycache__/ at the repo root held only conftest bytecode and is already
ignored, so this commit records the removal rather than carrying a diff."
```

---

### Task 4: Preserve `recon_hl.py` as an artifact instead of deleting it

An earlier draft of the spec listed this file as stray. It is not: `docs/research-log/specs/2026-07-07-hyperliquid-aggressor-delta-recon-design.md` names it as that lane's artifact, and `experiments/newdata/FREE_DATA_FEASIBILITY_bybit_trades.md` calls it the working keyless probe. Invariant 5 forbids deleting it. It moves to `tools/`, where the stablecoin-peg spec already refers to it as `tools/recon_hl.py`.

**Files:**
- Move: `recon_hl.py` → `tools/recon_hl.py`
- Modify: `tools/ops/phase_guard_baseline.json`
- Modify: `docs/research-log/specs/2026-07-07-hyperliquid-aggressor-delta-recon-design.md:5`
- Modify: `experiments/newdata/FREE_DATA_FEASIBILITY_bybit_trades.md:142-144`

**Interfaces:**
- Consumes: `tools/ops/phase_guard_baseline.json` from Task 1.
- Produces: `tools/recon_hl.py` at its new path, registered in the guard baseline.

- [ ] **Step 1: Confirm nothing imports it**

Run: `grep -rn "import recon_hl\|from recon_hl" --include=*.py . | grep -v '\.claude/worktrees'`
Expected: no output. It is a standalone probe script, so the move cannot break an import.

- [ ] **Step 2: Move it with git so history follows**

Run: `git mv recon_hl.py tools/recon_hl.py`

- [ ] **Step 3: Register the new path in the guard so no later phase can lose it**

In `tools/ops/phase_guard_baseline.json`, add `"tools/recon_hl.py"` to `required_paths`, keeping the list alphabetically sorted:

```diff
     "docs/research-log/specs/2026-08-22-repo-restructure-design.md",
     "tools/liquidation_collect.py",
-    "tools/deribit_chain_collect.py"
+    "tools/deribit_chain_collect.py",
+    "tools/recon_hl.py"
   ],
```

- [ ] **Step 4: Update the two documents that say "repo root"**

In `docs/research-log/specs/2026-07-07-hyperliquid-aggressor-delta-recon-design.md` line 5, change
`**Artifact:** \`recon_hl.py\` (repo root)` to
`**Artifact:** \`tools/recon_hl.py\` (moved from the repo root in G0, 2026-08-22)`.

In `experiments/newdata/FREE_DATA_FEASIBILITY_bybit_trades.md`, replace the three `recon_hl.py` mentions on lines 6, 142 and 144 with `tools/recon_hl.py`. Do not reword the surrounding prose — these are historical records.

- [ ] **Step 5: Verify**

Run:
```bash
.venv/bin/python tools/ops/phase_guard.py check
.venv/bin/python -m pytest -q
```
Expected: `GUARD PASS` including an `ok tools/recon_hl.py` line, then `2579 passed, 3 skipped`.

- [ ] **Step 6: Commit**

```bash
git add tools/recon_hl.py tools/ops/phase_guard_baseline.json \
  docs/research-log/specs/2026-07-07-hyperliquid-aggressor-delta-recon-design.md \
  experiments/newdata/FREE_DATA_FEASIBILITY_bybit_trades.md
git commit -m "chore(g0): keep recon_hl.py as an artifact, move it to tools/

An earlier draft listed this as a stray file at the repo root. It is the named
artifact of the 2026-07-07 hyperliquid aggressor-delta design, and the
bybit-trades feasibility doc calls it the working keyless probe. Invariant 5
puts it out of reach of deletion.

Moved rather than removed, to the path the stablecoin-peg spec already assumed,
with the two referencing documents updated and the new location registered in
the phase guard so no later phase can quietly lose it."
```

---

### Task 5: Truncate the collector log

`watch.log` is 3.2 MB and grows every minute from two cron jobs. It is gitignored, so this is a disk operation only. **Truncate rather than delete** — the cron jobs hold it open with `>>`, and removing the inode mid-append risks losing the current line.

**Files:**
- Truncate: `watch.log`

**Interfaces:**
- Consumes: `tools/ops/phase_guard.py` from Task 1.
- Produces: nothing importable.

- [ ] **Step 1: Keep the last 200 lines as recent operational context, then truncate**

Run:
```bash
tail -200 watch.log > /tmp/watch.tail && cat /tmp/watch.tail > watch.log && rm /tmp/watch.tail
ls -l watch.log
```
Expected: size drops from ~3.2 MB to a few KB.

- [ ] **Step 2: Confirm cron is still appending**

Wait for the next minute boundary, then run:
```bash
sleep 70 && tail -3 watch.log
```
Expected: fresh collector output with a current timestamp. If nothing new appears within two minutes, **stop** — that is a live collector incident (risk R1) and takes priority over the restructure.

- [ ] **Step 3: Verify the collectors did not lose rows**

Run: `.venv/bin/python tools/ops/phase_guard.py check`
Expected: `GUARD PASS`, with row counts equal to or above the Task 1 baseline.

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "chore(g0): truncate watch.log, keeping the last 200 lines

3.2 MB of collector output, appended every minute by two cron jobs. The file is
gitignored so this carries no diff; the commit records the operation and that
cron was confirmed still appending afterwards.

Truncated in place rather than deleted -- the cron jobs hold it open with >>, and
removing the inode mid-append risks losing the line being written."
```

---

### Task 6: Split the suite into a fast loop and a full loop

The full suite is 10 m 52 s (2579 passed, 3 skipped, measured 2026-08-22). Eight later phases each run it repeatedly, so this is the task that makes the rest of the restructure affordable. Marking the slowest tests is not sufficient on its own — see Step 1.

**Files:**
- Modify: `pyproject.toml` (dev extra + `[tool.pytest.ini_options]`)
- Modify: the slowest test files identified in Step 2

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: two commands used by every later phase — fast loop `.venv/bin/python -m pytest -q -m "not slow" -n auto`, full loop `.venv/bin/python -m pytest -q -n auto`.

- [ ] **Step 1: Add `pytest-timeout` and `pytest-xdist`, and declare the marker**

Neither is installed — the environment has only pytest 9.0.3, and `--timeout=120` fails with
`unrecognized arguments`.

In `pyproject.toml`:

```diff
 dev = [
     "pytest>=8.0.0",
+    "pytest-timeout>=2.3.0",
+    "pytest-xdist>=3.6.0",
     "ruff>=0.6.0",
 ]
```

```diff
 [tool.pytest.ini_options]
 testpaths = ["tests"]
+markers = [
+    "slow: over 1s wall clock; excluded from the fast loop via -m 'not slow'",
+]
+# A hang detector, not a budget. The slowest single test measured 70s.
+timeout = 300
```

Then install: `.venv/bin/pip install -e ".[dev]"`

**Why xdist is required and not optional.** The measurement in Step 2 was already taken; marking
the 40 slowest tests removes 570.6 s of 652.4 s but leaves **81.8 s**, which misses the 60 s target
on its own. The machine has 8 cores and the suite is overwhelmingly independent, so parallelism is
what closes the gap. Marking alone is not enough; parallelism alone leaves the fast loop carrying
70 s of MoE report tests on one worker.

- [ ] **Step 2: Confirm the measured distribution (already taken, re-run only if the suite changed)**

Run: `.venv/bin/python -m pytest -q --durations=40`

Measured 2026-08-22 — `2579 passed, 3 skipped in 652.42s`, with the 40 slowest accounting for
570.6 s (87 %):

| Seconds | Test |
|---|---|
| 70.12 | `tests/test_moe_report.py::test_ortho_none_bundle_matches_price_only_verdict` |
| 39.88 | `tests/test_smc_variants.py::FullReversalFlipTest::test_window_cap_ignores_ancient_history` |
| 36.56 | `tests/test_btc_practical_full_cli.py::test_explore_select_validate_end_to_end` |
| 35.11 | `tests/test_moe_report.py::test_report_has_identity_and_frozen_verdict_set` |
| 34.27 | `tests/test_edge_signals.py::SmcContinuationTest::test_ignores_history_beyond_window_cap` |
| 30.79 | `tests/test_btcspec_search_cli.py::test_explore_then_select_then_validate_flow` |
| 25.96 / 24.52 / 23.67 | `tests/test_engine_audit_loo.py` (three tests) |
| 17.76 / 14.95 | `tests/test_engine_audit_report.py` (two tests) |
| 17.69 / 17.48 | `tests/test_smc_decompose.py::CliSmokeTest` (two tests) |
| 15.14 / 14.54 | `tests/test_engine_audit_cli.py` (two tests) |
| 14.95 | `tests/test_moe_report.py::test_synthetic_noise_does_not_pass` |
| 13.01 | `tests/test_btcspec_s2_search_cli.py::test_explore_then_select_then_validate_flow` |
| 11.30 / 8.93 | `tests/test_moe_null_calibration.py` (two tests) |
| 10.94 / 10.93 | `tests/test_engine_audit_conditional.py` (two tests) |
| 7.10 / 5.94 / 3.71 | `tests/test_advval_run.py` (three tests) |
| 6.20 | `tests/test_consolidated_adapters.py::test_playbook_adapter` |
| 5.97 / 5.84 | `tests/test_engine_audit_fit.py` (two tests) |
| 5.34 | `tests/test_probe_cli.py::ProbeCliTest::test_generates_leaderboard_from_cached_data` |
| 5.04 | `tests/test_forced_flow_iid_guard.py::TestForcedFlowIidGuard::test_iid_guard_fails_on_directionless_synthetic_data` |
| 4.07 / 2.68 | `tests/research/test_mtf.py::TestEvaluate` (two tests) |
| 4.01 / 3.83 | `tests/test_v3_eval_report.py` (two tests) |
| 3.79 | `tests/test_v3_evaluate_cli.py::test_cli_runs_and_writes_report` |
| 3.70 | `tests/test_edge_signals.py::RegistryTest::test_every_signal_runs_and_respects_no_lookahead` |
| 3.39 | `tests/test_practical_search_cli.py::test_explore_then_select_then_validate` |
| 3.29 | `tests/test_system_search_cli.py::test_run_writes_result_and_leaderboard` |
| 2.90 | `tests/test_multifamily_loader.py::TestDefaultReaders::test_optional_readers_swallow_missing_files` |
| 2.66 | `tests/test_matrix_causal_pipeline.py::PipelineTest::test_deterministic` |
| 2.66 | `tests/research/practical_full/test_select_validate_full.py::test_select_full_drops_candidate_when_3x_cost_fails` |

- [ ] **Step 3: Mark the slow modules**

Every file in the table above is slow as a whole — none has a fast half worth preserving — so use
the module-level form. Add this as the **first statement after the existing imports** in each of
these 25 files:

```python
import pytest

pytestmark = pytest.mark.slow
```

Files to mark:

```
tests/test_moe_report.py                 tests/test_engine_audit_fit.py
tests/test_smc_variants.py               tests/test_probe_cli.py
tests/test_btc_practical_full_cli.py     tests/test_forced_flow_iid_guard.py
tests/test_edge_signals.py               tests/research/test_mtf.py
tests/test_btcspec_search_cli.py         tests/test_v3_eval_report.py
tests/test_engine_audit_loo.py           tests/test_v3_evaluate_cli.py
tests/test_engine_audit_report.py        tests/test_practical_search_cli.py
tests/test_smc_decompose.py              tests/test_system_search_cli.py
tests/test_engine_audit_cli.py           tests/test_multifamily_loader.py
tests/test_btcspec_s2_search_cli.py      tests/test_matrix_causal_pipeline.py
tests/test_moe_null_calibration.py       tests/research/practical_full/test_select_validate_full.py
tests/test_engine_audit_conditional.py   tests/test_consolidated_adapters.py
tests/test_advval_run.py
```

If a file already imports `pytest`, do not add a second import.

- [ ] **Step 4: Establish that the suite is parallel-safe before relying on xdist**

Several of the marked files are CLI end-to-end tests that write output. If any two write to the same
fixed path, parallelism will produce flaky failures that look like real regressions and will poison
every later phase's verification.

Run the full suite in parallel three times:

```bash
for i in 1 2 3; do .venv/bin/python -m pytest -q -n auto 2>&1 | tail -1; done
```

Expected: `2579 passed, 3 skipped` all three times.

If any run fails or the count differs, **do not paper over it with `-p no:randomly` or reruns.**
Identify the shared path from the failure, and either give the test an isolated `tmp_path` or add
`@pytest.mark.xdist_group(name="<shared-resource>")` to the colliding tests so they land on the same
worker. A test that cannot run beside its neighbours is a defect worth fixing here, while the suite
is still green and no imports have moved.

- [ ] **Step 5: Verify the fast loop clears 60 seconds**

Run: `time .venv/bin/python -m pytest -q -m "not slow" -n auto`
Expected: PASS, wall clock well under 60 s. Arithmetic: 81.8 s of unmarked work across 8 workers.

- [ ] **Step 6: Verify the full loop still passes everything**

Run: `time .venv/bin/python -m pytest -q -n auto`
Expected: `2579 passed, 3 skipped`, roughly 2 minutes rather than 10 m 52 s.

Markers and workers change scheduling, never outcomes. If the total moved, a `pytestmark` landed in
the wrong scope — check that it sits at module level and not inside a class body.

- [ ] **Step 7: Verify the two loops together cover the whole suite**

Run:
```bash
.venv/bin/python -m pytest -q -m "not slow" --collect-only | tail -1
.venv/bin/python -m pytest -q -m "slow" --collect-only | tail -1
```
Expected: the two collected counts sum to 2582 (2579 passed + 3 skipped). A shortfall means a marker
expression is excluding tests from both loops.

- [ ] **Step 8: Record the two loops where the next executor will find them**

Append to `docs/research-log/plans/2026-08-22-g0-waste-and-feedback-loop.md` under this task, and
carry the same two lines into each later phase plan:

```
fast loop (use during a task):   .venv/bin/python -m pytest -q -m "not slow" -n auto
full loop (use to close a task): .venv/bin/python -m pytest -q -n auto
```

*Recorded 2026-08-24, executing this plan:* Task 1 added `tests/tools/test_phase_guard.py` (8
tests) between the plan's baseline measurement and Task 6, so the live totals are `2587 passed,
3 skipped` (not the `2579` quoted above) throughout Tasks 2-7 — arithmetic checks out (2579 + 8).
The 3 skips are collection-time `pytest.importorskip("numpy")` skips in `test_pathsig_forest.py`,
`test_pathsig_rung2.py`, and `test_pathsig_rung2_cli.py`; they never produce collected items, which
is why `--collect-only` sums to 2587 (not 2590) across the fast/slow split — this is full coverage,
not a shortfall. Fast loop measured 43.6s (`2452 passed, 3 skipped`). Full loop `-n auto` measured
~5.3-5.9 min across four runs (318s-357s) on this 8-core machine, not the "roughly 2 minutes"
estimated above -- still a real win over the 10m52s serial baseline, just a smaller one than hoped.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml tests/ docs/research-log/plans/2026-08-22-g0-waste-and-feedback-loop.md
git commit -m "chore(g0): split the suite into a fast loop and a full loop

The full suite is 10m36s. Eight further phases each run it repeatedly, so the
loop cost is what makes or breaks the rest of the restructure.

Tests over 1.0s are marked slow; -m 'not slow' is the fast loop and lands under
60s. pytest-timeout was not installed at all -- it is now a dev dependency, with
a 300s per-test timeout as a hang detector rather than a budget.

Marker selection changes which tests run, never their outcome: the full loop
still reports 2579 passed, 3 skipped."
```

---

### Task 7: Close the phase

**Files:**
- Modify: `docs/research-log/specs/2026-08-22-repo-restructure-design.md` (G0 status line only)

**Interfaces:**
- Consumes: everything above.
- Produces: a verified starting point for G1.

- [ ] **Step 1: Run the phase's full green condition**

Run:
```bash
.venv/bin/python tools/ops/phase_guard.py check
.venv/bin/python -m pytest -q
git worktree list
du -sh .backtest_cache cache experiments/microscope
```

Expected, all four:
- `GUARD PASS`
- `2579 passed, 3 skipped`
- `worktree-vrp-measure` still listed at `1be2563`
- `.backtest_cache` ~3.3 G, `cache` ~927 M, `experiments/microscope` ~186 M — unchanged

- [ ] **Step 2: Confirm the reclaim actually landed**

Run: `find experiments -maxdepth 2 -type d -name .venv | wc -l`
Expected: `0`.

- [ ] **Step 3: Record G0 as done in the spec**

In `docs/research-log/specs/2026-08-22-repo-restructure-design.md`, append one line to the end of the G0 section:

```markdown
*Done 2026-08-22:* 1.30 GB reclaimed; fast loop `-m "not slow"` under 60 s; `recon_hl.py` preserved at `tools/recon_hl.py`; guard at `tools/ops/phase_guard.py` reused by every later phase.
```

- [ ] **Step 4: Commit**

```bash
git add docs/research-log/specs/2026-08-22-repo-restructure-design.md
git commit -m "chore(g0): phase complete -- 1.30 GB reclaimed, verify loop under 60s

Guard passes, full suite still 2579 passed / 3 skipped, and the three protected
assets are untouched: .backtest_cache, cache, experiments/microscope, plus the
vrp-measure worktree at 1be2563.

No import changed in this phase. G1 starts from here."
```

---

## Notes for the executor

**If the guard fails at any point**, stop and read which line failed before doing anything else:
- `MISSING experiments/newdata/...` — a collector output vanished. This is risk R1 and outranks the restructure. Check `crontab -l` and `tail watch.log` before touching anything further.
- `SHRUNK ...` — a collector CSV lost rows. Do not proceed; the Deribit clock may need a human ruling.
- `MISSING .backtest_cache` or `cache` — the G3 reproduction gate has lost its substrate. Restore from the previous commit's working tree before continuing.

**Do not "clean up" anything the plan does not name.** G0's entire lesson, learned twice while writing it, is that things which look like waste in this repo are frequently evidence. If something looks deletable and is not in this plan, note it for the human rather than removing it.
