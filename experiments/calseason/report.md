# Calseason calendar seasonality verdict

- generated: 2026-06-17T13:07:40.151975+00:00
- **status: closed_negative** - no fixed calendar cell clears the frozen gate
- winner: -
- accepted assets: 16 (skipped: 0)

| cell | m | pooled mean | Stouffer Z | |Z| | same-sign | stable | clears |
|---|---:|---:|---:|---:|---:|---|---|
| funding_pre | 16 | -0.00007454 | -0.815 | 0.815 | 11 | fail | fail |
| funding_post | 16 | -0.00014142 | -0.822 | 0.822 | 11 | PASS | fail |
| weekend | 16 | -0.00019202 | -1.540 | 1.540 | 12 | fail | fail |
| weekday | 16 | -0.00007456 | -0.682 | 0.682 | 7 | fail | fail |

## Time Halves

```json
{
  "funding_pre": {
    "first": {
      "m": 16,
      "pooled_mean": 0.000321213756507708,
      "effect_sign": 1,
      "same_sign": 14,
      "stouffer_z": 1.783285758286715,
      "abs_stouffer_z": 1.783285758286715
    },
    "second": {
      "m": 16,
      "pooled_mean": -0.000470302403212164,
      "effect_sign": -1,
      "same_sign": 15,
      "stouffer_z": -3.352209501799062,
      "abs_stouffer_z": 3.352209501799062
    }
  },
  "funding_post": {
    "first": {
      "m": 16,
      "pooled_mean": -0.00023672445604601858,
      "effect_sign": -1,
      "same_sign": 13,
      "stouffer_z": -1.1116674073829953,
      "abs_stouffer_z": 1.1116674073829953
    },
    "second": {
      "m": 16,
      "pooled_mean": -4.604216384288055e-05,
      "effect_sign": -1,
      "same_sign": 8,
      "stouffer_z": -0.019441945830677324,
      "abs_stouffer_z": 0.019441945830677324
    }
  },
  "weekend": {
    "first": {
      "m": 16,
      "pooled_mean": -0.0004775713371049925,
      "effect_sign": -1,
      "same_sign": 13,
      "stouffer_z": -2.5222413441885694,
      "abs_stouffer_z": 2.5222413441885694
    },
    "second": {
      "m": 16,
      "pooled_mean": 9.430348393934257e-05,
      "effect_sign": 1,
      "same_sign": 10,
      "stouffer_z": 0.5431965364793906,
      "abs_stouffer_z": 0.5431965364793906
    }
  },
  "weekday": {
    "first": {
      "m": 16,
      "pooled_mean": 0.00024922718297001683,
      "effect_sign": 1,
      "same_sign": 13,
      "stouffer_z": 1.74000774537884,
      "abs_stouffer_z": 1.74000774537884
    },
    "second": {
      "m": 16,
      "pooled_mean": -0.0003981525906028604,
      "effect_sign": -1,
      "same_sign": 14,
      "stouffer_z": -3.3105448158185786,
      "abs_stouffer_z": 3.3105448158185786
    }
  }
}
```
