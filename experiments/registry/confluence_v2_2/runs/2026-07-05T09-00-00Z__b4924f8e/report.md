# confluence_v2_2 — run 2026-07-05T09-00-00Z__b4924f8e

Companion narrative to `result.json` in this directory. Same facts, in prose.

## What was registered

`experiments/engine/CONFLUENCE_V22_FORWARD_REGISTRATION.md`, frozen 2026-07-05,
`engine_hash = b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5`.
Paper only, BTC/USDT:USDT 1h. Horizon: later of six months (2027-01-05) or
30 completed setups.

## What the journal shows

`journal/signals.jsonl`, filtered to rows at this hash: 572 rows spanning
2026-07-05T09:00:00Z to 2026-07-29T04:00:00Z. Every row is WAIT — 0 completed
setups. 20 rows carry the `no_ct` veto (v2.1's no-counter-trend-entries rule).

572 rows is fewer than the window implies (2026-07-05 to 2026-07-29 is ~575
hourly candles at 1h) because of one gap, backfilled, documented in
`experiments/engine/V22_DOWNTIME_RULING_2026-07-29.md`:

- 2026-07-08T07:00:00Z to ~2026-07-29T02:00:00Z (20d19h, 501 candles): the
  watch daemon was hand-started with `nohup` and died unsupervised.
- Backfilled the same day via a faithful replay (`engine_backtest` +
  historical `fetch_deriv_snapshot`, verified 0/501 decisions differ from
  what the live path would have produced): 503 rows reconstructed and
  appended (501 for the gap, plus 2 one-hour holes the live daemon had
  independently skipped), each row marked `"reconstructed": true`.
- That same document records its own ruling was amended hours later, after
  the backfill surfaced that the original replay had silently omitted the
  derivative-snapshot inputs, and that "zero evidence lost" had been false
  (18 of the 20 veto events sat inside the reconstructed span). Both errors
  are corrected in that document, not here — this file only cites it.

The pre-backfill journal state is kept at
`journal/signals.jsonl.pre-backfill-2026-07-29.bak` for anyone who wants to
diff against it.

## Why the record stops at 2026-07-29

`journal/signals.jsonl` has not been written since 2026-07-29T04:00:00Z — the
daemon was never restarted after that backfill. `docs/research-log/specs/2026-08-22-repo-restructure-design.md`,
dated 2026-08-22, states plainly that "the v2.2 forward run is halted." That
sentence is the ruling this run record closes against; no further backfill
was attempted for the silence after 2026-07-29.

`promotion/engine.json` still reads `"enabled": true` — the registration's own
kill rule (`DOWNGRADE -> enabled=false`) was never formally invoked. The halt
is at the daemon level, not a config change, and this record keeps that
distinction rather than collapsing it.

## What this record does not say

Per the restructure spec's invariant 0, this record carries no status field
and no verdict. It does not say confluence is dead, does not say the run
failed, and does not say the hypothesis is disproven. It says what happened:
572 rows, 0 completed setups against a 30-setup bar, one backfilled outage,
one un-backfilled silence, and the ruling that treats the silence as the
run's end rather than as a third outage to patch. Re-running this
registration, or a new one, needs no permission and does not overturn this
record — it would simply append beside it.
