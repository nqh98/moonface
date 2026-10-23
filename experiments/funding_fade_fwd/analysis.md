# funding_fade_fwd — pre-cutoff analysis (drafting input)

- generated: 2026-07-14T02:44:24.153147+00:00
- research n=254 mu=0.2549R sigma=2.8622R; tail n=68
- trades/year 108.46; 12-month horizon = 108 trades
- history: cum-min -15.2572R, max peak-DD -32.0R (research-only -32.0R), longest TUW 287.2d
- expectancy 95% CI: research (-0.170303937007874, 0.6630897637795276), tail (0.38235294117647056, 1.9664632352941178)

| budget R | capital at risk (f=0.01) | P(ruin, measured) | P(ruin, zero-edge) | P(ruin, peak-rel) |
|---|---|---|---|---|
| -40.0 | 40.0% | 0.0373 | 0.2755 | 0.1245 |
| -50.0 | 50.0% | 0.0152 | 0.1698 | 0.0454 |
| -64.0 | 64.0% | 0.0038 | 0.0799 | 0.0088 |

Verdict-trigger N (95% CI excludes 0): power 0.5 -> 485 trades; power 0.8 -> 990 trades; calendar floor 12 months. Later-of semantics; the human chooses the power level and budget at sign-off.
