# vol_compression Registered Results

**Verdict: gate fired `PASS` but the PASS is a VOID false positive — the lane is CLOSED
NEGATIVE (no genuine edge).** The pre-registered gate, as designed, does not isolate the
hypothesized effect; a null calibration proves the "PASS" is a selection-bias artifact.

## Primary registered run (`--feature rv`)

```text
Vol Compression -> Expansion — feature=rv cutoff=2024-07-01
── IN-SAMPLE (descriptive) ──
  signals            : 612
  win-rate (1d net>0): 0.546   [descriptive]
  mean net  1d       : +0.007134
  mean net  2d       : +0.012154
  95% CI 2d          : [+0.009699, +0.014560]
  95% CI 1d (GATE)   : [+0.005476, +0.008771]

── SEALED OOS (confirmatory) ──
  signals            : 249
  win-rate (1d net>0): 0.544   [descriptive]
  mean net  1d       : +0.004741
  mean net  2d       : +0.009193
  95% CI 2d          : [+0.006266, +0.011194]
  95% CI 1d (GATE)   : [+0.003139, +0.006386]

VERDICT (sealed OOS, 1d net CI vs 0): PASS
```

## Why the PASS is VOID — null calibration

The premium is priced off `RV_24` measured **at the compressed bar**, which is *low by
selection* (bottom-20th-percentile vol). The forward `|move|` is over the next 24h. Because
realized vol mean-reverts, forward vol exceeds the depressed trailing vol, so `|move|` beats
the premium **almost by construction — even with no compression→expansion effect at all.**
A real straddle is priced off forward-looking implied vol, not depressed trailing realized
vol; using the selection-depressed estimator reintroduces the exact tautology the design
claimed to avoid (DESIGN §0), only hidden inside the estimator.

**Diagnostic (synthetic, does not touch sealed data):** run the frozen `rv` pipeline on iid
Gaussian returns with CONSTANT vol (no expansion effect exists by construction), n≈56k:

```text
NULL (iid constant-vol) — frozen rv config:
  n_signals   : 1056
  mean net 1d : +0.006817
  95% CI 1d   : [+0.005138, +0.008625]
  VERDICT     : PASS
```

The null "PASSes" and its artifact mean (+0.006817) is **larger** than the real BTC OOS
(+0.004741). So:
- The gate is invalid: it fires PASS where no effect can exist.
- Using the null as its own control, BTC real (+0.0047) is **below** the iid artifact
  (+0.0068) → BTC shows *less* forward expansion after a squeeze than random noise. No
  positive edge; if anything a slight negative tilt vs. the null.

## Robustness run (`--feature atr`) — also FAIL

```text
── SEALED OOS (confirmatory) ──
  signals            : 216
  win-rate (1d net>0): 0.330
  mean net  1d       : -0.004050
  95% CI 1d (GATE)   : [-0.005248, -0.003162]
VERDICT: FAIL
```

The ATR variant fails (significantly negative). ATR/close is an average-absolute-range
measure on a different scale than the std-of-log-returns the premium formula assumes, so the
premium is mis-scaled — a second, independent sign that the premium/estimator, not a real
expansion edge, drives the numbers. The two features disagreeing in sign is itself a red
flag against a genuine structural effect.

## Interpretation

The direction-agnostic compression→expansion premise is **not supported**. The sealed gate
returned PASS, but a pre-committed-logic null calibration shows that PASS is a selection-bias
artifact of pricing the straddle off the compressed (downward-selected) trailing vol; the
real BTC payoff is actually *weaker* than the iid-null artifact, and the ATR variant is
outright negative. This is a **design failure caught post-run** — the honest reading is
**no genuine edge**, lane CLOSED NEGATIVE.

The seal is spent. A *valid* future test would need a **separately pre-registered** follow-on
on a fresh seal with a corrected premium — priced off a forward-neutral / long-run vol
estimate (not the selection-depressed trailing vol), or scored as a difference-in-differences
against the iid-null artifact — rather than any retune of this spent window. No deployment
claim; no upgrade from a rejected baseline.
