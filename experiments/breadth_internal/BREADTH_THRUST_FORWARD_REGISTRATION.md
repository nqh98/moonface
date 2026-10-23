# BREADTH_THRUST Forward Paper Registration (frozen)

Pre-registers the forward paper continuation for a frozen internal breadth spec that met the forward-candidate verdict on the unopened holdout.

## Frozen spec
- key: `breadth_thrust`
- builder: `breadth_thrust`
- params: `{'base_period': 50, 'low_band': 0.4, 'high_band': 0.6, 'window': 6}`
- exit: `atr_trail` `{'k_trail': 2.0, 'max_bars': 120, 'atr_period': 14}`
- h: `48`

## Validation result
- verdict: `forward_candidate`
- validate expectation: `0.2147`
- sealed expectation: `0.2121`
- pooled expectation: `0.2132`

## Honest caveat
Paper-only. Forward registration does not authorize live capital or modify the frozen breadth registry.
