# forced_flow — Stage 0 Feasibility + Overlap Audit

- **Date:** 2026-07-13
- **Status of lane:** Stage 0 executed per the draft pre-registration (§1). **No registration
  frozen, no Gate-0/Gate-1 code written, no lockbox opened, no sealed data touched.**
- **Verdict (bottom line):** **Liquidation axis BLOCKED** under the pre-committed Stage-0 kill
  rule (historical depth for the registered instrument = 0 months; forward collector history =
  **0 days — the collector authorized 2026-07-09 was never started**). The funding-bleed axis is
  data-feasible but **fails the §0 overlap audit as a standalone axis**. The lane as drafted
  cannot proceed; see "Disposition" for the two honest options.

---

## Overlap audit (§0 of the draft)

**Axis L (liquidation imbalance): CLEAR — 0% overlap with any falsified null.**
Real liquidation prints have never entered any prior lane:

- `lane1_twap` (CLOSED NEGATIVE 2026-07-09) tested only a **candle-derived proxy** and its kill
  rule explicitly permits Track B (real prints) under a NEW pre-registration.
- `liqladder` / `liqrev` used **OI**, not liquidation prints.
- `forced_error` Setup 3 (liquidation absorption) was **DEFERRED**, never tested.
- The microscope/sse axes contain no liquidation input.

**Axis F (funding bleed = funding_rate × OI): FAILS the audit as a stratification axis
(estimated overlap ≥50% in mechanism-space).** The functional form (dollar bleed magnitude) is
new, but the inputs and the exact question — *does forward-R stratify by a funding/OI-derived
descriptive state?* — are the already-falsified pattern:

- **microscope** (1838 events): crowding axis = mean(`funding_z`, `oi_chg_z`) — forward-R does
  NOT stratify; INDISTINGUISHABLE_FROM_NULL, robustness-checked.
- **sse** Track L control carried a crowding coordinate; both cells CLOSED at Gate 0.
- **regime_moe trial 3**: FUNDING expert never selected; OI expert weight real but CI straddles
  0 → CLOSED_NEGATIVE_VALIDATION.
- `price_oi_divergence`, `oibuild` ("mechanism does not exist"), and the funding-rate cycles all
  died on these inputs.

Since OI varies slowly relative to funding, funding×OI is close to a monotone rescaling of the
funding-rate axis — a state feature the program has stratified on repeatedly and found null.
Per the draft's own clause ("≥50% overlap with a falsified lane → registration void"), a
**reduced single-axis-F design is void** unless a human overrules the audit with a genuinely
distinct mechanism argument. The two-axis design's novelty rests entirely on Axis L.

---

## Q1 — Historical liquidation prints, keyless (probed 2026-07-13)

| Source | Keyless | Depth | Granularity | Verdict |
|---|---|---|---|---|
| Binance `GET /fapi/v1/forceOrders` | **NO** — returns `-2014 API-key format invalid`; USER_DATA endpoint (own orders only even with a key) | — | — | DEAD |
| Binance `GET /fapi/v1/allForceOrders` | Endpoint **removed** (April 2021); returns an HTML error page | — | — | DEAD |
| Binance Vision **USDT-M** (`data/futures/um/daily/` and `monthly/`) | yes | **No liquidationSnapshot data type exists** (probed both trees) | — | DEAD — confirms the 2026-07-08 memo for USDT-M |
| Binance Vision **COIN-M** `cm/daily/liquidationSnapshot/BTCUSD_PERP/` | **YES** | **2023-06-25 → 2024-10-14** (472 files / 478-day span, coverage 0.987, 6 missing days) — **archive FROZEN, stopped updating 2024-10-14** | per-order fills, ms timestamps (`time,side,order_type,…,average_price,last_fill_quantity,accumulated_fill_quantity`) | EXISTS but see caveats below |
| Bybit v5 REST | No liquidation-history endpoint exists (`/v5/market/recent-liq`, `/v5/market/liquidation` both empty/404); `public.bybit.com` has no liquidation directory | — | — | DEAD (WS-only, forward) |
| OKX `GET /api/v5/public/liquidation-orders` | yes | **Recent-only** (returns current liquidations; no deep history paging) | — | DEAD for history |
| Aggregators (Coinglass) | **NO** — `"API key missing"` hard wall, as predicted (ETF-flow pattern) | — | — | DEAD |

**COIN-M archive caveats (why it does not unblock Axis L):**

1. **Wrong instrument.** It covers the inverse COIN-M `BTCUSD_PERP`, not the registered USDT-M
   `BTCUSDT` (Q1's pre-committed scope: "BTCUSDT minimum"). The liquidated population (coin-margined
   inverse traders) is materially different from the USDT-M perp crowd the whole program models.
2. **Frozen 21 months stale.** Ends 2024-10-14. The frozen design's lockbox ("most recent 12
   months at freeze") is **unsatisfiable** — the axis has no data in the sealed window at all —
   and the era-stability requirement (≥2 of 3 eras independently) is likewise unsatisfiable on a
   15.7-month slice inside a single era.
3. **Throttle-sampled even historically.** The sample day 2024-08-05 (the most violent cascade
   day of 2024) contains only 1,905 rows (with visible duplicate lines) — consistent with the
   archived stream being the same 1-order/sec-throttled `forceOrder` feed. Cascade *magnitude*
   is undercounted in the archive exactly as in forward collection.

## Q2 — Forward liquidation stream

**The collector has NEVER run.** `tools/liquidation_collect.py` +
`moonface/research/exogenous/liquidation_feed.py` shipped 2026-07-09, but:

- output dir `experiments/newdata/liquidations/` does not exist; no `liq_*.csv` anywhere in repo;
- no crontab entry; no running process; zero matching lines in `watch.log`.

Cron was declared **human ops** in `experiments/newdata/FREE_DATA_FEASIBILITY_liquidations.md`
and was never installed. Forward history = **0 days** against the readiness gate of ≥180 days,
≥200 cascade clusters, coverage ≥0.90. If started today (2026-07-13), earliest readiness is
**~2027-01-09** — coinciding with the Deribit chain-collector readiness.

## Q3 — Funding × OI history

**PASS.**

- Funding: `cache/matrix/funding_BTC_USDT_USDT.csv` — 2020-01-01 → 2026-06-30, 8h intervals,
  7,119 rows; 17-symbol universe cached.
- OI: `cache/matrix/metrics_BTCUSDT.csv` (Binance Vision 5-min metrics) — 2020-09-01 →
  2026-07-02, 688k rows, `sum_open_interest` + `sum_open_interest_value`; 17-symbol universe.
- Alignment: 8h funding onto 1h/4h bars is the already-solved pattern from prior lanes.

## Stage-0 kill rule (pre-committed in the draft, §1)

> If historical liquidation depth < 12 months at ≤1h granularity AND forward collector history
> < 90 days → the liquidation axis is **BLOCKED**.

- Historical depth on the registered instrument (BTCUSDT): **0 months** (< 12). The COIN-M
  archive is ≥12 months but is out of the pre-committed Q1 scope and cannot satisfy the frozen
  design's lockbox or era requirements (caveats 1–2 above).
- Forward collector history: **0 days** (< 90).

**→ Axis L BLOCKED. Rule fired.**

## Disposition (per the draft's own pre-commitments)

The lane as registered **cannot be frozen**. The two permitted continuations:

1. **WAIT for forward accrual** (the honest default): start the liquidation collector NOW —
   it was already authorized as human ops on 2026-07-08/09 and simply never installed:

   ```
   * * * * * pgrep -f liquidation_collect || (cd <repo> && \
       .venv/bin/python tools/liquidation_collect.py --out \
       experiments/newdata/liquidations collect >> watch.log 2>&1 &)
   ```

   Revisit at the existing readiness gate (~2027-01 earliest). Any Axis-L feature must be robust
   to the throttle (cluster presence/direction/imbalance, not summed notional).
2. **Re-register as reduced single-axis (funding-bleed) design** — but this **fails the §0
   overlap audit** (see above) and is void under the draft's own clause unless a human overrules
   with a distinct mechanism argument. Not recommended.

A third option exists but is a **different lane, human decision required**: a COIN-M
`BTCUSD_PERP` pilot on the frozen 2023-06→2024-10 archive (15.7 months, event-level, keyless,
98.7% coverage). It would need its own registration acknowledging: different instrument,
single-era window, no recent lockbox possible, throttle-sampled magnitude. Its value would be a
cheap directional read on whether forced-flow stratification is worth the 6-month forward wait.

**No proxy substitution** (banned; `lane1_twap` falsified it). **Lockbox: never opened.**
