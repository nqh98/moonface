# 4h vol_expansion — Forward Paper Registration (frozen 2026-06-25)

Isolated research-side paper-watch for the practical-full finalist. PAPER ONLY —
REAFFIRM does NOT authorize live capital; going live stays a separate human-only
decision. Touches nothing in promotion/ or journal/signals.jsonl (those belong to
the Donchian watch). Evaluation is read-only via
`tools/vol_expansion_watch.py --report`.

## Strategy under test (byte-identical to frozen_candidates.json)
- entry vol_expansion mult=3.0, atr_period=14, lookback=24 ; nonoverlap h=24
- exit atr_trail k_trail=2.0, max_bars=120, atr_period=14 ; fraction=0.01
- asset BTC/USDT:USDT 4h ; status=paper

## Why it is on watch
Cleared the full practical bar (net-positive, |DD|<=30R, outlier-clean, robust to
2x/3x cost) on Explore AND Validate, then REVERSED to negative expectancy in the
sealed/most-recent window (2025-03 -> 2026-06, exp -0.32, n=32). This forward
watch tests whether that recent decay is a regime-transient or a real death,
using fresh out-of-time evidence — NOT a re-cut of the 6.5y path.

## t0 and counting
- t0 = 2026-06-25T15:56:22.653000+00:00 (t0_ms=1782402982653).
- The forward window counts CLOSED trades whose ENTRY bar timestamp >= t0 and
  whose full max_bars window has elapsed within available data (edge positions
  count as open, never marked-to-end).
- State at registration: 0 closed forward trades (data ends ~2026-06-20 < t0).

## Frozen resolution rule (fields from research.practical_full.forward.forward_report)
| Outcome | Pre-committed trigger |
|---|---|
| REAFFIRM PAPER | gate.passed == True — closed_trades >= 20 AND elapsed_weeks >= 12 AND net_r > 0 AND gate.drawdown_within_p95 == True (max_drawdown >= -0.30). |
| DOWNGRADE — early kill | gate.drawdown_within_p95 == False at ANY --report with >=1 closed trade (forward equity DD breaches the 0.30 budget). |
| DOWNGRADE — horizon | min_trades AND min_weeks both True but gate.passed False (fails on net_positive). |
| Stay INCONCLUSIVE | none of the above — keep paper-tracking. |

Thresholds (FORWARD_MIN_TRADES=20, FORWARD_MIN_WEEKS=12.0, MAX_DD_BUDGET=0.30)
mirror moonface.signal.journal.forward_report and the locked economic bar. No
threshold may change after this date.

## Honest caveats
- Single-asset BTC, paper-only. REAFFIRM != live.
- A 4h vol-expansion entry fires infrequently; reaching >=20 CLOSED forward
  trades will likely take well beyond 12 weeks. Continued INCONCLUSIVE is the
  expected near-term state, not a failure. The early-DD-kill guards a slow bleed.
- The finalist already FAILED the most-recent backtest window; this watch can
  only REAFFIRM or DOWNGRADE forward, it does not relitigate the negative holdout.
