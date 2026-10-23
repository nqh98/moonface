# NET_NEW_HIGHS Forward Paper Registration (frozen)

Pre-registers the forward paper continuation for a frozen internal breadth spec that met the forward-candidate verdict on the unopened holdout.

## Frozen spec
- key: `net_new_highs`
- builder: `net_new_highs`
- params: `{'n': 20, 'long_thr': 0.3, 'short_thr': -0.3}`
- exit: `atr_trail` `{'k_trail': 2.0, 'max_bars': 120, 'atr_period': 14}`
- h: `48`

## Validation result
- verdict: `forward_candidate`
- validate expectation: `0.5323`
- sealed expectation: `0.2588`
- pooled expectation: `0.3997`

## Honest caveat
Paper-only. Forward registration does not authorize live capital or modify the frozen breadth registry.
