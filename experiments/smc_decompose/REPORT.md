# SMC failure decomposition — RESEARCH-ONLY

> Diagnostic, not a strategy. No edge is claimed; the WAIT stance and
> `docs/findings/PROGRAM_CONCLUSION.md` are unchanged. Single-asset BTC
> mechanism check (within-BTC sign test + bootstrap 95% CI on mean_ret_r),
> not a promotion gate.

## BTC/USDT:USDT 1h  (bars=56800)

| variant | params | h | n | win_rate | mean_ret_r | ci95 |
|---|---|---|---|---|---|---|
| full_reversal | {"lookback": 10} | 6 | 1069 | 0.50 | 0.190 | [0.061, 0.320] |
| full_reversal | {"lookback": 10} | 12 | 1069 | 0.48 | 0.225 | [0.040, 0.414] |
| full_reversal | {"lookback": 10} | 18 | 1069 | 0.48 | 0.322 | [0.096, 0.553] |
| full_reversal | {"lookback": 10} | 30 | 1069 | 0.48 | 0.419 | [0.101, 0.747] |
| full_reversal | {"lookback": 30} | 6 | 1056 | 0.49 | 0.175 | [0.046, 0.305] |
| full_reversal | {"lookback": 30} | 12 | 1056 | 0.48 | 0.200 | [0.014, 0.391] |
| full_reversal | {"lookback": 30} | 18 | 1056 | 0.47 | 0.293 | [0.060, 0.524] |
| full_reversal | {"lookback": 30} | 30 | 1056 | 0.48 | 0.384 | [0.057, 0.712] |
| flip | {"lookback": 10} | 6 | 1069 | 0.50 | -0.190 | [-0.320, -0.060] |
| flip | {"lookback": 10} | 12 | 1069 | 0.52 | -0.225 | [-0.414, -0.040] |
| flip | {"lookback": 10} | 18 | 1069 | 0.52 | -0.322 | [-0.553, -0.096] |
| flip | {"lookback": 10} | 30 | 1069 | 0.52 | -0.419 | [-0.747, -0.101] |
| flip | {"lookback": 30} | 6 | 1056 | 0.51 | -0.175 | [-0.305, -0.046] |
| flip | {"lookback": 30} | 12 | 1056 | 0.52 | -0.200 | [-0.390, -0.014] |
| flip | {"lookback": 30} | 18 | 1056 | 0.53 | -0.293 | [-0.524, -0.060] |
| flip | {"lookback": 30} | 30 | 1056 | 0.52 | -0.384 | [-0.712, -0.057] |
| sweep_only | {"lookback": 10} | 6 | 4728 | 0.49 | -0.027 | [-0.084, 0.029] |
| sweep_only | {"lookback": 10} | 12 | 4727 | 0.50 | -0.042 | [-0.124, 0.038] |
| sweep_only | {"lookback": 10} | 18 | 4727 | 0.49 | -0.113 | [-0.214, -0.015] |
| sweep_only | {"lookback": 10} | 30 | 4726 | 0.50 | -0.064 | [-0.203, 0.074] |
| sweep_only | {"lookback": 30} | 6 | 4728 | 0.49 | -0.040 | [-0.099, 0.020] |
| sweep_only | {"lookback": 30} | 12 | 4728 | 0.49 | -0.084 | [-0.167, -0.001] |
| sweep_only | {"lookback": 30} | 18 | 4727 | 0.49 | -0.130 | [-0.234, -0.027] |
| sweep_only | {"lookback": 30} | 30 | 4726 | 0.50 | -0.094 | [-0.237, 0.047] |
| choch_only | {} | 6 | 1860 | 0.47 | 0.098 | [-0.011, 0.206] |
| choch_only | {} | 12 | 1860 | 0.47 | 0.080 | [-0.068, 0.229] |
| choch_only | {} | 18 | 1860 | 0.48 | 0.216 | [0.033, 0.397] |
| choch_only | {} | 30 | 1860 | 0.46 | 0.291 | [0.042, 0.538] |
| structure_bias | {"n_periods": 5} | 6 | 1814 | 0.48 | -0.019 | [-0.106, 0.067] |
| structure_bias | {"n_periods": 5} | 12 | 1813 | 0.48 | 0.053 | [-0.069, 0.177] |
| structure_bias | {"n_periods": 5} | 18 | 1813 | 0.50 | -0.010 | [-0.164, 0.144] |
| structure_bias | {"n_periods": 5} | 30 | 1812 | 0.49 | -0.006 | [-0.219, 0.208] |

## BTC/USDT:USDT 4h  (bars=14200)

| variant | params | h | n | win_rate | mean_ret_r | ci95 |
|---|---|---|---|---|---|---|
| full_reversal | {"lookback": 10} | 6 | 272 | 0.53 | 0.352 | [0.051, 0.663] |
| full_reversal | {"lookback": 10} | 12 | 272 | 0.54 | 0.552 | [0.154, 0.960] |
| full_reversal | {"lookback": 10} | 18 | 272 | 0.51 | 0.552 | [0.071, 1.041] |
| full_reversal | {"lookback": 10} | 30 | 272 | 0.49 | 0.582 | [-0.050, 1.242] |
| full_reversal | {"lookback": 30} | 6 | 270 | 0.54 | 0.357 | [0.048, 0.674] |
| full_reversal | {"lookback": 30} | 12 | 270 | 0.54 | 0.559 | [0.158, 0.970] |
| full_reversal | {"lookback": 30} | 18 | 270 | 0.51 | 0.559 | [0.068, 1.055] |
| full_reversal | {"lookback": 30} | 30 | 270 | 0.49 | 0.590 | [-0.043, 1.256] |
| flip | {"lookback": 10} | 6 | 272 | 0.47 | -0.352 | [-0.663, -0.051] |
| flip | {"lookback": 10} | 12 | 272 | 0.46 | -0.552 | [-0.959, -0.154] |
| flip | {"lookback": 10} | 18 | 272 | 0.49 | -0.552 | [-1.041, -0.071] |
| flip | {"lookback": 10} | 30 | 272 | 0.51 | -0.582 | [-1.242, 0.050] |
| flip | {"lookback": 30} | 6 | 270 | 0.46 | -0.357 | [-0.674, -0.047] |
| flip | {"lookback": 30} | 12 | 270 | 0.46 | -0.559 | [-0.970, -0.158] |
| flip | {"lookback": 30} | 18 | 270 | 0.49 | -0.559 | [-1.055, -0.068] |
| flip | {"lookback": 30} | 30 | 270 | 0.51 | -0.590 | [-1.255, 0.044] |
| sweep_only | {"lookback": 10} | 6 | 1178 | 0.49 | 0.004 | [-0.102, 0.111] |
| sweep_only | {"lookback": 10} | 12 | 1178 | 0.51 | 0.027 | [-0.134, 0.188] |
| sweep_only | {"lookback": 10} | 18 | 1177 | 0.51 | 0.058 | [-0.144, 0.259] |
| sweep_only | {"lookback": 10} | 30 | 1176 | 0.48 | -0.130 | [-0.409, 0.154] |
| sweep_only | {"lookback": 30} | 6 | 1178 | 0.49 | -0.002 | [-0.109, 0.106] |
| sweep_only | {"lookback": 30} | 12 | 1178 | 0.50 | 0.012 | [-0.150, 0.171] |
| sweep_only | {"lookback": 30} | 18 | 1177 | 0.50 | 0.029 | [-0.175, 0.230] |
| sweep_only | {"lookback": 30} | 30 | 1176 | 0.48 | -0.132 | [-0.413, 0.151] |
| choch_only | {} | 6 | 492 | 0.53 | 0.371 | [0.148, 0.601] |
| choch_only | {} | 12 | 491 | 0.51 | 0.378 | [0.077, 0.685] |
| choch_only | {} | 18 | 491 | 0.50 | 0.416 | [0.050, 0.792] |
| choch_only | {} | 30 | 491 | 0.52 | 0.661 | [0.161, 1.165] |
| structure_bias | {"n_periods": 5} | 6 | 458 | 0.45 | -0.040 | [-0.212, 0.135] |
| structure_bias | {"n_periods": 5} | 12 | 458 | 0.47 | -0.035 | [-0.290, 0.223] |
| structure_bias | {"n_periods": 5} | 18 | 458 | 0.49 | 0.039 | [-0.290, 0.363] |
| structure_bias | {"n_periods": 5} | 30 | 458 | 0.52 | 0.283 | [-0.114, 0.684] |

---

## Findings (interpretation)

**Framing.** All numbers above are *exit-free* path stats with a single-asset
(within-BTC) bootstrap 95% CI on `mean_ret_r`. There is **no multiple-testing
correction** across variants × timeframes × horizons × slices, so this is a
mechanism check, **not a promotion gate**. The advisor stays falsified on the
full exit + cost basis used in `docs/findings/PROGRAM_CONCLUSION.md`; the WAIT
stance is unchanged. Treat any single "CI excludes zero" below as suggestive,
not actionable.

**Internal consistency.** `flip` is constructed as the exact side-inverse of
`full_reversal` at identical indices, and the table reflects that: every `flip`
cell is the signed negative of its `full_reversal` counterpart (e.g. 1h
lookback=10, h=12: `+0.225` vs `−0.225`). This confirms the machinery, not an
independent signal.

**Where the directional drift lives.** Exit-free, the reversal direction shows
positive forward drift with CIs excluding zero on **both** timeframes — and it
isolates cleanly to one component:

- `choch_only` and `full_reversal` both carry the positive drift (1h and 4h);
  the CHoCH + displacement leg is the active ingredient.
- `sweep_only` is flat (CI straddles 0) — the liquidity-sweep precondition
  **adds no directional information on its own**.
- `structure_bias` is flat everywhere — the HTF trend filter contributes
  nothing standalone.

**Conditional caveats** (consistent across `full_reversal` and `choch_only`;
read from the `slices` blocks in the JSON):

- **High-ATR regime kills it.** `full_reversal` 1h h=12: mid-tercile `+0.47r` →
  high-tercile `−0.02r`. CHoCH displacement in high volatility reads as noise.
- **Recency-concentrated.** `full_reversal` 1h h=12: first half `+0.08r`, second
  half `+0.37r` — a stationarity yellow flag, not a stable constant.
- **Trending > neutral for CHoCH.** `choch_only` 4h h=12: BULLISH `+0.62r`,
  BEARISH `+0.70r`, NEUTRAL `+0.00r` — a break of structure means something in a
  trend and nothing in a range, as it should.

**Bottom line.** The decomposition explains *how* the SMC reversal works
mechanistically: the exit-free, uncorrected drift is the CHoCH/displacement leg,
annulled in high volatility and uneven across the sample. It does **not**
resurrect the advisor. Per the plan's honesty guard, the only legitimate
follow-up to any sub-slice drift is a separately pre-registered,
multiplicity-corrected probe — never a promotion.

