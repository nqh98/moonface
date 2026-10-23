# BTC-Specialized Practical Signal Optimization

NEW lane — Slice 1 = 2h/4h trend + breakout. PAPER-signal discovery only; never live.
Closed `system_search` / `practical` lanes and the active Donchian Slice-3 thread are
untouched. DSR is reported, never gated. Expected outcome: NEGATIVE (valid).

## Staged run (human-gated; commit between phases)

```bash
OUT=experiments/btc_specialized/slice1_trend_breakout
W="--start-ms 1577836800000 --end-ms 1782000000000"   # ~2020-01 -> 2026
.venv/bin/python tools/btcspec_search.py --register $W --out-dir $OUT
git add $OUT/PREREGISTRATION.md && git commit -m "research(btcspec): freeze Slice-1 PREREGISTRATION"
.venv/bin/python tools/btcspec_search.py --explore  $W --out-dir $OUT   # CPU-bound (wide grid, ~hours)
.venv/bin/python tools/btcspec_search.py --select   $W --out-dir $OUT
git add $OUT/frozen_candidates.json && git commit -m "research(btcspec): freeze Slice-1 candidates"
.venv/bin/python tools/btcspec_search.py --validate $W --out-dir $OUT
git add $OUT/RESULT.md $OUT/result.json && git commit -m "research(btcspec): Slice-1 RESULT"
```

A `paper_accept` triggers a SEPARATE, future, human-gated paper-forward protocol —
never live capital, never the Donchian slot.
