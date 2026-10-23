# funding_fade_fwd — Pipeline Freeze Plan

## Code paths the forward evaluation uses (exhaustive)

| Stage | Path |
|---|---|
| OHLCV ingestion | `src/moonface/foundation/data.py::fetch_history` + `OhlcvCache` |
| Funding ingestion | `src/moonface/foundation/series.py::fetch_funding_history` + `FundingCache` |
| Funding alignment | `src/moonface/foundation/series.py::align_funding` |
| Entry signal | `src/moonface/research/edge/funding_signals.py::make_funding_fade` |
| Exit simulation | `src/moonface/foundation/exits.py::fixed_bracket` (via `EXIT_REGISTRY`) |
| R streams / split | `src/moonface/research/edge/exit_score.py::exit_r_streams`, `src/moonface/research/sizing.py::split_research_tail` |
| Summaries | `src/moonface/foundation/metrics.py::summarize_r` |
| Orchestration/clamp | `src/moonface/research/funding_fade_fwd.py` |
| CI / ruin / power / forward rule | `src/moonface/research/fwd_analysis.py` (`bootstrap_expectancy_ci`, `forward_success`, `null_p95_threshold`) |
| Null generator | `src/moonface/research/fwd_null.py::shuffle_funding_segments` |
| CLI / reports | `tools/funding_fade_fwd.py` |

## Freeze mechanics

- At human sign-off, record in STATUS.md: the git commit hash containing all
  paths above, the identity_hash, the chosen DD budget, and the chosen N.
- The forward evaluation is a SINGLE run of a forward-mode entry point added
  only after sign-off, executed from the pinned commit (e.g. a detached
  worktree at that hash). One spend; the run computes the 200-seed null
  benchmark (seeds 0–199, frozen convention) and the three-condition
  verdict in the same execution, and writes the verdict file directly.
  Re-runs require a written VOID/amendment note — there is no silent second
  spend.
- Between sign-off and verdict: no code changes to any listed path. If an
  unrelated repo change forces one (e.g. dependency breakage), that is a
  spec §5 escalation with a dated note, decided by the human.

## Dry-run record

- `dryrun_report.json` (2026-07-14): reproduced the completed-candle
  baseline EXACTLY (Amendment 1 tolerance: exact match on all
  completed-candle figures at reported precision). Window: 3y ending
  2026-06-10T06:51:46Z; `oos_tail_bars=1095`, `warmup=60`, `future_bars=48`.
  Escalation-1 history: the two archived OOS aggregates embedded a
  forming-candle snapshot and were re-baselined (+76.7285R → +77.3435R);
  every in-principle-reproducible figure matched the archive exactly.
- Null-guard record (2026-07-14): 192/200 nulls fail the three-condition
  rule → guard_ok (machinery validation; circularity acknowledged).
- Reproduction failure policy: STOP and ask; never patch silently (spec §5.2).

## Forward-run data plan (Approach A, design §5)

- No collector, no daemon. At trigger time, one retroactive fetch:
  candles/funding from before `FORWARD_START_MS` (2026-06-10T08:00:00Z)
  only as indicator warmup (60-bar funding z-window state); trades count
  only from bars with open time ≥ `FORWARD_START_MS`; `end_ms` = trigger
  date.
- Cache isolation: the forward run uses its own cache directory (the
  drafting phase used `.backtest_cache_fwd`, clamped pre-cutoff; the shared
  `.backtest_cache` is partial for this symbol and is not used).
- Reconstructibility check against VOID rule 2 runs BEFORE any performance
  aggregation: bar-count and funding-cadence audit vs expected calendar.
- The 200-seed null benchmark shuffles the FORWARD window's aligned funding
  series per-segment; nulls share the identical pipeline, warmup, and
  window as the real run.
