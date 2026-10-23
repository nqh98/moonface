# DESCRIPTIVE DIAGNOSTIC — NOT A GATE, NOT A RESULT

- events supplied: 1838; usable: 1838; UNLABELED at event time: 90
- regime buckets examined: 14 (multiplicity: every bucket below is one implicit comparison)
- null calibration: real effect 0.6092 vs shuffled p95 0.8354 → **INDISTINGUISHABLE_FROM_NULL**

**SELECTION ARTIFACT WARNING:** bucket differences below are consistent with label shuffling; do not interpret.

| bucket | n | fwd_r_12 mean | 95% CI | MFE med | MAE med | P(stop first) | verdict |
|---|---|---|---|---|---|---|---|
| RANGE/HIGH/NEUTRAL | 4 | — | — | — | — | — | INSUFFICIENT_DATA |
| RANGE/LOW/CROWDED_LONG | 3 | — | — | — | — | — | INSUFFICIENT_DATA |
| RANGE/LOW/NEUTRAL | 25 | — | — | — | — | — | INSUFFICIENT_DATA |
| RANGE/MID/CROWDED_LONG | 3 | — | — | — | — | — | INSUFFICIENT_DATA |
| RANGE/MID/NEUTRAL | 20 | — | — | — | — | — | INSUFFICIENT_DATA |
| UP/HIGH/CROWDED_LONG | 121 | -0.0967 | [-0.3413, 0.1574] | 1.5688 | 1.7872 | 0.5289 | DESCRIPTIVE |
| UP/HIGH/CROWDED_SHORT | 16 | — | — | — | — | — | INSUFFICIENT_DATA |
| UP/HIGH/NEUTRAL | 501 | 0.1817 | [0.0197, 0.3479] | 1.4763 | 1.4474 | 0.5233 | DESCRIPTIVE |
| UP/LOW/CROWDED_LONG | 35 | 0.5126 | [0.1799, 0.843] | 3.1834 | 1.5572 | 0.4857 | DESCRIPTIVE |
| UP/LOW/CROWDED_SHORT | 3 | — | — | — | — | — | INSUFFICIENT_DATA |
| UP/LOW/NEUTRAL | 254 | 0.1816 | [-0.0177, 0.3916] | 1.9154 | 1.7742 | 0.4409 | DESCRIPTIVE |
| UP/MID/CROWDED_LONG | 116 | 0.2477 | [-0.1, 0.6694] | 1.8256 | 1.8163 | 0.6 | DESCRIPTIVE |
| UP/MID/CROWDED_SHORT | 16 | — | — | — | — | — | INSUFFICIENT_DATA |
| UP/MID/NEUTRAL | 631 | 0.1908 | [0.0545, 0.3318] | 1.6231 | 1.534 | 0.4595 | DESCRIPTIVE |

Any pattern here requires a separate pre-registered lane before it may influence trading.
