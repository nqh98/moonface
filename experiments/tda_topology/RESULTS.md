# tda_topology_v1 — results

Design: `docs/research-log/specs/2026-07-16-tda-topology-design.md`.
Run: `experiments/tda_topology/run.py --cache-dir cache/matrix --events
experiments/microscope/donchian_universe_events.csv --seed 1`, 2026-07-16.

## Verdict

**INDISTINGUISHABLE_FROM_NULL** (primary: block-permutation null, `BLOCK=30`,
`N_SHUFFLES=200`) — real effect **0.6867** vs null p95 **1.0291** (beaten 80%
of shuffles). Persistent homology of the cross-sectional correlation matrix
does **not** stratify the forward-R distribution of the 1838 Donchian events
beyond a null that preserves the label series' time structure.

**Secondary diagnostic (row-wise null, same shape as `microscope`):**
EXCEEDS_NULL — real effect 0.6867 vs null p95 0.4922. The row null ignores
label autocorrelation and is therefore easier to beat. This is the exact
asymmetry spec §3.5 predicted as the reason the block null is primary: had
this study only run the row-wise check (the microscope's method), it would
have looked like a pass. The block null is the harder, correct bar, and this
instrument fails it.

## Head-to-head: Market State Microscope, same 1838 events

| | real effect | null p95 | verdict |
|---|---:|---:|---|
| microscope 5-factor (2026-07-10) | 0.609 | 0.835 | INDISTINGUISHABLE_FROM_NULL |
| tda_topology block null (2026-07-16) | 0.6867 | 1.0291 | INDISTINGUISHABLE_FROM_NULL |

Both instruments land in the same place on the same event set: real effect
comparable in magnitude, both well inside their respective nulls. Topology
sees no more than the microscope's regime factors did.

## Buckets

| label | n | verdict | fwd_r_6 mean | fwd_r_12 mean | fwd_r_42 mean |
|---|---:|---|---:|---:|---:|
| CONCENTRATED/BREAK | 27 | INSUFFICIENT_DATA | - | - | - |
| CONCENTRATED/STABLE | 61 | DESCRIPTIVE | 0.6496 | 0.7953 | 2.2498 |
| DISPERSED/BREAK | 1098 | DESCRIPTIVE | 0.0876 | 0.192 | 0.6448 |
| DISPERSED/STABLE | 545 | DESCRIPTIVE | 0.0638 | 0.1086 | 0.2125 |

1838/1838 events usable, 107 UNLABELED (burn-in), 1215 distinct bars.

**Bucket-size note, recorded not chased.** Spec §3.3 projected roughly 300
bars/bucket from a 4-way median split; the realized split is heavily skewed
toward DISPERSED (1643 of 1731 labeled bars) vs CONCENTRATED (88). The
concentration axis's expanding median evidently sits in a regime where later
history is persistently more dispersed than the early burn-in window that set
the running median — plausible given crypto's falling average cross-asset
correlation over 2020→2026. `CONCENTRATED/BREAK` (n=27) misses `POWER_FLOOR`
and reports size only. This asymmetry does not change the verdict: the two
largest, best-powered buckets (DISPERSED/BREAK and DISPERSED/STABLE, n=1098
and 545) show the smallest spread between them, and the effect is carried by
the small CONCENTRATED/STABLE bucket (n=61) against the DISPERSED buckets —
exactly the kind of small-bucket-driven spread the block null is built to
catch, and did.

## Scope caveat

All 1838 events are **long-only** trend-breakout entries, firing mainly in
UP-ish regimes; RANGE is thin and DOWN is absent in this event source. This
verdict closes the geometric axis **for long trend-breakout entries**, the
same scope the microscope finding already carries. A long+short event source
would be a different lane, not a rescue of this one.

## Decision under spec §7

`INDISTINGUISHABLE_FROM_NULL` → **the geometric axis is closed.** Per the
stop rule: no v2, no re-run at `W=30` or `W=120`, no alternate point-cloud
construction (Takens embedding, Mapper) as a follow-on, no retuning `BLOCK`,
`BURN_IN`, or the label thresholds against this outcome. `W=60` was frozen in
the spec before this run; it is the only verdict, not one of three.

This closes direction 4 (Topological Data Analysis) from
`docs/research-log/concepts/crypto_geometric_signal_research_ai_readable.md`, the last of the
six geometric directions without a prior verdict in this program. See
`docs/findings/BACKLOG.md` for the full six-direction closure mapping.
