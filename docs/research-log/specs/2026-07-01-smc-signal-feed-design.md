# SMC Signal Feed — Design Spec

- **Date:** 2026-07-01
- **Status:** Approved (brainstormed 2026-07-01) → pending implementation plan
- **Scope:** A new broadcast signal channel that posts TradesAI-style SMC setup cards to a Telegram channel, built on MoonFace's existing foundation + SMC detectors.

## 1. Context & motivation

MoonFace today is a **BTC perpetual-futures signal research engine** with an honest, anti-hype identity:

- One promoted strategy (`mtf_long`, BTC/USDT:USDT, 15m, long-only, **paper**), plus baseline/participation tiers.
- Telegram is **one-way broadcast to a single chat** (`signal/notify.py`) — no inbound commands, no users, no execution.
- **No order execution, no portfolio management** — the deterministic advisor, Telegram bot, LLM layer, and autopilot were removed on 2026-06-11 because "no validated edge supported them."
- Strong honesty stance: baseline output is tagged `[BASELINE — heuristic, NOT a validated edge]`; the multi-family drift screens across 16+ perps all returned `mechanism_does_not_exist`.

The user wants a product resembling **TradesAI (t.me/trades_ai)** — a consumer-facing Telegram signal channel. The full product (user accounts, subscriptions, copy/execution) conflicts hard with MoonFace's no-execution, no-validated-edge ethos. Through brainstorming, the scope was narrowed to the subset that is both useful and honest: a **broadcast channel of caveat-labeled SMC setup cards**.

The key honesty fact that shapes this design: the SMC reversal advisor (sweep → CHOCH) was **explicitly falsified** in `PROGRAM_CONCLUSION`. The detectors work fine as *setup finders*, but **no posted setup carries a validated out-of-sample edge**. Therefore every posted card carries an explicit caveat, and nothing here claims otherwise.

## 2. Goal & non-goals

**Goal:** A Telegram channel where, on each 4h candle close, the bot posts text-only TradesAI-style cards for *fresh, fully-confirmed* SMC setups across a top-volume perp universe — one post per setup until it resolves, with outcome tracking and honest caveat labels. No commands, no interactivity.

**Non-goals (explicitly out of scope):**
- No inbound Telegram commands (`/start`, `/signal`, `/portfolio`).
- No user accounts, subscriptions, or paywalls.
- No order execution, copy-trading, or exchange API keys.
- No validated-edge claim — the feed is heuristic, caveat-labeled.
- No leverage/"x" recommendations.
- v2 setups (order-block retest, FVG fill, EQH/EQL) are noted but **not built in v1**.

## 3. Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Product shape | Broadcast signal **channel** (no commands, no interactivity) |
| Signal source | **SMC/setup scan**, caveat-labeled (heuristic; no validated edge) |
| Card format | **Text-only** signal card (no chart images, no TradingView links) |
| Scan model | **Selective, fresh-only**: top ~30–50 perps by 24h volume @ 4h; post only fresh confirmed setups; one post per setup until resolved |
| Code structure (approach) | **A**: promote SMC/pivots detectors to `foundation`; new `moonface.feed` package + `moonface-feed` entry point |

**Baked-in ethos defaults (approved):**
- **No leverage/"x"** on cards; a fixed fractional-risk note (`risk ~1% — reference only, not execution sizing`) instead — mirroring how `mtf_long` treats `fraction`.
- **Dry-run by default.** Cards go to stdout; nothing posts unless `--post` / `MOONFACE_FEED_POST=1`.
- **Every card caveat-tagged** + a one-time **pinned disclaimer**.

## 4. Architecture & layering

MoonFace enforces a strictly-downward layer graph, locked by `tests/test_import_boundaries.py`: `foundation` imports nothing inside `moonface`; `signal` imports only `foundation`; `research` imports `foundation` freely; `signal` may not import `research`.

```
foundation  ←  signal  ←  feed
                ↑              ↑
       (notify + cadence helper reused)
```

**Detector promotion (foundation-pure already):**
- `research/edge/_smc.py` → `foundation/smc.py`
- `research/edge/pivots.py` → `foundation/pivots.py`

Both currently import only `foundation.models` / `foundation.risk`, so the move is mechanical. `research/edge/_smc.py` and `pivots.py` become **thin re-import shims** so every existing leaderboard and `PROGRAM_CONCLUSION` repro stays byte-identical — no research logic changes.

**New top-level package `moonface.feed`** imports `foundation` and `signal` (for `signal.notify.TelegramNotifier`); it **never** imports `research`. The scan loop lives in `feed/loop.py` and **mirrors** the cadence/restart-safe pattern of `signal.cli.watch` (duplicated, ~40 lines) rather than extracting a shared helper — that avoids refactoring `signal.cli`, which is out of scope. A shared helper can be extracted later if a third caller appears.

**Import-boundary test update:** allow `feed → {foundation, signal}`; forbid `feed → research`; re-affirm `foundation → ∅`.

## 5. Components

Foundation additions:

| Module | Responsibility |
|---|---|
| `foundation/smc.py` | Liquidity pools, sweeps, swings, structure trend (HH/HL vs LH/LL), CHOCH+displacement, **new `detect_bos()`**; v2 hooks for order blocks/FVG |
| `foundation/pivots.py` | Traditional daily pivots P / S1–3 / R1–3 (promoted as-is) |

`moonface.feed` package:

| Module | Responsibility |
|---|---|
| `feed/universe.py` | Select top-N USDT perps by 24h quote volume via ccxt; refresh the list daily; warmup from `.backtest_cache` + fetch the latest closed candle (reuse `foundation.data.load_bundle`) |
| `feed/setups.py` | Per-symbol: run detectors over the candle series and emit `Setup` events whose **confirming event is on the last closed candle** only |
| `feed/levels.py` | Derive entry zone, TP1/TP2/TP3, invalidation (SL), and confidence from structure + pivots + ATR |
| `feed/card.py` | `Setup` → TradesAI-style text card + caveat tag (pure function, golden-tested) |
| `feed/state.py` | Open-setup store (`jsonl`); fresh-only dedup via `setup_hash`; outcome resolution (TP/SL/timeout) |
| `feed/loop.py` | Cadence-aware, restart-safe scan loop (mirrors `signal.cli.watch`) |
| `feed/cli.py` | `moonface-feed` entry point |

## 6. Data flow (one 4h tick)

```
universe.select()  ──▶  for each symbol:
                          load_bundle(live + cache)           (reuse foundation.data)
                          setups.detect_last(candles)         ──▶ Setup candidates
                          state.is_fresh(symbol, setup_hash)? ──▶ skip if already open/posted
                          levels.derive(setup, pivots, atr)   ──▶ entry/TPs/SL/confidence
                          card.render(setup)                  ──▶ text + caveat
                          [if --post] notify.send(card)       ──▶ Telegram channel
                          state.open(symbol, setup)
                        state.resolve_open(candles)          ──▶ mark TP/SL/timeout; record outcome
```

**Fresh-only guarantee:** a symbol posts **once per setup**. `setup_hash` = hash of (setup-type, side, key SMC levels). While a setup is open it is never re-posted. On resolve (TP hit / SL hit / N-bar timeout), the outcome is journaled and an optional brief **result card** is posted.

## 7. Setups (v1) & level derivation

**v1 setups — only what existing detectors support:**

1. **Sweep + CHoCH reversal.** Sell-side liquidity sweep followed by bullish CHOCH+displacement → `LONG` (mirror → `SHORT`). Reuses `detect_liquidity` / `detect_sweeps` / `detect_choch`. Card name: *🟢 Sell-side sweep + bullish CHoCH*.
2. **BOS continuation.** In a confirmed structure, a close beyond the last opposing swing → continuation in trend direction. Requires a new `detect_bos()` — a close cousin of the existing `detect_choch` (~15 lines, lookahead-free).

**v2 (noted, not built):** order-block retest, FVG fill, EQH/EQL — to be ported from `docs/script/SMC.pine` (LuxAlgo reference).

**Level derivation:**
- **Entry zone:** confirming-candle close ± 0.25·ATR.
- **SL (invalidation):** beyond the swept level / opposing structural swing — the level that breaks the setup thesis.
- **TP1/TP2/TP3:** daily pivots (R1/R2/R3 for longs, S1/S2/S3 for shorts) blended with the next opposing swings, chosen so R-multiples ascend sensibly from entry vs. SL distance.
- **Confidence:** transparent composite (structure agreement + displacement strength + liquidity freshness), labeled *"setup quality, NOT a probability of profit"* — mirrors `baseline.confidence` semantics.
- **No leverage/"x".** A `risk ~1% — reference only` line instead.

## 8. Cadence, delivery, error handling

- **Loop:** sleep until next 4h close + `--grace-seconds`; re-read config each tick (no restart on edit); a symbol's data error alerts + retries next candle without killing other symbols — directly mirroring `signal.cli.watch`.
- **Dry-run by default.** Cards → stdout; nothing posts unless `--post` (or `MOONFACE_FEED_POST=1`). New env: `MOONFACE_FEED_TELEGRAM_TOKEN` / `MOONFACE_FEED_CHAT_ID` (separate from the watch-alert chat).
- **Rate limiting:** per-symbol hard cap + ≤ `--max-posts` (default 5) posts per tick, so a violent market cannot flood the channel.
- **Pinned disclaimer:** `moonface-feed --disclaimer` posts/prints the one-time honesty banner (heuristic setups, no validated edge, not financial advice); the bot pins it.
- **Telegram send failure never kills the loop** — same contract as `signal.notify`.

## 9. Testing

- **Unit:** `setups.detect_last` on fixture candles; `levels.derive` R-multiple sanity; `card.render` golden strings (including the caveat tag); `state` fresh → open → resolved state machine; `universe` volume-sort determinism.
- **Frozen-window replay:** run the scanner over a fixed slice of cached 4h history → assert a deterministic setup list (mirrors the repo's frozen-window convention from recent commits).
- **Import-boundary test** updated for `feed`.
- **No network in tests** — `load_bundle` and `notify` are injected seams, same as today.

## 10. CLI

```bash
moonface-feed --once --dry-run          # scan now, print cards, post nothing
moonface-feed --watch --post            # cadence loop, post fresh setups to channel
moonface-feed --report                  # open setups + resolved outcomes
moonface-feed --disclaimer --post       # post + pin the honesty banner
# flags: --universe-size 40 --timeframe 4h --grace-seconds 60 --max-posts 5
```

New entry point registered in `pyproject.toml`: `moonface-feed = "moonface.feed.cli:main"`.

## 11. Open questions / v2

- Whether to add a separate "high-conviction" tier that surfaces the validated `mtf_long` BTC long when it fires (deferred — v1 is pure SMC, all caveat-labeled).
- Order-block / FVG / EQH-EQL setups (v2, ported from the Pine).
- Optional chart-image rendering (explicitly deferred; would add a matplotlib + sendPhoto path).

## 12. Implementation order (for the plan)

1. Promote `_smc.py`/`pivots.py` to `foundation`; add re-import shims; update import-boundary test.
2. Add `detect_bos()` to `foundation/smc.py`.
3. `feed/setups.py` + `feed/levels.py` + unit tests.
4. `feed/card.py` + golden tests.
5. `feed/state.py` (dedup + outcome) + state-machine tests.
6. `feed/universe.py` + volume-sort tests.
7. `feed/loop.py` + `feed/cli.py` + entry point + frozen-window replay test.
8. Dry-run end-to-end against cached history; then `--post` to a test channel.
