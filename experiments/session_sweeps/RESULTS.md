# session_sweeps Registered Results

## Primary registered run (`--mode reversal`)

```text
Session Sweeps - mode=reversal cutoff=2024-07-01
── IN-SAMPLE (descriptive) ──
  signals            : 3348
  hit-rate (4H>0)    : 0.565   [descriptive]
  mean signed  2H    : +0.00022
  mean signed  4H    : +0.00028
  95% CI  2H         : [-0.00013, +0.00055]
  95% CI  4H (GATE)  : [-0.00015, +0.00066]

── SEALED OOS (confirmatory) ──
  signals            : 1517
  hit-rate (4H>0)    : 0.507   [descriptive]
  mean signed  2H    : -0.00028
  mean signed  4H    : -0.00013
  95% CI  2H         : [-0.00069, +0.00008]
  95% CI  4H (GATE)  : [-0.00074, +0.00040]

VERDICT (sealed OOS, 4H CI vs 0): FAIL
```

Primary run summary:

- In-sample signals: `3348`
- Sealed OOS signals: `1517`
- In-sample 2H CI: `[-0.00013, +0.00055]`
- In-sample 4H gate CI: `[-0.00015, +0.00066]`
- OOS 2H CI: `[-0.00069, +0.00008]`
- OOS 4H gate CI: `[-0.00074, +0.00040]`

## Robustness run (`--mode continuation`)

```text
Session Sweeps - mode=continuation cutoff=2024-07-01
── IN-SAMPLE (descriptive) ──
  signals            : 3320
  hit-rate (4H>0)    : 0.420   [descriptive]
  mean signed  2H    : -0.00020
  mean signed  4H    : -0.00054
  95% CI  2H         : [-0.00056, +0.00016]
  95% CI  4H (GATE)  : [-0.00104, -0.00006]

── SEALED OOS (confirmatory) ──
  signals            : 1574
  hit-rate (4H>0)    : 0.449   [descriptive]
  mean signed  2H    : -0.00019
  mean signed  4H    : -0.00027
  95% CI  2H         : [-0.00056, +0.00016]
  95% CI  4H (GATE)  : [-0.00078, +0.00025]

VERDICT (sealed OOS, 4H CI vs 0): FAIL
```

Continuation-mode robustness read:

- In-sample signals: `3320`
- Sealed OOS signals: `1574`
- OOS 2H CI: `[-0.00056, +0.00016]`
- OOS 4H gate CI: `[-0.00078, +0.00025]`

Interpretation:

The registered reversal study is not underpowered, but it does not clear the sealed-OOS gate: the 4H confirmatory CI remains negative-to-positive around zero, so this run is a `FAIL`, not a candidate edge. The continuation variant is also weak out of sample and does not rescue the thesis. On this single sealed look, the prior-session sweep baseline should be treated as not confirmed by this study, with no deployment claim and no upgrade beyond a rejected baseline unless a separately pre-registered follow-on design is proposed.
