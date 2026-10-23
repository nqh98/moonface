# Regime-Mechanism Engine (v3) — Design

**Status:** design approved, spec under review
**Date:** 2026-07-06
**Supersedes at promotion:** confluence engine v2.2 (hash `b4924f8e…`), which stays byte-frozen until a human swaps the daemon.

## 1. Goal

Replace the additive confluence engine with a **regime-mechanism matrix**. The
market regime selects **exactly one** specialist mechanism; that mechanism's
trigger is the *sole* decision to trade; a post-selection quality score only
**sizes** the position (and zeroes degenerate cases). No trade is ever created
by summing weak confirmations, and no second mechanism is ever consulted on a
bar.

This is a new **live engine** (`ENGINE_VERSION = "v3"`, new `engine_hash_v3`,
its own forward-registration doc and fresh paper clock). It ships behind the
same discipline as every other instrument in this program.

### Non-goals

- Not a read-only evaluation lane; this is the engine itself.
- No reuse of the v2.2 `Decision`/`decide` code path or the trend/revert
  module weights. v2.2 files are not edited.
- Sizing carries no regime term — regime's only job is selection.

## 2. The core invariant (the line the design must not cross)

> A trade exists **iff** the single regime-selected mechanism's trigger fires.
> The quality score is a *descriptor of that one instance* whose only power is
> to scale size within `[0, max_fraction]` and to veto degenerate cases
> (`quality < q_floor → size 0`). Quality may blend several sub-features of the
> *same* mechanism, because the trigger — not the blend — created the trade.
> Blending sub-features across *different* mechanisms, or letting the score
> promote a non-triggered bar into a trade, is forbidden.

Every component below is testable against this invariant, and the test suite
asserts it directly (§10).

## 3. Module layout

New isolated subpackage; nothing under `src/moonface/signal/engine/` that
belongs to v2.2 is touched.

```
src/moonface/signal/engine/v3/
  indicators.py   stdlib EMA/ADX/RSI/ROC/Donchian/bands/vol-ratio helpers
  regime.py       classify_regime(candles, cfg) -> Regime      # pure
  mechanisms/
    base.py       Mechanism protocol, MechanismSignal, BarContext
    breakout.py   BREAKOUT specialist
    pullback.py   PULLBACK specialist
    reversion.py  REVERSION specialist
  matrix.py       REGIME_MECHANISM frozen map; select_mechanism(regime) -> name | None
  sizing.py       size_from_quality(mechanism_name, quality, cfg) -> float
  config_v3.py    EngineConfigV3 + engine_hash_v3 (all frozen constants)
  decide.py       decide_v3(ctx, cfg) -> DecisionV3            # daemon entrypoint
```

### Data flow (single bar)

```
classify_regime(ctx) ──► Regime(dir_state, vol_state)
   │  vol_state == EXTREME ─────────────────────────► WAIT
   ▼
select_mechanism(regime) ──► name | None
   │  None ─────────────────────────────────────────► WAIT
   ▼
mechanism.evaluate(ctx, regime) ──► MechanismSignal(direction, quality, detail)
   │  direction == 0 ───────────────────────────────► WAIT
   ▼
size_from_quality(name, quality, cfg) ──► fraction
   │  fraction == 0 (quality < q_floor) ────────────► WAIT   # degenerate veto
   ▼
ENTER(direction, name, regime, quality, fraction)
```

Exactly one mechanism is consulted; nothing on the path sums.

## 4. Regime classifier (`regime.py`)

`Regime = (dir_state, vol_state)`, both enums.

- **`dir_state ∈ {TRENDING_UP, RANGING, TRENDING_DOWN}`** from ADX + slope at
  the trade timeframe:
  - `ADX ≥ ADX_TREND` → trending; sign from `DI+ vs DI−` (equivalently EMA
    slope sign) → `TRENDING_UP` / `TRENDING_DOWN`.
  - `ADX < ADX_TREND` → `RANGING`.
  - Conservative by construction: anything not clearly trending is `RANGING`
    (we never claim a trend we cannot measure).
- **`vol_state ∈ {QUIET, NORMAL, HIGH, EXTREME}`** from the ATR/close ratio's
  percentile over a rolling window, with three frozen cutpoints. `EXTREME`
  short-circuits `decide_v3` to `WAIT` before the matrix is consulted.

Pure function of the candle window + `cfg`; no I/O, no mutable state.

## 5. Mechanism library (`mechanisms/`)

### Interface (`base.py`)

```python
@dataclass(frozen=True)
class MechanismSignal:
    direction: int    # -1, 0, +1  (0 = no trigger this bar)
    quality: float    # [0, 1], meaningful only when direction != 0
    detail: str

class Mechanism(Protocol):
    name: str
    def evaluate(self, ctx: BarContext, regime: Regime) -> MechanismSignal: ...
```

`BarContext` is a thin read-only view: candle window up to `index`, plus shared
precomputed indicators (ATR, ADX, EMA fast/slow, channel high/low) so each
mechanism recomputes nothing. `regime` is passed so directional mechanisms read
the trend sign.

All quality blends `clip(·, 0, 1)` their result; weights are frozen constants.

### `BREAKOUT` (direction `d` = regime trend sign)

- **Trigger:** `d=+1` → `close > max(high[i−N : i])`; `d=−1` →
  `close < min(low[i−N : i])`. Fires `direction = d`, else `0`.
- **Quality:** blend of extension `(close − channel_edge)/ATR`, momentum
  `ROC(M)` normalized, and close-in-bar-range location.

### `PULLBACK` (direction `d` = regime trend sign)

- **Trigger:** trend already asserted by regime; price tags the fast EMA and
  reclaims — `d=+1` → `low ≤ EMA·(1+tol)` and `close > EMA` and `close > open`;
  `d=−1` mirrored. Fires `direction = d`, else `0`.
- **Quality:** blend of trend strength (ADX/slope), pullback shallowness, and
  reclaim-bar close location.

### `REVERSION` (two-sided; direction from the band hit)

- **Trigger:** stretch beyond an outer band **with rejection** — upper:
  `high ≥ upper_band` and `close < upper_band` → `direction = −1`; lower
  mirrored → `+1`; else `0`.
- **Quality:** blend of stretch distance from the mean (ATR/σ units), rejection
  wick depth, and optional RSI stretch.

## 6. The matrix (`matrix.py`)

`REGIME_MECHANISM: dict[tuple[DirState, VolState], str | None]` — a frozen
lookup. `select_mechanism(regime)` returns the name or `None`.

| `dir_state` \ `vol_state` | QUIET | NORMAL | HIGH |
|---|---|---|---|
| TRENDING_UP | `PULLBACK` | `BREAKOUT` | `BREAKOUT` |
| RANGING | `REVERSION` | `REVERSION` | `None` |
| TRENDING_DOWN | `PULLBACK` | `BREAKOUT` | `BREAKOUT` |

`EXTREME` vol → `WAIT` before lookup (handled in `decide_v3`). A `None` cell is
a first-class outcome: the engine declines to trade, which is the structural
opposite of confluence manufacturing a trade.

## 7. Sizing (`sizing.py`)

Purely quality-driven, mechanism-owned, no regime term:

```
f(q)          = clip((q − q_floor[name]) / (1 − q_floor[name]), 0, 1)
risk_fraction = min(base_fraction + f(q)·(max_fraction − base_fraction), max_fraction)
```

Interpolates from `base_fraction` at the quality floor up to `max_fraction` at
`q = 1`, so higher quality scales conviction *up*. Monotone;
`quality < q_floor → 0` is the sole veto (a deliberate discontinuity at the
floor). Each mechanism owns its own frozen `q_floor`.

## 8. Decision output & daemon integration (`decide.py`)

```python
@dataclass(frozen=True)
class DecisionV3:
    action: str            # "ENTER" | "WAIT"
    direction: int         # -1, 0, +1
    mechanism: str | None
    regime: Regime
    quality: float | None
    risk_fraction: float   # 0.0 on WAIT
    detail: str
```

`DecisionV3` exposes the fields the daemon already consumes from v2.2's
`Decision` (action, direction, a sizing fraction, detail) plus `regime` and
`mechanism`, so the daemon swap is a construction-site change, not a protocol
rewrite. The swap itself is a separate human step, not part of this build.

## 9. Config, freezing, forward registration

- `config_v3.py` holds every constant: `ADX_TREND`, ADX/ATR periods, EMA
  fast/slow + `tol`, breakout `N` and `ROC` `M`, reversion band period/`k` and
  RSI params, the three vol-percentile cutpoints and the `EXTREME` cutpoint,
  per-mechanism `q_floor`, `base_fraction`, `max_fraction`.
- `engine_hash_v3(cfg)` hashes the frozen config (same technique as
  `engine_hash`), producing the pin recorded in the forward-registration doc.
- This build authors the frozen pre-registration
  `experiments/engine/ENGINE_V3_FORWARD_REGISTRATION.md` (constants + pinned
  `engine_hash_v3`) and states the verdict horizon/sample. **Starting the paper
  clock and swapping the daemon from v2.2 to v3 is the human step**, out of
  scope for this build. No live constant is changed after freeze without a new
  version + new hash + new registration.

## 10. Testing strategy

Per-unit, hermetic, stdlib + pytest (matches repo convention):

- `regime.py`: synthetic candle series drive each `dir_state`/`vol_state`
  boundary, including the `EXTREME` short-circuit and the conservative
  RANGING default.
- Each mechanism: trigger fires only on its pattern and in the right
  direction; `direction == 0` when the pattern is absent; quality is in
  `[0,1]` and monotone in each sub-feature; two-sided `REVERSION` picks the
  correct side.
- `matrix.py`: every regime maps as tabled; `None` cells return `None`; no
  cell maps to an unknown mechanism name.
- `sizing.py`: `f` monotone, `0` below floor, capped at `max_fraction`.
- `decide.py` **invariant tests** (§2): (a) a non-triggering bar never
  returns `ENTER` regardless of quality inputs; (b) exactly one mechanism's
  `evaluate` is called per bar (spy/monkeypatch the others and assert
  zero calls); (c) `EXTREME` vol and `None` cells always `WAIT`.

## 11. The falsifiable bet

This program has repeatedly found that **adding regime conditioning subtracts**
(regime-selector, regime-overlay both closed negative) — but in those cases
regime *filtered an already-additive score*. Here regime is a **selector that
restricts trading to where one specialist has edge**, and empty cells are a
first-class outcome. The bet: selection-not-summation, with size-only scoring,
survives the forward window where confluence did not. If v3's forward
registration fails its gate like its predecessors, the negative result falls on
the *selection* architecture, not on yet another additive weighting — a
genuinely new thing learned either way.
