# Collector & forward-experiment audit — 2026-07-29

Triggered by the standing mandate. Every remaining path to a credible signal
depends on data accruing between now and ~2027. This audit checks whether it
actually is.

**Headline: it is not. All three accruing streams are dead or empty.** The
program believes it has three clocks running toward 2027. It has zero.

Nothing was restarted or reconfigured — the v2.2 gap in particular is a
registration-integrity question, not an ops chore, and is a human ruling.

---

## 1. Confluence v2.2 forward experiment — DEAD 20 days

The program's **only live experiment**.

| | |
|---|---|
| Registered live | 2026-07-05 09:00 UTC |
| Last journal row | **2026-07-08 07:00 UTC** |
| Gap to now | **20 days 19 h** |
| Clock covered | 2 d 22 h of 23 d elapsed = **12.3 %** |
| Rows at hash `b4924f8e…` | 69, **all WAIT** |
| Completed setups | **0** (verdict needs ≥ 30) |
| `moonface-signal --watch` process | **not running** |
| In crontab | **no** |

The daemon was started by hand on 2026-07-05 (`nohup`) and has not survived.
There is no supervisor for it — unlike the liquidation collector, it has no
cron entry and no flock guard.

**This is not merely an ops gap.** The registration's clock is *"later of 6
months from 2026-07-05 / ≥30 completed setups"*. A 20-day hole in a forward
record is material to that clock, and the ruling is the human's:

- treat the hole as documented downtime and continue the existing clock; or
- restart the clock from the resume date; or
- void the registration and re-register as v2.3 (new hash, fresh clock).

Restarting the daemon *without* recording that ruling would silently paper over
the hole. Not done.

**Note independent of the gap:** at the observed rate (0 setups in 3 days, all
WAIT at score 25 vs threshold 60), the ≥30-setup criterion was never going to
bind before the 2027-01-05 date. Even a perfectly-run v2.2 was likely to
deliver a date-triggered verdict on a thin sample.

## 2. Liquidation collector — running, collecting nothing, 16 days

| | |
|---|---|
| Cron | present, every minute, `flock -n` guard — **correct** |
| Process | alive |
| `manifest.json` | `rows: 0`, `days: 0`, `coverage_ratio: 0.0`, unchanged since 2026-07-13 10:01 |
| CSV output | **`liq_BTCUSDT.csv` does not exist** — not one row ever appended |
| `watch.log` | continuous `ping-pong keepalive missing` and `closing code 1006` |

The 2026-07-13 fix (reconnect-on-NetworkError + flock watchdog replacing the
self-matching `pgrep`) **worked as designed** — the supervisor is not the
problem this time. The failure moved downstream.

**Root cause isolated (two probes, this session):**

- `watch_liquidations("BTC/USDT:USDT")` — 30 s budget, no message. Ambiguous
  on its own: could be sparsity or a dead socket.
- `watch_trades("BTC/USDT:USDT")` — returned immediately. **The WebSocket path
  is alive**; ccxt 4.5.56; no geo-block, no firewall.

So the socket is reachable and `forceOrder` is genuinely sparse — but sparse is
not zero, and BTC liquidations certainly occurred during 16 days. The picture
consistent with the log is a **keepalive/reconnect loop**: with no inbound
message the ping-pong watchdog expires, the socket drops 1006, the retry sleeps
5 s and reconnects, and the cycle repeats without ever holding a connection
long enough to receive an event.

**Consequence:** the readiness gate (≥180 d, ≥200 clusters, coverage ≥ 0.90 →
~2027-01-09) has **not started counting**. Its date is fiction.

**Fix direction (not applied):** subscribe to the combined `!forceOrder@arr`
stream rather than the per-symbol channel — `liquidation_feed.py:5` documents
`!forceOrder@arr` as the intended source, and an all-symbol firehose ticks
often enough to keep the keepalive satisfied — and/or drive an explicit
application-level ping. Needs its own change + test; not done here.

## 3. Deribit options-chain collector — never scheduled

| | |
|---|---|
| In crontab | **no — zero entries** |
| Output | one snapshot, `chain_BTC.csv`, 2026-07-03 09:30 |
| `manifest.json` | `history_days: 1`, `cadence_ms: 86400000` (daily) |
| Elapsed since | **26 days** |
| Days collected | **1** |

This is the *exact* failure recorded on 2026-07-13 for the liquidation
collector — *"the collector was NEVER started: no cron, no process, no output
dir. Cron was human ops and was never installed."* It was fixed there and the
same lesson was **not** applied here.

**Consequence:** Deribit readiness ~2027-01 is fiction. This matters more than
the other two: per `experiments/vrp_stage1/SPEC.md` §3.1 and the forced-flow
audit, the Deribit chain is the **only 0 %-overlap untested information source
the program has left**.

---

## Why this is the mandate's binding constraint

Free data is permanently finished (`liqprem` KILL, 2026-07-29). VRP Stage 1 is
not writable (premium below its estimator's noise floor). Every remaining route
to a credible signal runs through data accruing *now*:

| Stream | Believed state | Actual state | Days lost |
|---|---|---|---|
| Confluence v2.2 forward record | accruing to 2027-01-05 | dead | 20 |
| USDⓈ-M liquidations | accruing to ~2027-01-09 | 0 rows | 16 |
| Deribit options chain | accruing to ~2027-01 | 1 snapshot | 26 |

**No further analysis can advance the mandate.** It is blocked on collection,
and collection is not happening.

## Standing lesson (third occurrence)

*Verify accrual via output — file, row count, manifest — never via "the tool
was shipped" or "the cron was written."* This has now failed three times:
liquidation collector (never started, 2026-07-13), Deribit chain (never
scheduled, found today), confluence v2.2 daemon (started, died unsupervised,
found today).

The generalisation the first two fixes missed: **a hand-started `nohup` process
and an uninstalled cron are the same failure**. Every forward-collecting
component needs a supervisor *and* a liveness check that reads its output, not
its process table.

---

## Follow-up, same day: both collectors verified against reality

**Liquidation collector — FIXED and live** (`b82a641`). It had two bugs, and the
second meant it could **never** have written a row: ccxt hands back the inner
order object as `info`, so `parse_force_order`'s `"e" != "forceOrder"` guard
rejected every message — and the trap is that the inner object *does* carry an
`"o"` key meaning order *type* (`"LIMIT"`), not a nested order. Verified live:
**132 rows in 75 s**, against 0 rows in 16 days. Stale process replaced by cron
at 10:35; **zero error lines in a 120 s observation window** where the old
behaviour produced one every ~5 s.

**Deribit chain collector — VERIFIED WORKING, only the schedule is missing.**
Run once into a scratch directory on 2026-07-29: `[collected] appended=842`,
exit 0, valid rows (strike, IV, OI, underlying 63606.81). This matters because
the liquidation collector had just proved that "it ran once in July" is not
evidence a collector works — that one produced a plausible-looking manifest for
16 days while being structurally incapable of writing a row. Deribit is not in
that category. Installing its cron will produce data, not another 26 days of
silence.

**Detection is now automated** (`e51e2eb`): `tools/accrual_check.py` reads each
stream's output and exits non-zero when any is behind. `NO_OUTPUT` is a level
distinct from `STALE`, because a stream that never produced a row cannot be
caught by an age threshold — the shape all three failures took. A regression
test pins the 2026-07-29 scenario.

**Still pending, both human decisions:**

1. **Install the Deribit cron.** Suggested line, matching the tool's own
   docstring: `5 0 * * * cd <repo> && .venv/bin/python
   tools/deribit_chain_collect.py collect >> watch.log 2>&1`. Note that each
   day of delay is **permanently lost** — there is no options-chain archive to
   backfill from.
2. **Rule on the confluence v2.2 20-day gap** before the daemon is restarted:
   document as downtime and continue the clock / restart the clock / void and
   re-register as v2.3.
