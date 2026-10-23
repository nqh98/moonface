# funding_fade_fwd — Observation Notes (non-gating)

## 2026-07-14 — Random-entry bracket return in the tail window

During the Escalation-2 null diagnostic (100 funding-shuffle nulls, frozen
pipeline, pre-cutoff data), random-time entries with the frozen
`fixed_bracket {k_stop: 2.0, m_tp: 4.0}` exit earned a mean **+25.97R net
(+0.32R/trade, median +26.96R)** over the OOS-tail analogue window
(~2025-12 → 2026-06). The asymmetric bracket harvests regime drift at
random entries in that window.

This is an observation, NOT a lane. Unconditional bracket-holding of drift
is the core program's closed drawdown-wall question
(`experiments/PROGRAM_CONCLUSION.md`, "The single replicated finding":
positive drift exists but no bounded-risk exit harvests it within an
acceptable drawdown budget — the null paths here inherit the same
peak-relative drawdown behavior, cf. the analysis table's peak-relative
ruin probabilities). Recorded per the Escalation-2 ruling, condition 5.
