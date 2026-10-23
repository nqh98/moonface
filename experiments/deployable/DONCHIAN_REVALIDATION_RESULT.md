# BTC Donchian Revalidation — BTCUSDT 4h

## Verdict: INCONCLUSIVE / PAPER-SUSPENDED

- asof: 2026-06-20T13:13:13.037054+00:00
- bars: 14175  data_sha: 35e47dd5da9dfafa
- gates: ECON_BAR (PF>=1.2/exp>=0.05R/MAR>=0.5/|maxDD|<=30R/robust>=0.60)

## Reasons

- N=4 robust_frac 0.5 < 0.60 (quantized; see Slice-2)

## Headline non-overlap walk-forward
- windows: 4  wf_pass: True
- expectancy_r 0.4442  PF 1.7543  MAR 4.6755  maxDD -7.7908R  robust_frac 0.5

## Exit ablation (entry fixed: Donchian n=40)
- gross_h12_probe: n=225 z=2.4537 (edge-search reproduction; expect |z|<2)
| arm | n | expectancy_r | PF | MAR | maxDD_R |
|---|---|---|---|---|---|
| net_fixed_horizon_exit | 224 | 0.1001 | 1.2046 | 1.4881 | -15.0728 |
| stop_only | 6 | 27.8225 | 23.2204 | 22.2204 | -7.5127 |
| trail | 133 | 0.6466 | 2.0923 | 5.831 | -14.749 |

## Local parameter plateau (one-axis star around 40/20/2.0/14)
- center expectancy_r 0.6466 PF 2.0923 MAR 5.831
  - entry_n=30,trail_n=20,k_stop=2.0,atr_period=14: exp 0.447 PF 1.7024 MAR 3.4775
  - entry_n=55,trail_n=20,k_stop=2.0,atr_period=14: exp 0.6225 PF 2.0374 MAR 5.5919
  - entry_n=40,trail_n=10,k_stop=2.0,atr_period=14: exp 0.3401 PF 1.6687 MAR 6.2493
  - entry_n=40,trail_n=30,k_stop=2.0,atr_period=14: exp 0.8649 PF 2.2671 MAR 7.18
  - entry_n=40,trail_n=20,k_stop=1.5,atr_period=14: exp 0.857 PF 2.2372 MAR 6.7929
  - entry_n=40,trail_n=20,k_stop=2.5,atr_period=14: exp 0.5499 PF 2.0656 MAR 7.2943
  - entry_n=40,trail_n=20,k_stop=2.0,atr_period=20: exp 0.685 PF 2.1815 MAR 6.2771

## Cost / fill stress
| tier | n | expectancy_r | PF | MAR | maxDD_R | gate |
|---|---|---|---|---|---|---|
| base | 133 | 0.6466 | 2.0923 | 5.831 | -14.749 | econ_pass=True |
| moderate | 132 | 0.6202 | 1.9508 | 4.8363 | -16.9262 | alive=True |
| severe | 132 | 0.4874 | 1.6591 | 3.0098 | -21.3777 | report-only |

## Trade distribution
- n 133 win_rate 0.3534 payoff 3.8284
- top1_contribution 0.3335 exp_drop_top1 0.4342 exp_drop_top5 -0.0098 td_extreme False
- hold_hist {'<3': 8, '<6': 10, '<12': 21, '<24': 29, '<48': 39, '>=48': 26}
- r_hist {'<-1.0': 58, '<0.0': 28, '<1.0': 19, '<2.0': 8, '<5.0': 11, '>=5.0': 9}

## Regime breakdown (point-in-time labels)
- trend/bull: n 97 exp 0.6765 PF 2.1525 total_r 65.6197
- trend/bear: n 33 exp 0.6129 PF 1.9755 total_r 20.2258
- trend/warmup: n 3 exp 0.0522 PF 1.1467 total_r 0.1565
- vol/low: n 76 exp 0.9739 PF 2.5314 total_r 74.0132
- vol/mid: n 41 exp 0.2867 PF 1.5366 total_r 11.7546
- vol/high: n 16 exp 0.0146 PF 1.0276 total_r 0.2342
- rg_flag False  regime_sufficient True

## Honest caveat

Single-asset BTC, paper-only. REAFFIRM means keep on paper, never go live. N=4 windows give a quantized robust_frac; Slice-2's overlapping estimate is the finer read. Point-in-time regime labels still describe one realised 6.5y BTC path.
