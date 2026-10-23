# Confluence Engine v2.2 — Evidence-Backed Module Prune (Design)

**Date:** 2026-07-05
**Status:** Approved design, pre-implementation
**Predecessor:** v2.1 (`experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md`, hash `4e35561f…`)
**Evidence:** `experiments/engine/SCORING_AUDIT_2026-07.md` (Stage-1 f72c3a1, Stage-2 d1da1c7 — read-only, one-run rule honored)

## 1. Decision and rationale

The 2026-07 scoring audit is the human-gated evidence feed this change consumes.
Per its registered results:

- **m4_pullback is HARMFUL in both stages** (LOO Δρ CI entirely > 0, pooled:
  Stage-1 [0.0003, 0.0222], Stage-2 [0.0052, 0.0245]; conditional SHORT
  ordering CI-clean negative). Removal *improves* outcome ordering on
  direction-stable bars. This is the only module removal the audit directly
  supports.
- **The mean_revert book is NO_SIGNAL_IN_ANY_WEIGHTING in both stages.** No
  code change is needed: v2.1 already converts every valid revert candidate
  into a `VETO_NO_CT` shadow (`confluence.py` `decide()`), so the book never
  emits. v2.2 keeps that behavior and records the audit verdict as its
  standing rationale.
- **Everything else stays.** LOO "DEAD" does not license deletion: the LOO Δρ
  was computed only on direction-stable bars, and e.g. m1_macro removal flips
  the book direction on ~14k bars — an unmeasured, structurally different
  engine. The fitted upper bound found no reweighting that beats the hand
  weights, so weights are untouched too.

**v2.2 = v2.1 minus m4_pullback's influence on the trend book. Nothing else.**

## 2. Behavioral change (the only one)

### 2.1 m4_pullback exclusion

- A frozen constant in `confluence.py`:
  `EXCLUDED_MODULES = ("m4_pullback",)` (v2.2, audit-based; a tuple, not a
  set — `config._jsonable` only encodes dict/tuple/list, and the constant
  must fold into the `engine_hash` payload).
- `_book_context` skips excluded modules when computing the **signed sum**,
  **breadth**, and **max_attainable**. The module is still *scored* every bar
  by `trend_book.score` and still journals its points via `Decision.modules`
  — it just no longer counts.
- Trend book max drops 100 → 85 (70 on bars without funding data).
  `BASE_THRESHOLD = 60` and `TIER_A = 75` stay **absolute** — the engine is
  knowingly stricter, both on score and on breadth (BREADTH_MIN 3 now out of
  5 countable modules, 4 when deriv data is absent). This is the approved
  trade-off: no new hand-picked constants; the v2.2 score is exactly the
  LOO score the audit measured.

### 2.2 Exclusion shadow (forward falsifiability)

New veto label, following the v2.1 shadow pattern:

```
VETO_M4_EXCLUDED = "v2.2 m4_pullback excluded"
```

When the **with-m4** trend book (v2.1 scoring, all current policy applied —
long-only, gate) would have produced a valid candidate but the **v2.2**
(without-m4) book does not emit a trend candidate, the decision journals
`veto = VETO_M4_EXCLUDED`, `shadow_score` = with-m4 score,
`shadow_direction` = with-m4 direction. Precedence when multiple vetoes
apply follows the existing trend-before-revert convention.

`tools/engine_ablation.py` gains the family `m4_pullback` alongside `macro`,
`no_ct`, `long_only`, so the horizon ablation can test the exclusion on
forward data. (The journal's full per-module points additionally allow exact
counterfactual reconstruction.)

## 3. What deliberately does not change

- All remaining module weights (20/20/10/20 + funding 15), all module panel
  params, `BASE_THRESHOLD`, `TIER_A`, `CT_SURCHARGE`, `BREADTH_MIN`, the
  macro gate matrix, long-only, no-CT, flat tier fraction 0.005 (high-vol
  halved), reversal-exit semantics, `lookback_bars = 6000`.
- The mean_revert book: still scored, still journaled, still shadow-only.
- `promotion/engine.json` (config identical; only code constants change).

## 4. Versioning, hash, registration

- `ENGINE_VERSION = "2.2"` (`config.py`); `EXCLUDED_MODULES` and
  `VETO_M4_EXCLUDED` fold into the `engine_hash` payload with the other
  frozen constants → new hash → journal record isolates from v2.1 rows.
- v2.1 registration gets a SUPERSEDED addendum (same pattern as v2 → v2.1;
  its record was 1 day old with no completed setups).
- New `experiments/engine/CONFLUENCE_V22_FORWARD_REGISTRATION.md`, terms
  carried over from v2.1 unchanged: paper-only, NO_CLAIM banner, horizon =
  later of 6 months / ≥ 30 completed setups, success bar = net R > 0 + the
  layered DD budgets + mandatory (non-gating) ablation report — now over
  four families — one-cycle kill rule, fresh clock.
- Non-gating sanity replay via `tools/engine_honest_report.py`
  (2020-01 → 2026-06, deriv=None) at the v2.2 hash, recorded in the
  registration **only after verifying the output artifact exists**
  (v2.1 gotcha: a frozen doc once claimed a replay that had never started).
- Ships disabled; daemon restart is human ops.

## 5. Ripple: calibration/audit harness

The calibration harness (`calibration.scoring_pass` and its parity tests
against `evaluate_engine`) mirrors the frozen engine; it follows the engine
to v2.2 so parity holds. The registered 2026-07 calibration and audit
reports remain historical records at hash `4e35561f…` — they are not re-run
(one-run rule).

## 6. Testing

- New tests pin: (a) m4_pullback points appear in `Decision.modules` /
  journal but never in score, breadth, or max_attainable; (b) a bar whose
  with-m4 score crosses the threshold but without-m4 does not journals
  `VETO_M4_EXCLUDED` with the with-m4 shadow score/direction; (c) revert
  book still never emits; (d) `engine_hash` differs from v2.1's and changes
  if `EXCLUDED_MODULES` changes; (e) ablation tool reports the new family.
- Existing engine suite adapts where it asserts trend scores that included
  m4_pullback.
- Full suite green before the registration freezes.

## 7. Honesty note (binding for the registration text)

Stage-2 showed even the trend book at NO_SIGNAL_IN_ANY_WEIGHTING on the
deriv-inclusive panel, and the audit measured m4-removal ordering only on
direction-stable bars. v2.2 is a **defensibility improvement over v2.1, not
a validated edge**; the registration must say so explicitly.
