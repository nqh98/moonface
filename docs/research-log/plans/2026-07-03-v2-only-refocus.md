# V2-Only Refocus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Confluence engine v2 the only tier that can produce new paper-forward signals, archive (not delete) every other lineage, close the two stranded forward registrations, and complete the v2 freeze runbook so a clean forward-paper record can start.

**Architecture:** Four small code changes to the engine layer (hash digest of frozen constants, `shadow_direction` journaling, gate-ablation pure function, ablation CLI), then pure config/doc surgery (archive-move + single-style manifest + registration addenda + freeze). Tier routing in `src/moonface/signal/cli.py` is NOT modified — the design achieves "engine-only" purely by which config files exist at which paths.

**Tech Stack:** Python 3.12, pytest, dataclasses, no new dependencies.

**Spec:** `docs/research-log/specs/2026-07-03-v2-only-refocus-design.md` (approved 2026-07-03).

## Global Constraints

- **Never change the VALUE of any frozen constant** (module weights, thresholds, `GATE`, panel params, `_TIER_PROFILE_FRACTION`, CT constants, `ENGINE_VERSION = "2.0"`). This plan adds a digest over them; it must not alter them.
- **`promotion/engine.json` is gitignored — never `git add -f` it.** Only the `.example` is tracked.
- **`journal/signals.jsonl` is append-only and never edited**; tests use `tmp_path` journals only.
- **Git hygiene (MoonFace convention):** never chain `git add && git commit`; stage, then verify with `git diff --cached --stat`, then commit. No `Co-Authored-By`/AI-attribution trailers in commit messages.
- **docs/ is gitignored**; plan/spec files under `docs/research-log/` are force-added (`git add -f`) per repo precedent. Registration files under `experiments/` are tracked normally.
- Registration documents are **append-only**: addenda only, no edits to existing text (exception: the v2 registration's own DRAFT→FROZEN fill-in, which the document itself prescribes).
- Lint: `ruff check src tests tools` must stay clean (line-length 100). Full suite: `python3 -m pytest -q` (~4 min, ~1544 tests) must stay green.
- The full suite in some environments needs `--ignore` of legacy pathsig tests; if the plain run errors on collection, use the same ignore flags as CI/last green run — do not silence real failures.

---

### Task 1: Fold the frozen module constants into `engine_hash`

Closes the registration's OPEN pre-freeze item (spec decision 3): editing any frozen constant must mechanically change `engine_hash`, voiding the paper record, instead of relying on a human remembering to bump `ENGINE_VERSION`.

**Files:**
- Modify: `src/moonface/signal/engine/config.py` (the `engine_hash` function, currently lines 67–71)
- Test: `tests/test_engine_config.py`

**Interfaces:**
- Consumes: module-level constants of `moonface.signal.engine.{confluence,discipline,macro,position}` and `moonface.signal.engine.modules.{trend_book,revert_book}` (read-only).
- Produces: `engine_hash(cfg: EngineConfig) -> str` — same signature, new value (every downstream caller picks it up automatically). New private helper `_frozen_constants_payload() -> dict` in the same module.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_engine_config.py`:

```python
def test_hash_is_deterministic():
    cfg = EngineConfig()
    assert engine_hash(cfg) == engine_hash(cfg)


def test_hash_folds_trend_book_weight(monkeypatch):
    from moonface.signal.engine.modules import trend_book
    baseline = engine_hash(EngineConfig())
    monkeypatch.setattr(trend_book, "W_BREAKOUT", trend_book.W_BREAKOUT + 5)
    assert engine_hash(EngineConfig()) != baseline


def test_hash_folds_gating_matrix(monkeypatch):
    from moonface.signal.engine import confluence
    baseline = engine_hash(EngineConfig())
    patched = dict(confluence.GATE)
    patched[("BEAR", "TREND", "LONG")] = "ALLOW"
    monkeypatch.setattr(confluence, "GATE", patched)
    assert engine_hash(EngineConfig()) != baseline


def test_hash_folds_risk_lookup(monkeypatch):
    from moonface.signal.engine import discipline
    baseline = engine_hash(EngineConfig())
    patched = dict(discipline._TIER_PROFILE_FRACTION)
    patched[("A", "WT")] = 0.011
    monkeypatch.setattr(discipline, "_TIER_PROFILE_FRACTION", patched)
    assert engine_hash(EngineConfig()) != baseline
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_engine_config.py -v`
Expected: the three `test_hash_folds_*` tests FAIL (hash unchanged by the monkeypatch); `test_hash_is_deterministic` passes trivially.

- [ ] **Step 3: Implement the digest** — in `src/moonface/signal/engine/config.py`, replace the existing `engine_hash` (keep everything above it unchanged):

```python
def _frozen_constants_payload() -> dict:
    """Digest source for the frozen (non-config) engine constants. Any edit to
    these values changes engine_hash -> the journal's version filter isolates
    the old record and the forward registration is void (v2-only refocus spec,
    decision 3). Imports are function-local: config is imported by every engine
    module, so top-level imports here would be circular."""
    from moonface.signal.engine import confluence, discipline, macro, position
    from moonface.signal.engine.modules import revert_book, trend_book

    def _flat(d: dict) -> dict:
        # tuple-keyed dicts (GATE, risk lookup) -> JSON-serializable string keys
        return {"|".join(map(str, k)): v for k, v in d.items()}

    return {
        "confluence": {
            "BASE_THRESHOLD": confluence.BASE_THRESHOLD,
            "TIER_A": confluence.TIER_A,
            "CT_SURCHARGE": confluence.CT_SURCHARGE,
            "BREADTH_MIN": confluence.BREADTH_MIN,
            "GATE": _flat(confluence.GATE),
            "TREND_MAX": confluence._TREND_MAX,
            "REVERT_MAX": confluence._REVERT_MAX,
        },
        "trend_book": {k: getattr(trend_book, k) for k in (
            "W_MACRO", "W_BREAKOUT", "W_MA_ALIGN", "W_ROC_STRONG",
            "W_ROC_WEAK", "W_PULLBACK", "TREND_MA", "DONCHIAN_N",
            "PULLBACK_MA", "MOMENTUM_N")},
        "revert_book": {k: getattr(revert_book, k) for k in (
            "W_SWEEP", "W_RECLAIM", "W_DIVERGENCE", "W_FUND_CT",
            "W_OI_FLUSH", "W_STRETCH", "SWEEP_LOOKBACK", "EVENT_TTL_BARS",
            "PIVOT_K", "DIV_MAX_SPAN", "RSI_PERIOD", "OI_FLUSH_LOOKBACK")},
        "macro": {"MACRO_MA_WEEKS": macro.MACRO_MA_WEEKS,
                  "MACRO_CONFIRM_CLOSES": macro.MACRO_CONFIRM_CLOSES},
        "position": {"CT_STOP_ATR": position.CT_STOP_ATR,
                     "CT_TARGET_R": position.CT_TARGET_R,
                     "CT_MAX_BARS": position.CT_MAX_BARS},
        "risk_lookup": _flat(discipline._TIER_PROFILE_FRACTION),
    }


def engine_hash(cfg: EngineConfig) -> str:
    payload = {k: getattr(cfg, k) for k in sorted(_CONFIG_FIELDS) if k != "enabled"}
    payload["__engine_version__"] = ENGINE_VERSION
    payload["__frozen_constants__"] = _frozen_constants_payload()
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run the config tests, then the engine test files**

Run: `python3 -m pytest tests/test_engine_config.py -v`
Expected: ALL PASS (including the pre-existing `test_hash_excludes_enabled` and `test_hash_folds_in_engine_version`).

Run: `python3 -m pytest tests/test_engine_cli.py tests/test_engine_scorecard.py tests/test_engine_discipline.py tests/test_engine_evaluate.py -q`
Expected: PASS — these use `engine_hash` only relationally (same-config = same hash), never a literal hash value. If any test hard-codes a hash literal, it must be updated to compute it via `engine_hash(...)` instead.

- [ ] **Step 5: Lint and commit**

```bash
ruff check src tests
git add src/moonface/signal/engine/config.py tests/test_engine_config.py
git diff --cached --stat
git commit -m "feat(engine): fold frozen module constants into engine_hash (defense-in-depth)"
```

---

### Task 2: Journal `shadow_direction` on vetoed setups

The gate-ablation counterfactual needs the direction the macro gate vetoed. Today only the free-text `veto` string carries it. Add it as a first-class field — additive, pre-clock, no frozen scoring value changes.

**Files:**
- Modify: `src/moonface/signal/engine/confluence.py` (Decision dataclass ~line 72; `_book_context` ~line 88; `decide` ~line 128)
- Modify: `src/moonface/signal/cli.py` (`_emit_engine` journal dict, the line `"shadow_score": ...` ~line 353)
- Test: `tests/test_engine_confluence.py`, `tests/test_engine_cli.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Decision.shadow_direction: int | None` (defaults `None`; `1`/`-1` only when `veto` is set) and journal key `"shadow_direction"` on every `status="engine"` entry. Task 3 reads this journal key.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_engine_confluence.py` (reuses its existing `_m`, `_macro`, `_cfg` helpers):

```python
def test_veto_carries_shadow_direction_long():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 20),
    ]
    d = decide(trend, [], _macro("BEAR"), _cfg())
    assert d.veto is not None
    assert d.shadow_score == 80
    assert d.shadow_direction == 1


def test_veto_carries_shadow_direction_short():
    trend = [
        _m("m1_macro", -1, 20),
        _m("m2_breakout", -1, 20),
        _m("m3_roc", -1, 20),
        _m("m4_pullback", -1, 20),
    ]
    d = decide(trend, [], _macro("BULL"), _cfg())
    assert d.veto is not None
    assert d.shadow_direction == -1


def test_no_veto_means_no_shadow_direction():
    d = decide([], [], _macro("NEUTRAL"), _cfg())
    assert d.veto is None
    assert d.shadow_direction is None
```

And append to `tests/test_engine_cli.py` (same fixture pattern as `test_engine_tier_emits_and_journals`):

```python
def test_engine_journal_carries_shadow_direction_key(tmp_path, monkeypatch):
    engine_path = tmp_path / "engine.json"
    engine_path.write_text(json.dumps({
        "enabled": True, "regime_ma_fast": 10, "regime_ma_slow": 20,
        "vol_window": 8, "atr_period": 10, "lookback_bars": 400,
        "asset": {"exchange": "binance", "symbol": "BTC/USDT:USDT",
                  "timeframe": "1h"}}))
    journal = tmp_path / "signals.jsonl"
    monkeypatch.setattr(cli_mod, "load_bundle",
                        lambda asset, s, e, cd: DataBundle(candles=_rising(400)),
                        raising=False)
    monkeypatch.setattr(cli_mod, "_now_ms", lambda: 400 * H)
    monkeypatch.setattr(cli_mod, "fetch_deriv_snapshot",
                        lambda symbol, now: None, raising=False)
    rc = cli_mod.run([
        "--strategy", str(tmp_path / "missing.json"),
        "--policy", str(tmp_path / "missing.json"),
        "--baseline", str(tmp_path / "missing_baseline.json"),
        "--engine", str(engine_path),
        "--journal", str(journal), "--json"])
    assert rc == 0
    lines = [json.loads(x) for x in journal.read_text().splitlines() if x.strip()]
    assert "shadow_direction" in lines[-1]
    assert "shadow_score" in lines[-1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_engine_confluence.py tests/test_engine_cli.py -v`
Expected: the three new confluence tests FAIL with `AttributeError: 'Decision' object has no attribute 'shadow_direction'`; the CLI test FAILS on the missing journal key.

- [ ] **Step 3: Implement** — three edits in `src/moonface/signal/engine/confluence.py`:

(a) Add the field to `Decision` (defaults keep the extreme-vol early-return construction unchanged):

```python
@dataclass(frozen=True)
class Decision:
    action: str
    direction: int
    archetype: str | None
    policy: str | None
    score: int
    max_attainable: int
    breadth: int
    tier: str | None
    veto: str | None
    shadow_score: int | None
    modules: tuple[ModuleScore, ...]
    detail: str
    shadow_direction: int | None = None
```

(b) In `_book_context`, record the vetoed direction. Replace:

```python
            if breadth >= BREADTH_MIN and score >= BASE_THRESHOLD:
                veto = f"macro {macro_effective} vetoes {label} {direction_label.lower()}"
                shadow_score = score
```

with:

```python
            if breadth >= BREADTH_MIN and score >= BASE_THRESHOLD:
                veto = f"macro {macro_effective} vetoes {label} {direction_label.lower()}"
                shadow_score = score
                shadow_direction = direction
```

and initialize `shadow_direction: int | None = None` alongside the existing `shadow_score: int | None = None` near the top of the function, then add `"shadow_direction": shadow_direction,` to the returned dict (next to `"shadow_score"`).

(c) In `decide`, next to the existing shadow_score line:

```python
    veto = trend_ctx["veto"] or revert_ctx["veto"]
    shadow_score = trend_ctx["shadow_score"] if trend_ctx["veto"] else revert_ctx["shadow_score"]
    shadow_direction = (trend_ctx["shadow_direction"] if trend_ctx["veto"]
                        else revert_ctx["shadow_direction"])
```

and pass `shadow_direction=shadow_direction,` in all four `Decision(...)` constructions that already pass `veto=veto, shadow_score=shadow_score` (the no-candidates WAIT, single-candidate SETUP, books-conflict WAIT, and winner SETUP). The extreme-volatility early return stays untouched (field default `None`).

Then in `src/moonface/signal/cli.py::_emit_engine`, directly below the `"shadow_score"` line in the `append_entry` dict, add:

```python
        "shadow_direction": (decision.shadow_direction
                             if decision is not None else None),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_engine_confluence.py tests/test_engine_cli.py tests/test_engine_evaluate.py tests/test_engine_setupcard.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Lint and commit**

```bash
ruff check src tests
git add src/moonface/signal/engine/confluence.py src/moonface/signal/cli.py tests/test_engine_confluence.py tests/test_engine_cli.py
git diff --cached --stat
git commit -m "feat(engine): journal shadow_direction on macro-vetoed setups"
```

---

### Task 3: Gate-ablation pure function

The registration makes the gate-ablation report MANDATORY at the horizon verdict. Build the pure function now, before any forward data exists (no peeking risk, guaranteed availability later).

**Files:**
- Create: `src/moonface/signal/engine/ablation.py`
- Test: `tests/test_engine_ablation.py`

**Interfaces:**
- Consumes: journal entry dicts (Task 2's `shadow_direction`/`shadow_score`/`veto`/`regime_vol`/`candle_ts_ms` keys); `engine_entries` + `tier_size_fraction` from `discipline`; `open_position`/`manage_position`/`PositionState` from `position`; `TIER_A` from `confluence`; `engine_hash` from `config`.
- Produces: `gate_ablation(entries: list[dict], candles: list[Candle], cfg: EngineConfig) -> dict` — Task 4's CLI prints exactly this dict.

- [ ] **Step 1: Write the failing tests** — create `tests/test_engine_ablation.py`:

```python
from moonface.foundation.models import Candle
from moonface.signal.engine.ablation import gate_ablation
from moonface.signal.engine.config import EngineConfig, engine_hash

H = 3_600_000


def _rising(n, start=100.0, step=1.0, spread=3.0):
    out, p = [], start
    for i in range(n):
        out.append(Candle(i * H, p, p + spread, p - spread, p, 1.0))
        p += step
    return out


def _cfg():
    return EngineConfig(enabled=True, atr_period=10)


def _veto_entry(cfg, bar_idx, direction, score=80, vol="normal"):
    return {
        "status": "engine",
        "strategy_version": engine_hash(cfg),
        "decision": "WAIT",
        "action": "WAIT",
        "veto": "macro BULL vetoes TREND short",
        "shadow_score": score,
        "shadow_direction": direction,
        "candle_ts_ms": bar_idx * H,
        "regime_vol": vol,
        "ts_ms": bar_idx * H + H,
    }


def test_empty_journal_reports_zeros():
    rep = gate_ablation([], _rising(50), _cfg())
    assert rep["n_vetoed"] == 0
    assert rep["counterfactual"]["net_r_if_taken"] == 0.0
    assert rep["counterfactual"]["rows"] == []
    assert rep["assumptions"]


def test_short_veto_on_rising_series_resolves_negative():
    cfg = _cfg()
    candles = _rising(60)
    rep = gate_ablation([_veto_entry(cfg, 30, -1, score=80)], candles, cfg)
    assert rep["n_vetoed"] == 1
    assert rep["shadow_scores"]["count"] == 1
    assert rep["shadow_scores"]["tier_a"] == 1        # 80 >= TIER_A(75)
    row = rep["counterfactual"]["rows"][0]
    assert row["resolved"] is True
    assert row["net_r"] < 0                           # short into a rally loses
    # a losing counterfactual means the gate SAVED that R
    assert rep["counterfactual"]["gate_saved_r"] > 0


def test_long_veto_never_exits_stays_unresolved():
    cfg = _cfg()
    candles = _rising(60)
    rep = gate_ablation([_veto_entry(cfg, 30, 1, score=70)], candles, cfg)
    row = rep["counterfactual"]["rows"][0]
    assert row["resolved"] is False
    assert row["net_r"] is None
    assert rep["shadow_scores"]["tier_b"] == 1        # 70 < TIER_A(75)
    # unresolved rows are excluded from the counterfactual sum
    assert rep["counterfactual"]["net_r_if_taken"] == 0.0


def test_missing_or_early_veto_bars_are_skipped():
    cfg = _cfg()
    candles = _rising(60)
    entries = [
        _veto_entry(cfg, 5, -1),         # inside ATR warmup -> skipped
        _veto_entry(cfg, 999, -1),       # bar not in the series -> skipped
        {**_veto_entry(cfg, 30, -1), "shadow_direction": None},  # no direction
    ]
    rep = gate_ablation(entries, candles, cfg)
    assert rep["n_vetoed"] == 3
    assert rep["counterfactual"]["replayed"] == 0
    assert all(r["skipped"] for r in rep["counterfactual"]["rows"])


def test_other_versions_and_non_vetoes_ignored():
    cfg = _cfg()
    entries = [
        {"status": "engine", "strategy_version": "someotherhash",
         "veto": "x", "shadow_score": 80, "shadow_direction": 1,
         "candle_ts_ms": 30 * H, "ts_ms": 31 * H},
        {"status": "engine", "strategy_version": engine_hash(cfg),
         "veto": None, "action": "WAIT", "candle_ts_ms": 31 * H,
         "ts_ms": 32 * H},
        {"status": "paper", "strategy_version": engine_hash(cfg),
         "veto": "x", "shadow_score": 80, "shadow_direction": 1,
         "candle_ts_ms": 32 * H, "ts_ms": 33 * H},
    ]
    rep = gate_ablation(entries, _rising(60), cfg)
    assert rep["n_vetoed"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_engine_ablation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.ablation'`.

- [ ] **Step 3: Implement** — create `src/moonface/signal/engine/ablation.py`:

```python
# src/moonface/signal/engine/ablation.py
"""Gate-ablation report over the engine forward journal (read-only diagnostic).

The v2 forward registration makes this report MANDATORY at the horizon: how
many setups the 1W macro gate vetoed, the distribution of their shadow_scores,
and the counterfactual R had the vetoed setups been taken. The reporter never
gates and never mutates state; it exists so the gate's value is measurable from
the forward record instead of assumed."""
from __future__ import annotations

from statistics import median

from moonface.foundation.models import Candle
from moonface.signal.engine.config import EngineConfig, engine_hash
from moonface.signal.engine.confluence import TIER_A
from moonface.signal.engine.discipline import engine_entries, tier_size_fraction
from moonface.signal.engine.position import (PositionState, manage_position,
                                             open_position)

ASSUMPTIONS = (
    "each vetoed setup is replayed independently — no interaction with the"
    " real book or other replays (overlapping replays double-count exposure)",
    "vetoed setups are TREND-book by construction (the gate REJECTs only"
    " TREND cells), so the WT discipline (k_stop/k_trail/max_bars) applies",
    "entry at the veto bar's close; cost accounting identical to the engine",
    "sizing = frozen tier lookup at the journaled regime_vol",
)


def _shadow_tier(score: int) -> str:
    # REJECT cells never apply the CT surcharge, so base TIER_A splits A/B
    return "A" if score >= TIER_A else "B"


def _replay(candles: list[Candle], i: int, direction: int, fraction: float,
            cfg: EngineConfig) -> tuple[float | None, int]:
    """WT replay entering at candles[i].close. Returns (net_r, bars_held);
    net_r is None when the replay is still open at the end of the series."""
    step = open_position(candles[:i + 1], cfg, direction, 0.0, fraction, "WT")
    pos = PositionState(direction, step.entry_price, step.stop, step.extreme,
                        step.atr_at_entry, fraction, 0)
    for j in range(i + 1, len(candles)):
        step = manage_position([candles[j]], cfg, pos, 0, 0.0)
        if step.action == "EXIT":
            return step.realized_r, step.bars_held
        pos = PositionState(direction, step.entry_price, step.stop,
                            step.extreme, step.atr_at_entry, fraction,
                            step.bars_held)
    return None, pos.bars_held


def gate_ablation(entries: list[dict], candles: list[Candle],
                  cfg: EngineConfig) -> dict:
    version = engine_hash(cfg)
    vetoed = [e for e in engine_entries(entries, version) if e.get("veto")]
    scores = sorted(int(e["shadow_score"]) for e in vetoed
                    if e.get("shadow_score") is not None)
    by_ts = {c.timestamp_ms: idx for idx, c in enumerate(candles)}

    rows: list[dict] = []
    for e in vetoed:
        score = e.get("shadow_score")
        direction = e.get("shadow_direction")
        idx = by_ts.get(e.get("candle_ts_ms"))
        row = {"candle_ts_ms": e.get("candle_ts_ms"),
               "shadow_score": score, "shadow_direction": direction,
               "tier": _shadow_tier(int(score)) if score is not None else None,
               "net_r": None, "bars_held": None, "resolved": False,
               "skipped": None}
        if direction not in (1, -1) or score is None:
            row["skipped"] = "missing shadow fields"
        elif idx is None:
            row["skipped"] = "veto bar not in candle series"
        elif idx < cfg.atr_period + 1:
            row["skipped"] = "insufficient ATR warmup before veto bar"
        else:
            fraction = tier_size_fraction(row["tier"], "WT",
                                          e.get("regime_vol") or "normal", cfg)
            net_r, bars = _replay(candles, idx, int(direction), fraction, cfg)
            row.update(net_r=net_r, bars_held=bars,
                       resolved=net_r is not None)
        rows.append(row)

    resolved = [r["net_r"] for r in rows if r["resolved"]]
    counterfactual = round(sum(resolved), 4) if resolved else 0.0
    return {
        "engine_hash": version,
        "n_vetoed": len(vetoed),
        "shadow_scores": {
            "count": len(scores),
            "min": scores[0] if scores else None,
            "median": median(scores) if scores else None,
            "max": scores[-1] if scores else None,
            "tier_a": sum(1 for s in scores if s >= TIER_A),
            "tier_b": sum(1 for s in scores if s < TIER_A),
        },
        "counterfactual": {
            "replayed": sum(1 for r in rows if r["skipped"] is None),
            "resolved": len(resolved),
            "net_r_if_taken": counterfactual,
            "gate_saved_r": round(-counterfactual, 4),
            "rows": rows,
        },
        "assumptions": list(ASSUMPTIONS),
        "note": "DIAGNOSTIC ONLY — never gates, never mutates state",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_engine_ablation.py -v`
Expected: ALL PASS. If `test_short_veto_on_rising_series_resolves_negative` fails on `resolved is True`, the series is too short for the stop to fill — the fixture's 60 bars with `atr_period=10`, `k_stop=2.0` puts the short stop ≈ entry+12 with highs rising 1/bar, filling ~9 bars after entry; do not change frozen constants to make the test pass, extend the fixture instead.

- [ ] **Step 5: Lint and commit**

```bash
ruff check src tests
git add src/moonface/signal/engine/ablation.py tests/test_engine_ablation.py
git diff --cached --stat
git commit -m "feat(engine): gate-ablation reporter (mandatory horizon diagnostic)"
```

---

### Task 4: Ablation CLI (`tools/engine_ablation.py`)

**Files:**
- Create: `tools/engine_ablation.py`
- Test: `tests/test_engine_ablation_cli.py`

**Interfaces:**
- Consumes: `gate_ablation` (Task 3), `load_engine_config`/`engine_hash`, `engine_entries`, `read_entries`, `load_bundle(asset, start_ms, end_ms, cache_dir)` from `moonface.foundation.bundle`, `TIMEFRAME_MS` from `moonface.foundation.data`.
- Produces: `run(argv: list[str] | None = None) -> int` printing the `gate_ablation` dict as JSON. Read-only: never writes the journal or any config.

- [ ] **Step 1: Write the failing test** — create `tests/test_engine_ablation_cli.py`:

```python
import json

import tools.engine_ablation as ea
from moonface.foundation.bundle import DataBundle
from moonface.foundation.models import Candle
from moonface.signal.engine.config import EngineConfig, engine_hash

H = 3_600_000


def _rising(n, start=100.0, step=1.0, spread=3.0):
    out, p = [], start
    for i in range(n):
        out.append(Candle(i * H, p, p + spread, p - spread, p, 1.0))
        p += step
    return out


def test_cli_reports_vetoed_setups(tmp_path, monkeypatch, capsys):
    engine_path = tmp_path / "engine.json"
    engine_path.write_text(json.dumps({"enabled": True, "atr_period": 10}))
    cfg_hash = engine_hash(EngineConfig(enabled=True, atr_period=10))
    journal = tmp_path / "signals.jsonl"
    journal.write_text(json.dumps({
        "status": "engine", "strategy_version": cfg_hash,
        "veto": "macro BULL vetoes TREND short", "shadow_score": 80,
        "shadow_direction": -1, "candle_ts_ms": 30 * H,
        "regime_vol": "normal", "ts_ms": 31 * H}) + "\n")
    monkeypatch.setattr(ea, "load_bundle",
                        lambda asset, s, e, cd: DataBundle(candles=_rising(60)))
    rc = ea.run(["--journal", str(journal), "--engine", str(engine_path),
                 "--cache-dir", str(tmp_path / "cache")])
    assert rc == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["n_vetoed"] == 1
    assert rep["counterfactual"]["resolved"] == 1


def test_cli_no_vetoes_skips_fetch(tmp_path, monkeypatch, capsys):
    engine_path = tmp_path / "engine.json"
    engine_path.write_text(json.dumps({"enabled": True}))
    journal = tmp_path / "signals.jsonl"
    journal.write_text("")

    def _boom(*a, **kw):
        raise AssertionError("must not fetch when there are no vetoes")

    monkeypatch.setattr(ea, "load_bundle", _boom)
    rc = ea.run(["--journal", str(journal), "--engine", str(engine_path)])
    assert rc == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["n_vetoed"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_engine_ablation_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.engine_ablation'`.

- [ ] **Step 3: Implement** — create `tools/engine_ablation.py`:

```python
#!/usr/bin/env python3
"""Read-only gate-ablation report for the confluence engine v2 forward record.

Usage:
    python tools/engine_ablation.py [--journal journal/signals.jsonl]
        [--engine promotion/engine.json] [--cache-dir .backtest_cache]

Prints the gate_ablation JSON (moonface.signal.engine.ablation): macro-vetoed
setup counts, shadow_score distribution, and the counterfactual R had the
vetoed setups been taken. Mandatory input to the horizon verdict per
experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md. Never writes the
journal or any config."""
from __future__ import annotations

import argparse
import json
import time

from moonface.foundation.bundle import load_bundle
from moonface.foundation.data import TIMEFRAME_MS
from moonface.signal.engine.ablation import gate_ablation
from moonface.signal.engine.config import engine_hash, load_engine_config
from moonface.signal.engine.discipline import engine_entries
from moonface.signal.journal import read_entries

WARMUP_BARS = 60          # ATR warmup headroom fetched before the first veto


def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal", default="journal/signals.jsonl")
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--cache-dir", default=".backtest_cache")
    args = p.parse_args(argv)

    cfg = load_engine_config(args.engine)
    entries = read_entries(args.journal)
    version = engine_hash(cfg)
    vetoed_ts = [int(e["candle_ts_ms"])
                 for e in engine_entries(entries, version)
                 if e.get("veto") and e.get("candle_ts_ms") is not None]
    if not vetoed_ts:
        print(json.dumps(gate_ablation(entries, [], cfg),
                         indent=2, sort_keys=True))
        return 0

    tf_ms = TIMEFRAME_MS[cfg.asset["timeframe"]]
    start_ms = min(vetoed_ts) - WARMUP_BARS * tf_ms
    end_ms = (int(time.time() * 1000) // tf_ms) * tf_ms
    bundle = load_bundle(cfg.asset, start_ms, end_ms, args.cache_dir)
    print(json.dumps(gate_ablation(entries, bundle.candles, cfg),
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_engine_ablation_cli.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Lint and commit**

```bash
ruff check src tests tools
git add tools/engine_ablation.py tests/test_engine_ablation_cli.py
git diff --cached --stat
git commit -m "feat(engine): read-only gate-ablation CLI for the horizon verdict"
```

---

### Task 5: Suspend all non-engine lineages (archive + engine-only manifest)

**Files:**
- Create: `promotion/archive/2026-07-03-v2-refocus/README.md`, `promotion/baseline.json`
- Move (git mv): `promotion/strategy.json`, `promotion/mtf_long/` (whole dir), `promotion/day/` (whole dir), `promotion/participation.json` → under `promotion/archive/2026-07-03-v2-refocus/`
- Modify: `promotion/styles.json`, `tests/test_signal_style.py`
- Test: `tests/test_signal_style.py`, `tests/test_engine_cli.py`

**Interfaces:**
- Consumes: existing tier routing in `cli.py` (`_load_style`, `run`) — deliberately unmodified.
- Produces: a repo state in which the only journal-writing path is the engine tier. Task 7 freezes on top of this state.

- [ ] **Step 1: Update the shipped-manifest test and add routing tests (failing first)** — in `tests/test_signal_style.py`, REPLACE `test_shipped_manifest_resolves_two_labeled_styles` with:

```python
def test_shipped_manifest_resolves_single_engine_style():
    styles = load_styles(Path("promotion/styles.json"))
    assert styles is not None
    assert [s.name for s in styles] == ["engine"]
    assert styles[0].label is True
    assert styles[0].engine == "promotion/engine.json"
    assert styles[0].strategy == "promotion/none.json"
    assert styles[0].policy == "promotion/none.json"
    assert styles[0].baseline == "promotion/baseline.json"


def test_archived_lineages_not_at_live_paths():
    # the watch loop and one-shot CLI must be physically unable to load the
    # suspended lineages from their registered paths
    for gone in ("promotion/strategy.json", "promotion/mtf_long/strategy.json",
                 "promotion/participation.json"):
        assert not Path(gone).exists(), f"{gone} must be archived"
    archive = Path("promotion/archive/2026-07-03-v2-refocus")
    for kept in ("strategy.json", "mtf_long/strategy.json",
                 "participation.json", "README.md"):
        assert (archive / kept).exists(), f"{archive/kept} must be preserved"


def test_shipped_baseline_stub_is_disabled():
    import json as _json
    raw = _json.loads(Path("promotion/baseline.json").read_text())
    assert raw == {"enabled": False}
```

And append to `tests/test_engine_cli.py`:

```python
def test_load_style_routes_engine_when_no_strategy(tmp_path):
    from moonface.signal.engine.config import engine_hash, load_engine_config
    from moonface.signal.style import Style
    engine_path = tmp_path / "engine.json"
    engine_path.write_text(json.dumps({"enabled": True}))
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"enabled": False}))
    style = Style(name="engine", strategy=str(tmp_path / "none.json"),
                  policy=str(tmp_path / "none.json"),
                  baseline=str(baseline_path), engine=str(engine_path))
    ev = cli_mod._load_style(style)
    assert ev.strategy is None
    assert ev.engine_cfg is not None and ev.engine_cfg.enabled
    assert ev.version == engine_hash(load_engine_config(engine_path))


def test_disabled_engine_falls_to_disabled_baseline_wait(tmp_path, capsys):
    # defense-in-depth: with the engine off, the shipped stack must print the
    # no-strategy WAIT — never revive the on-by-default heuristic baseline
    engine_path = tmp_path / "engine.json"
    engine_path.write_text(json.dumps({"enabled": False}))
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"enabled": False}))
    journal = tmp_path / "signals.jsonl"
    rc = cli_mod.run([
        "--strategy", str(tmp_path / "missing.json"),
        "--policy", str(tmp_path / "missing.json"),
        "--baseline", str(baseline_path),
        "--engine", str(engine_path),
        "--journal", str(journal)])
    assert rc == 0
    assert "WAIT (no validated strategy)" in capsys.readouterr().out
    assert not journal.exists()
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python3 -m pytest tests/test_signal_style.py tests/test_engine_cli.py -v`
Expected: `test_shipped_manifest_resolves_single_engine_style`, `test_archived_lineages_not_at_live_paths`, `test_shipped_baseline_stub_is_disabled` FAIL (files not moved yet). The two routing tests should PASS already (routing code is unchanged by design) — they are regression guards.

- [ ] **Step 3: Archive-move and write the new configs**

```bash
mkdir -p promotion/archive/2026-07-03-v2-refocus
git mv promotion/strategy.json promotion/archive/2026-07-03-v2-refocus/strategy.json
git mv promotion/mtf_long promotion/archive/2026-07-03-v2-refocus/mtf_long
git mv promotion/day promotion/archive/2026-07-03-v2-refocus/day
git mv promotion/participation.json promotion/archive/2026-07-03-v2-refocus/participation.json
```

Write `promotion/styles.json` (overwrite):

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

Write `promotion/baseline.json` (new):

```json
{"enabled": false}
```

Write `promotion/archive/2026-07-03-v2-refocus/README.md`:

```markdown
# Archived promotion configs — v2-only refocus (2026-07-03)

Archived by the human refocus mandate of 2026-07-03 (spec:
docs/research-log/specs/2026-07-03-v2-only-refocus-design.md). From this date
only the confluence engine v2 may produce new paper-forward signals.

Contents (moved verbatim, never edited):
- strategy.json — Donchian 4h 40/20 paper lineage (hash df7cc856…). Its Slice-3
  forward registration is WITHDRAWN-UNRESOLVED; see the addendum in
  experiments/deployable/DONCHIAN_SLICE3_FORWARD_REGISTRATION.md.
- mtf_long/ — MTF long-only paper lineage (hash df023c2…) + its styles
  manifest. Registration WITHDRAWN-UNRESOLVED; see the addendum in
  experiments/mtf/LONG_ONLY_FORWARD_REGISTRATION.md.
- day/ — the disabled day-slot baseline stub.
- participation.json — the disabled post-program participation advisor.

Governance: these files are preserved for audit and comparison. Nothing here
may be re-pointed at by a styles manifest or promotion path without a NEW
frozen forward registration (fresh clock). Historical journal entries for
these lineages remain in journal/signals.jsonl, isolated by strategy_version.
```

- [ ] **Step 4: Run the affected tests, then the full suite**

Run: `python3 -m pytest tests/test_signal_style.py tests/test_engine_cli.py -v`
Expected: ALL PASS.

Run: `python3 -m pytest -q`
Expected: green (~1544 passed, ~3 skipped, ~4 min). Any failure that mentions `promotion/...` paths means a test depended on the moved files — fix the TEST to use the archive path or a tmp fixture, never move the files back.

- [ ] **Step 5: Commit**

```bash
git add promotion/ tests/test_signal_style.py tests/test_engine_cli.py
git diff --cached --stat
git commit -m "feat(promotion): v2-only refocus — archive non-engine lineages, engine-only manifest"
```

---

### Task 6: WITHDRAWN-UNRESOLVED addenda on the two stranded registrations

**Files:**
- Modify (append-only): `experiments/deployable/DONCHIAN_SLICE3_FORWARD_REGISTRATION.md`
- Modify (append-only): `experiments/mtf/LONG_ONLY_FORWARD_REGISTRATION.md`

**Interfaces:**
- Consumes: archive location from Task 5.
- Produces: closed governance state for both lineages; referenced by Task 5's archive README (already written pointing here).

- [ ] **Step 1: Append to `experiments/deployable/DONCHIAN_SLICE3_FORWARD_REGISTRATION.md`** (at end of file, no other edits):

```markdown

## ADDENDUM — WITHDRAWN, SUSPENDED UNRESOLVED (2026-07-03)

Administrative withdrawal by the human v2-only refocus mandate of 2026-07-03
(spec: docs/research-log/specs/2026-07-03-v2-only-refocus-design.md). This is
NOT a REAFFIRM and NOT a DOWNGRADE — the frozen resolution rule above was
never triggered.

- State at withdrawal: 0 closed trades, 0 open trades, ~1.9 of 12 weeks
  elapsed since t0 2026-06-20; all 23 journal entries at df7cc856… are WAIT.
- The forward clock is VOID as of this date. The strategy config is archived
  verbatim at promotion/archive/2026-07-03-v2-refocus/strategy.json and is no
  longer loadable from any promotion path.
- Journal history is preserved untouched (journal/signals.jsonl, filtered by
  strategy_version df7cc856…).
- Resuming this lineage requires a NEW registration with a fresh clock and
  fresh criteria; this document stays closed forever.
```

- [ ] **Step 2: Append to `experiments/mtf/LONG_ONLY_FORWARD_REGISTRATION.md`** (at end of file, no other edits):

```markdown

## ADDENDUM — WITHDRAWN, SUSPENDED UNRESOLVED (2026-07-03)

Administrative withdrawal by the human v2-only refocus mandate of 2026-07-03
(spec: docs/research-log/specs/2026-07-03-v2-only-refocus-design.md). This is
NOT a REAFFIRM and NOT a DOWNGRADE — the frozen resolution rule above was
never triggered.

- State at withdrawal: frozen 2026-07-01, 0 closed forward trades; all 39
  journal entries at df023c2… are WAIT.
- The forward clock is VOID as of this date. The strategy config and its
  styles manifest are archived verbatim under
  promotion/archive/2026-07-03-v2-refocus/mtf_long/ and are no longer loadable
  from any promotion path.
- Journal history is preserved untouched (journal/signals.jsonl, filtered by
  strategy_version df023c2…).
- Resuming this lineage requires a NEW registration with a fresh clock and
  fresh criteria; this document stays closed forever.
```

- [ ] **Step 3: Verify append-only** — confirm the diff only ADDS lines at the end of each file:

Run: `git diff -- experiments/deployable/DONCHIAN_SLICE3_FORWARD_REGISTRATION.md experiments/mtf/LONG_ONLY_FORWARD_REGISTRATION.md | grep -c "^-[^-]"`
Expected output: `0` (no removed lines).

- [ ] **Step 4: Commit**

```bash
git add experiments/deployable/DONCHIAN_SLICE3_FORWARD_REGISTRATION.md experiments/mtf/LONG_ONLY_FORWARD_REGISTRATION.md
git diff --cached --stat
git commit -m "docs(governance): withdraw Donchian Slice-3 + MTF long-only forward registrations (unresolved)"
```

---

### Task 7: Complete the v2 freeze runbook

Must run LAST — the hash frozen here depends on Tasks 1–2 being merged.

**Files:**
- Create/overwrite: `promotion/engine.json` (gitignored — written, never committed)
- Modify: `experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md` (the DRAFT→FROZEN fill-in the document itself prescribes)
- Delete: the stray 0-byte repo-root file `paper signal: LONG @ 100.0, invalidation 95.0, f=0.01` (untracked)

**Interfaces:**
- Consumes: final `engine_hash` from Tasks 1–2; engine-only promotion state from Task 5.
- Produces: FROZEN registration + armed config. The human starts `moonface-signal --watch` afterward (out of scope).

- [ ] **Step 1: Pre-freeze checks**

Run: `grep -c '"status": "engine"' journal/signals.jsonl || true`
Expected output: `0` (the forward record starts clean; if nonzero, STOP and escalate to the human — do not delete journal lines).

Run: `test -f promotion/strategy.json && echo LIVE || echo ARCHIVED`
Expected output: `ARCHIVED` (Task 5 landed).

- [ ] **Step 2: Write the armed engine config** — overwrite `promotion/engine.json` with exactly (this is the tracked `.example` plus `enabled: true`; it must differ from `EngineConfig()` defaults ONLY in `enabled`):

```json
{
  "enabled": true,
  "asset": {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "1h"},
  "lookback_bars": 6000,
  "k_stop": 2.0,
  "k_trail": 3.0,
  "base_fraction": 0.005,
  "max_fraction": 0.02,
  "drawdown_budget_r": 15.0,
  "drawdown_window_days": 90.0,
  "hard_drawdown_budget_r": 30.0,
  "cooldown_bars": 6
}
```

- [ ] **Step 3: Compute and verify the frozen hash**

Run:

```bash
python3 -c "
from moonface.signal.engine.config import EngineConfig, engine_hash, load_engine_config
default = engine_hash(EngineConfig())
loaded = engine_hash(load_engine_config('promotion/engine.json'))
cfg = load_engine_config('promotion/engine.json')
assert cfg.enabled and cfg.lookback_bars == 6000, 'config not armed correctly'
assert default == loaded, f'hash mismatch: {default} != {loaded}'
print('engine_hash =', loaded)
"
```

Expected: prints `engine_hash = <64-hex>` with no assertion error. Record the printed value — it is the frozen hash used in Step 4.

- [ ] **Step 4: Freeze the registration** — edit `experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md`:

(a) Replace the STATUS block:

```markdown
**STATUS: DRAFT — a human must freeze this document before enabling the engine.**
Until this file is frozen (STATUS changed to `FROZEN`, dates/hashes filled in, committed),
the engine stays `enabled=False` and no forward clock runs. Freezing, enabling, and starting
the clock are human-only actions.
```

with:

```markdown
**STATUS: FROZEN (2026-07-03, human-approved v2-only refocus mandate).**
Frozen per the approved spec docs/research-log/specs/2026-07-03-v2-only-refocus-design.md.
No frozen value below may change until the horizon; any change is a new
ENGINE_VERSION → new hash → new registration.
```

(b) Replace the fill-in line

```markdown
- Fill in at freeze time: `engine_hash = ____________________` (run
```

and its continuation lines (`python -c ...`, `enable_date_utc = __________`, `journal_path = __________`, `symbol/timeframe = BTC/USDT:USDT 1h`.) with (substituting the Step-3 hash and the actual UTC date of execution):

```markdown
- Frozen at freeze time: `engine_hash = <PASTE STEP-3 VALUE>`,
  `enable_date_utc = 2026-07-03`, `journal_path = journal/signals.jsonl`,
  `symbol/timeframe = BTC/USDT:USDT 1h`.
```

(c) Replace the OPEN checklist item paragraph beginning `- **OPEN (human decision) — hash does not auto-cover module constants.**` (the whole bullet) with:

```markdown
- **RESOLVED (2026-07-03) — hash now auto-covers the module constants.**
  `engine_hash` folds a digest of the frozen weight/threshold/gate/panel/risk
  constants (`_frozen_constants_payload` in
  src/moonface/signal/engine/config.py), so editing any frozen constant
  mechanically resets the paper record. The ENGINE_VERSION-bump convention
  remains as a second, human-visible layer.
```

(d) Append a freeze record at the end of the file:

```markdown

## Freeze record (2026-07-03)

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
```

- [ ] **Step 5: Remove the stray root artifact**

Run: `rm "paper signal: LONG @ 100.0, invalidation 95.0, f=0.01"`
Then: `git status --short` — expected: only the registration file modified (promotion/engine.json is ignored).

- [ ] **Step 6: Full suite + lint**

Run: `python3 -m pytest -q` — expected green.
Run: `ruff check src tests tools` — expected clean.

- [ ] **Step 7: Commit the freeze**

```bash
git add experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md
git diff --cached --stat
git commit -m "docs(engine): FREEZE confluence v2 forward registration (hash covers module constants)"
```

- [ ] **Step 8: Hand back to the human** — report the frozen hash and state plainly: the engine is armed for paper-forward journaling; starting `moonface-signal --watch` (and keeping it running) is the human's operational decision; the horizon verdict is due at the later of 6 months from 2026-07-03 or ≥30 completed setups, and MUST include the gate-ablation report.

---

## Self-review notes (already applied)

- **Spec coverage:** decision 1 → Task 6; decision 2 → Tasks 3/7 (shared journal, hash-filtered); decision 3 → Task 1; decision 4 → Task 7 Step 8. Spec §1 → Task 5; §2 → Task 6; §3a → Task 1 (+Task 2 enabling §3b's counterfactual); §3b → Tasks 3–4; §4 → Task 7; §5 → Task 7 Step 8 (no code — unchanged registration semantics); §6 → test steps of Tasks 1–5. Stray-file cleanup → Task 7 Step 5.
- **Ordering:** Tasks 1–2 change the hash/journal schema and MUST precede Task 7. Tasks 3–6 are order-independent among themselves but Task 6's addenda reference Task 5's archive paths, so keep 5 → 6.
- **Type consistency:** `gate_ablation(entries, candles, cfg)` matches Task 4's call; `Decision.shadow_direction: int | None = None` matches the journal key and ablation's `e.get("shadow_direction")`; `PositionState(direction, entry_price, stop, extreme, atr_at_entry, fraction, bars_held)` positional order matches `position.py`.
- **Known judgment call:** vetoed CT setups cannot exist (GATE REJECTs only TREND cells), so the WT-only replay in Task 3 is exact, not an approximation — asserted in `ASSUMPTIONS` for the record.
