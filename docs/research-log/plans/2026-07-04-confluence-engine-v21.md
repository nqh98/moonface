# Confluence Engine v2.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Confluence Engine v2.1 — drop counter-trend entries, flatten tiers to one threshold/one size, go long-only (all three removals journaled as shadows) — supersede the v2 registration, and freeze a new v2.1 forward-paper registration.

**Architecture:** Constant surgery inside the existing engine package: a v2.1 policy layer in `confluence.decide()` converts would-be-valid CT and short-trend candidates into journaled shadows; `discipline` flattens the sizing table; `engine` lets a long-only shadow still close an open long (reversal exit); `ablation` gains per-veto-family grouping so the horizon report tests each removal on forward data. `ENGINE_VERSION = "2.1"` plus changed frozen constants move `engine_hash` mechanically, isolating the v2 record.

**Tech Stack:** Python 3.11+ stdlib only, pytest (plain functions), ruff.

## Global Constraints

- **Spec:** `docs/research-log/specs/2026-07-04-confluence-engine-v21-design.md`. Read it before starting any task.
- Module scorers (`trend_book.py`, `revert_book.py`), `macro.py`, `regime.py`, `resample.py`, `position.py`, `EngineConfig` fields: **DO NOT TOUCH** (spec Out of scope). `TIER_A` and `CT_SURCHARGE` stay defined in `confluence.py` (vestigial; `calibration.py` imports `CT_SURCHARGE`).
- Veto reason constants, exact values: `VETO_NO_CT = "v2.1 no counter-trend entries"`, `VETO_LONG_ONLY = "v2.1 long-only"`.
- Flattened sizing: `_TIER_PROFILE_FRACTION = {("B", "WT"): 0.005}`; high-vol halving stays.
- v2 frozen hash (the identity we are leaving): `10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf`.
- Run everything as `.venv/bin/python -m pytest ...` / `.venv/bin/python -m tools....` — no bare `python` on PATH; rtk does not proxy `python`.
- Ruff clean: `.venv/bin/python -m ruff check src tools tests`.
- Git: never chain `git add && git commit`; stage, verify `git diff --cached --stat`, then commit. No AI-attribution trailers. Do not push.
- Project CLAUDE.md asks for gitnexus impact/detect-changes around symbol edits and commits; if the MCP tools are unavailable, note it and proceed — every symbol edited here is named explicitly by the spec.
- Registration docs are append-only: the v2 registration gains a dated addendum; nothing above it is edited or deleted.
- The calibration diagnostic is NOT re-run (one-run rule). The only real-data run in this plan is the non-gating sanity replay in Task 5.

---

### Task 1: v2.1 policy layer in `confluence.py` + version bump

**Files:**
- Modify: `src/moonface/signal/engine/confluence.py` (constants block after `GATE`, `_book_context` tier logic, `decide()` policy layer)
- Modify: `src/moonface/signal/engine/config.py:10` (`ENGINE_VERSION`) and the `_FROZEN_FIELDS_BY_MODULE["confluence"]` tuple (~line 55)
- Test: `tests/test_engine_confluence.py` (update pinned v2 behaviors), `tests/test_engine_config.py` (append), `tests/test_engine_calibration_pass.py` (hash pin)

**Interfaces:**
- Consumes: existing `decide(trend_scores, revert_scores, macro, cfg) -> Decision`, `_book_context` dict contract (`valid`, `veto`, `shadow_score`, `shadow_direction`, `tier` keys).
- Produces: module constants `VETO_NO_CT: str`, `VETO_LONG_ONLY: str` (Tasks 2–3 import them); `decide()` that never returns a mean_revert or short SETUP; `ENGINE_VERSION == "2.1"`.

- [ ] **Step 1: Update the pinned v2 tests to the v2.1 contract**

In `tests/test_engine_confluence.py`, extend the import:

```python
from moonface.signal.engine.confluence import (VETO_LONG_ONLY, VETO_NO_CT,
                                               decide)
```

Replace `test_bear_mean_revert_long_clears_ct_threshold_tier_b` (fixture unchanged, expectations flipped):

```python
def test_would_be_ct_setup_is_vetoed_with_shadow():
    revert = [
        _m("m1_sweep", 1, 20, "mean_revert"),
        _m("m2_reclaim", 1, 15, "mean_revert"),
        _m("m3_divergence", 1, 25, "mean_revert"),
        _m("m4_fund_ct", 1, 15, "mean_revert"),
    ]  # score 75, breadth 4, ALLOW_CT threshold 70 -> valid under v2 rules
    d = decide([], revert, _macro("BEAR"), _cfg())
    assert d.action == "WAIT"
    assert d.direction == 0
    assert d.veto == VETO_NO_CT
    assert d.shadow_score == 75
    assert d.shadow_direction == 1
```

Replace `test_bear_mean_revert_long_clears_ct_tier_a`:

```python
def test_high_score_ct_candidate_also_vetoed():
    revert = [
        _m("m1_sweep", 1, 20, "mean_revert"),
        _m("m2_reclaim", 1, 15, "mean_revert"),
        _m("m3_divergence", 1, 25, "mean_revert"),
        _m("m4_fund_ct", 1, 15, "mean_revert"),
        _m("m5_oi_flush", 1, 10, "mean_revert"),
    ]  # score 85 — would have been Tier A in v2
    d = decide([], revert, _macro("BEAR"), _cfg())
    assert d.action == "WAIT"
    assert d.veto == VETO_NO_CT
    assert d.shadow_score == 85
```

Replace `test_bear_mean_revert_short_allow_no_surcharge_tier_b`:

```python
def test_ct_short_candidate_vetoed_with_shadow():
    revert = [
        _m("m1_sweep", -1, 20, "mean_revert"),
        _m("m2_reclaim", -1, 15, "mean_revert"),
        _m("m4_fund_ct", -1, 15, "mean_revert"),
        _m("m5_oi_flush", -1, 10, "mean_revert"),
    ]  # score 60, breadth 4, ALLOW threshold 60 -> valid under v2 rules
    d = decide([], revert, _macro("BEAR"), _cfg())
    assert d.action == "WAIT"
    assert d.veto == VETO_NO_CT
    assert d.shadow_direction == -1
```

Replace `test_two_books_conflict_waits` (the conflict WAIT is gone — the CT side is vetoed, the trend long trades):

```python
def test_ct_conflict_no_longer_blocks_trend_long():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 20),
    ]  # trend LONG score 80
    revert = [
        _m("m1_sweep", -1, 20, "mean_revert"),
        _m("m2_reclaim", -1, 15, "mean_revert"),
        _m("m3_divergence", -1, 25, "mean_revert"),
        _m("m4_fund_ct", -1, 15, "mean_revert"),
        _m("m5_oi_flush", -1, 5, "mean_revert"),
    ]  # revert SHORT score 80 -> v2.1 shadow, not a conflicting candidate
    d = decide(trend, revert, _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.direction == 1
    assert d.archetype == "trend"
    assert d.veto == VETO_NO_CT       # the CT shadow rides along on the row
    assert d.shadow_direction == -1
```

Replace `test_two_books_same_direction_higher_score_wins`:

```python
def test_trend_wins_when_revert_candidate_is_vetoed():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 10),
    ]  # trend LONG score 70
    revert = [
        _m("m1_sweep", 1, 20, "mean_revert"),
        _m("m2_reclaim", 1, 15, "mean_revert"),
        _m("m3_divergence", 1, 25, "mean_revert"),
        _m("m4_fund_ct", 1, 15, "mean_revert"),
        _m("m5_oi_flush", 1, 5, "mean_revert"),
    ]  # revert LONG score 80 -> shadow; trend candidate trades
    d = decide(trend, revert, _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.direction == 1
    assert d.archetype == "trend"
    assert d.score == 70
    assert d.veto == VETO_NO_CT
    assert d.shadow_score == 80
```

Append two new tests:

```python
def test_trend_short_vetoed_long_only():
    trend = [
        _m("m1_macro", -1, 20),
        _m("m2_breakout", -1, 20),
        _m("m3_roc", -1, 20),
        _m("m4_pullback", -1, 20),
    ]  # trend SHORT score 80, NEUTRAL macro -> valid under v2, shadowed now
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.direction == 0
    assert d.veto == VETO_LONG_ONLY
    assert d.shadow_score == 80
    assert d.shadow_direction == -1


def test_trend_long_high_score_tier_stays_b():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m2_ma_align", 1, 10),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 15),
    ]  # score 85 — would have been Tier A in v2; v2.1 has one tier
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.tier == "B"
```

Leave untouched (they pin behavior v2.1 keeps): `test_bear_vetoes_trend_long`,
`test_bear_vetoes_mean_revert_short`, `test_bear_mean_revert_long_below_ct_threshold_waits`,
`test_unconfirmed_bear_does_not_gate`, `test_breadth_guard_rejects_thin_book`,
`test_degraded_ceiling_*`, `test_extreme_vol_forces_flat_v2`,
`test_every_wait_detail_reports_score_threshold_breadth`.

Append to `tests/test_engine_config.py`:

```python
V2_FROZEN_HASH = "10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf"


def test_engine_version_is_v21():
    assert engine_config.ENGINE_VERSION == "2.1"


def test_hash_left_the_v2_identity():
    assert engine_hash(EngineConfig()) != V2_FROZEN_HASH
```

(Use the module aliases already imported at the top of that file — it imports
the config module as `engine_config` for the monkeypatch tests; if the names
differ, match the file's existing imports.)

In `tests/test_engine_calibration_pass.py`, replace the frozen-hash test:

```python
V2_FROZEN_HASH = "10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf"


def test_engine_hash_left_the_v2_identity():
    # v2.1 must not journal under the superseded v2 identity. Task 5 pins the
    # exact v2.1 hash at freeze time.
    assert engine_hash(EngineConfig()) != V2_FROZEN_HASH
```

(delete the old `FROZEN_HASH` constant and `test_engine_hash_is_the_frozen_registration_hash`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_confluence.py tests/test_engine_config.py -q`
Expected: FAIL — `ImportError: cannot import name 'VETO_LONG_ONLY'` plus version/hash asserts.

- [ ] **Step 3: Implement — `confluence.py`**

Add after the `GATE` construction block (after the `del _archetype_label, _direction_label` line):

```python
# --- v2.1 policy layer (frozen constants; spec 2026-07-04) -------------------
# Would-be-valid candidates blocked by policy journal as shadows so the
# horizon ablation can test each removal on forward data. TIER_A and
# CT_SURCHARGE above stay defined: CT_SURCHARGE still sets the ALLOW_CT
# validity threshold that defines a CT shadow, and diagnostics import both.
VETO_NO_CT = "v2.1 no counter-trend entries"
VETO_LONG_ONLY = "v2.1 long-only"
```

In `_book_context`, delete the `tier_a = TIER_A` line, and change the valid branch:

```python
            if policy == "ALLOW_CT":
                threshold = BASE_THRESHOLD + CT_SURCHARGE
            valid = breadth >= BREADTH_MIN and score >= threshold
            if valid:
                tier = "B"  # v2.1: tiers flattened — one threshold, one size
```

In `decide()`, immediately after the `revert_ctx = _book_context(...)` line, insert:

```python
    # v2.1: counter-trend entries and trend shorts never trade. A candidate
    # that would have been valid under v2 rules becomes a journaled shadow.
    if revert_ctx["valid"]:
        revert_ctx["valid"] = False
        revert_ctx["veto"] = VETO_NO_CT
        revert_ctx["shadow_score"] = revert_ctx["score"]
        revert_ctx["shadow_direction"] = revert_ctx["direction"]
    if trend_ctx["valid"] and trend_ctx["direction"] < 0:
        trend_ctx["valid"] = False
        trend_ctx["veto"] = VETO_LONG_ONLY
        trend_ctx["shadow_score"] = trend_ctx["score"]
        trend_ctx["shadow_direction"] = trend_ctx["direction"]
```

Everything downstream (`veto = trend_ctx["veto"] or revert_ctx["veto"]`,
candidates, single/conflict/winner branches) is untouched — the conflict and
same-direction branches simply become unreachable for vetoed books.

- [ ] **Step 4: Implement — `config.py`**

```python
ENGINE_VERSION = "2.1"
```

In `_FROZEN_FIELDS_BY_MODULE["confluence"]`, add the two new constants to the tuple:

```python
        "VETO_LONG_ONLY",
        "VETO_NO_CT",
```

(the drift guard requires the observed frozen-name set to match exactly — without this, `engine_hash` raises `RuntimeError` at import of any caller).

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_confluence.py tests/test_engine_config.py tests/test_engine_calibration_pass.py -q`
Expected: all pass.

- [ ] **Step 6: Ruff + commit**

Run: `.venv/bin/python -m ruff check src/moonface/signal/engine/confluence.py src/moonface/signal/engine/config.py tests/test_engine_confluence.py tests/test_engine_config.py tests/test_engine_calibration_pass.py`

```bash
git add src/moonface/signal/engine/confluence.py src/moonface/signal/engine/config.py tests/test_engine_confluence.py tests/test_engine_config.py tests/test_engine_calibration_pass.py
git diff --cached --stat   # exactly these 5 files
git commit -m "feat(engine): v2.1 policy layer - no CT entries, long-only, flat tier (shadows journaled)"
```

---

### Task 2: Flatten sizing + long-only reversal exit

**Files:**
- Modify: `src/moonface/signal/engine/discipline.py:97-103` (`_TIER_PROFILE_FRACTION`)
- Modify: `src/moonface/signal/engine/engine.py` (import + `signal_dir` derivation, ~lines 8-9 and 98-101)
- Test: `tests/test_engine_discipline.py` (replace two tier tests), Create: `tests/test_engine_v21_reversal.py`

**Interfaces:**
- Consumes: `VETO_LONG_ONLY`, `VETO_NO_CT` from Task 1; `Decision` dataclass (fields: action, direction, archetype, policy, score, max_attainable, breadth, tier, veto, shadow_score, modules, detail, shadow_direction).
- Produces: `engine._reversal_direction(decision: Decision) -> int` (pure); flattened `_TIER_PROFILE_FRACTION`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_engine_v21_reversal.py`:

```python
# tests/test_engine_v21_reversal.py
"""v2.1 reversal semantics: a would-be SHORT trend setup (valid but for the
long-only rule) still closes an open long; CT shadows and macro vetoes do
not drive exits."""
from moonface.signal.engine.confluence import (Decision, VETO_LONG_ONLY,
                                               VETO_NO_CT)
from moonface.signal.engine.engine import _reversal_direction


def _decision(action="WAIT", direction=0, veto=None, shadow_direction=None):
    return Decision(action=action, direction=direction, archetype=None,
                    policy=None, score=0, max_attainable=100, breadth=0,
                    tier=None, veto=veto, shadow_score=None, modules=(),
                    detail="t", shadow_direction=shadow_direction)


def test_setup_direction_passes_through():
    assert _reversal_direction(_decision("SETUP", 1)) == 1
    assert _reversal_direction(_decision("SETUP", -1)) == -1


def test_long_only_shadow_drives_reversal():
    d = _decision(veto=VETO_LONG_ONLY, shadow_direction=-1)
    assert _reversal_direction(d) == -1


def test_ct_shadow_does_not_drive_reversal():
    d = _decision(veto=VETO_NO_CT, shadow_direction=1)
    assert _reversal_direction(d) == 0


def test_macro_veto_does_not_drive_reversal():
    d = _decision(veto="macro BEAR vetoes TREND long", shadow_direction=1)
    assert _reversal_direction(d) == 0


def test_plain_wait_no_reversal():
    assert _reversal_direction(_decision()) == 0
```

In `tests/test_engine_discipline.py`, delete
`test_tier_size_fraction_lookup_by_tier_and_profile` and
`test_tier_size_fraction_high_vol_halves` and add (matching the file's
existing `EngineConfig` import/helpers):

```python
def test_tier_size_fraction_flattened_v21():
    cfg = EngineConfig()
    assert tier_size_fraction("B", "WT", "normal", cfg) == 0.005
    # v2.1: no Tier-A upsize and no CT sizing — missing cells size to zero
    assert tier_size_fraction("A", "WT", "normal", cfg) == 0.0
    assert tier_size_fraction("A", "CT", "normal", cfg) == 0.0
    assert tier_size_fraction("B", "CT", "normal", cfg) == 0.0


def test_tier_size_fraction_high_vol_halves():
    cfg = EngineConfig()
    assert tier_size_fraction("B", "WT", "high", cfg) == 0.0025
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_v21_reversal.py tests/test_engine_discipline.py -q`
Expected: FAIL — `ImportError: cannot import name '_reversal_direction'` and the old-table asserts.

- [ ] **Step 3: Implement**

`discipline.py` — replace the table:

```python
# Frozen tier x profile sizing lookup — NOT in EngineConfig (anti-overfitting).
# v2.1: tiers flattened to the single surviving cell (spec §3); missing cells
# size to 0.0, and no decide() path can produce them anyway.
_TIER_PROFILE_FRACTION: dict[tuple[str, str], float] = {
    ("B", "WT"): 0.005,
}
```

`engine.py` — extend the confluence import:

```python
from moonface.signal.engine.confluence import (Decision, VETO_LONG_ONLY,
                                               decide)
```

Add above `evaluate_engine`:

```python
def _reversal_direction(decision: Decision) -> int:
    """Direction that may close an open position. v2.1: a would-be SHORT
    trend setup (valid but for the long-only rule) still closes an open
    long — the calibration's reversal-sensitivity block showed reversal
    exits added R on the triggered trend subset. CT shadows and macro
    vetoes do NOT drive exits (v2 semantics preserved for those)."""
    if decision.action == "SETUP":
        return decision.direction
    if (decision.veto == VETO_LONG_ONLY
            and decision.shadow_direction is not None):
        return decision.shadow_direction
    return 0
```

Replace the line inside `evaluate_engine`'s held-position branch:

```python
        signal_dir = _reversal_direction(decision)
```

(the old line is `signal_dir = decision.direction if decision.action == "SETUP" else 0`; keep the surrounding comment, updating "Only an opposite tiered SETUP reverses" to "An opposite tiered SETUP or a long-only shadow reverses").

- [ ] **Step 4: Run tests + the engine suite**

Run: `.venv/bin/python -m pytest tests/test_engine_v21_reversal.py tests/test_engine_discipline.py tests/test_engine_evaluate.py tests/test_engine_position.py tests/test_engine_scorecard.py -q`
Expected: pass. If `test_engine_evaluate.py` pins a mean_revert/short SETUP path, update that test to the v2.1 contract (WAIT + shadow) and say so in the commit body.

- [ ] **Step 5: Ruff + commit**

Run: `.venv/bin/python -m ruff check src/moonface/signal/engine/discipline.py src/moonface/signal/engine/engine.py tests/test_engine_v21_reversal.py tests/test_engine_discipline.py`

```bash
git add src/moonface/signal/engine/discipline.py src/moonface/signal/engine/engine.py tests/test_engine_v21_reversal.py tests/test_engine_discipline.py
git diff --cached --stat
git commit -m "feat(engine): v2.1 flat sizing + long-only shadow reversal exit"
```

(add `tests/test_engine_evaluate.py` to the stage list only if Step 4 required updating it).

---

### Task 3: Journal `veto` (defect fix) + per-family ablation

**Files:**
- Modify: `src/moonface/signal/cli.py` (~line 352, journal dict in `_emit_engine`)
- Modify: `src/moonface/signal/engine/ablation.py` (import, tier fallbacks, `veto_family`, per-family grouping, per-family counterfactual profile)
- Test: `tests/test_engine_ablation.py` (two assert updates + new tests), `tests/test_signal_cli.py` / `tests/test_engine_cli.py` (run, update only if a test pins the exact journal key set)

**Interfaces:**
- Consumes: `VETO_NO_CT`, `VETO_LONG_ONLY` (Task 1); existing `gate_ablation(entries, candles, cfg) -> dict`.
- Produces: `ablation.veto_family(veto: str | None) -> str` returning `"none" | "macro" | "no_ct" | "long_only" | "other"`; `gate_ablation` output gains a top-level `"families"` dict and per-row `"family"` keys (existing keys unchanged).

**Defect being fixed (call out in the commit body):** `_emit_engine` never
journaled `veto`, but `gate_ablation` filters on `e.get("veto")` — on the real
forward journal the mandatory ablation report would have been empty. Additive
journal field; no hash impact.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_engine_ablation.py`:

```python
from moonface.signal.engine.ablation import veto_family
from moonface.signal.engine.confluence import VETO_LONG_ONLY, VETO_NO_CT


def test_veto_family_classifier():
    assert veto_family(None) == "none"
    assert veto_family("") == "none"
    assert veto_family("macro BEAR vetoes TREND long") == "macro"
    assert veto_family(VETO_NO_CT) == "no_ct"
    assert veto_family(VETO_LONG_ONLY) == "long_only"
    assert veto_family("something else") == "other"


def _family_entry(ts, veto, direction, version):
    return {"status": "engine", "strategy_version": version,
            "candle_ts_ms": ts, "veto": veto, "shadow_score": 80,
            "shadow_direction": direction, "tier": None,
            "regime_vol": "normal"}


def test_gate_ablation_groups_by_family():
    from moonface.foundation.models import Candle
    from moonface.signal.engine.config import EngineConfig, engine_hash
    from moonface.signal.engine.ablation import gate_ablation
    H = 3_600_000
    # flat series: ATR 4; neither WT stop (92/108) nor CT stop/target fills
    # within the series and no time stop is reached -> all unresolved, 0R.
    candles = [Candle(i * H, 100.0, 102.0, 98.0, 100.0, 1.0)
               for i in range(40)]
    cfg = EngineConfig(atr_period=3)
    version = engine_hash(cfg)
    ts = candles[20].timestamp_ms
    entries = [
        _family_entry(ts, "macro BEAR vetoes TREND long", 1, version),
        _family_entry(ts, VETO_NO_CT, 1, version),
        _family_entry(ts, VETO_LONG_ONLY, -1, version),
    ]
    out = gate_ablation(entries, candles, cfg)
    fams = out["families"]
    assert set(fams) == {"macro", "no_ct", "long_only"}
    for fam in fams.values():
        assert fam["n_vetoed"] == 1
        assert fam["resolved"] == 0
        assert fam["net_r_if_taken"] == 0.0
    assert all(row["family"] in ("macro", "no_ct", "long_only")
               for row in out["counterfactual"]["rows"])
```

Update the two tier-inference asserts in the existing tests (v2 inferred "A"
from `shadow_score >= TIER_A`; v2.1 has one tier):
- `test_gate_ablation_short_veto_on_rising_series_resolves_negative_and_saves_r`:
  `rows[0]["tier"] == "A"` → `rows[0]["tier"] == "B"`.
- `test_gate_ablation_long_veto_never_exits_stays_unresolved`:
  `rows[0]["tier"] == "A"` → `rows[0]["tier"] == "B"`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_ablation.py -q`
Expected: FAIL — `ImportError: cannot import name 'veto_family'`.

- [ ] **Step 3: Implement — `ablation.py`**

Replace the `TIER_A` import with:

```python
from moonface.signal.engine.confluence import VETO_LONG_ONLY, VETO_NO_CT
```

Add:

```python
def veto_family(veto: str | None) -> str:
    """Group a journaled veto reason into its ablation family (spec §4)."""
    if not veto:
        return "none"
    if veto == VETO_NO_CT:
        return "no_ct"
    if veto == VETO_LONG_ONLY:
        return "long_only"
    if str(veto).startswith("macro"):
        return "macro"
    return "other"
```

Tier fallbacks (v2.1 single tier):
- `_shadow_score_summary`: `tier = "A" if score >= TIER_A else "B"` → `tier = "B"`.
- `_skipped_row`: replace the whole `if score is not None and tier is None:` block with `tier = tier or "B"` (drop the try/except).
- `_replay_counterfactual`: `tier = entry.get("tier") or ("A" if score >= TIER_A else "B")` → `tier = entry.get("tier") or "B"`.

Per-family counterfactual exit discipline in `_replay_counterfactual` — replace
the `fraction`/`open_position` lines:

```python
    family = veto_family(entry.get("veto"))
    profile = "CT" if family == "no_ct" else "WT"
    fraction = tier_size_fraction(tier, "WT", regime_vol, cfg)
    pos = open_position(
        candles[: candle_index + 1],
        cfg,
        direction,
        0.0,
        fraction,
        profile,
    )
```

Per-family grouping in `gate_ablation` — inside the existing per-entry loop,
after `rows.append(row)`, add family bookkeeping (initialize
`families: dict[str, dict] = {}` and `family_entries: dict[str, list] = {}`
before the loop):

```python
        fam = veto_family(entry.get("veto"))
        row["family"] = fam
        family_entries.setdefault(fam, []).append(entry)
        agg = families.setdefault(fam, {"n_vetoed": 0, "resolved": 0,
                                        "net_r_if_taken": 0.0})
        agg["n_vetoed"] += 1
        if row["resolved"]:
            agg["resolved"] += 1
            agg["net_r_if_taken"] += float(row["net_r"] or 0.0)
```

Also set `row["family"] = veto_family(entry.get("veto"))` on the early-skip
paths (`missing shadow fields`, `missing candle timestamp`, `invalid candle
timestamp`, `veto bar not in candle series`) with the same bookkeeping —
simplest is to compute `fam` and do the bookkeeping ONCE at the top of the
loop body, then append the row and update `resolved`/`net_r_if_taken` after
the row is known. And in the return dict add:

```python
        "families": {
            fam: {
                "n_vetoed": agg["n_vetoed"],
                "resolved": agg["resolved"],
                "net_r_if_taken": round(agg["net_r_if_taken"], 4),
                "veto_saved_r": round(-agg["net_r_if_taken"], 4),
                "shadow_scores": _shadow_score_summary([
                    e for e in family_entries[fam]
                    if e.get("shadow_score") is not None]),
            }
            for fam, agg in sorted(families.items())
        },
```

Update the assumptions list:

```python
        "assumptions": [
            "no_ct counterfactuals replay the CT exit discipline without a "
            "sweep wick (entry-anchored stop); other families replay WT",
            "veto rows without candle_ts_ms or shadow_score are skipped",
            "unresolved replays contribute 0R",
        ],
```

- [ ] **Step 4: Implement — `cli.py`**

In `_emit_engine`'s `append_entry` dict, after the `"gate":` line, add:

```python
        "veto": decision.veto if decision is not None else None,
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/test_engine_ablation.py tests/test_engine_ablation_cli.py tests/test_signal_cli.py tests/test_engine_cli.py -q`
Expected: pass. If a CLI test pins the exact journal key set, add `"veto"` to
its expectation and note it in the commit body.

- [ ] **Step 6: Ruff + commit**

Run: `.venv/bin/python -m ruff check src/moonface/signal/cli.py src/moonface/signal/engine/ablation.py tests/test_engine_ablation.py`

```bash
git add src/moonface/signal/cli.py src/moonface/signal/engine/ablation.py tests/test_engine_ablation.py
git diff --cached --stat
git commit -m "fix(engine): journal veto field + per-family gate ablation (defect: mandatory report was empty)"
```

---

### Task 4: v2 registration SUPERSEDED addendum

**Files:**
- Modify: `experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md` (append ONLY)

- [ ] **Step 1: Verify the withdrawal-state facts before writing them**

```bash
grep -c '"status": "engine"' journal/signals.jsonl
grep '"status": "engine"' journal/signals.jsonl | grep -c '"action": "EXIT"'
```
Expected: N WAIT-only rows (5 at plan time, may have grown — use the actual
count), 0 EXITs. If any non-WAIT/OPEN action appears, STOP and report — the
addendum text below assumes a zero-trade record.

- [ ] **Step 2: Append the addendum (nothing above it edited)**

```markdown

## SUPERSEDED — WITHDRAWN (2026-07-04)

Human-approved v2.1 mandate 2026-07-04
(spec `docs/research-log/specs/2026-07-04-confluence-engine-v21-design.md`):
v2.1 supersedes this registration before any setup accrued. Record at
withdrawal: <N> journal rows at the frozen hash, all WAIT, 0 setups,
0 completed trades. Forward clock VOID. The v2 identity
(ENGINE_VERSION "2.0", engine_hash 10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf)
is retired; resuming it would require a NEW registration with a fresh clock.
Design evidence for the supersession:
`experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md` (verdict UNCALIBRATED —
CT book negative at every score level; Tier-A bucket inverts; short trend
side negative). Successor registration:
`experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md`.
No text above this addendum was edited or removed.
```

(replace `<N>` with the actual row count from Step 1).

- [ ] **Step 3: Commit**

```bash
git add experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md
git diff --cached --stat
git commit -m "docs(engine): v2 registration SUPERSEDED addendum (v2.1 mandate, zero-trade record)"
```

---

### Task 5: Full suite, non-gating sanity replay, freeze v2.1 registration

**Files:**
- Create: `experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md`
- Create: `experiments/engine/v21_sanity_honest_report.json` (tool output)
- Modify: `tests/test_engine_calibration_pass.py` (pin the exact v2.1 hash)

- [ ] **Step 1: Full suite + ruff (whole-lane gate)**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: green (baseline before this lane: 1814 passed, 3 skipped). Any
failure outside the files this plan touched: STOP and report.
Run: `.venv/bin/python -m ruff check src tools tests`
Expected: no findings.

- [ ] **Step 2: Compute and pin the v2.1 hash**

```bash
.venv/bin/python -c "from moonface.signal.engine.config import EngineConfig, engine_hash; print(engine_hash(EngineConfig()))"
```

In `tests/test_engine_calibration_pass.py`, extend the Task 1 test with the
exact value printed (keeping the != v2 assert):

```python
V21_FROZEN_HASH = "<paste the printed 64-hex value>"


def test_engine_hash_is_the_frozen_v21_registration_hash():
    h = engine_hash(EngineConfig())
    assert h != V2_FROZEN_HASH
    assert h == V21_FROZEN_HASH
```

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_pass.py -q` → pass.

- [ ] **Step 3: Non-gating sanity replay (background; potentially hours)**

```bash
.venv/bin/python -m tools.engine_honest_report \
    --start-ms 1577836800000 --end-ms 1782316800000 \
    --out experiments/engine/v21_sanity_honest_report.json
```
Record the headline scorecard (net R, trades, drawdown, pause state) — it is
HOUSE-CONVENTION SANITY ONLY: not a gate, not an edge claim; the expected
outcome is "disciplined, DD-bounded", nothing more. Note the tool feeds
`deriv=None`, so this replays the price-structure core.

- [ ] **Step 4: Write and freeze the v2.1 registration**

Create `experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md` (fill the
two `<...>` values from Steps 2–3; everything else is frozen text):

```markdown
# Confluence Engine v2.1 — Forward-Paper Pre-Registration

**STATUS: FROZEN (2026-07-04, human-approved v2.1 mandate).**
No frozen value below may change until the horizon; any change is a new
ENGINE_VERSION → new hash → new registration (v2.2).

Spec: `docs/research-log/specs/2026-07-04-confluence-engine-v21-design.md`.
Predecessor: `CONFLUENCE_V2_FORWARD_REGISTRATION.md` (SUPERSEDED addendum,
zero-trade record). Design evidence: `CALIBRATION_DIAGNOSTIC_2026-07.md`
(UNCALIBRATED; one-run rule stands — v2.1 gets no new historical calibration).

## Posture (binding)

Paper only. Disciplined heuristic, **no validated-edge claim** — the NO_CLAIM
banner rides on every emitted signal. v2.1 is an evidence-guided
SIMPLIFICATION of v2: no counter-trend entries, one tier (threshold 60,
fraction 0.005, high-vol halved), long-only. All three removals journal as
shadows so this registration's ablation can test them on forward data.
NOT tuned against history beyond the three registered removals.

## Frozen identity

- `ENGINE_VERSION = "2.1"`, folded into `engine_hash` with the frozen module
  constants (incl. `VETO_NO_CT`, `VETO_LONG_ONLY`, the flattened
  `_TIER_PROFILE_FRACTION`).
- `engine_hash = <v2.1 hash from Step 2>`
- `enable_date_utc = 2026-07-04`, `journal_path = journal/signals.jsonl`,
  `symbol/timeframe = BTC/USDT:USDT 1h`, `lookback_bars = 6000`.

## Horizon (pre-committed)

Evaluate at the LATER of **6 months** from enable_date_utc OR **≥ 30
completed setups** (EXIT rows at the frozen hash). No interim
peeking-to-decide; one verdict, written once.

## Success bar (all must hold)

1. **Net R > 0** over all completed setups at the frozen hash.
2. **Drawdown within the layered budgets** — trailing 15R/90d window never
   beyond routine pause; the 30R hard latch never tripped.
3. **Mandatory ablation report** (part of the verdict, from the journal via
   `tools/engine_ablation.py`): per-family — `macro`, `no_ct`, `long_only` —
   shadow-score distributions and counterfactual R. REPORTED, none gating.

## Kill rule (binding)

One cycle. DOWNGRADE → `enabled=false`, no re-tune on this hash; any constant
change is v2.2 → new hash → new registration → fresh clock.

## Sanity replay (non-gating, house convention)

`tools/engine_honest_report.py` over 2020-01→2026-06 (deriv=None,
price-structure core): <one-line headline: net R, trades, MaxDD, pause state>.
Recorded for audit only — NOT an edge claim, NOT a gate.

## Enable runbook (human ops)

1. This file FROZEN + committed.
2. `promotion/engine.json` already carries `enabled: true` /
   `lookback_bars: 6000`; it needs no change (config identical, only code
   constants moved).
3. Restart the watch daemon; the first journal row at the v2.1 hash starts
   the record. The 5+ v2 WAIT rows remain in the journal under the retired
   hash (isolated by the version filter).
4. Do not touch frozen constants until the horizon.
```

- [ ] **Step 5: Verify + commit**

```bash
.venv/bin/python -m pytest tests/test_engine_calibration_pass.py tests/test_engine_config.py -q
git add experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md experiments/engine/v21_sanity_honest_report.json tests/test_engine_calibration_pass.py
git diff --cached --stat   # exactly these 3 files
git commit -m "docs(engine): freeze confluence v2.1 forward registration (hash pinned, sanity replay recorded)"
```

---

## Plan self-review notes (already applied)

- Spec coverage: §1 version/governance → Tasks 1 (version, hash) + 4 (addendum)
  + 5 (registration); §2 decision semantics → Task 1 (policy layer) + Task 2
  (reversal); §2.5 precedence → unchanged `trend or revert` veto line (Task 1
  leaves it untouched); §3 tiers/sizing → Tasks 1 (tier "B") + 2 (table);
  §4 shadows/ablation → Task 3 (incl. the newly-found `veto` journaling
  defect); §5 registration/success bar → Task 5; §6 testing → each task's
  test steps + Task 5 full suite and sanity replay.
- `TIER_A`/`CT_SURCHARGE` remain defined (spec §3); Task 3 removes ablation's
  `TIER_A` *import*, which is a usage change, not a constant removal —
  `calibration.py`'s `CT_SURCHARGE` import is unaffected.
- Type consistency: `veto_family` strings (`"macro"/"no_ct"/"long_only"`)
  match the `families` keys and the registration §"Success bar" item 3;
  `_reversal_direction` consumes the `Decision` fields exactly as defined in
  `confluence.py`; `V2_FROZEN_HASH`/`V21_FROZEN_HASH` names are consistent
  across Tasks 1 and 5.
- Known non-hermetic gotcha: some `test_signal_cli.py` tests read the live
  `promotion/engine.json` if enabled — the current tree runs green with it,
  but if Task 3's CLI run hits fetch-attempt failures, move the live config
  aside for the test run and restore it (do NOT edit the config).
