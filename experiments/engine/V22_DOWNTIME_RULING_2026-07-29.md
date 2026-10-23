# Confluence v2.2 — ruling on the 2026-07-08 → 2026-07-29 downtime

Attaches to `experiments/engine/CONFLUENCE_V22_FORWARD_REGISTRATION.md`. The
registration itself is **not modified**; this is the downtime record its clock
needs in order to remain interpretable.

## The gap

| | |
|---|---|
| Registered live | 2026-07-05 09:00 UTC |
| Last journal row | 2026-07-08 07:00 UTC |
| Daemon restarted | pending (human) |
| Gap | **20 d 19 h**, 501 hourly candles |
| Cause | `moonface-signal --watch` was hand-started with `nohup` and died unsupervised. No cron entry, no flock guard — unlike the liquidation collector. |

## Did the gap cost evidence?

Measured, not assumed. `tools/engine_backtest.replay()` drives the **same
`evaluate_engine` path the live loop uses** (faithful by construction, per its
own docstring), with the identical rolling `lookback_bars` window.

Pre-check: `engine_hash(load_engine_config("promotion/engine.json"))` still
returns `b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5` —
byte-identical to the frozen v2.2 registration. The engine did not change
during the outage, so a replay reproduces what the daemon would have written.

Result over the gap window:

```
replayed entries: 501
decisions:        {'WAIT': 501}
NON-WAIT:         0
```

**Zero setups would have fired.** The gap cost calendar time only. The
`≥30 completed setups` criterion stands at 0 either way.

*Non-contamination:* decisions only were computed. No forward returns were
observed, no scorecard was produced, nothing was written to the journal. Same
discipline as `tools/v3_replay.py`.

## Ruling

**Document as downtime and continue the existing clock.** The registration
stands unamended; the verdict trigger remains *later of 2027-01-05 / ≥30
completed setups*.

Reasoning, in the order it was decided:

1. **Identity intact.** The frozen hash still matches, so this is the same
   experiment, not a new one.
2. **No evidence lost.** 501/501 WAIT. Nothing that the registration counts was
   missed, so there is nothing to compensate for.
3. **The alternatives are strictly worse.** Restarting the clock, or voiding to
   v2.3, would discard 69 valid rows and reset six months to recover from an
   outage that cost zero setups. That is over-punishment, and re-registering
   would itself be a fresh hash and a fresh clock for no epistemic gain.
4. **Reconstruction was rejected.** The replayed rows are *not* being inserted
   into the journal. They would be indistinguishable in content from live rows,
   but they were produced knowing the price path, and a forward record whose
   rows are generated after the fact is no longer a forward record. The
   diagnostic answers the question; it does not backfill the artefact.

The journal therefore carries a real 20-day hole. That is the honest state and
it is preserved deliberately.

## The larger problem this exposed

Independent of the outage, and more serious than it:

- 69 live rows + 501 replayed = **570 consecutive hourly candles at the v2.2
  hash, every one WAIT, zero setups.**
- The frozen sanity replay recorded 130 trades over the multi-year backtest —
  roughly one setup per 17 days.
- The trigger is the **later of** the date and the setup count, so the date is a
  floor: the verdict will land on 2027-01-05 with an expected handful of setups,
  not 30.

**v2.2 is on course to deliver a date-triggered verdict on a sample far below
the one its own success criterion names.** That was baked in at registration and
is not caused by the gap. It is recorded here so the eventual verdict is not
read as more than it is. Changing the criterion now would require a new
registration and a fresh clock; that is a human decision and is not taken here.

## Required before the daemon is restarted

Restarting with `nohup` reproduces the exact failure this document is about.
The daemon needs a supervisor, mirroring the liquidation collector's pattern:

```
* * * * * cd <repo> && flock -n /tmp/moonface_watch.lock \
    .venv/bin/moonface-signal --watch >> watch.log 2>&1
```

(Do **not** use a `pgrep -f ... ||` watchdog — the cron wrapper's own command
line contains the process name, so pgrep self-matches and the restart branch
never fires. `flock` cannot self-match.)

And verify accrual afterwards by reading output, never the process table:

```
.venv/bin/python tools/accrual_check.py
```

---

# AMENDMENT — the ruling above was overturned the same day, and it was wrong

The human directed a backfill. Executing it surfaced two errors in the ruling,
one of method and one of substance. Both are recorded here rather than edited
away.

## Error 1 (method): the replay was not faithful

The ruling claimed the replay "reproduces what the daemon would have written."
It did not. `tools/engine_backtest.replay()` calls `evaluate_engine` with the
default `deriv=None`, while the live path
([cli.py:316](../../src/moonface/signal/cli.py:316)) fetches a derivatives
snapshot and passes it in. The live rows show `m5_funding` and `m4_fund_ct`
scoring 15 points each with `data_ok: true` — the derivative modules were
active live and absent in the replay.

`replay()`'s own docstring — "accumulating synthetic journal entries with the
exact schema `_emit_engine` writes" — is also wrong: it omits eight fields
(`gate`, `modules`, `profile`, `shadow_direction`, `shadow_score`, `target`,
`tier`, `veto`) and writes `style: "backtest"`.

Corrected by rebuilding through `evaluate_engine` directly with a per-candle
`fetch_deriv_snapshot(symbol, candle_ts)` — which is reconstructible, since it
takes `now_ms` as a parameter. **Verified: 0 of 501 decisions differ between
the deriv-less and deriv-enabled runs**, max confidence 0.7500 in both. So the
ruling's conclusion survived, but it had been asserted on weaker evidence than
claimed.

## Error 2 (substance): "the gap cost zero evidence" is false

It cost zero *setups*. It did not cost zero *evidence*:

| in the 501-candle gap | count |
|---|---|
| bars scoring ≥ 60 (the threshold) | **23** |
| bars scoring ≥ 75 (Tier-A) | **10** |
| bars vetoed `v2.1 no counter-trend entries` | **18** |

The registration's success criterion includes a **four-family ablation report**,
one family of which is `no_ct`, and `tools/engine_ablation.py:42` reads exactly
the `veto` field. Those 18 veto events are the ablation's input. Losing them is
a real loss, and the original ruling — "nothing that the registration counts was
missed" — was simply incorrect.

**The instruction to backfill was better founded than the ruling that resisted
it.**

## What was actually done

503 rows rebuilt and appended to `journal/signals.jsonl` (501 for the outage,
plus two one-hour holes at 2026-07-06 10:00 and 2026-07-07 10:00 that the *live*
daemon itself had skipped). Each carries provenance:

```json
"reconstructed": true,
"reconstructed_utc": "...",
"reconstructed_by": "engine_backtest replay + historical fetch_deriv_snapshot"
```

Content is field-identical to a live row; the markers exist so the record cannot
be mistaken for wholly-live. The journal was then re-sorted chronologically —
`position.reconstruct()` takes `mine[-1]` in *file* order, so out-of-order rows
are a latent hazard even though every row here is WAIT.

State after: **572 rows at hash `b4924f8e…` (69 live + 503 reconstructed),
0 hourly gaps, 2026-07-05 09:00 → 2026-07-29 04:00, 20 veto events.**
`read_entries`, `engine_scorecard` and `reconstruct` all verified working.

## Consequence for the registration, stated plainly

**v2.2 is no longer a pure forward record.** 88% of its rows were generated
after the fact, with the price path known. The determinism argument (frozen
hash, causal engine, verified identical decisions) makes the rows *correct*; it
does not make them *forward*. Any verdict written on 2027-01-05 must state
"live + reconstructed" and must not be presented as an out-of-sample forward
result.

That is a real cost, accepted deliberately by the human in exchange for a
continuous record and the recovered veto events. It is recorded here so the
eventual verdict is read for exactly what it is.
