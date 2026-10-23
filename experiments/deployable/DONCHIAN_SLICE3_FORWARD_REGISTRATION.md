# Donchian 4h — Slice-3 Forward Paper Registration (frozen 2026-06-20)

Pre-registers the already-running forward paper test as the mechanism that
resolves the 2026-06-20 revalidation verdict
`INCONCLUSIVE / PAPER-SUSPENDED`
(`experiments/deployable/DONCHIAN_REVALIDATION_RESULT.md`) into REAFFIRM or
DOWNGRADE — using fresh out-of-time evidence, NOT a re-cut of the 6.5y path and
NOT post-hoc tuning of the N=4 robust_frac. Criteria are frozen at registration.
Evaluation is read-only via `moonface/signal/cli.py --report`.

## Strategy under test (byte-identical to the revalidated config)
- donchian_break n=40, long_only; exit donchian_trail atr_period=14, k_stop=2.0,
  trail_n=20; fraction=0.01; asset BTC/USDT:USDT 4h; status=paper.
- strategy_version (strategy_hash): df7cc856875b290c3c1421979f04f74197b2344373ff39289f75ac685c4c2df9
- Source of truth: promotion/strategy.json. Journal: journal/signals.jsonl.

## t0 and counting
- t0 = 2026-06-20 (this registration).
- The forward window counts CLOSED trades of strategy_version df7cc856 only.
  Prior-version (2002f4be…) journal entries are excluded automatically by
  forward_report's version filter.
- State at registration: 0 closed trades, 0 open trades, 9 WAIT signals.

## Frozen resolution rule (fields from moonface.signal.journal.forward_report)
| Outcome | Pre-committed trigger |
|---|---|
| REAFFIRM PAPER | gate.passed == True — closed_trades >= 20 AND elapsed_weeks >= 12 AND net_r > 0 AND gate.drawdown_within_p95 == True (max_drawdown >= -0.30). Verbatim from journal.py (FORWARD_MIN_TRADES=20, FORWARD_MIN_WEEKS=12.0). |
| DOWNGRADE — early kill | gate.drawdown_within_p95 == False at ANY --report check (forward equity drawdown breaches the 0.30 p95 budget) → downgrade immediately, before the horizon. |
| DOWNGRADE — horizon | gate.min_trades AND gate.min_weeks both True but gate.passed False (fails on net_positive) → downgrade. |
| Stay INCONCLUSIVE | none of the above — keep paper-tracking; journal keeps accumulating. |

No threshold may be changed after this date. REAFFIRM means KEEP ON PAPER (clears
the paper→live review only); going live stays a separate human-only decision.

## Honest caveats
- Single-asset BTC, paper-only. REAFFIRM != live.
- The 12-week clock is wall-clock forward time; a 4h trend-follower fires
  infrequently, so reaching >=20 CLOSED trades will likely take well beyond 12
  weeks. Continued INCONCLUSIVE with an accumulating journal is the expected
  near-term state, not a failure. The early-DD-kill guards against a slow bleed
  during that accumulation.
- forward_report.max_drawdown is an equity-curve drawdown at fraction=0.01 over
  closed forward trades only; open positions are not marked to market (matches
  the backtest accounting).

## Out of scope
- No scheduler/daemon (running --watch unattended is a separate operational
  concern). No new gate/engine code. No threshold changes. Single-asset BTC 4h.

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
