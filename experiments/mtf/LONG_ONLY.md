# MTF broaden_best — BTCUSDT LONG-ONLY deployment analysis

## Verdict: DOES NOT CLEAR ECON_BAR (DD cap over 30R — sizing failure)

- asof: 2026-07-01T05:00:32.353846+00:00
- data_sha: 7b8ea8ba0826e1b0
- frozen cell: `4h:trend_strength|rsi_reversion|horizon_hold@2d` (LONG trades only — side filter, cell byte-unchanged)
- approx time in market: 33.1% (not always-long; 391 × 2-day holds)

## Long-only vs the L/S whole (single faithful path)

| book | n | pf | exp/trade | win_rate | totalR | maxDD_R | MAR | +ve |
|---|---|---|---|---|---|---|---|---|
| L/S whole full | 731 | 1.24 | +0.897 | 0.501 | +655.6 | -135.61 | 4.8346 | YES |
| LONG-ONLY full | 391 | 1.5725 | +1.942 | 0.560 | +759.2 | -87.53 | 8.6739 | YES |
| LONG-ONLY recent | 121 | 1.4388 | +1.689 | 0.512 | +204.4 | -78.43 | 2.6059 | YES |

Dropping the short book lifts MAR and cuts drawdown: the short leg added drawdown and subtracted return over full history (see CHARACTERIZE.md).

## ECON_BAR check (long-only, full)

`PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

PF 1.5725 PASS | exp 1.9418 PASS | MAR 8.6739 PASS | DD -87.53 FAIL | robust 0.8571 PASS

## Per-year — long-only vs passive buy-and-hold (the beta test)

| year | n | pf | exp/trade | long-only totalR | BTC buy&hold | +ve |
|---|---|---|---|---|---|---|
| 2020 | 74 | 2.1736 | +3.084 | +228.2R | +303% | YES |
| 2021 | 61 | 1.6691 | +2.241 | +136.7R | +61% | YES |
| 2022 | 44 | 0.8185 | -0.765 | -33.6R | -64% | no |
| 2023 | 63 | 2.6452 | +4.060 | +255.8R | +156% | YES |
| 2024 | 64 | 1.3377 | +1.382 | +88.4R | +120% | YES |
| 2025 | 62 | 1.2662 | +1.095 | +67.9R | -6% | YES |
| 2026 | 23 | 1.2275 | +0.691 | +15.9R | -27% | YES |

robust_frac = 0.8571

**Beta test:** long-only was positive in 2 of 3 BTC DOWN years (2022 -34R vs BTC -64%, 2025 +68R vs BTC -6%, 2026 +16R vs BTC -27%). Positive in the shallow down years (2025/2026) but NEGATIVE in the severe 2022 bear (-33.6R vs BTC -64%) — so the long-only book is a long-biased TIMING overlay with real alpha in mild drawdowns, carrying PARTIAL beta that a full-cycle bear overwhelms. Not all-weather; not pure beta either.

## Honest reading

The long-only book is the cleanest-shaped object the lane has produced — it clears 4 of 5 ECON gates (PF 1.57, exp 1.94R, MAR 8.67, robust 0.857 = 6/7 years), better than the L/S basket's 3/5, with lower drawdown and higher MAR than the L/S whole. But three caveats bind: (1) it is a POST-HOC side filter chosen after seeing the short book lose, so on this sample it is selection, not discovery; (2) it is NOT all-weather — it loses in the severe 2022 bear (the short book was that year's hero), so it carries partial long beta; (3) it still fails the 30R fixed-f drawdown cap (the same sizing wall). It clears no new academic gate. Its only legitimate path forward is the frozen forward registration (LONG_ONLY_FORWARD_REGISTRATION.md), which resolves the selection out-of-sample. Paper only; promotes nothing to live.
