# Telegram Alerts for the Signal Watch Daemon — Design

**Date:** 2026-06-15
**Status:** Approved design; ready for implementation plan.

## Goal

Send signal-watch alerts to Telegram. When the watch daemon emits an alert, also
deliver it to a Telegram chat via the Bot API. The integration is additive: it
must not change existing stderr or `--alert-cmd` behavior, and must never crash
the daemon.

## Background & constraints

- The signal CLI (`src/moonface/signal/cli.py`) has a `watch()` loop that calls a
  single `_alert(args, message)` function for every "human attention needed"
  event: non-WAIT signals (strategy / participation / baseline tiers), forward
  gate PASSED, participation kill-switch, and data errors. `_alert()` prints to
  stderr and optionally shells out to `--alert-cmd`.
- The codebase performs HTTP with the **stdlib `urllib.request`** (see
  `backtest/metrics_data.py`, `backtest/bookdepth_data.py`,
  `backtest/universe_data.py`). No `requests`/`httpx` dependency exists, and none
  is added here.
- A Telegram bot existed previously and was **deliberately torn down**. `PKG-INFO`
  records the removal, and `tests/test_config.py` asserts the `Settings`
  dataclass has no `telegram_*` fields. This design keeps Telegram config out of
  `Settings` entirely (env-only) so that contract stays intact.

## Decisions (locked)

| Question | Decision |
|---|---|
| Integration depth | Native sender module (`signal/notify.py`) using stdlib `urllib`. |
| Which events | **All** messages that flow through `_alert()` (single tap point). |
| Credentials | Env vars `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (via `.env`). |
| Send failure | **Non-fatal** — log to stderr, never raise; daemon keeps running. |
| Activation | **Auto** when both env vars are set; **watch mode only**. No new flag. |

## Architecture

One new module plus minimal wiring in `cli.py`.

```
src/moonface/signal/notify.py
  class TelegramNotifier
    __init__(self, token, chat_id, transport=<default urllib POST>)
    send(self, message: str) -> None
      # POST to https://api.telegram.org/bot<token>/sendMessage
      # JSON body {"chat_id": chat_id, "text": message}
      # plain text (no parse_mode), ~10s timeout
      # on any transport/HTTP error: print "TELEGRAM SEND FAILED: <err>" to
      #   stderr and return normally — never raise

  notifier_from_env(env=os.environ) -> TelegramNotifier | None
    # returns TelegramNotifier iff BOTH env vars are present and non-empty,
    # else None (Telegram silently off)
```

- **Transport seam:** `TelegramNotifier` takes its POST function as an injectable
  `transport` defaulting to the real `urllib.request` call, so tests pass a fake
  and assert on URL + payload without network access.
- **Single off-switch:** `notifier_from_env()` is the only place that decides
  whether Telegram is active. `cli.py` only does `if notifier:`.

## Wiring into `cli.py`

1. `_alert()` gains an optional `notifier` parameter:

   ```python
   def _alert(args, message, notifier=None):
       print(f"ALERT: {message}", file=sys.stderr)
       if args.alert_cmd:
           subprocess.run([*shlex.split(args.alert_cmd), message], check=False)
       if notifier:
           notifier.send(message)
   ```

   Order is stderr -> alert-cmd -> telegram, so a Telegram failure cannot
   suppress the existing outputs. Telegram is purely additive.

2. `watch()` resolves the notifier once and passes it to every `_alert()` call.
   To keep this testable without touching env, `watch()` accepts the notifier via
   an optional parameter that defaults to `notifier_from_env()` — mirroring the
   existing `sleep_fn=time.sleep` injection pattern:

   ```python
   def watch(args, *, iterations=None, sleep_fn=time.sleep, notifier=None):
       if notifier is None:
           notifier = notifier_from_env()
       ...
       _alert(args, message, notifier)   # at each of the ~5 call sites
   ```

3. `run()` (one-shot) is unchanged. Per the watch-only decision, and because
   `run()` does not call `_alert()` today.

## Message content

Telegram receives the exact string `_alert()` already composes — no new
formatting in this iteration. Examples:

- `baseline signal: LONG @ 64000, conf 0.6, f=0.1`
- `forward gate PASSED — paper->live review is unlocked (human decision)`
- `participation kill switch: <reason>`
- `data fetch failed: <repr>`

Sent as plain text (no Markdown/HTML parse mode) to avoid escaping pitfalls.

## Error handling

- `TelegramNotifier.send()` wraps the POST in
  `try/except (urllib.error.URLError, OSError, TimeoutError)` plus a broad
  fallback. `urllib.error.HTTPError` (non-2xx) is a subclass of `URLError` and is
  caught the same way. On error it prints `TELEGRAM SEND FAILED: <err>` to stderr
  and returns. The watch loop never sees a notification exception.
- `notifier_from_env()` returns `None` when either var is missing/empty —
  Telegram silently off, no warning spam.

## Testing

New `tests/test_signal_notify.py`:

- `notifier_from_env`: returns a notifier when both vars set; `None` when either
  is missing or empty.
- `send()` happy path: fake transport receives the correct URL
  (`.../bot<token>/sendMessage`) and JSON payload (`chat_id`, `text`).
- `send()` failure path: fake transport raises -> no exception propagates, and
  the stderr failure line is emitted.

Additions to `tests/test_signal_cli.py`:

- `watch(iterations=1, notifier=<fake>)` on a non-WAIT signal -> fake
  `notifier.send` called with the alert text.
- `_alert()` with `notifier=None` behaves exactly as today (stderr + alert-cmd
  unaffected).

## Config & docs

- `.env.example`: add `TELEGRAM_BOT_TOKEN=` and `TELEGRAM_CHAT_ID=` with a
  one-line comment that they are optional and used only in watch mode.
- `README.md`: short "Telegram alerts (optional)" note under watch mode.
- No change to the `Settings` dataclass; `tests/test_config.py` stays green.

## Out of scope (YAGNI)

- One-shot (`run()`) notifications.
- Per-event filtering / routing to multiple chats.
- Rich formatting, retries, rate limiting, message threading.
- Inbound Telegram commands (this is one-way, outbound only).
```