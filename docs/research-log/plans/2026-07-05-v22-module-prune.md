# Confluence Engine v2.2 Module Prune — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v2.2 = v2.1 minus m4_pullback's influence on the trend book (audit-based exclusion), with a with-m4 counterfactual shadow, new engine identity, and a fresh forward registration.

**Architecture:** The exclusion lives at the aggregation layer: `confluence.decide()` filters `EXCLUDED_MODULES` out of the trend book before `_book_context`, so the module is still scored and journaled (`Decision.modules`) but never counts toward score, breadth, or max_attainable. A new `VETO_M4_EXCLUDED` shadow journals when the with-m4 book would have emitted a long under all current policy. `calibration.scoring_pass` mirrors the filter for `BarRow.trend`; the ablation reporter gains an `m4_pullback` family. `ENGINE_VERSION` bumps to "2.2" and both new constants fold into `engine_hash`.

**Tech Stack:** Python 3.12 (repo `.venv`), stdlib only in `src/`, pytest plain functions.

**Spec:** `docs/research-log/specs/2026-07-05-v22-module-prune-design.md`

## Global Constraints

- **Read-only elsewhere:** never modify `journal/`, `promotion/engine.json`, the frozen body of `experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md` (Task 6 prepends a SUPERSEDED addendum only — same precedent as the v2 doc), or the registered calibration/audit reports.
- **stdlib only** in `src/moonface/` — no numpy/scipy.
- **Tests hermetic:** no network, no `.backtest_cache` reads in tests; run as `.venv/bin/python -m pytest <file> -q`. (Task 6's sanity replay is a tool run, not a test — it may read `.backtest_cache`.)
- **Git:** never chain `git add && git commit` — stage, verify `git diff --cached --stat`, then commit. No AI-attribution trailers. Files under `docs/` need `git add -f` (globally gitignored, tracked by repo convention).
- **GitNexus (project CLAUDE.md):** run `gitnexus_impact({target: "<symbol>", direction: "upstream"})` before editing a function/class and report blast radius; run `gitnexus_detect_changes()` before each commit; warn on HIGH/CRITICAL.
- **All frozen-constant values are final in Task 1** — the v2.2 hash is stable from Task 1 onward; later tasks change behavior and docs only.
- **Task 6's replay runs once** (non-gating, house convention); verify the output artifact exists before transcribing numbers into the registration (v2.1 gotcha: a frozen doc once claimed a replay that never ran).

---

### Task 1: v2.2 identity + m4_pullback exclusion in `confluence.decide`

**Files:**
- Modify: `src/moonface/signal/engine/confluence.py` (constants after line 77; `decide()` line 152)
- Modify: `src/moonface/signal/engine/config.py:10` (version) and `config.py:54-78` (frozen-fields registry)
- Test: `tests/test_engine_confluence.py` (new tests + 6 expectation updates)
- Test: `tests/test_engine_config.py` (version test, new hash-fold test)
- Test: `tests/test_engine_calibration_pass.py` (hash pin)

**Interfaces:**
- Produces: `confluence.EXCLUDED_MODULES: tuple[str, ...] = ("m4_pullback",)` and `confluence.VETO_M4_EXCLUDED: str = "v2.2 m4_pullback excluded"` — consumed by Tasks 2, 3, 4. `decide()` signature unchanged; trend book score/breadth/max_attainable now exclude m4_pullback. `ENGINE_VERSION = "2.2"`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_engine_confluence.py`:

```python
# --- v2.2: m4_pullback exclusion (spec 2026-07-05) ---------------------------

def test_m4_pullback_points_do_not_count_toward_score_or_breadth():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 15),
        _m("m3_roc", 1, 10),
        _m("m4_pullback", 1, 10),
    ]  # counted 45 / breadth 3; even with m4 it is 55 < 60, so the Task-2
    #    exclusion shadow can never fire here (assertions stable across tasks)
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.score == 45
    assert d.breadth == 3
    assert d.veto is None
    # the module is still scored and journaled via Decision.modules
    assert any(m.module == "m4_pullback" and m.points == 10
               for m in d.modules)


def test_max_attainable_excludes_m4():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m2_ma_align", 1, 10),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 15),
        _m("m5_funding", 1, 15),
    ]
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.score == 85           # 100 signed minus m4's 15
    assert d.max_attainable == 85  # m4's 15 is no longer attainable
```

- [ ] **Step 2: Update the six existing tests whose expectations change** (m4 points no longer count) in `tests/test_engine_confluence.py`:

  - `test_bear_vetoes_trend_long` (line 43): `assert d.shadow_score == 80` → `assert d.shadow_score == 60`
  - `test_bear_vetoes_mean_revert_short` (line 58): `assert d.shadow_score == 80` → `assert d.shadow_score == 60`
  - `test_trend_wins_when_revert_candidate_is_vetoed` (line 181): `assert d.score == 70` → `assert d.score == 60` (the `shadow_score == 80` on line 183 stays — it is the revert book's NO_CT shadow, which has no m4)
  - `test_trend_short_vetoed_long_only` (line 197): `assert d.shadow_score == 80` → `assert d.shadow_score == 60`
  - `test_degraded_ceiling_drops_max_attainable` (line 224): `assert d.max_attainable == 85` → `assert d.max_attainable == 70`
  - `test_degraded_ceiling_still_uses_absolute_threshold` (line 240): `assert d.max_attainable == 85` → `assert d.max_attainable == 70`

  Update the inline `# score = …` comments on those fixtures to note the counted (ex-m4) values.

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_confluence.py -q`
Expected: FAIL — the two new tests fail on `d.score`/`max_attainable` (m4 still counts), and the six updated tests fail on the new expectations.

- [ ] **Step 4: Implement in `src/moonface/signal/engine/confluence.py`** — add after line 77 (`VETO_LONG_ONLY = …`):

```python
# --- v2.2 module prune (spec 2026-07-05) -------------------------------------
# Audit-based exclusion: m4_pullback is LOO-HARMFUL in both stages of the
# 2026-07 scoring audit (experiments/engine/SCORING_AUDIT_2026-07.md). The
# module is still scored and journaled; it no longer counts toward score,
# breadth, or max_attainable. The with-m4 counterfactual journals as a
# VETO_M4_EXCLUDED shadow so the horizon ablation can test the exclusion.
EXCLUDED_MODULES = ("m4_pullback",)
VETO_M4_EXCLUDED = "v2.2 m4_pullback excluded"
```

and in `decide()`, replace line 152:

```python
    trend_ctx = _book_context("trend", trend_scores, _TREND_MAX, macro_effective)
```

with:

```python
    trend_counted = [m for m in trend_scores
                     if m.module not in EXCLUDED_MODULES]
    trend_ctx = _book_context("trend", trend_counted, _TREND_MAX,
                              macro_effective)
```

(`Decision.modules` keeps `all_modules` — m4 stays journaled. `revert_scores` are untouched: `EXCLUDED_MODULES` names no revert module.)

- [ ] **Step 5: Register the new constants and bump the version in `src/moonface/signal/engine/config.py`** — without this, `_frozen_constants_payload` raises `frozen constant drift` and every `engine_hash` call fails:

  - Line 10: `ENGINE_VERSION = "2.1"` → `ENGINE_VERSION = "2.2"`
  - In `_FROZEN_FIELDS_BY_MODULE["confluence"]` (lines 55-78), add two entries to the tuple, keeping it readable:

```python
        "VETO_LONG_ONLY",
        "VETO_NO_CT",
        "VETO_M4_EXCLUDED",
        "EXCLUDED_MODULES",
```

- [ ] **Step 6: Run the confluence tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_confluence.py -q`
Expected: PASS (all tests in the file)

- [ ] **Step 7: Compute the v2.2 frozen hash**

Run: `.venv/bin/python -c "from moonface.signal.engine.config import EngineConfig, engine_hash; print(engine_hash(EngineConfig()))"`
Expected: a 64-hex digest, different from `4e35561fe6b7d639712e10f8b87d78b5cf0a6d629d9ccc2cac8d605909305a6a`. Record it — it is pasted into the test in Step 8 and into the registration in Task 6.

- [ ] **Step 8: Update the identity tests**

In `tests/test_engine_config.py`, replace `test_engine_version_is_v21` (line ~51):

```python
def test_engine_version_is_v22():
    assert engine_config.ENGINE_VERSION == "2.2"
```

and append:

```python
def test_hash_folds_excluded_modules(monkeypatch):
    # v2.2: the exclusion tuple is part of the frozen identity — changing it
    # must change the hash (and therefore reset the journal record).
    from moonface.signal.engine import confluence
    cfg = EngineConfig()
    baseline = engine_hash(cfg)
    monkeypatch.setattr(confluence, "EXCLUDED_MODULES", ())
    assert engine_hash(cfg) != baseline
```

In `tests/test_engine_calibration_pass.py`, next to `V21_FROZEN_HASH` (line 19) add the Step-7 digest:

```python
V22_FROZEN_HASH = "<paste the Step-7 digest here>"
```

and replace the test at ~line 44 that asserts `h == V21_FROZEN_HASH` with:

```python
def test_engine_hash_matches_v22_frozen_identity():
    h = engine_hash(EngineConfig())
    assert h != V2_FROZEN_HASH
    assert h != V21_FROZEN_HASH
    assert h == V22_FROZEN_HASH
```

- [ ] **Step 9: Run the touched suites**

Run: `.venv/bin/python -m pytest tests/test_engine_confluence.py tests/test_engine_config.py tests/test_engine_calibration_pass.py -q`
Expected: PASS, zero failures

- [ ] **Step 10: Commit**

```bash
git add src/moonface/signal/engine/confluence.py src/moonface/signal/engine/config.py tests/test_engine_confluence.py tests/test_engine_config.py tests/test_engine_calibration_pass.py
git diff --cached --stat
git commit -m "feat(engine): v2.2 — m4_pullback excluded from trend scoring (audit-based), new frozen identity"
```

---

### Task 2: `VETO_M4_EXCLUDED` exclusion shadow in `decide()`

**Files:**
- Modify: `src/moonface/signal/engine/confluence.py` (`decide()`, after the v2.1 policy block at lines ~157-166)
- Test: `tests/test_engine_confluence.py` (append)

**Interfaces:**
- Consumes: `EXCLUDED_MODULES`, `VETO_M4_EXCLUDED`, `_book_context` (Task 1).
- Produces: decisions where the with-m4 trend book would have emitted a LONG under all current policy but the counted book does not now carry `veto=VETO_M4_EXCLUDED`, `shadow_score`/`shadow_direction` from the with-m4 book. Existing veto precedence (macro, long-only) wins over the m4 shadow. Task 4's ablation family and Task 6's registration rely on this exact label.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_engine_confluence.py` (extend the file's confluence import with `VETO_M4_EXCLUDED`):

```python
def test_m4_exclusion_shadow_journals_when_full_book_would_fire():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 10),
        _m("m4_pullback", 1, 15),
    ]  # counted 50 -> WAIT; with m4: 65, breadth 4, NEUTRAL ALLOW -> v2.1 valid
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.score == 50
    assert d.veto == VETO_M4_EXCLUDED
    assert d.shadow_score == 65
    assert d.shadow_direction == 1


def test_no_m4_shadow_when_counted_book_fires():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 15),
    ]  # counted 60 -> SETUP; the exclusion changed nothing gate-relevant
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.score == 60
    assert d.veto is None


def test_m4_shadow_not_journaled_for_full_short():
    trend = [
        _m("m1_macro", -1, 20),
        _m("m2_breakout", -1, 20),
        _m("m3_roc", -1, 10),
        _m("m4_pullback", -1, 15),
    ]  # counted short 50 (not valid, so no long-only veto); with m4 the short
    #    would clear 60 — but long-only policy blocks the counterfactual too
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.veto is None
    assert d.shadow_score is None


def test_m4_shadow_yields_to_macro_veto():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 15),
    ]  # counted 60 >= 60, breadth 3 — BEAR REJECT macro-veto fires first
    d = decide(trend, [], _macro("BEAR"), _cfg())
    assert d.action == "WAIT"
    assert d.veto is not None and d.veto.startswith("macro")
    assert d.shadow_score == 60   # counted score, per the live macro family
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_confluence.py -q`
Expected: FAIL — `ImportError: cannot import name 'VETO_M4_EXCLUDED'` is already satisfied (Task 1 defined it), so the first and fourth tests fail on `d.veto` being `None`/shadow fields empty.

- [ ] **Step 3: Implement** — in `decide()`, insert after the v2.1 long-only block (after line ~166, before `veto = trend_ctx["veto"] or revert_ctx["veto"]`):

```python
    # v2.2: m4_pullback exclusion shadow. If the with-m4 book (v2.1 scoring)
    # would have emitted a trend candidate under ALL current policy (gate via
    # _book_context, long-only via direction > 0) while the counted book does
    # not, journal the counterfactual. Existing vetoes take precedence.
    if not trend_ctx["valid"] and trend_ctx["veto"] is None:
        trend_full = _book_context("trend", trend_scores, _TREND_MAX,
                                   macro_effective)
        if trend_full["valid"] and trend_full["direction"] > 0:
            trend_ctx["veto"] = VETO_M4_EXCLUDED
            trend_ctx["shadow_score"] = trend_full["score"]
            trend_ctx["shadow_direction"] = trend_full["direction"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_confluence.py -q`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the engine-evaluate suite as a smoke check** (the shadow flows through `evaluate_engine`'s decision handling; `engine.py` needs no change — only `VETO_LONG_ONLY` drives reversal exits)

Run: `.venv/bin/python -m pytest tests/test_engine_evaluate.py tests/test_engine_setupcard.py -q`
Expected: PASS (if a failure appears, stop and apply Task 5's decision rules early rather than patching blind)

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/confluence.py tests/test_engine_confluence.py
git diff --cached --stat
git commit -m "feat(engine): v2.2 m4_pullback exclusion shadow (with-m4 counterfactual journals as veto)"
```

---

### Task 3: Calibration mirror — `BarRow.trend` excludes m4

**Files:**
- Modify: `src/moonface/signal/engine/calibration.py` (`scoring_pass`, line ~112; confluence import at top)
- Test: `tests/test_engine_calibration_pass.py` (append)

**Interfaces:**
- Consumes: `confluence.EXCLUDED_MODULES` (Task 1).
- Produces: `scoring_pass` rows whose `trend: BookState` is computed over the counted (ex-m4) book, mirroring the live engine; `module_points` still carries all 12 modules including m4. Any future calibration/audit run at the v2.2 hash inherits v2.2 semantics. The registered 2026-07 reports at hash `4e35561f…` are historical and are NOT re-run.

- [ ] **Step 1: Write the failing test** — append to `tests/test_engine_calibration_pass.py` (add `from moonface.signal.engine.calibration import _TREND_MODULES` and `from moonface.signal.engine.confluence import EXCLUDED_MODULES` and `from moonface.signal.engine.modules.base import ModuleScore` to the imports if not present):

```python
def test_book_state_excludes_m4_pullback(monkeypatch):
    # Force m4_pullback to a nonzero score on every bar: the BarRow trend
    # BookState must mirror the live engine and leave it uncounted, while
    # module_points still journals it.
    candles = _walk_series(430, seed=29)
    cfg = _cfg()
    original = trend_book.score

    def forced(views, macro, deriv, c):
        out = []
        for m in original(views, macro, deriv, c):
            if m.module == "m4_pullback":
                m = ModuleScore(module="m4_pullback", direction=1, points=15,
                                archetype=m.archetype, data_ok=True,
                                evidence=("forced",))
            out.append(m)
        return out

    monkeypatch.setattr(trend_book, "score", forced)
    rows = scoring_pass(cfg, candles, warmup=380)
    counted = [m for m in _TREND_MODULES if m not in EXCLUDED_MODULES]
    assert counted == ["m1_macro", "m2_breakout", "m2_ma_align",
                       "m3_roc", "m5_funding"]
    for row in rows:
        assert row.module_points["m4_pullback"] == 15
        signed = sum(row.module_points[m] for m in counted)
        assert row.trend.score == abs(signed)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_pass.py::test_book_state_excludes_m4_pullback -q`
Expected: FAIL — `row.trend.score` includes the forced 15 points

- [ ] **Step 3: Implement** — in `src/moonface/signal/engine/calibration.py`, extend the existing `from moonface.signal.engine.confluence import …` line with `EXCLUDED_MODULES`, and change line ~112 in `scoring_pass`:

```python
        t_state = _book_state(trend_scores, "trend", macro_eff)
```

to:

```python
        t_state = _book_state(
            [m for m in trend_scores if m.module not in EXCLUDED_MODULES],
            "trend", macro_eff)
```

(`r_state` and `module_points` are untouched — the map keeps all 12 modules.)

- [ ] **Step 4: Run the calibration and audit suites to verify pass + no regression**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_pass.py tests/test_engine_calibration_sim.py tests/test_engine_calibration_stats.py tests/test_engine_calibration_report.py tests/test_engine_calibration_cli.py tests/test_engine_audit_stats.py tests/test_engine_audit_loo.py tests/test_engine_audit_conditional.py tests/test_engine_audit_fit.py tests/test_engine_audit_report.py -q`
Expected: PASS (the audit tests build their own synthetic rows and are unaffected; the decision-parity test passes because both sides share `decide`)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/calibration.py tests/test_engine_calibration_pass.py
git diff --cached --stat
git commit -m "feat(engine): calibration BarRow trend state mirrors v2.2 m4 exclusion"
```

---

### Task 4: Ablation family `m4_pullback`

**Files:**
- Modify: `src/moonface/signal/engine/ablation.py` (`veto_family`, line ~55; confluence import line 7)
- Test: `tests/test_engine_ablation.py` (append)

**Interfaces:**
- Consumes: `confluence.VETO_M4_EXCLUDED` (Task 1).
- Produces: `veto_family(VETO_M4_EXCLUDED) == "m4_pullback"`; `gate_ablation` groups those shadows under `families["m4_pullback"]` and replays them with the WT profile (the existing `profile = "CT" if family == "no_ct" else "WT"` rule already does this — no replay change).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_engine_ablation.py` (extend its confluence import with `VETO_M4_EXCLUDED`; the file already defines `_family_entry` and imports `EngineConfig`, `engine_hash`, `gate_ablation`, `veto_family`):

```python
def test_veto_family_m4_exclusion():
    assert veto_family(VETO_M4_EXCLUDED) == "m4_pullback"


def test_gate_ablation_groups_m4_family():
    cfg = EngineConfig()
    version = engine_hash(cfg)
    entries = [_family_entry(3_600_000, VETO_M4_EXCLUDED, 1, version)]
    report = gate_ablation(entries, [], cfg)
    fam = report["families"]["m4_pullback"]
    assert fam["n_vetoed"] == 1
    assert fam["shadow_scores"]["count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_ablation.py -q`
Expected: FAIL — `veto_family(VETO_M4_EXCLUDED)` returns `"other"`

- [ ] **Step 3: Implement** — in `src/moonface/signal/engine/ablation.py`, extend the line-7 import to include `VETO_M4_EXCLUDED`, and in `veto_family` add before the `startswith("macro")` check:

```python
    if text == VETO_M4_EXCLUDED:
        return "m4_pullback"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_ablation.py tests/test_engine_ablation_cli.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/ablation.py tests/test_engine_ablation.py
git diff --cached --stat
git commit -m "feat(engine): ablation family m4_pullback for v2.2 exclusion shadows"
```

---

### Task 5: Full-suite sweep

**Files:**
- Modify: only test files that fail under the rules below (expected candidates: `tests/test_engine_evaluate.py`, `tests/test_engine_cli.py`, watch/daemon tests — anything that drives real scorers over synthetic candles and asserts scores or SETUP/WAIT flips near the 60 threshold).

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces: full suite green at the v2.2 identity.

- [ ] **Step 1: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: mostly green (~1850+ tests); any failures cluster in engine tests whose fixtures counted on m4 points.

- [ ] **Step 2: Fix failures under these decision rules** (apply per failing test, in this order):

  1. **Numeric expectation includes m4** (asserted score/breadth/max_attainable/shadow_score built from a book containing m4 points): recompute the expectation without m4's points, exactly as Task 1 Step 2 did.
  2. **Fixture needs a valid setup that no longer clears threshold/breadth**: strengthen a *counted* module in the fixture (raise m2_breakout/m3_roc points, or add m2_ma_align) until the original intent (a firing setup) holds again; keep m4 in the fixture if it was there — it documents the exclusion.
  3. **Anything else** — a failure that suggests the engine misbehaves (wrong veto precedence, shadow on an emitted setup, revert book emitting): STOP. Do not patch the test; report the failure verbatim for review.

- [ ] **Step 3: Re-run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — record the exact `N passed, M skipped` line for Task 6's registration.

- [ ] **Step 4: Commit** (only if Step 2 touched files)

```bash
git add tests/
git diff --cached --stat
git commit -m "test(engine): adapt fixtures to v2.2 m4 exclusion"
```

---

### Task 6: Sanity replay + registration docs

**Files:**
- Create: `experiments/engine/CONFLUENCE_V22_FORWARD_REGISTRATION.md`
- Create (tool output): `experiments/engine/v22_sanity_honest_report.json`
- Modify: `experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md` (prepend addendum only)

**Interfaces:**
- Consumes: the Task-1 Step-7 v2.2 hash; Task 5's suite tally.
- Produces: the frozen v2.2 registration. Daemon restart remains human ops — do NOT restart or enable anything.

- [ ] **Step 1: Run the non-gating sanity replay** (2020-01 → 2026-06 inclusive, matching the v2.1 convention; needs `.backtest_cache`, ~minutes):

Run: `.venv/bin/python tools/engine_honest_report.py --start-ms 1577836800000 --end-ms 1782864000000 --out experiments/engine/v22_sanity_honest_report.json`
Expected: exit 0.

- [ ] **Step 2: Verify the artifact exists and read it** — this step is mandatory before any doc claims the replay ran:

Run: `ls -la experiments/engine/v22_sanity_honest_report.json && .venv/bin/python -m json.tool experiments/engine/v22_sanity_honest_report.json | head -60`
Expected: the file exists and parses. Read the full JSON and note: closed-trade count, net R, PF, expectancy, win rate, max realized drawdown R, discipline state (latch/pause), first-half/second-half/last-365d splits, ex-best-3/5 outliers, cost-multiple survival — the same fields the v2.1 doc reports. If the file is missing or the run failed, STOP and report; do not write the registration.

- [ ] **Step 3: Write `experiments/engine/CONFLUENCE_V22_FORWARD_REGISTRATION.md`** with this structure, filling every `⟨…⟩` from the artifact / Task 1 / Task 5 (no `⟨…⟩` may survive into the commit):

```markdown
# Confluence Engine v2.2 — Forward-Paper Pre-Registration

**STATUS: FROZEN (2026-07-05, human-approved v2.2 mandate).**
No frozen value below may change until the horizon; any change is a new
ENGINE_VERSION → new hash → new registration (v2.3).

Spec: `docs/research-log/specs/2026-07-05-v22-module-prune-design.md`.
Predecessor: `CONFLUENCE_V21_FORWARD_REGISTRATION.md` (SUPERSEDED addendum,
zero completed setups). Design evidence:
`experiments/engine/SCORING_AUDIT_2026-07.md` (Stage-1 trend
CURRENT_WEIGHTS_ADEQUATE / revert NO_SIGNAL; Stage-2 BOTH books NO_SIGNAL;
m4_pullback LOO-HARMFUL in both stages — the sole audit-licensed removal).

## Posture (binding)

Paper only. Disciplined heuristic, **no validated-edge claim** — the
NO_CLAIM banner rides on every emitted signal. v2.2 is a DEFENSIBILITY
improvement over v2.1, not a validated edge: Stage-2 of the scoring audit
showed even the trend book at NO_SIGNAL_IN_ANY_WEIGHTING on the
deriv-inclusive panel, and the audit measured m4-removal ordering only on
direction-stable bars. Single change vs v2.1: m4_pullback is excluded from
the trend book's score, breadth, and max_attainable (still scored and
journaled; with-m4 counterfactuals journal as `v2.2 m4_pullback excluded`
shadows). Threshold 60 / Tier-A 75 stay ABSOLUTE over the reduced max (85
with funding data, 70 without) — knowingly stricter, no new constants.
The mean_revert book remains shadow-only (v2.1 `VETO_NO_CT` mechanism,
unchanged); the audit's NO_SIGNAL verdict on that book is its standing
rationale. NOT tuned against history beyond this one registered removal.

## Frozen identity

- `ENGINE_VERSION = "2.2"`, `EXCLUDED_MODULES = ("m4_pullback",)` and
  `VETO_M4_EXCLUDED` folded into `engine_hash` with the other frozen
  module constants.
- `engine_hash = ⟨Task-1 Step-7 digest⟩`
- `enable_date_utc = 2026-07-05`, `journal_path = journal/signals.jsonl`,
  `symbol/timeframe = BTC/USDT:USDT 1h`, `lookback_bars = 6000`.
- Full test suite at freeze: ⟨N passed, M skipped from Task 5⟩.

## Horizon (pre-committed)

Evaluate at the LATER of **6 months** from enable_date_utc OR **≥ 30
completed setups** (EXIT rows at the frozen hash). No interim
peeking-to-decide; one verdict, written once.

## Success bar (all must hold)

1. **Net R > 0** over all completed setups at the frozen hash.
2. **Drawdown within the layered budgets** — trailing 15R/90d window never
   beyond routine pause; the 30R hard latch never tripped.
3. **Mandatory ablation report** (part of the verdict, from the journal via
   `tools/engine_ablation.py`): per-family — `macro`, `no_ct`, `long_only`,
   `m4_pullback` — shadow-score distributions and counterfactual R.
   REPORTED, none gating. The `m4_pullback` family is the forward test of
   this registration's one change.

## Kill rule (binding)

One cycle. DOWNGRADE → `enabled=false`, no re-tune on this hash; any
constant change is v2.3 → new hash → new registration → fresh clock.

## Sanity replay (non-gating, house convention)

`tools/engine_honest_report.py` over 2020-01→2026-06 (deriv=None,
price-structure core), filled 2026-07-05 from
`experiments/engine/v22_sanity_honest_report.json` at the frozen hash:
⟨closed trades (~/yr), net R, PF, expectancy, win %⟩; max realized DD
⟨value⟩ vs the 30R latch — ⟨state; latch/pause tripped or not⟩.
Recency: ⟨first half / second half / last 365d⟩. Outliers: ⟨ex-best-3 /
ex-best-5⟩. Cost: ⟨survival multiples⟩. Recorded for audit only — NOT an
edge claim, NOT a gate. ⟨One sentence comparing trade count and DD headroom
to v2.1's replay (167 trades, +41.16R, DD −27.94R): the stricter absolute
threshold should show FEWER trades; call out if it does not.⟩

## Enable runbook (human ops)

1. This file FROZEN + committed.
2. `promotion/engine.json` needs no change (config identical; only code
   constants moved).
3. Restart the watch daemon; the first journal row at the v2.2 hash starts
   the record. v2.1 rows remain in the journal under the retired hash
   (isolated by the version filter).
4. Do not touch frozen constants until the horizon.
```

- [ ] **Step 4: Prepend the SUPERSEDED addendum to the v2.1 registration** — insert directly under the title line of `experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md` (do not edit any frozen value below it):

```markdown
> **SUPERSEDED 2026-07-05 by v2.2** (audit-driven m4_pullback exclusion;
> see `CONFLUENCE_V22_FORWARD_REGISTRATION.md` and
> `SCORING_AUDIT_2026-07.md`). Withdrawn with ZERO completed setups at the
> v2.1 hash — the one-day record is uncontaminated; no verdict is claimed.
```

- [ ] **Step 5: Commit** (registration docs live under `experiments/`, tracked normally; add the replay JSON too — precedent: `v21_sanity_honest_report.json`):

```bash
git add experiments/engine/CONFLUENCE_V22_FORWARD_REGISTRATION.md experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md experiments/engine/v22_sanity_honest_report.json
git diff --cached --stat
git commit -m "docs(engine): v2.2 forward registration FROZEN; v2.1 superseded (zero-setup record)"
```

---

## Post-plan notes (not tasks)

- Daemon restart / enable is **human ops** — never done by the implementer.
- The registered 2026-07 calibration + audit reports stay untouched at hash `4e35561f…` (one-run rule); v2.2 gets no new historical calibration.
