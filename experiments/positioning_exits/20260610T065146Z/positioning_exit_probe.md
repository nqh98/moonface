# MoonFace Positioning-Entry Exit Probe

- generated: 2026-06-10T06:51:46.862739+00:00
- timeframe: 4h
- spot symbol: BTC/USDT
- perp symbol: BTC/USDT:USDT
- rows scored: 30

| entry | entry params | exit | exit params | rsch trades | rsch net R | rsch exp | rsch maxDD R | OOS trades | OOS net R | OOS exp | valid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| funding_fade | {'window': 60, 'z_thr': 1.5} | horizon_hold | {'n_bars': 48, 'atr_period': 14} | 254 | -57.7073 | -0.2272 | -114.0369 | 68 | 111.0237 | 1.6327 | False |
| funding_fade | {'window': 60, 'z_thr': 1.5} | fixed_bracket | {'k_stop': 2.0, 'm_tp': 4.0, 'atr_period': 14} | 254 | 64.7507 | 0.2549 | -32.0 | 68 | 76.7285 | 1.1284 | False |
| funding_fade | {'window': 60, 'z_thr': 1.5} | atr_trail | {'k_trail': 3.0, 'max_bars': 48, 'atr_period': 14} | 254 | 93.3356 | 0.3675 | -33.0619 | 68 | 74.1983 | 1.0912 | False |
| funding_fade | {'window': 60, 'z_thr': 1.5} | horizon_hold | {'n_bars': 24, 'atr_period': 14} | 254 | 18.0577 | 0.0711 | -73.3621 | 68 | 52.7523 | 0.7758 | False |
| funding_fade | {'window': 60, 'z_thr': 1.5} | fixed_bracket | {'k_stop': 1.0, 'm_tp': 4.0, 'atr_period': 14} | 254 | 46.0647 | 0.1814 | -18.0 | 68 | 48.4305 | 0.7122 | False |
| basis_discount | {'window': 60, 'pct': 5} | horizon_hold | {'n_bars': 48, 'atr_period': 14} | 539 | 124.5456 | 0.2311 | -225.0443 | 102 | 60.9694 | 0.5977 | False |
| basis_discount | {'window': 180, 'pct': 5} | horizon_hold | {'n_bars': 24, 'atr_period': 14} | 490 | 148.5259 | 0.3031 | -96.8794 | 97 | 36.5891 | 0.3772 | False |
| funding_fade | {'window': 60, 'z_thr': 1.5} | horizon_wide_stop | {'n_bars': 24, 'k_stop': 3.0, 'atr_period': 14} | 254 | 94.0086 | 0.3701 | -54.4143 | 68 | 25.4611 | 0.3744 | False |
| funding_fade | {'window': 60, 'z_thr': 1.5} | horizon_wide_stop | {'n_bars': 24, 'k_stop': 2.5, 'atr_period': 14} | 254 | 111.8359 | 0.4403 | -44.939 | 68 | 24.4855 | 0.3601 | False |
| basis_discount | {'window': 180, 'pct': 5} | horizon_hold | {'n_bars': 48, 'atr_period': 14} | 490 | 85.0142 | 0.1735 | -277.0201 | 97 | 32.789 | 0.338 | False |
| basis_discount | {'window': 60, 'pct': 5} | horizon_hold | {'n_bars': 24, 'atr_period': 14} | 539 | 62.2107 | 0.1154 | -131.3262 | 102 | 33.0456 | 0.324 | False |
| basis_discount | {'window': 180, 'pct': 5} | horizon_wide_stop | {'n_bars': 24, 'k_stop': 2.5, 'atr_period': 14} | 490 | 215.624 | 0.44 | -41.9468 | 97 | 30.3146 | 0.3125 | False |
| basis_discount | {'window': 180, 'pct': 5} | horizon_wide_stop | {'n_bars': 24, 'k_stop': 3.0, 'atr_period': 14} | 490 | 236.5637 | 0.4828 | -53.8882 | 97 | 27.3703 | 0.2822 | False |
| basis_discount | {'window': 60, 'pct': 5} | horizon_wide_stop | {'n_bars': 24, 'k_stop': 2.5, 'atr_period': 14} | 539 | 124.1033 | 0.2302 | -83.2103 | 102 | 27.7286 | 0.2718 | False |
| basis_discount | {'window': 60, 'pct': 5} | fixed_bracket | {'k_stop': 2.0, 'm_tp': 4.0, 'atr_period': 14} | 539 | 112.5539 | 0.2088 | -61.507 | 102 | 26.1264 | 0.2561 | False |
| basis_discount | {'window': 60, 'pct': 5} | horizon_wide_stop | {'n_bars': 24, 'k_stop': 3.0, 'atr_period': 14} | 539 | 165.7082 | 0.3074 | -68.5298 | 102 | 22.2843 | 0.2185 | False |
| funding_fade | {'window': 60, 'z_thr': 1.5} | breakeven_horizon | {'n_bars': 24, 'k_stop': 3.0, 'atr_period': 14} | 254 | 103.008 | 0.4055 | -40.8767 | 68 | 14.2052 | 0.2089 | False |
| funding_fade | {'window': 60, 'z_thr': 1.5} | horizon_hold | {'n_bars': 12, 'atr_period': 14} | 254 | 31.7564 | 0.125 | -39.6846 | 68 | 11.5087 | 0.1692 | False |
| basis_discount | {'window': 60, 'pct': 5} | fixed_bracket | {'k_stop': 1.0, 'm_tp': 4.0, 'atr_period': 14} | 539 | 112.018 | 0.2078 | -36.0 | 102 | 12.7579 | 0.1251 | False |
| basis_discount | {'window': 60, 'pct': 5} | breakeven_horizon | {'n_bars': 24, 'k_stop': 3.0, 'atr_period': 14} | 539 | 161.2476 | 0.2992 | -46.9428 | 102 | 8.4482 | 0.0828 | False |
| basis_discount | {'window': 60, 'pct': 5} | atr_trail | {'k_trail': 3.0, 'max_bars': 48, 'atr_period': 14} | 539 | 156.2295 | 0.2899 | -54.7034 | 102 | 7.4162 | 0.0727 | False |
| basis_discount | {'window': 180, 'pct': 5} | fixed_bracket | {'k_stop': 1.0, 'm_tp': 4.0, 'atr_period': 14} | 490 | 130.6456 | 0.2666 | -24.0 | 97 | 6.7365 | 0.0694 | False |
| basis_discount | {'window': 180, 'pct': 5} | breakeven_horizon | {'n_bars': 24, 'k_stop': 3.0, 'atr_period': 14} | 490 | 165.9153 | 0.3386 | -47.5944 | 97 | 6.6751 | 0.0688 | False |
| basis_discount | {'window': 180, 'pct': 5} | fixed_bracket | {'k_stop': 2.0, 'm_tp': 4.0, 'atr_period': 14} | 490 | 145.7614 | 0.2975 | -52.0 | 97 | 5.105 | 0.0526 | False |
| funding_fade | {'window': 60, 'z_thr': 1.5} | atr_trail | {'k_trail': 2.0, 'max_bars': 48, 'atr_period': 14} | 254 | 52.8073 | 0.2079 | -29.8088 | 68 | 1.6618 | 0.0244 | False |
| basis_discount | {'window': 180, 'pct': 5} | atr_trail | {'k_trail': 3.0, 'max_bars': 48, 'atr_period': 14} | 490 | 246.125 | 0.5023 | -52.1447 | 97 | -0.7341 | -0.0076 | False |
| basis_discount | {'window': 180, 'pct': 5} | horizon_hold | {'n_bars': 12, 'atr_period': 14} | 490 | 63.8832 | 0.1304 | -61.5847 | 97 | -8.2698 | -0.0853 | False |
| basis_discount | {'window': 60, 'pct': 5} | horizon_hold | {'n_bars': 12, 'atr_period': 14} | 539 | 38.1994 | 0.0709 | -66.9893 | 102 | -16.4202 | -0.161 | False |
| basis_discount | {'window': 60, 'pct': 5} | atr_trail | {'k_trail': 2.0, 'max_bars': 48, 'atr_period': 14} | 539 | 125.3695 | 0.2326 | -59.8448 | 102 | -21.3428 | -0.2092 | False |
| basis_discount | {'window': 180, 'pct': 5} | atr_trail | {'k_trail': 2.0, 'max_bars': 48, 'atr_period': 14} | 490 | 157.0781 | 0.3206 | -53.8038 | 97 | -26.1202 | -0.2693 | False |

## Verdict

- **Outcome A** (no robust survivor; drift unharvestable by fixed exits)
