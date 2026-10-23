# BREADTH_MOMENTUM Forward Paper Registration (frozen, Lane 2)

Forward continuation for a frozen high-frequency breadth spec that met the forward-candidate verdict on the unopened holdout.

## Frozen spec
- key: `breadth_momentum`  builder: `breadth_momentum`
- params: `{'n': 10, 'thr': 0.1, 'base_period': 50}`  block_len: `8`
- exit: `atr_trail` `{'k_trail': 2.0, 'max_bars': 120, 'atr_period': 14}`  h: `48`

## Validation result
- verdict: `forward_candidate`  pooled exp: `0.1539`
- boot_lo: `-0.06960212730452711`  p_le0: `0.07428`

## Resolution rule
CONFIRM iff forward-only pooled n>=30 AND bootstrap CI lower bound > 0 AND forward-only exp > 0; REFUTE / early-kill at cumulative -30R.

Paper-only. Does not authorize live capital or modify any registry.
