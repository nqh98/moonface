# BTC Portfolio Tournament — Build Status

**Date:** 2026-06-25
**Branch:** `lane/btc-portfolio-tournament` (base `3af23ec`, NOT merged to main, NOT pushed)
**Plan:** `docs/research-log/plans/2026-06-25-btc-portfolio-tournament.md` (gitignored)
**Spec:** `docs/research-log/specs/2026-06-25-btc-portfolio-tournament-design.md` (gitignored)

## Status: BUILT + TASK-REVIEWED CLEAN; real run is HUMAN-GATED

The `research/portfolio/` lane is implemented, tested, and task-reviewed (12/12 tasks,
each with spec-compliance + code-quality review). The build ships **disabled by default**
— it is pure research tooling. The actual register/explore/select/validate run on real
BTCUSDT 1h+4h data (which opens the sealed holdout) is **NOT part of this build** and must
be triggered by a human.

## What was built

- `src/moonface/research/portfolio/` (9 modules): `components` (frozen 9 center cells),
  `streams` (per-bar positions/returns + 4h→1h MTF alignment), `correlation` (Step-0
  low-correlation basket screen), `operators` (vote / vol_target / regime_switch /
  long_short_net), `evaluate` (equity metrics), `gates` (DSR + 3× cost battery + ensemble
  gate), `validate` (ECON_BAR walk-forward + sealed tail), `grid`+`pipeline` (frozen
  8-portfolio grid + staged register/explore/select/validate).
- `tools/portfolio_search.py` — 4-subcommand CLI mirroring `tools/practical_search.py`.
- `src/moonface/foundation/exits.py` + `metrics.py` — **additive** trade-span resolver
  (`_SPAN_FNS`, `resolve_trade_span`); `single_trade_r` and `EXIT_REGISTRY` byte-unchanged.
- 11 test files (84 portfolio-lane tests).

## Frozen design (cannot be changed without re-registration)

- **Components:** the 9 system_cells 1h+4h center (median-swept) price components ONLY
  (1h: roc_sign, atr_channel_break, trend_pullback, vol_expansion, vol_regime; 4h: ma_cross,
  donchian_break, atr_channel_break, vol_regime). Funding/OI/out-of-grid families are OUT
  OF SCOPE (no frozen centers in system_cells).
- **Common currency:** `asset_bar_r = (close−close_prev)/atr` denominates components AND
  portfolio; grid = 1h; 4h components forward-filled onto 1h.
- **Cost model:** one-way turnover `|Δpos| × COST_FRACTION / (2 × atr_frac)` ⇒ one
  entry+exit round-trip = `COST_FRACTION/atr_frac` (matches `single_trade_r`).
- **Grid:** 8 portfolios (vote×2, vol_target×4, regime_switch×1, long_short_net×1);
  pooled DSR `n_trials = 8` (trial_srs = the portfolios' own Sharpes, self-derived).
- **Economic bar verbatim:** PF≥1.2 / exp≥0.05R / MAR≥0.5 / MaxDD≤30R @f=0.01 /
  robust_frac≥0.6; DSR≥0.95; battery incl. +5bps/side AND 3× base-cost; ensemble gate =
  portfolio MAR > best-MAR component's MAR AND |portfolio MaxDD| ≤ 80% × |that component's MaxDD|.
- **Window:** 3y BTC, `start_ms=1687305600000` → `end_ms=1782000000000`; force fresh fetch 1h+4h.
- **Holdout:** 60/20/20 per TF; sealed last-20% opened ONLY at `--validate`.

## Verification (controller-run)

- **Portfolio lane:** 84/84 tests green.
- **Full suite:** 1063 passed, 1 failed — the 1 failure is `test_pathsig_rung2_cli.py`
  (`ModuleNotFoundError: No module named 'numpy'`), a pre-existing carry-over from the
  unmerged distributional-path program, documented in prior lanes; **unrelated to this build**
  (portfolio imports neither numpy nor pathsig). Ignoring the 3 pathsig carry-overs
  (`test_pathsig_forest.py`, `test_pathsig_rung2.py`, `test_pathsig_rung2_cli.py`) ⇒ clean.
- **Ruff:** clean (portfolio pkg, foundation edits, CLI, tests).
- **Isolation:** `test_portfolio_isolation.py` (13) + `test_import_boundaries.py` green;
  `EXIT_REGISTRY` membership unchanged (5); no `_PAPER_BRIDGES` edit; portfolio imports no
  closed lane.

## Human-gated next step (NOT done)

```
.venv/bin/python tools/portfolio_search.py --register   --symbol BTCUSDT \
    --start-ms 1687305600000 --end-ms 1782000000000 --out-dir experiments/portfolio/run1
# commit PREREGISTRATION.md, then force-fresh-fetch 1h+4h, then:
.venv/bin/python tools/portfolio_search.py --explore  ... --out-dir experiments/portfolio/run1
.venv/bin/python tools/portfolio_search.py --select   ... --out-dir experiments/portfolio/run1
# commit frozen_candidates.json, then:
.venv/bin/python tools/portfolio_search.py --validate ... --out-dir experiments/portfolio/run1
```

Per spec §9, the likely outcome is NEGATIVE (the 9 price-trend components are expected to
co-move ⇒ Step-0 `thesis_dead`, no holdout spent; or fail DSR/econ). A portfolio that clears
all four gates earns a forward paper-watch registration (modeled on the Donchian Slice-3
forward journal binding). Kill-rule: a failed family is closed, not retuned.
