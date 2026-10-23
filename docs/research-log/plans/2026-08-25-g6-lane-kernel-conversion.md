# G6.1 — Generalized Lane-Kernel Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `tools/research.py`'s two hand-copied `cmd_reproduce_oibuild_study`/`cmd_reproduce_liqladder` functions with one data-driven `tools/lane_registry.py`, add a persisted run-record for every reproduction, and convert 7 more lanes (`calseason`, `macro_event`, `liqrev`, `bab`, `xsection`, `liqprem`, `resrev`) through it — proving the mechanism generalizes before any of the ~77 remaining lanes are attempted.

**Architecture:** A `LaneEntry` dataclass in `tools/lane_registry.py` pairs each lane's existing `run_fn` with its `compare_fields` and a `run_args_builder` (one of three shared builder functions, chosen by the lane's fetcher shape). `tools/research.py`'s `cmd_reproduce` becomes one function that looks up `LANES[args.lane]`, calls the already-existing `kernel.reproduce.reproduce()`, computes the provenance triple generically, and writes `experiments/<lane>/kernel_runs/<run_id>.json`. Three new cache-only offline fetchers (`offline_fetch_daily_klines`, `offline_fetch_funding_rates`, `offline_list_um_perp_symbols`) are added to `kernel/reproduce.py` alongside the two that already exist there.

**Tech Stack:** Python 3, stdlib only (`dataclasses`, `json`, `hashlib`, `csv`, `pathlib`), pytest.

**Spec:** `docs/research-log/specs/2026-08-25-g6-lane-kernel-conversion-design.md` (parent: `docs/research-log/specs/2026-08-22-repo-restructure-design.md` §4, G6)

## Global Constraints

- `kernel/` must never import a lane or `moonface.research` (enforced by `tests/test_import_boundaries.py::test_kernel_imports_neither_models_strategies_nor_a_lane`). All lane-importing code (`lane_registry.py`, the run-args builders) lives in `tools/`, which is outside the checked `src/moonface/` layers.
- `.backtest_cache/` is read-only for every code path this plan adds — every new fetcher follows the existing `offline_fetch_perp_candles`/`offline_fetch_metrics_history` contract: cache-only, zero writes, `[]`/no-fallback on a miss.
- `experiments/<lane>/verdict.json` is never opened for writing by anything in this plan. `kernel/reproduce.py`'s existing one-touch guard on `out_dir` (verified in each lane's `run_fn`) already prevents the scratch run from touching a lane's real directory.
- No `tools/lanes/*.py` file is deleted or has its own `run_fn`/`run_pipeline` modified in this plan, even for a lane whose reproduction matches — deletion is out of scope for G6.1 (design spec §3.4).
- `tools/liquidation_collect.py` and `tools/deribit_chain_collect.py` (the two live cron collectors) are not touched by any task in this plan.
- Full test suite (`pytest`) must be green after every task's commit, not just at the end.

## Corrections against the design spec (found while researching this plan)

1. **Provenance triple is not embedded in 7 of 9 lanes' `run_fn`s.** Only `oibuild_study.run_analysis` and `liqladder.run_analysis` compute `registration_hash`/`data_fingerprint`/`code_hash` themselves (grepped and confirmed — none of `calseason`/`macro_event`/`liqrev`/`bab`/`xsection`/`liqprem`/`resrev` do). The triple is computed generically in `cmd_reproduce` for all 9 lanes uniformly (Task 3), never read from `result.recomputed`.
2. **`liqrev` reclassified B2 → B1.** Its `run_analysis(cfg, fetch_candles, fetch_metric, out_dir)` is the same shape as `oibuild_study`/`liqladder`, not `bab`/`xsection`/`liqprem`/`resrev`'s `run_pipeline`. Bucket B1 is 3 lanes (`calseason`, `macro_event`, `liqrev`), B2 is 4 (`bab`, `xsection`, `liqprem`, `resrev`).
3. **B2's `run_pipeline` needs a third input the design spec's two-fetcher sketch missed: `symbols`.** Its real signature is `run_pipeline(cfg, symbols, fetch_daily, fetch_funding, out_dir)` — `symbols` is a plain list, not a fetch closure, produced in production by `data.universe.list_um_perp_symbols()`, which makes a **live HTTP request** to the Binance Vision S3 listing (no cache-only mode exists today). A new offline substitute, `offline_list_um_perp_symbols(cache_dir)`, is added in Task 1: every symbol with a cached `uni1d_<SYM>.csv` file, sorted — the same cache-glob technique `tools/lanes/oibuild_study.py::candidates_from_caches` already uses. Since `bab`/`xsection`/`liqprem`/`resrev` are all closed/historical lanes, their cache already holds exactly the daily files their original run fetched, so this substitution should reproduce the same `daily` dict without a live call.
4. **`LaneEntry`'s `fetchers` field is replaced with a `run_args_builder` callable**, not a string-keyed tuple of fetcher "kinds." The design spec's sketch (`fetchers: tuple[str, ...]`, e.g. `("daily", "funding")`) can't cleanly express B2's 3-positional-argument shape (`symbols, fetch_daily, fetch_funding`) vs. B1's 1-or-2 (`fetch_candles[, fetch_metric]`). Storing the builder function directly (`Callable[[dict, str, dict], tuple]`, returning exactly `reproduce()`'s `run_args` tuple) handles both arities without special-casing.
5. **`compare_fields` per new lane**, concretely (verified against each lane's actual `verdict.json`, excluding narrative fields `status`/`winner`/`reason`/`generated_utc` per the parent spec's §1.1 — a conclusion is never treated as authoritative):
   - `calseason`: `("assets", "skipped", "cells", "halves")`
   - `macro_event`: `("cells", "candles")`
   - `liqrev`: `("verdict", "stouffer_z", "pooled_mean", "k_positive", "m_assets")` — identical shape to `LIQLADDER_COMPARE_FIELDS`
   - `bab`, `xsection`, `resrev`: `("universe_symbols", "funding_symbols", "constructions")`
   - `liqprem`: `("universe_symbols", "viability_members", "funding_symbols", "constructions")` (one extra field — its pipeline also tracks a viability-filtered universe)
   - B2's own `status` field is excluded even though it's boolean-derived (`closed_positive`/`closed_negative` from `any_pass`), for the same reason B1's `status`/`winner` are excluded — it's a conclusion computed *from* `constructions`, so comparing `constructions` already implies `status` matches; excluding it costs no rigor and keeps the exclusion rule uniform across all 9 lanes.

---

### Task 1: Offline daily-klines, funding-rate, and symbol-listing fetchers

**Files:**
- Modify: `src/moonface/kernel/reproduce.py` (append after `offline_fetch_metrics_history`, before `ReproductionResult`)
- Test: `tests/kernel/test_reproduce.py` (append new test classes)

**Interfaces:**
- Produces: `offline_fetch_daily_klines(symbol: str, start_ms: int, end_ms: int, cache_dir: str) -> list[DailyRow]`, `offline_fetch_funding_rates(symbol: str, start_ms: int, end_ms: int, cache_dir: str) -> list[tuple[int, float]]`, `offline_list_um_perp_symbols(cache_dir: str) -> list[str]` — all three used by Task 5's `_daily_funding_run_args`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/kernel/test_reproduce.py`:

```python
from moonface.kernel.reproduce import (offline_fetch_daily_klines,
                                        offline_fetch_funding_rates,
                                        offline_list_um_perp_symbols)


class TestOfflineFetchDailyKlines:
    def test_returns_empty_list_on_cache_miss_no_network_call(self):
        with TemporaryDirectory() as tmp:
            out = offline_fetch_daily_klines("NOPE", 0, 1_000_000, tmp)
        assert out == []

    def test_reads_and_filters_the_cached_window(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "uni1d_BTCUSDT.csv"
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                for ts in (0, 86_400_000, 172_800_000, 259_200_000):
                    w.writerow([ts, 100.0, 1_000_000.0])
            out = offline_fetch_daily_klines("BTCUSDT", 86_400_000, 259_200_000, tmp)
        assert [r.ts_ms for r in out] == [86_400_000, 172_800_000]


class TestOfflineFetchFundingRates:
    def test_returns_empty_list_on_cache_miss_no_network_call(self):
        with TemporaryDirectory() as tmp:
            out = offline_fetch_funding_rates("NOPE", 0, 1_000_000, tmp)
        assert out == []

    def test_reads_and_filters_the_cached_window(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "unifunding_BTCUSDT.csv"
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                for ts, rate in ((0, 0.0001), (28_800_000, 0.0002), (57_600_000, -0.0001)):
                    w.writerow([ts, rate])
            out = offline_fetch_funding_rates("BTCUSDT", 28_800_000, 57_600_000, tmp)
        assert out == [(28_800_000, 0.0002)]


class TestOfflineListUmPerpSymbols:
    def test_returns_empty_list_when_no_daily_cache_present(self):
        with TemporaryDirectory() as tmp:
            assert offline_list_um_perp_symbols(tmp) == []

    def test_returns_sorted_symbols_from_daily_cache_filenames(self):
        with TemporaryDirectory() as tmp:
            for sym in ("ETHUSDT", "BTCUSDT", "SOLUSDT"):
                (Path(tmp) / f"uni1d_{sym}.csv").write_text("")
            out = offline_list_um_perp_symbols(tmp)
        assert out == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/kernel/test_reproduce.py -v -k "DailyKlines or FundingRates or ListUmPerpSymbols"`
Expected: FAIL with `ImportError: cannot import name 'offline_fetch_daily_klines'`

- [ ] **Step 3: Implement the three offline fetchers**

Insert into `src/moonface/kernel/reproduce.py`, immediately after the existing
`offline_fetch_metrics_history` function (currently ends at line 54) and before the
`ReproductionResult` dataclass:

```python
def offline_fetch_daily_klines(symbol: str, start_ms: int, end_ms: int,
                               cache_dir: str) -> list:
    """Daily rows from .backtest_cache/ only -- no network fallback, no cache
    write, on a cache miss returns []. Same window-filter semantics as
    data.universe.fetch_daily_klines's cache-hit path."""
    from moonface.data.universe import load_daily_cache

    cached = load_daily_cache(cache_dir, symbol)
    if cached is None:
        return []
    return [r for r in cached if start_ms <= r.ts_ms < end_ms]


def offline_fetch_funding_rates(symbol: str, start_ms: int, end_ms: int,
                                cache_dir: str) -> list:
    """Funding (timestamp, rate) pairs from .backtest_cache/ only -- no
    network fallback, no cache write, on a cache miss returns []. Same
    window-filter semantics as data.universe.fetch_funding_rates's
    cache-hit path."""
    import csv

    from moonface.data.universe import _funding_cache_path

    path = _funding_cache_path(cache_dir, symbol)
    if not path.exists():
        return []
    with open(path, newline="") as fh:
        cached = [(int(t), float(r)) for t, r in csv.reader(fh)]
    return [(t, r) for t, r in cached if start_ms <= t < end_ms]


def offline_list_um_perp_symbols(cache_dir: str) -> list:
    """Every symbol with a cached daily-klines file (uni1d_<SYM>.csv),
    sorted -- the offline substitute for data.universe.list_um_perp_symbols,
    which makes a live S3 listing request with no cache-only mode. Valid
    only for lanes whose cache already holds every symbol their original
    run fetched (true for a closed/historical lane's frozen cache)."""
    return sorted(p.stem.removeprefix("uni1d_")
                 for p in Path(cache_dir).glob("uni1d_*.csv"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/kernel/test_reproduce.py -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS, same pass count as before this task plus the 6 new tests, 0 failures

- [ ] **Step 6: Commit**

```bash
git add src/moonface/kernel/reproduce.py tests/kernel/test_reproduce.py
git commit -m "feat(g6): add offline daily-klines/funding/symbol-listing fetchers to the reproduction harness"
```

---

### Task 2: `tools/lane_registry.py` — migrate `oibuild_study`/`liqladder`, generalize `cmd_reproduce`

**Files:**
- Create: `tools/lane_registry.py`
- Modify: `tools/research.py:1-46` (imports, compare-field constants), `tools/research.py:221-286` (delete `cmd_reproduce_oibuild_study`, `cmd_reproduce_liqladder`, rewrite `cmd_reproduce`), `tools/research.py:359-365` (dynamic `choices`)
- Test: `tests/tools/test_lane_registry.py` (new)

**Interfaces:**
- Consumes: nothing from Task 1 yet (this task only touches the 2 lanes already using `_candles_metric_run_args`, which needs no new offline fetcher).
- Produces: `LaneEntry` dataclass, `LANES: dict[str, LaneEntry]`, `_candles_metric_run_args(cfg, cache_dir, series_by_key) -> tuple` — Task 4 reuses `LaneEntry`/`LANES`/this builder for `liqrev` and adds `_candles_run_args`; Task 5 adds `_daily_funding_run_args`.

- [ ] **Step 1: Write the failing test**

Create `tests/tools/test_lane_registry.py`:

```python
from tools.lane_registry import LANES, LaneEntry


def test_oibuild_study_and_liqladder_are_registered():
    # Subset check, not equality: Task 4 and Task 5 append more lanes to this
    # same LANES dict in later commits, and this test must stay green then too.
    assert {"oibuild_study", "liqladder"} <= set(LANES)


def test_each_entry_has_the_expected_shape():
    for name, entry in LANES.items():
        assert isinstance(entry, LaneEntry)
        assert callable(entry.run_fn)
        assert isinstance(entry.compare_fields, tuple) and entry.compare_fields
        assert callable(entry.run_args_builder)
        assert entry.code_paths == (f"tools/lanes/{name}.py",)


def test_candles_metric_run_args_builds_two_callables():
    entry = LANES["oibuild_study"]
    series_by_key: dict = {}
    cfg = {"metrics_field": "sum_open_interest"}
    run_args = entry.run_args_builder(cfg, ".backtest_cache", series_by_key)
    assert len(run_args) == 2
    fetch_candles, fetch_metric = run_args
    assert callable(fetch_candles) and callable(fetch_metric)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_lane_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.lane_registry'`

- [ ] **Step 3: Create `tools/lane_registry.py`**

```python
#!/usr/bin/env python
"""LANES: every lane wired into `tools/research.py reproduce --lane <name>`.

Adding a lane after G6.1 is: confirm its run function's dependency-injection
shape, pick (or write) a run_args_builder that matches it, define
compare_fields (the substantive numeric/structural output fields -- never a
status/winner/reason/generated_utc narrative field; the parent restructure
spec's invariant is that a verdict/conclusion is never treated as
authoritative), and add one LANES entry. No new cmd_reproduce_* function --
tools/research.py's cmd_reproduce is lane-agnostic (see design spec
docs/research-log/specs/2026-08-25-g6-lane-kernel-conversion-design.md)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from moonface.core.provenance import raw_series_fingerprint
from moonface.core.stats import series_fingerprint
from moonface.kernel.reproduce import (offline_fetch_metrics_history,
                                       offline_fetch_perp_candles)
from tools.lanes.liqladder import run_analysis as liqladder_run
from tools.lanes.oibuild_study import run_analysis as oibuild_study_run


@dataclass(frozen=True)
class LaneEntry:
    run_fn: Callable[..., dict]
    compare_fields: tuple[str, ...]
    run_args_builder: Callable[[dict, str, dict], tuple]
    code_paths: tuple[str, ...]


def _candles_metric_run_args(cfg: dict, cache_dir: str,
                             series_by_key: dict) -> tuple:
    interval = cfg.get("interval", "4h")
    field = cfg["metrics_field"]

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    def fetch_metric(sym, start, end):
        raw = offline_fetch_metrics_history(sym, start, end, cache_dir)
        points = [(ts, f[field]) for ts, f in raw if field in f]
        series_by_key[f"{sym}:metric"] = raw_series_fingerprint(points)
        return points

    return (fetch_candles, fetch_metric)


OIBUILD_STUDY_COMPARE_FIELDS = ("verdict", "stouffer_z", "pooled_mean", "p_sign",
                                "k_positive", "m_assets")
LIQLADDER_COMPARE_FIELDS = ("verdict", "stouffer_z", "pooled_mean", "k_positive",
                            "m_assets")

LANES: dict[str, LaneEntry] = {
    "oibuild_study": LaneEntry(oibuild_study_run, OIBUILD_STUDY_COMPARE_FIELDS,
                               _candles_metric_run_args,
                               ("tools/lanes/oibuild_study.py",)),
    "liqladder": LaneEntry(liqladder_run, LIQLADDER_COMPARE_FIELDS,
                           _candles_metric_run_args,
                           ("tools/lanes/liqladder.py",)),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_lane_registry.py -v`
Expected: PASS

- [ ] **Step 5: Rewrite `tools/research.py`'s reproduce machinery to use the registry**

In `tools/research.py`, delete lines 36-37 (the `from moonface.kernel.reproduce import ...`
import — no longer needed directly, `lane_registry` re-exports what's needed) and lines 40-46
(the two `tools.lanes` imports and the two `*_COMPARE_FIELDS` constants). Replace with:

```python
from moonface.kernel.reproduce import reproduce
from tools.lane_registry import LANES
```

Delete the entire `cmd_reproduce_oibuild_study` function (lines 221-248) and the entire
`cmd_reproduce_liqladder` function (lines 251-276). Replace `cmd_reproduce` (lines 279-285) with:

```python
def cmd_reproduce(args: argparse.Namespace) -> None:
    entry = LANES[args.lane]
    reg_path = Path(f"experiments/{args.lane}/registration.json")
    verdict_path = Path(f"experiments/{args.lane}/verdict.json")
    if not reg_path.exists() or not verdict_path.exists():
        sys.exit(f"missing {reg_path} or {verdict_path}")
    cfg = json.loads(reg_path.read_text())
    recorded = json.loads(verdict_path.read_text())

    series_by_key: dict = {}
    run_args = entry.run_args_builder(cfg, args.cache_dir, series_by_key)

    with TemporaryDirectory() as tmp:
        result = reproduce(entry.run_fn, cfg, recorded,
                           compare_fields=entry.compare_fields,
                           scratch_dir=Path(tmp), run_args=run_args)

    if result.matched:
        print(f"REPRODUCED: {args.lane} -- every compared field matches"
              " the recorded verdict.json")
    else:
        print(f"DID NOT REPRODUCE: {args.lane}")
        for field_name, (rec, new) in result.mismatches.items():
            print(f"  {field_name}: recorded={rec!r} recomputed={new!r}")
        sys.exit(1)
```

(The run-record write is deliberately not here yet — Task 3 adds it. This step is
behavior-preserving only.)

Update the `reproduce` subparser (around line 363) from a hardcoded choices tuple to the registry:

```python
    rep2.add_argument("lane", choices=tuple(LANES))
```

- [ ] **Step 6: Update `tests/tools/test_research_cli_divergence.py`-style smoke check**

Append to `tests/tools/test_lane_registry.py`:

```python
def test_research_cli_reproduce_choices_come_from_the_registry():
    import importlib.util
    from pathlib import Path as P

    spec = importlib.util.spec_from_file_location(
        "research_cli_g6", P("tools/research.py"))
    research_cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(research_cli)
    parser = research_cli.build_parser()
    args = parser.parse_args(["reproduce", "liqladder", "--cache-dir", "/unused"])
    assert args.lane == "liqladder"
    assert args.fn is research_cli.cmd_reproduce
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/tools/test_lane_registry.py -v`
Expected: PASS

- [ ] **Step 8: Manually verify behavior preservation against the real cache**

Run both commands and confirm the printed output is identical in substance to what
`cmd_reproduce_oibuild_study`/`cmd_reproduce_liqladder` produced before this task (per the G3
"Done" note: `oibuild_study` REPRODUCED, `liqladder` did NOT reproduce on `stouffer_z`/`pooled_mean`
for the already-recorded cache-mutation reason):

```bash
python tools/research.py reproduce oibuild_study --cache-dir .backtest_cache
python tools/research.py reproduce liqladder --cache-dir .backtest_cache
```

Expected: `oibuild_study` prints `REPRODUCED`; `liqladder` prints `DID NOT REPRODUCE` with exactly
the `stouffer_z`/`pooled_mean` mismatch (exit code 1) — same as before this task. If either output
differs from that prior baseline, the migration introduced a behavior change; stop and investigate
before continuing.

- [ ] **Step 9: Run the full suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add tools/lane_registry.py tools/research.py tests/tools/test_lane_registry.py
git commit -m "refactor(g6): generalize cmd_reproduce into a data-driven lane registry"
```

---

### Task 3: Persist a run record for every reproduction

**Files:**
- Modify: `tools/research.py` (add imports, a `_write_run_record` helper, wire it into `cmd_reproduce`)
- Test: `tests/tools/test_lane_registry.py` (append)

**Interfaces:**
- Consumes: `LANES`, `LaneEntry.code_paths` (Task 2).
- Produces: `experiments/<lane>/kernel_runs/<run_id>.json` on every `reproduce --lane <name>` call, matched or not.

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_lane_registry.py`:

```python
def test_write_run_record_creates_a_kernel_runs_file(tmp_path):
    from tools.research import _write_run_record
    from moonface.kernel.reproduce import ReproductionResult

    result = ReproductionResult(matched=True, mismatches={}, recomputed={"verdict": "x"})
    verdict_path = tmp_path / "verdict.json"
    verdict_path.write_text("{}")
    triple = {"registration_hash": "r", "data_fingerprint": "d", "code_hash": "c"}

    path = _write_run_record("fake_lane", result, verdict_path, triple,
                             kernel_runs_root=tmp_path / "kernel_runs")

    assert path.exists()
    record = __import__("json").loads(path.read_text())
    assert record["lane"] == "fake_lane"
    assert record["matched"] is True
    assert record["mismatches"] == {}
    assert record["compared_against"] == str(verdict_path)
    assert record["registration_hash"] == "r"
    assert record["data_fingerprint"] == "d"
    assert record["code_hash"] == "c"


def test_write_run_record_preserves_mismatches(tmp_path):
    from tools.research import _write_run_record
    from moonface.kernel.reproduce import ReproductionResult

    result = ReproductionResult(matched=False, mismatches={"stouffer_z": (-1.0, -2.0)},
                                recomputed={"verdict": "x"})
    verdict_path = tmp_path / "verdict.json"
    verdict_path.write_text("{}")
    triple = {"registration_hash": "r", "data_fingerprint": "d", "code_hash": "c"}

    path = _write_run_record("fake_lane", result, verdict_path, triple,
                             kernel_runs_root=tmp_path / "kernel_runs")
    record = __import__("json").loads(path.read_text())
    assert record["mismatches"] == {"stouffer_z": [-1.0, -2.0]}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_lane_registry.py -v -k write_run_record`
Expected: FAIL with `ImportError: cannot import name '_write_run_record'`

- [ ] **Step 3: Implement `_write_run_record` and wire it into `cmd_reproduce`**

Add to the top of `tools/research.py` (alongside the existing `import time`): `import datetime as dt`.

Add this import: `from moonface.core.provenance import code_hash, data_fingerprint, registration_hash`.

Add the helper function, placed just above `cmd_reproduce`:

```python
def _write_run_record(lane: str, result, verdict_path: Path, triple: dict,
                      kernel_runs_root: Path | None = None) -> Path:
    run_id = dt.datetime.now(dt.timezone.utc).isoformat(
        timespec="seconds").replace(":", "-")
    out_dir = kernel_runs_root or Path(f"experiments/{lane}/kernel_runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "lane": lane,
        "run_id": run_id,
        "matched": result.matched,
        "mismatches": {k: list(v) for k, v in result.mismatches.items()},
        "compared_against": str(verdict_path),
        **triple,
    }
    path = out_dir / f"{run_id}.json"
    path.write_text(json.dumps(record, indent=2))
    return path
```

In `cmd_reproduce`, insert the record write between the `reproduce(...)` call and the
`if result.matched:` branch:

```python
    triple = {
        "registration_hash": registration_hash(cfg),
        "data_fingerprint": data_fingerprint(series_by_key),
        "code_hash": code_hash(list(entry.code_paths)),
    }
    record_path = _write_run_record(args.lane, result, verdict_path, triple)
    print(f"run record: {record_path}")

    if result.matched:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_lane_registry.py -v`
Expected: PASS

- [ ] **Step 5: Manually verify against the real cache and inspect the written record**

```bash
python tools/research.py reproduce oibuild_study --cache-dir .backtest_cache
cat experiments/oibuild_study/kernel_runs/*.json
```

Expected: the printed `run record: experiments/oibuild_study/kernel_runs/<timestamp>.json` path
exists and its JSON has `matched: true`, `mismatches: {}`, and three non-empty hash strings.
Confirm `experiments/oibuild_study/verdict.json`'s mtime is unchanged (`stat -c %Y
experiments/oibuild_study/verdict.json` before and after) — this run must never write it.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add tools/research.py tests/tools/test_lane_registry.py
git commit -m "feat(g6): persist a kernel_runs/ record for every lane reproduction"
```

---

### Task 4: Convert `calseason`, `macro_event`, `liqrev` (Bucket B1 — zero new adapter)

**Files:**
- Modify: `tools/lane_registry.py` (add `_candles_run_args`, 3 new compare-field constants, 3 new `LANES` entries and imports)
- Test: `tests/tools/test_lane_registry.py` (append)

**Interfaces:**
- Consumes: `LaneEntry`, `_candles_metric_run_args` (Task 2), `offline_fetch_perp_candles` (already imported in Task 2).
- Produces: `_candles_run_args(cfg, cache_dir, series_by_key) -> tuple` — a 1-fetcher variant, for any future candles-only lane.

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_lane_registry.py`:

```python
def test_b1_lanes_registered():
    from tools.lane_registry import LANES
    assert {"calseason", "macro_event", "liqrev"} <= set(LANES)


def test_candles_run_args_builds_one_fetcher():
    from tools.lane_registry import LANES
    entry = LANES["calseason"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({"interval": "4h"}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_lane_registry.py -v -k "calseason or b1_lanes"`
Expected: FAIL — `calseason` not in `LANES`

- [ ] **Step 3: Add the new builder, compare fields, and LANES entries**

In `tools/lane_registry.py`, add imports:

```python
from tools.lanes.calseason import run_analysis as calseason_run
from tools.lanes.liqrev import run_analysis as liqrev_run
from tools.lanes.macro_event import run_analysis as macro_event_run
```

Add the new builder, right after `_candles_metric_run_args`:

```python
def _candles_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    interval = cfg.get("interval", "4h")

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    return (fetch_candles,)
```

Add the three compare-field constants, after `LIQLADDER_COMPARE_FIELDS`:

```python
LIQREV_COMPARE_FIELDS = ("verdict", "stouffer_z", "pooled_mean", "k_positive",
                         "m_assets")
CALSEASON_COMPARE_FIELDS = ("assets", "skipped", "cells", "halves")
MACRO_EVENT_COMPARE_FIELDS = ("cells", "candles")
```

Add the three `LANES` entries, inside the existing dict literal:

```python
    "liqrev": LaneEntry(liqrev_run, LIQREV_COMPARE_FIELDS,
                        _candles_metric_run_args, ("tools/lanes/liqrev.py",)),
    "calseason": LaneEntry(calseason_run, CALSEASON_COMPARE_FIELDS,
                           _candles_run_args, ("tools/lanes/calseason.py",)),
    "macro_event": LaneEntry(macro_event_run, MACRO_EVENT_COMPARE_FIELDS,
                             _candles_run_args, ("tools/lanes/macro_event.py",)),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_lane_registry.py -v`
Expected: PASS, including `test_b1_lanes_registered`

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 6: Manually run all three new lanes against the real cache**

```bash
python tools/research.py reproduce calseason --cache-dir .backtest_cache
python tools/research.py reproduce macro_event --cache-dir .backtest_cache
python tools/research.py reproduce liqrev --cache-dir .backtest_cache
```

Expected: each prints either `REPRODUCED` or `DID NOT REPRODUCE` with a field-level diff — either
outcome is valid and gets recorded (design spec §3.4: never force a match). Record whichever each
one actually reports; do not treat a mismatch as a bug to fix. Confirm a
`experiments/<lane>/kernel_runs/*.json` file now exists for all three, and that none of the three
`verdict.json` files' mtimes changed.

- [ ] **Step 7: Commit**

```bash
git add tools/lane_registry.py tests/tools/test_lane_registry.py
git commit -m "feat(g6): convert calseason, macro_event, liqrev onto the kernel (bucket B1)"
```

---

### Task 5: Convert `bab`, `xsection`, `liqprem`, `resrev` (Bucket B2 — new daily/funding adapter)

**Files:**
- Modify: `tools/lane_registry.py` (add `_daily_funding_run_args`, 4 new compare-field constants, 4 new `LANES` entries and imports)
- Test: `tests/tools/test_lane_registry.py` (append)

**Interfaces:**
- Consumes: `offline_fetch_daily_klines`, `offline_fetch_funding_rates`, `offline_list_um_perp_symbols` (Task 1); `LaneEntry` (Task 2).
- Produces: `_daily_funding_run_args(cfg, cache_dir, series_by_key) -> tuple` — a 3-positional-arg variant (`symbols, fetch_daily, fetch_funding`), for any future `run_pipeline`-shaped lane.

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_lane_registry.py`:

```python
def test_daily_funding_run_args_builds_symbols_list_and_two_fetchers():
    from tools.lane_registry import LANES
    entry = LANES["bab"]
    series_by_key: dict = {}
    with __import__("tempfile").TemporaryDirectory() as tmp:
        from pathlib import Path as P
        (P(tmp) / "uni1d_BTCUSDT.csv").write_text("")
        run_args = entry.run_args_builder({}, tmp, series_by_key)
    symbols, fetch_daily, fetch_funding = run_args
    assert symbols == ["BTCUSDT"]
    assert callable(fetch_daily) and callable(fetch_funding)


def test_all_nine_lanes_registered():
    from tools.lane_registry import LANES
    assert set(LANES) == {
        "oibuild_study", "liqladder", "calseason", "macro_event", "liqrev",
        "bab", "xsection", "liqprem", "resrev",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_lane_registry.py -v -k "daily_funding or all_nine"`
Expected: FAIL — `bab` not in `LANES`

- [ ] **Step 3: Add the new builder, compare fields, and LANES entries**

In `tools/lane_registry.py`, add imports:

```python
from moonface.kernel.reproduce import (offline_fetch_daily_klines,
                                       offline_fetch_funding_rates,
                                       offline_list_um_perp_symbols)
from tools.lanes.bab import run_pipeline as bab_run
from tools.lanes.liqprem import run_pipeline as liqprem_run
from tools.lanes.resrev import run_pipeline as resrev_run
from tools.lanes.xsection import run_pipeline as xsection_run
```

(Merge these into the existing `from moonface.kernel.reproduce import ...` line rather than adding
a second one — keep one import statement per source module.)

Add the new builder, right after `_candles_run_args`:

```python
def _daily_funding_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    symbols = offline_list_um_perp_symbols(cache_dir)

    def fetch_daily(sym, start, end):
        rows = offline_fetch_daily_klines(sym, start, end, cache_dir)
        series_by_key[f"{sym}:daily"] = raw_series_fingerprint(
            [(r.ts_ms, r.close) for r in rows])
        return rows

    def fetch_funding(sym, start, end):
        points = offline_fetch_funding_rates(sym, start, end, cache_dir)
        series_by_key[f"{sym}:funding"] = raw_series_fingerprint(points)
        return points

    return (symbols, fetch_daily, fetch_funding)
```

Add the four compare-field constants, after `MACRO_EVENT_COMPARE_FIELDS`:

```python
BAB_COMPARE_FIELDS = ("universe_symbols", "funding_symbols", "constructions")
XSECTION_COMPARE_FIELDS = ("universe_symbols", "funding_symbols", "constructions")
RESREV_COMPARE_FIELDS = ("universe_symbols", "funding_symbols", "constructions")
LIQPREM_COMPARE_FIELDS = ("universe_symbols", "viability_members",
                          "funding_symbols", "constructions")
```

Add the four `LANES` entries:

```python
    "bab": LaneEntry(bab_run, BAB_COMPARE_FIELDS, _daily_funding_run_args,
                     ("tools/lanes/bab.py",)),
    "xsection": LaneEntry(xsection_run, XSECTION_COMPARE_FIELDS,
                          _daily_funding_run_args, ("tools/lanes/xsection.py",)),
    "liqprem": LaneEntry(liqprem_run, LIQPREM_COMPARE_FIELDS,
                         _daily_funding_run_args, ("tools/lanes/liqprem.py",)),
    "resrev": LaneEntry(resrev_run, RESREV_COMPARE_FIELDS,
                        _daily_funding_run_args, ("tools/lanes/resrev.py",)),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_lane_registry.py -v`
Expected: PASS, including `test_all_nine_lanes_registered`

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 6: Manually run all four new lanes against the real cache**

```bash
python tools/research.py reproduce bab --cache-dir .backtest_cache
python tools/research.py reproduce xsection --cache-dir .backtest_cache
python tools/research.py reproduce liqprem --cache-dir .backtest_cache
python tools/research.py reproduce resrev --cache-dir .backtest_cache
```

Expected: each prints `REPRODUCED` or `DID NOT REPRODUCE` with a diff — record whichever outcome
actually happens (§3.4, never forced). If a mismatch traces to `offline_list_um_perp_symbols`
returning a narrower symbol set than the lane's original live `list_um_perp_symbols()` call saw
(cache pruned since the historical run), that is itself a valid, informative recorded outcome, not
a bug — note it in the commit body if it occurs. Confirm all four `verdict.json` mtimes are
unchanged and a `kernel_runs/*.json` exists for each.

- [ ] **Step 7: Commit**

```bash
git add tools/lane_registry.py tests/tools/test_lane_registry.py
git commit -m "feat(g6): convert bab, xsection, liqprem, resrev onto the kernel (bucket B2)"
```

---

### Task 6: Full-suite verification and phase-complete record

**Files:**
- Modify: `docs/research-log/specs/2026-08-25-g6-lane-kernel-conversion-design.md` (append a "Done" note, matching the G3/G4/G5 convention of recording actual outcomes against the design)

**Interfaces:** none (documentation + verification only).

- [ ] **Step 1: Run the full suite one more time, from a clean state**

Run: `pytest -q`
Expected: PASS, 0 failures. Note the exact pass count for the commit message (matching the
"Suite `2652 passed, 3 skipped`"-style notes in prior phases' Done sections) — do not claim green
without having just run it in this session (per this repo's own G5 retro: a prior "full suite was
green" claim was later found false because it wasn't re-verified after the final commit).

- [ ] **Step 2: Confirm the import-boundary invariant still holds**

Run: `pytest tests/test_import_boundaries.py -v`
Expected: PASS, unmodified — this plan added no new entries to `_KERNEL_RESEARCH_BRIDGES` or any
other bridge dict; `kernel/reproduce.py`'s new functions only import from `moonface.data`, which is
already below `kernel` in the layering.

- [ ] **Step 3: Confirm no `verdict.json` was modified by this phase**

```bash
git status --short experiments/oibuild_study/verdict.json experiments/liqladder/verdict.json \
  experiments/calseason/verdict.json experiments/macro_event/verdict.json \
  experiments/liqrev/verdict.json experiments/bab/verdict.json experiments/xsection/verdict.json \
  experiments/liqprem/verdict.json experiments/resrev/verdict.json
```

Expected: no output (none of these 9 files appear as modified — only new, untracked
`kernel_runs/` directories should show up under `git status`).

- [ ] **Step 4: Confirm the two live collectors are untouched**

```bash
git diff --stat main -- tools/liquidation_collect.py tools/deribit_chain_collect.py
```

Expected: no output.

- [ ] **Step 5: Append the Done note to the design spec**

Edit `docs/research-log/specs/2026-08-25-g6-lane-kernel-conversion-design.md`, adding a `*Done
2026-08-25:*` (or the actual completion date) paragraph after §4's task list, following the exact
style of the parent restructure spec's own G3/G4/G5 Done notes: which of the 9 lanes matched vs.
mismatched (with the specific mismatched fields, if any), the final `pytest -q` pass count, and
explicit confirmation of Steps 2-4 above. State plainly that G6.2 (the remaining `tools/lanes/`
CLI-only files) and G6.3 (the `research/<lane>/` packages) are unscheduled follow-on work, not
committed to by this phase.

- [ ] **Step 6: Commit**

```bash
git add docs/research-log/specs/2026-08-25-g6-lane-kernel-conversion-design.md
git commit -m "docs(g6): phase complete -- 9 lanes reproducible through the generalized registry"
```
