# Baseline Composite Signal Tier — Design

- **Date:** 2026-06-15
- **Status:** approved (design)
- **Goal:** Turn MoonFace from a research CLI plus an always-WAIT advisor into a
  deployable BTC perpetual-futures **signal engine** that always emits an
  actionable `LONG` / `SHORT` / `WAIT` call with `confidence`, `reason`,
  `timeframe`, and `risk notes` — while staying honest that no OOS-valid edge has
  been found, and while never executing a trade.

## 1. Context

The falsification program (`docs/findings/PROGRAM_CONCLUSION.md`) closed negative:
no out-of-sample-valid edge exists on free BTC data. The codebase was therefore
architected around a WAIT default. What already ships:

- `moonface-signal` CLI: one-shot, `--json`, `--watch` daemon, journal,
  `--alert-cmd` shell-out, forward-gate report.
- A **staging contract**: `promotion/strategy.json` drives paper→live; promotion
  is a human git commit gated by a pre-committed forward gate.
- A **participation advisor** (`signal/participation.py`): emits actionable
  signals *without an expectancy claim*, `enabled: false` by default.
- A library of signal generators (price / funding / positioning / basis /
  lead-lag) in `backtest/edge`.

The requirement is a real signal bot: emit actionable directional signals now,
staged — **baseline first, research-validated later** — without abandoning the
honesty the program earned.

## 2. Decisions (resolved during brainstorming)

1. **Baseline logic = multi-signal composite.** Combine existing generators into
   a transparent LONG/SHORT/WAIT call where confidence is how strongly the
   sub-signals agree. Honest "heuristic, not a validated edge" stamp on every
   emission.
2. **Precedence = baseline as lowest tier, ON by default.** Resolution order per
   closed candle: live strategy → paper strategy → participation mandate →
   baseline composite. A promoted/validated strategy automatically supersedes the
   baseline.
3. **Delivery = reuse the existing surface.** One-shot CLI, `--json`, `--watch`,
   `--alert-cmd`. No new network code or committed credentials; the user owns the
   notification channel via the alert command.

## 3. Architecture

### 3.1 Resolution ladder

Both `run()` and `watch()` resolve the active voice once per closed candle:

```
1. promotion/strategy.json  status=live   -> actionable LONG/SHORT/WAIT
2. promotion/strategy.json  status=paper  -> shown, actionable = WAIT
3. promotion/participation.json enabled    -> actionable, no-expectancy
4. baseline composite (ON by default)      -> actionable, "heuristic/unvalidated"
```

Step 4 always exists, so the engine is never silent unless data is stale/missing
(which surfaces as an explicit error/alert, never a fake WAIT).

### 3.2 Units

- **`src/moonface/signal/baseline.py`** (new)
  - `BaselineConfig` dataclass + `load_baseline_config(path)`: optional
    `promotion/baseline.json`; a missing/invalid file yields the default
    on-by-default composite (fail-safe, mirroring `load_strategy`/`load_policy`).
    Tunable fields: per-voter weights, `agreement_floor`, `risk_fraction`,
    `k_stop`, `atr_period`, voter params, `asset`. A config with
    `enabled: false` lets the human silence the baseline (then the ladder falls
    through to the structural WAIT).
  - `evaluate_baseline(config, bundle, now_ms) -> Signal`: runs the voters,
    aggregates the decision and confidence, builds the risk notes, returns a
    `Signal` with `tier="baseline"`.
  - Voters are small functions that reuse `moonface.research.entries.generate_entries`
    on the last closed candle (via the existing `_sentinel_extended` helper).
- **`src/moonface/signal/evaluate.py`** — extend the shared `Signal` dataclass
  with `confidence: float = 0.0`, `timeframe: str = ""`, `risk_notes: str = ""`,
  `tier: str = ""`. Defaults preserve existing construction sites; `evaluate()`
  and `participation.py` are updated to populate the new fields for their tiers.
- **`src/moonface/signal/cli.py`** — add `_emit_baseline` and wire baseline as
  ladder step 4 in `run()` and `watch()`. Surface `confidence`, `timeframe`,
  `risk_notes`, and `tier` in human, `--json`, and `--alert-cmd` output.

### 3.3 Data inputs

Baseline v1 reads only data the repo already fetches live on free BTC:
**OHLCV + funding**. Positioning / basis / lead-lag legs are not reliably free
live and are excluded from v1; the voter list is structured so they can be added
later without changing the aggregation contract.

## 4. The composite

### 4.1 Voters

Each directional voter returns `+1` (LONG), `-1` (SHORT), or `0` (neutral). The
regime voter is non-directional — it damps confidence and can force WAIT.

| Voter | Generator | Reads | Role |
|---|---|---|---|
| Trend breakout | `donchian_break` (most-replicated drift) | OHLCV | directional |
| Trend confirm | `price_vs_ma` (fast vs slow) | OHLCV | directional |
| Funding contrarian | `funding_fade` (fade crowded funding) | funding | directional |
| Regime gate | `vol_regime` | OHLCV | confidence damp / WAIT |

### 4.2 Decision & confidence

- `net = Σ weight·vote` over directional voters; `total = Σ weight`.
- `agreement = |net| / total` ∈ [0, 1].
- `decision = sign(net)` if `agreement ≥ agreement_floor` (default 0.5) **and**
  the regime gate is not in its WAIT state; otherwise **WAIT**.
- `confidence = agreement × regime_damp` ∈ [0, 1]. This is **agreement strength,
  explicitly NOT a probability of profit.** The phrase "heuristic — not a
  validated edge" travels with every baseline emission.

`regime_damp` is a multiplier in (0, 1]: 1.0 in normal volatility, reduced (or
0 → WAIT) in the extreme-vol state reported by `vol_regime`.

### 4.3 Risk notes & timeframe

- `risk_notes` (structured string): ATR-based invalidation `price ± k·ATR(atr_period)`,
  `1R = ATR(atr_period)`, suggested tiny size `f` (default anchored to the worst
  observed −277R drawdown like the participation advisor), any regime warning,
  and the standing "no expectancy claim / unvalidated" caveat.
- `invalidation` = `price − k·ATR` for LONG, `price + k·ATR` for SHORT.
- `fraction` = the suggested size `f`.
- `timeframe` = `"4h"`, with the next candle-close time included in the human
  output line.

### 4.4 Sample output

```
BTC/USDT:USDT  LONG  confidence 0.62  [BASELINE — heuristic, NOT a validated edge]
 reason: donchian up-break + price>MA + funding<0 agree (3/3 dir), vol normal
 risk: invalidation 95800 (1R=ATR14~1900), suggested f=0.0005, no expectancy claim
 timeframe: 4h (next close 14:00 UTC, in 2h11m)
```

## 5. Honesty guardrails

Enforced by tests; non-negotiable:

- The baseline **never executes trades** and never sets a validated/`live`
  status. It is its own `tier="baseline"`.
- Every baseline emission carries the unvalidated / no-expectancy label in human,
  JSON, and alert output.
- The baseline does **not** auto-promote. The "baseline → validated" path is the
  unchanged existing one: run the research ladder → pass the lockbox + forward
  gate → human commits `promotion/strategy.json` → it supersedes the baseline
  automatically via the resolution ladder. This spec delivers the baseline stage
  only; the validated stage already exists and stays gated.

## 6. Staging path

```
baseline (this spec, ON by default)
   │  research ladder finds a candidate (tools/research.py)
   ▼
candidate passes one-touch lockbox + forward gate
   │  human git commit of promotion/strategy.json
   ▼
paper  -> (forward gate: >=20 trades, >=12 weeks, net R>0, DD within p95)
   │  human git commit flips status
   ▼
live  -> actionable, supersedes baseline
```

No new staging machinery is introduced beyond the baseline tier and the `Signal`
extension.

## 7. Testing

- **`tests/test_signal_baseline.py`** (new): voter direction; net/agreement math;
  `agreement_floor` → WAIT; regime damping and regime-WAIT gate; label presence;
  risk-note / invalidation arithmetic; config fail-safe (missing/invalid →
  default on; `enabled:false` → fall-through). Deterministic on synthetic bundles
  (`moonface.research.synth.make_candles` + a funding list); no network.
- **`tests/test_signal_cli.py`** (extend): baseline emitted when no
  strategy/policy is present; precedence (a promoted strategy supersedes the
  baseline; an enabled participation mandate supersedes the baseline); `--json`
  payload includes `confidence`, `timeframe`, `risk_notes`, `tier`; `--alert-cmd`
  receives the labelled message.
- **Regression**: `tests/test_signal_evaluate.py` and
  `tests/test_signal_participation.py` still pass with the extended `Signal`
  (new fields have defaults; the two tiers are updated to populate them).

## 8. Out of scope

- Any order execution, broker, or portfolio management.
- A built-in push channel / credential handling (delivery stays via
  `--alert-cmd`).
- New data legs (positioning / basis / lead-lag) in the baseline composite.
- Changes to the research ladder, lockbox, or the paper→live forward gate.
