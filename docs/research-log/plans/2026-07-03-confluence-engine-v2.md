# Confluence Engine v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the existing confluence paper tier (`src/moonface/signal/engine/`) into the v2 Pro-Trader-Assistant: five fixed-weight scoring modules on two archetype scorebooks (TREND / MEAN_REVERT), a 1W Macro Gating Matrix (veto-only, shadow-scored), threshold+breadth trigger, archetype-specific risk profiles, SetupCard output — shipped DISABLED, paper-only, forward-evaluated.

**Architecture:** In-place rewrite of the v1 engine package. Frozen spec: `docs/research-log/specs/2026-07-03-confluence-engine-v2-design.md`. Weights/thresholds/gate table live as frozen constants in code (NOT in `EngineConfig`); `ENGINE_VERSION` is folded into `engine_hash`, so v2 journal entries are versioned apart from v1's and any constant change resets the paper record. The watch-loop CLI keeps its existing call shape (`evaluate_engine(cfg, bundle, entries, now)` + optional deriv snapshot).

**Tech Stack:** Python 3.11 stdlib only. Reuses `moonface.foundation.{indicators, models, risk, metrics, bundle, data}`, `moonface.signal.baseline.vol_ratio`, `moonface.research.universe_data.fetch_funding_rates` (deriv adapter only). Tests: `unittest`, same style as `tests/test_engine_*.py`.

## Global Constraints

Copied from the frozen spec + repo rules. Every task's requirements implicitly include these.

- **NO edge claim:** v1's `NO_CLAIM` banner stays verbatim on every emitted signal. Engine ships `enabled=False`; enabling is human-only. PAPER only.
- **Frozen scoring (quantum 5, both books max 100):**
  - TREND book: M1 macro aligned+confirmed +20 (else 0); M2 Donchian-40 4h breakout +20, MA-alignment (close & SMA-20 on d-side of SMA-50, 4h) +10; M3 ROC-12 4h ≥5% +20 / ≥2% +10; M4 1h pullback-to-SMA-20 in intact trend +15; M5 funding vs d: extreme-against +15 / neutral(10th–80th pct) +5 / crowded-in-d 0.
  - MEAN_REVERT book: M4 sweep of prior 20-bar 1h extreme (wick beyond, close inside) +20, next-close reclaim +15; M3 RSI-14 divergence (k=2 confirmed pivots, ≤40 bars apart) +25; M5 funding extreme against bounce +15, OI flush ≥3%/6h +10; M2 stretch ≥2×ATR beyond SMA-50 (1h) +15.
  - Signed points; opposing evidence subtracts inside a book; `data_ok=False` → module scores 0 AND book max drops by its weight (no renormalisation); event scores (sweep/reclaim/divergence) valid confirm-bar +2 then expire.
- **Trigger:** score ≥ 60 (ALLOW_CT: ≥ 70) AND breadth ≥ 3 modules non-zero in direction. Tier A ≥ 75 (ALLOW_CT: ≥ 85), else Tier B. Book arbitration: same direction → higher score; opposite → WAIT.
- **Gate (veto-only):** `(BEAR, TREND, LONG) → REJECT`; `(BEAR, MEAN_REVERT, LONG) → ALLOW_CT`; BEAR shorts ALLOW; BULL mirror; NEUTRAL all ALLOW. Every REJECT journals `veto` + `shadow_score`. Extreme vol → flat (v1 rule). Macro hysteresis: 2 consecutive 1W closes across the 30-week SMA, else effective NEUTRAL.
- **Closed bars only:** weekly anchor Monday 00:00 UTC (`WEEK_MS=604_800_000`, offset `345_600_000` from epoch-Thursday); partial groups dropped; divergence pivots need k=2 later closed bars.
- **Risk lookup (frozen):** WT-A 0.010 / WT-B 0.005, stop 2.0×ATR + 3.0×ATR trail + 96-bar time stop (v1 path). CT-A 0.0075 / CT-B 0.005, stop 1.5×ATR beyond sweep wick, fixed 2R target, 24-bar time stop, no trail, no adds. High-vol halves fraction. Discipline layer (15R/90d pause, 30R latch, cooldown) UNCHANGED.
- **Anti-overfitting:** weights/thresholds/gate as module constants, excluded from `EngineConfig`; `ENGINE_VERSION = "2.0"` folded into `engine_hash`; no backtest-driven weight tuning at any step; feasibility-only calibration.
- **Data:** 1h base feed, `lookback_bars` default 6000 (30-week SMA + hysteresis needs ~5400 closed 1h bars). Deriv adapter: funding percentile over trailing 30d of 8h rates; OI 6h change; any fetch failure → `DerivSnapshot` fields None → `data_ok=False` (never raises into the engine).
- **Git:** local trunk-based `main`, never push; `docs/` and `experiments/` are gitignored — force-add `docs/research-log/**` and new tracked `experiments/**`; NEVER stage-and-commit in one chained command; verify `git diff --cached --stat` before each commit; NEVER include AI attribution trailers.
- **Quality bar per task:** failing tests first → implement → full `pytest` green (note: repo historically ignores 3 pathsig test files if collection conflicts arise) → `ruff check` clean (line-length 100).

---

## File Map

**Create:**
- `src/moonface/signal/engine/macro.py` — MacroState, weekly bias, hysteresis (Task 2).
- `src/moonface/signal/engine/modules/__init__.py`, `modules/base.py` — ModuleScore contract (Task 3).
- `src/moonface/signal/engine/modules/trend_book.py` — M1..M5 trend scorers (Task 3).
- `src/moonface/signal/engine/modules/revert_book.py` — sweep/divergence/stretch scorers (Task 4).
- `src/moonface/signal/engine/deriv.py` — DerivSnapshot + funding/OI adapter + M5 scorers (Task 5).
- `src/moonface/signal/engine/setupcard.py` — card rendering (Task 8).
- `tests/test_engine_macro.py`, `tests/test_engine_modules_trend.py`, `tests/test_engine_modules_revert.py`, `tests/test_engine_deriv.py`, `tests/test_engine_setupcard.py`.
- `experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md` — prereg skeleton, human-frozen (Task 9).

**Modify:**
- `src/moonface/signal/engine/resample.py` — generic closed-bar resampler incl. 1d/1w (Task 1).
- `src/moonface/signal/engine/confluence.py` — REWRITE: gate + two-book aggregator (Task 6).
- `src/moonface/signal/engine/position.py` — CT risk profile branch (Task 7).
- `src/moonface/signal/engine/discipline.py` — `size_fraction` → tier/profile lookup (Task 7).
- `src/moonface/signal/engine/config.py` — v2 operational fields, `ENGINE_VERSION` in hash (Task 8).
- `src/moonface/signal/engine/engine.py` — orchestration (Task 8).
- `src/moonface/signal/engine/signals.py` — retired into `modules/` (delete after port, Task 3).
- `src/moonface/signal/cli.py` — SetupCard rendering + deriv snapshot pass-through (Task 8).
- Existing tests updated where the surface changes: `tests/test_engine_resample.py`, `test_engine_confluence.py`, `test_engine_signals.py` (→ modules), `test_engine_position.py`, `test_engine_discipline.py`, `test_engine_config.py`, `test_engine_evaluate.py`, `test_engine_cli.py`.

---

## Task 1: Generic closed-bar resampler (4h / 1d / 1w, Monday-anchored weeks)

**Files:** modify `resample.py`; tests `tests/test_engine_resample.py`.

**Interfaces:** `resample(candles_1h, tf: str) -> list[Candle]` for `tf ∈ {"4h","1d","1w"}`; keep `resample_to_4h` as a thin wrapper (call sites in engine.py). Week bucket: `start = ((ts - 345_600_000) // 604_800_000) * 604_800_000 + 345_600_000`.

- [ ] **Step 1: failing tests.** Cases: (a) 4h path identical to v1 wrapper output on a 30-bar fixture; (b) 1d groups of 24, partial trailing day dropped; (c) 1w: a Monday-00:00 1h bar starts a new week; a Sunday bar belongs to the prior week; (d) a week with 167 bars is dropped (closed-bar guard); (e) OHLCV aggregation correctness (open=first, high=max, low=min, close=last, vol=sum) on a hand-built week.

```python
def test_week_anchor_monday(self):
    # 2024-01-01 is a Monday. Bars Mon 00:00 .. Sun 23:00 = one full week.
    mon = 1_704_067_200_000
    bars = [_c(mon + i * 3_600_000) for i in range(168)]
    wk = resample(bars, "1w")
    self.assertEqual(len(wk), 1)
    self.assertEqual(wk[0].timestamp_ms, mon)

def test_partial_week_dropped(self):
    mon = 1_704_067_200_000
    bars = [_c(mon + i * 3_600_000) for i in range(167)]  # one bar short
    self.assertEqual(resample(bars, "1w"), [])
```

- [ ] **Step 2: implement** — generalise the existing grouping (bucket width + expected bar count from `TIMEFRAME_MS`), anchor offset only for `1w`.
- [ ] **Step 3: verify** — task tests + existing resample tests green; ruff clean; commit (`feat(engine): generic closed-bar resampler with weekly Monday anchor`).

## Task 2: Macro bias module (1W, 30-week SMA, 2-close hysteresis)

**Files:** create `macro.py`; tests `tests/test_engine_macro.py`.

**Interfaces:** `MacroState(bias: str, confirmed: bool, vol_state: str)` with `.effective()` returning `"NEUTRAL"` when unconfirmed; `classify_macro(weekly: list[Candle], vol_state: str, cfg) -> MacroState`. Constants `MACRO_MA_WEEKS = 30`, `MACRO_CONFIRM_CLOSES = 2` frozen in `macro.py`.

- [ ] **Step 1: failing tests.** (a) < 31 weekly bars → NEUTRAL/unconfirmed; (b) long series closing above MA for many weeks → BULL confirmed; (c) flip: series above MA then ONE close below → bias BEAR but `confirmed=False` → `effective()=="NEUTRAL"`; (d) two closes below → BEAR confirmed; (e) close oscillating across the MA each week never confirms; (f) uses only closed weekly bars (caller contract — assert function is pure on its input list).
- [ ] **Step 2: implement** — walk the weekly closes vs SMA-30 from the earliest bar with full history, track run-length of the current side; `confirmed = run_len >= 2`.
- [ ] **Step 3: verify + commit** (`feat(engine): 1W macro bias with 30w SMA and 2-close hysteresis`).

## Task 3: ModuleScore contract + TREND book scorers

**Files:** create `modules/base.py`, `modules/trend_book.py`; port then DELETE `signals.py`; tests `tests/test_engine_modules_trend.py`; rewrite `tests/test_engine_signals.py` away (cases move here).

**Interfaces:**
```python
@dataclass(frozen=True)
class ModuleScore:
    module: str; direction: int; points: int   # points >= 0, quantum 5
    archetype: str                             # "trend" | "mean_revert" | "context"
    data_ok: bool; evidence: tuple[str, ...]
```
`trend_book.score(views: TfViews, macro: MacroState, deriv: DerivSnapshot | None, cfg) -> list[ModuleScore]` where `TfViews` bundles the 1h/4h/1d/1w candle lists (built once in engine.py). Weights are constants: `W_MACRO=20, W_BREAKOUT=20, W_MA_ALIGN=10, W_ROC_STRONG=20, W_ROC_WEAK=10, W_PULLBACK=15, W_FUND_AGAINST=15, W_FUND_NEUTRAL=5`.

- [ ] **Step 1: failing tests.** Table-driven fixtures (reuse the synthetic-candle helpers from `test_engine_signals.py`): (a) M2 breakout +20 long when 4h close > prior Donchian-40 high; short mirror; inside channel → 0; (b) M2 MA-align +10 only when close AND SMA-20 both on trend side of SMA-50; (c) M3 tiers at |roc| 5% / 2% / below; (d) M4 pullback fires only when trend intact AND price within 0.5×ATR of SMA-20; (e) M1 = +20 only when macro confirmed AND aligned, 0 for NEUTRAL/unconfirmed/opposed; (f) M5 with `deriv=None` → `data_ok=False`, points 0; (g) every score's `points % 5 == 0` and direction ∈ {-1,0,1}; (h) insufficient history → module returns `data_ok=False`, never raises.
- [ ] **Step 2: implement**; keep `foundation.indicators` (`sma`, `roc`, `donchian_channel`) and `foundation.risk.atr` as the only math deps. Delete `signals.py` and fix imports.
- [ ] **Step 3: verify + commit** (`feat(engine): ModuleScore contract + TREND scorebook`).

## Task 4: MEAN_REVERT book scorers (sweep/reclaim, divergence, stretch)

**Files:** create `modules/revert_book.py`; tests `tests/test_engine_modules_revert.py`.

**Interfaces:** `revert_book.score(views, macro, deriv, cfg) -> list[ModuleScore]` plus `sweep_state(candles_1h, lookback=20) -> SweepState | None` exposing the swept level and wick extreme (position.py needs the wick for the CT stop). Constants: `W_SWEEP=20, W_RECLAIM=15, W_DIVERGENCE=25, W_FUND_CT=15, W_OI_FLUSH=10, W_STRETCH=15, SWEEP_LOOKBACK=20, EVENT_TTL_BARS=3, PIVOT_K=2, DIV_MAX_SPAN=40`.

- [ ] **Step 1: failing tests.** Lookahead is the hazard — test it explicitly:
  - sweep long: bar wicks below `min(low[-21:-1])` and closes back above → +20; close below the level → 0 (no sweep, breakdown).
  - reclaim: +15 only on the NEXT closed bar; the sweep bar itself never earns reclaim points.
  - TTL: score present on confirm bar, +1, +2; gone at +3.
  - divergence: hand-built series with two swing lows (k=2 pivots), price LL + RSI HL → +25 long; pivot NOT yet confirmed (fewer than 2 bars after the low) → 0 (**the** lookahead trap); pivots 41 bars apart → 0.
  - stretch: close 2.1×ATR below SMA-50 → +15 toward long; 1.9×ATR → 0.
  - short mirrors for sweep and divergence.
  - `sweep_state` returns the wick low of the sweep bar.
- [ ] **Step 2: implement.** RSI-14 via a small local helper if `foundation.indicators` lacks it (stdlib only; Wilder smoothing; add to foundation if cleaner, with its own unit test).
- [ ] **Step 3: verify + commit** (`feat(engine): MEAN_REVERT scorebook — sweep/reclaim, divergence, stretch`).

## Task 5: DerivSnapshot + adapter + M5 scorers

**Files:** create `deriv.py`; tests `tests/test_engine_deriv.py`.

**Interfaces:**
```python
@dataclass(frozen=True)
class DerivSnapshot:
    funding_pct: float | None      # percentile of current 8h rate in trailing 30d
    oi_change_6h: float | None     # fractional change, e.g. -0.031
def fetch_deriv_snapshot(symbol: str, now_ms: int) -> DerivSnapshot   # never raises
def funding_points_trend(snap, direction) -> tuple[int, str]          # 15/5/0 + evidence
def funding_points_ct(snap, direction) -> tuple[int, str]             # 15/0
def oi_flush_points(snap) -> tuple[int, str]                          # 10/0
```
Constants: `FUND_WINDOW_DAYS=30, FUND_LOW=10.0, FUND_HIGH=90.0, FUND_CROWDED=80.0, OI_FLUSH=-0.03, OI_WINDOW_H=6`.

- [ ] **Step 1: failing tests.** Percentile math on a fixed rate list; band edges (exactly 10th/80th/90th); `None` fields → 0 points + `data_ok` semantics upstream; `fetch_deriv_snapshot` with a monkeypatched failing fetcher returns all-None (never raises); long/short symmetry (funding extreme HIGH favors short entries, LOW favors long).
- [ ] **Step 2: implement.** Reuse `universe_data.fetch_funding_rates` for the 30d funding history; OI via the same REST family (30d cap is fine for a 6h window); wrap every network call in the never-raise guard. The engine and all module code accept `DerivSnapshot | None` — the network is touched only in the CLI layer.
- [ ] **Step 3: verify + commit** (`feat(engine): derivatives snapshot adapter + M5 scorers`).

## Task 6: Gating Matrix + two-book aggregator (confluence.py rewrite)

**Files:** rewrite `confluence.py`; rewrite `tests/test_engine_confluence.py`.

**Interfaces:**
```python
@dataclass(frozen=True)
class Decision:
    action: str            # "SETUP" | "WAIT"
    direction: int; archetype: str | None; policy: str | None   # ALLOW/ALLOW_CT
    score: int; max_attainable: int; breadth: int
    tier: str | None       # "A" | "B"
    veto: str | None; shadow_score: int | None
    modules: tuple[ModuleScore, ...]; detail: str
def decide(trend_scores, revert_scores, macro: MacroState, cfg) -> Decision
```
Constants: `BASE_THRESHOLD=60, TIER_A=75, CT_SURCHARGE=10, BREADTH_MIN=3` and the `GATE` dict exactly as in the spec.

- [ ] **Step 1: failing tests.** Table-driven over the full gate (12 non-neutral cells + neutral row):
  - `(BEAR, TREND, LONG)` with a 80-point trend-long book → WAIT, `veto` set, `shadow_score == 80`.
  - `(BEAR, MEAN_REVERT, LONG)` at 72 → WAIT (below 70+breadth? no—72 ≥ 70 passes if breadth ok) — pin: 68 → WAIT, 72 → SETUP Tier B, 85 → Tier A.
  - `(BEAR, MEAN_REVERT, SHORT)` at 62 → SETUP Tier B (no surcharge when aligned).
  - unconfirmed BEAR behaves as NEUTRAL (no veto, no macro points).
  - breadth: 75 points from only 2 modules → WAIT.
  - conflict: books signal opposite directions, both above threshold → WAIT("books conflict").
  - same direction both books → higher score wins; archetype follows the winning book.
  - `data_ok=False` on M5 lowers `max_attainable` by 15 and the threshold stays absolute (a 58 with degraded data still WAITs).
  - extreme vol → flat regardless of scores (keep v1 test).
  - every WAIT carries a human-readable `detail` with score/threshold/breadth.
- [ ] **Step 2: implement** — pure function, no journal/IO here.
- [ ] **Step 3: verify + commit** (`feat(engine): macro gating matrix + two-book aggregator`).

## Task 7: Counter-trend risk profile + tier sizing

**Files:** modify `position.py`, `discipline.py`; extend `tests/test_engine_position.py`, `tests/test_engine_discipline.py`.

**Interfaces:** `PositionState` gains `profile: str` ("WT"|"CT") and `target: float | None`; `open_position(..., profile, sweep_wick=None)`; CT path: stop `= sweep_wick ∓ 1.5×ATR` (fallback entry∓1.5×ATR if no wick), `target = entry ± 2R`, `max_bars=24`, no trail ratchet. `discipline.size_fraction(tier, profile, vol_state, cfg) -> float` from the frozen lookup `{("A","WT"):0.010, ("B","WT"):0.005, ("A","CT"):0.0075, ("B","CT"):0.005}`, halved when `vol_state=="high"`, capped by `cfg.max_fraction`.

- [ ] **Step 1: failing tests.** CT: (a) stop placed off the wick, not entry; (b) target fill exits at exactly +2R net-of-cost accounting consistent with `_net_r`; (c) stop-before-target pessimism when both hit in one bar; (d) no trail: stop never ratchets on CT; (e) 24-bar time stop; (f) reversal-exit rule still applies. WT: existing v1 tests keep passing unchanged. Sizing: the 4-cell lookup, high-vol halving, `max_fraction` cap, and journal `reconstruct` round-trips the new `profile`/`target` fields (older v1 entries without them are ignored by version mismatch anyway — assert that).
- [ ] **Step 2: implement**, preserving the v1 stop-check-then-ratchet ordering for WT (mirrors `foundation.exits.atr_trail`).
- [ ] **Step 3: verify + commit** (`feat(engine): counter-trend risk profile + tier sizing lookup`).

## Task 8: Orchestration, config v2, SetupCard, CLI wiring

**Files:** modify `engine.py`, `config.py`, `cli.py`; create `setupcard.py`; tests `tests/test_engine_evaluate.py` (rewrite), `tests/test_engine_config.py`, `tests/test_engine_setupcard.py`, `tests/test_engine_cli.py`.

**Interfaces:**
- `config.py`: `ENGINE_VERSION = "2.0"` folded into `engine_hash` payload; new operational fields only (`lookback_bars=6000`, keep discipline/vol fields; REMOVE `weights`, `confidence_floor`, `trend_gate_boost`, `counter_trend_damp`, `notrend_floor`, panel params now frozen in modules). `enabled=False` default unchanged.
- `engine.py`: `evaluate_engine(cfg, bundle, entries, now_ms, deriv=None)` — build `TfViews` via `resample`, `classify_macro`, score both books, `decide`, then discipline gates → open/manage with profile; `EngineResult` gains `decision: Decision`. Managing an open position ignores new setups (v1 behaviour).
- `setupcard.py`: `render(decision, plan, discipline_state, version) -> str` — the boxed card from the spec §5; journal dict gains `modules`, `gate`, `shadow_score`, `tier`, `profile`, `target`.
- `cli.py`: engine command prints the card; fetches `DerivSnapshot` best-effort (never blocks the loop on failure → `deriv=None`).

- [ ] **Step 1: failing tests.** (a) `engine_hash` changes when `ENGINE_VERSION` changes and ignores `enabled` (keep v1 test); v1 journal entries are invisible to v2 `reconstruct` (different hash) — regression-pin this; (b) end-to-end on synthetic candles: a bear-macro fixture with a sweep+divergence+stretch long setup ≥70 emits a CT SETUP with wick-based stop; the same fixture with a trend-long book instead is vetoed and journals the shadow score; (c) insufficient weekly history → macro NEUTRAL, engine still runs; (d) `deriv=None` end-to-end degrades ceilings, never crashes; (e) card contains every module line, gate line, discipline line, and the NO_CLAIM banner; (f) CLI smoke test with monkeypatched feed.
- [ ] **Step 2: implement.**
- [ ] **Step 3: full-suite verify** — entire `pytest` run green (update any straggler tests referencing removed config fields), `ruff check` clean. Commit (`feat(engine): confluence v2 orchestration, SetupCard, config hash versioning`).

## Task 9: Forward-paper pre-registration skeleton + ship-disabled check

**Files:** create `experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md` (force-add).

- [ ] **Step 1:** Write the prereg skeleton per spec §6: horizon = 6 months from human enable date OR ≥30 setups (whichever later); success = net R > 0 AND MaxDD within the 15R window budget AND CT/WT sub-books separately ≥ 0; gate-ablation report (shadow scores) mandatory in the verdict; kill rule = one cycle, no re-tune-and-rerun without a version bump. Mark `STATUS: DRAFT — human must freeze before enabling the engine`.
- [ ] **Step 2:** Verify ship-disabled: default `EngineConfig().enabled is False` (test exists from Task 8), and grep that no code path enables it implicitly.
- [ ] **Step 3:** Final commit; then STOP. Enabling the engine, freezing the registration, and starting the forward clock are human-only actions.

---

## Verification (whole plan)

1. Full `pytest` green; `ruff check` clean.
2. `python -m moonface.signal.cli engine ...` (existing invocation) on live BTC 1h data prints a SetupCard or a reasoned WAIT with book scores — no crash with the deriv feed unreachable.
3. Feasibility read (NOT a backtest fit): over the cached history, sweeps/divergences fire at a sane monthly rate; if a module never fires or fires every bar, that is a spec bug to fix at the definition level, not a weight to tune.
4. `git log` shows one commit per task, no attribution trailers, docs force-added.
