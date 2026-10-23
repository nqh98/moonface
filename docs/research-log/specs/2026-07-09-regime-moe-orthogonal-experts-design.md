# Regime-MoE Combiner — Orthogonal-Expert Expansion (Design Spec)

> **Lineage.** Extends the frozen MoE combiner (`docs/research-log/specs/2026-07-09-regime-moe-combiner-design.md`,
> `src/moonface/signal/engine/moe/`). Trials 1 (`q_confluence=2`, no-fire) and 2
> (`q_confluence=1`, fires n=353 but flat, CI straddles 0) both CLOSED_NEGATIVE_VALIDATION
> with the sealed window UNSPENT and the config-tuning line closed. This spec adds
> **orthogonal (non-price) experts** — the last free-data lever — under the same
> anti-artifact protocol.

## 1. Goal

Add **two frozen non-price experts (FUNDING, OI)** to the MoE expert set and test whether
**regime-conditioned weighting of orthogonal data** contributes edge the 3 price mechanisms
(BREAKOUT/PULLBACK/REVERSION) lacked. The deliverable is the protocol result, not an edge
claim — a certified NEGATIVE is success.

**Honest prior (stated up front, pre-registered):** strongly negative. OI standalone is dead
(`price_oi_divergence` CLOSED_NEGATIVE, `oi_build` mechanism-does-not-exist) and funding-fade
transfer CLOSED_NEGATIVE. The genuine open question is whether *regime-conditioned combination*
extracts what each signal lacked standalone. A negative here closes the free-data
orthogonal-expert line; further work would require genuinely new data.

## 2. The two frozen experts

Each expert is a **theory-specified transform of non-price data → `RawSignal(direction, magnitude)`**,
frozen from theory. **Only `W` (the regime×expert weight matrix) is fit to returns** (spec §4.1
unchanged). The train-frozen `Normalizer` rank-standardizes each expert's raw series to `[-1,1]`
(a train-only descriptive stat, allowed by §4.1). **Missing data (`None`) → `RawSignal(0, 0)`
(no-fire).**

### 2.1 `FUNDING` — funding-extreme fade
- **Input:** `funding[index]` — aligned funding rate at the bar (`DataBundle.funding`), or `None`.
- **Theory:** crowded positioning mean-reverts; extreme positive funding (crowded longs) → short
  bias, extreme negative funding → long bias.
- **Transform (frozen):**
  - `direction = -sign(funding[index])` (fade); `0` if `funding[index]` is `None` or `0`.
  - `magnitude = clip01(abs(funding[index]) / FUNDING_CAP)`, `FUNDING_CAP = 0.01` (1% per funding
    interval = saturating-extreme; frozen theory constant).
- **Causality:** `align_funding` is an as-of join (rate known at/before bar close); uses only
  data ≤ `index`.

### 2.2 `OI` — OI-confirmed momentum
- **Input:** `oi[index]`, `oi[index - OI_LOOKBACK]` (aligned `sum_open_interest`,
  `DataBundle.feature` via `metrics_field="sum_open_interest"`), and `window` closes.
- **Theory:** new open interest entering *with* a price move confirms conviction; OI leaving
  (positions closing) carries no directional conviction.
- **Transform (frozen), `OI_LOOKBACK = 24` bars:**
  - `d_oi = oi[index] - oi[index - OI_LOOKBACK]`; `d_px = close[index] - close[index - OI_LOOKBACK]`.
  - If `d_oi > 0` (OI rising = conviction): `direction = sign(d_px)`,
    `magnitude = clip01(d_oi / oi[index - OI_LOOKBACK])` (relative OI growth).
  - Else (`d_oi <= 0`, positions closing) or any operand `None`/lookback unavailable:
    `direction = 0`.
- **Not the dead divergence lane:** this is OI *confirmation* (conviction gate on momentum),
  distinct from the CLOSED `price_oi_divergence` fade.
- **Causality:** all operands at index ≤ `index`.

### 2.3 Frozen constants
`FUNDING_CAP = 0.01`, `OI_LOOKBACK = 24` live as module-level constants in the experts module
(frozen, recorded verbatim in the registration). They are NOT fit and NOT in `MoeConfig`.

## 3. Architecture — `ExpertContext` (the one real code change)

Current `Expert.signal(window, index, cfg) -> RawSignal` sees candles only. Widen to a
uniform, well-bounded context:

```python
@dataclass(frozen=True)
class ExpertContext:
    window: list[Candle]          # trailing candle slice ending at the eval bar
    index: int                    # position of the eval bar within window
    funding: list[float | None]   # aligned 1:1 to window (same length), or all-None
    oi: list[float | None]        # aligned 1:1 to window (same length), or all-None
    cfg: EngineConfigV3

class Expert(Protocol):
    name: str
    def signal(self, ctx: ExpertContext) -> RawSignal: ...
```

- **Price experts** (`_MechanismExpert`) read only `ctx.window`/`ctx.index`/`ctx.cfg` —
  behavior identical to today.
- **Orthogonal experts** read `ctx.funding` / `ctx.oi`.
- `mechanism_experts()` stays; add `orthogonal_experts()` and a combined
  `default_experts() -> [BREAKOUT, PULLBACK, REVERSION, FUNDING, OI]`.

Because `DataBundle` aligns funding/OI 1:1 with candles (as-of, no lookahead), the context
for `window = candles[a:b+1]` is `funding[a:b+1]`, `oi[a:b+1]`.

## 4. Data plumbing

- **`build_moe_report`** signature changes from candle-lists to **`DataBundle`s**:
  `build_moe_report(btc: DataBundle, eth: DataBundle, sol: DataBundle, ...)`. It reads
  `.candles`, `.funding`, `.feature` (OI). When `.funding`/`.feature` are `None`, the
  orthogonal experts no-fire → behavior reduces to the price-only combiner (keeps the existing
  synthetic report test valid by passing a bundle with `funding=None, feature=None`).
- **`_raw_series`, `build_fit_panel`, `moe_stream`, `_stream_from_series`** build an
  `ExpertContext` per bar carrying the aligned funding/OI slices. The **Gate-0 null path is
  unchanged in logic** — nulls still permute the *computed raw series*; orthogonal raws flow
  through identically.
- **CLI `tools/moe_evaluate.py`:** asset dicts gain `"funding_symbol"` and
  `"metrics_field": "sum_open_interest"` so `load_bundle` populates funding + OI; pass the full
  bundle (not `.candles`) to `build_moe_report`. Add `--experts {price,ortho,all}` (default
  `all` for this lane; `price` reproduces trials 1–2).

## 5. Registration-integrity fix — expert-set in the frozen identity

`moe_hash(cfg)` hashes only `MoeConfig` — **not the expert set** — so adding experts would
silently reuse trial-2's identity space. Add a tamper-evident **`identity_hash`** without
changing `moe_hash`'s signature (it stays stable for existing callers):

```python
def identity_hash(cfg: MoeConfig, expert_names: list[str],
                  ortho_constants: dict) -> str:
    # sha256 over (moe_hash(cfg), sorted(expert_names), ortho_constants)
```

`build_moe_report` records `"experts": [...names]`, `"identity_hash": ...`, and
`"ortho_constants": {"FUNDING_CAP":0.01, "OI_LOOKBACK":24}` in the report. The registration
freezes `identity_hash` (not `moe_hash`) as this trial's identity.

## 6. Anti-artifact protocol (reused verbatim)

Unchanged from the MoE spec §4.4–4.6:
`GATE0_FAILED_HALT → POWER_BUDGET_REFUSED → CLOSED_NEGATIVE_VALIDATION →
CLOSED_NEGATIVE_SEALED_BTC → CLOSED_NEGATIVE_TRANSFER → ALL_GATES_PASSED_HUMAN_DECISION_PENDING`.

- **Gate-0 null calibration runs first** and must return negative on all nulls (now over the
  5-expert set) or the run halts.
- **Power budget** gates `p_eff`: 5 experts × 3 tradeable regimes = 15 candidate cells, still
  capped by `allowed_p_eff(n_train, m_per_weight)` (≈199 at n≈9983 → not binding).
- **Sealed window** (2025-07→2026-07) opens ONLY if Gate-0 + power + Gate-1 pass, spent **once**;
  currently UNSPENT.
- **DSR `n_trials = EFFECTIVE_TRIALS = 12`.** This is **trial 3 of ≤12** (trials 1–2 used).

## 7. Testing (TDD; house conventions)

One `tests/test_moe_<area>.py` per changed area:
- **`test_moe_orthogonal_experts`:** FUNDING fade sign (+funding→short, −funding→long); OI
  confirmation (d_oi>0 → sign(d_px); d_oi≤0 → 0); `None`/short-history → `RawSignal(0,0)`;
  causality (bar `t` uses only funding/OI/closes ≤ `t`).
- **`test_moe_experts` (extend):** `ExpertContext` construction; `default_experts()` names ==
  `{BREAKOUT,PULLBACK,REVERSION,FUNDING,OI}`; price experts unchanged under the new context.
- **`test_moe_null_calibration` (extend):** Gate-0 stays **non-vacuous and negative** with the
  5-expert set (candles span all split windows via the DAY_MS `_make_candles`; synthetic
  funding/OI series attached).
- **`test_moe_identity_hash`:** `identity_hash` differs when the expert set or an ortho constant
  changes; equal for the same inputs.
- **`test_moe_report` (extend):** bundle-input signature; ortho-`None` bundle reproduces the
  price-only verdict; verdict ∈ the frozen set; sealed stays `None` unless Gate-0+power+Gate-1
  pass.
- **`test_moe_cli` (extend):** `--experts` parses; asset dicts carry `funding_symbol` +
  `metrics_field`.

## 8. Known risks / constraints

- **OI coverage head-gap.** Binance Vision `sum_open_interest` starts ~2020-09; the train window
  opens 2020-01. `load_bundle`'s `_check_coverage` may reject the ~9-month gap. Resolution
  order: (1) OI expert no-fires on `None` (already specified), (2) the plan verifies
  `_check_coverage`'s threshold and, if it rejects, relaxes it **for the optional feature series
  only** (never for candles) or documents an OI-channel start offset. Funding has full-window
  coverage.
- **No look-ahead, ever.** funding/OI enter only via the as-of-aligned `DataBundle` series;
  experts index ≤ current bar; trades still enter at `t+1`.
- **OI expert references price direction** (conviction-gated momentum) — by construction it may
  correlate with the price experts; whether it adds *independent* confluence is exactly what
  validation tests. Acceptable; not a defect.

## 9. File-change summary

- `src/moonface/signal/engine/moe/experts.py` — `ExpertContext`; `Expert` protocol signature;
  adapt `_MechanismExpert`; add `_FundingExpert`, `_OiExpert`, frozen constants,
  `orthogonal_experts()`, `default_experts()`.
- `src/moonface/signal/engine/moe/config_moe.py` — add `identity_hash(...)` (keep `moe_hash`).
- `src/moonface/signal/engine/moe/evaluate_moe.py` — `ExpertContext` construction in
  `_raw_series`/`build_fit_panel`/`moe_stream`/`_stream_from_series`; `build_moe_report` takes
  `DataBundle`s; record `experts`/`identity_hash`/`ortho_constants`.
- `tools/moe_evaluate.py` — asset dicts gain funding/OI; pass bundles; `--experts` flag.
- `tests/test_moe_*.py` — as in §7.
- `experiments/engine/MOE_ORTHO_REGISTRATION.md` — pre-registration (frozen `identity_hash`,
  expert set, constants, kill rule, trial 3/≤12), committed **before** the run.

## 10. Kill rule / terminal state

Expected `CLOSED_NEGATIVE_VALIDATION` or `CLOSED_NEGATIVE_SEALED_BTC`. Only
`ALL_GATES_PASSED_HUMAN_DECISION_PENDING` warrants human deliberation — never auto-promote,
never auto-open capital. A negative closes the free-data orthogonal-expert line; the sealed
window is spent at most once and only on a genuine Gate-0+power+Gate-1 pass.
