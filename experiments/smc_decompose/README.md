# SMC failure decomposition — RESEARCH-ONLY

Re-examination of the falsified SMC advisor (PROGRAM_CONCLUSION cycles 1–2) via
component decomposition, run on the cached 6.5y BTC 1h series (56,800 bars; 4h
derived, 14,200 bars). Exit-free path stats + single-asset bootstrap CI; no
promotion, no edge claim.

## Artifacts

- `REPORT.md` — generated headline tables (variant × horizon) **plus a Findings
  section** interpreting them.
- `results_{1h,4h}.json` — raw per-variant × horizon documents, plus the
  conditional `slices` (structure / side / atr_tercile / first-second half).

## Findings (summary)

All stats are **exit-free**, single-asset (within-BTC), and **uncorrected** for
the ~5 × 2 × 4 × 12 looks — a mechanism check, **not a promotion gate**. The
advisor stays falsified; the WAIT stance is unchanged.

- **Mechanism:** the directional drift lives in the **CHoCH/displacement leg**
  (`choch_only`, `full_reversal`). The **sweep precondition** (`sweep_only`) and
  the **HTF structure filter** (`structure_bias`) are each flat standalone.
- **Consistency check:** `flip` is the exact side-inverse of `full_reversal`
  (every cell the signed negative) — confirms the math, not an independent edge.
- **Conditional caveats:** drift is **annulled in the high-ATR tercile**,
  **concentrated in the recent half** (stationarity flag), and for `choch_only`
  present only in **trending structure** (flat in NEUTRAL).

See `REPORT.md` for the full tables and interpretation. Verdict language is
consistent with `docs/findings/PROGRAM_CONCLUSION.md`: any sub-slice drift
warrants a separately pre-registered, multiplicity-corrected probe — never a
promotion.
