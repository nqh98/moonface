# Telegram Alerts for the Signal Watch Daemon — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver every signal-watch alert to a Telegram chat via the Bot API, additively and without ever crashing the watch daemon.

**Architecture:** A new `src/moonface/signal/notify.py` module holds a `TelegramNotifier` (stdlib `urllib` POST to the Telegram Bot API, with an injectable transport for testing) and a `notifier_from_env()` factory that returns a notifier only when both env vars are set. `cli.py`'s single `_alert()` function gains an optional `notifier` parameter; `watch()` resolves the notifier once and passes it to every `_alert()` call. One-shot `run()` is untouched.

**Tech Stack:** Python 3.11, stdlib `urllib.request` / `urllib.error` / `json` / `os`, pytest.

**Spec:** `docs/research-log/specs/2026-06-15-telegram-alerts-design.md`

---

## File Structure

- **Create** `src/moonface/signal/notify.py` — `TelegramNotifier` + `notifier_from_env()`. Sole responsibility: turn a message string into a Telegram Bot API call, deciding activation from env. Knows nothing about signals.
- **Create** `tests/test_signal_notify.py` — unit tests for the notifier and factory.
- **Modify** `src/moonface/signal/cli.py` — add `notifier` param to `_alert()`; add `notifier` kwarg to `watch()`; thread it through the ~5 in-loop `_alert()` calls.
- **Modify** `tests/test_signal_cli.py` — `_watch_args` unchanged; add tests proving `watch()` forwards alerts to an injected notifier and that `notifier=None` is unchanged.
- **Modify** `.env.example` — document the two optional env vars.
- **Modify** `README.md` — short "Telegram alerts (optional)" note.

---

## Task 1: TelegramNotifier.send happy path

**Files:**
- Create: `src/moonface/signal/notify.py`
- Test: `tests/test_signal_notify.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_signal_notify.py
import json

from moonface.signal.notify import TelegramNotifier


def test_send_posts_to_bot_api():
    calls = []

    def fake_transport(url, data):
        calls.append((url, data))

    n = TelegramNotifier("TOK", "CHAT", transport=fake_transport)
    n.send("hello world")

    assert len(calls) == 1
    url, data = calls[0]
    assert url == "https://api.telegram.org/botTOK/sendMessage"
    body = json.loads(data)
    assert body == {"chat_id": "CHAT", "text": "hello world"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signal_notify.py::test_send_posts_to_bot_api -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.notify'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/notify.py
"""Outbound Telegram alerts for the signal watch daemon.

Transport-only: this module turns an alert string into a Telegram Bot API
call. It knows nothing about signals, and a send failure never propagates —
the watch daemon must outlive a notification outage."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

_API = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT_S = 10.0


def _post(url: str, data: str) -> None:
    """Default transport: POST a JSON body. Raises on transport/HTTP error."""
    req = urllib.request.Request(
        url, data=data.encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S):
        pass


class TelegramNotifier:
    """Sends alert messages to one Telegram chat. Construct via
    `notifier_from_env()`; `transport` is injectable for tests."""

    def __init__(self, token: str, chat_id: str, transport=_post) -> None:
        self._url = _API.format(token=token)
        self._chat_id = chat_id
        self._transport = transport

    def send(self, message: str) -> None:
        body = json.dumps({"chat_id": self._chat_id, "text": message})
        self._transport(self._url, body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_signal_notify.py::test_send_posts_to_bot_api -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/notify.py tests/test_signal_notify.py
git commit -m "feat(signal): TelegramNotifier.send posts an alert to the Bot API"
```

---

## Task 2: send swallows transport failures

**Files:**
- Modify: `src/moonface/signal/notify.py`
- Test: `tests/test_signal_notify.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_signal_notify.py
def test_send_swallows_errors_and_logs(capsys):
    def boom(url, data):
        raise OSError("network down")

    n = TelegramNotifier("TOK", "CHAT", transport=boom)
    n.send("hello")  # must not raise

    assert "TELEGRAM SEND FAILED" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signal_notify.py::test_send_swallows_errors_and_logs -v`
Expected: FAIL — `OSError: network down` propagates out of `send`.

- [ ] **Step 3: Write minimal implementation**

Replace the `send` method in `src/moonface/signal/notify.py` with:

```python
    def send(self, message: str) -> None:
        body = json.dumps({"chat_id": self._chat_id, "text": message})
        try:
            self._transport(self._url, body)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            print(f"TELEGRAM SEND FAILED: {exc!r}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - never kill the daemon
            print(f"TELEGRAM SEND FAILED: {exc!r}", file=sys.stderr)
```

(`urllib.error.HTTPError` is a subclass of `URLError`, so non-2xx responses are
caught by the first branch.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_signal_notify.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/notify.py tests/test_signal_notify.py
git commit -m "feat(signal): TelegramNotifier.send never raises on send failure"
```

---

## Task 3: notifier_from_env factory

**Files:**
- Modify: `src/moonface/signal/notify.py`
- Test: `tests/test_signal_notify.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_signal_notify.py
from moonface.signal.notify import notifier_from_env


def test_notifier_from_env_returns_notifier_when_both_set():
    env = {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_ID": "CHAT"}
    n = notifier_from_env(env)
    assert isinstance(n, TelegramNotifier)


def test_notifier_from_env_none_when_token_missing():
    assert notifier_from_env({"TELEGRAM_CHAT_ID": "CHAT"}) is None


def test_notifier_from_env_none_when_chat_missing():
    assert notifier_from_env({"TELEGRAM_BOT_TOKEN": "TOK"}) is None


def test_notifier_from_env_none_when_value_empty():
    env = {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_ID": ""}
    assert notifier_from_env(env) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signal_notify.py::test_notifier_from_env_returns_notifier_when_both_set -v`
Expected: FAIL with `ImportError: cannot import name 'notifier_from_env'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/moonface/signal/notify.py`:

```python
def notifier_from_env(env=None) -> TelegramNotifier | None:
    """A notifier iff both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are present
    and non-empty, else None (Telegram silently off)."""
    if env is None:
        env = os.environ
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return None
    return TelegramNotifier(token, chat_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_signal_notify.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/notify.py tests/test_signal_notify.py
git commit -m "feat(signal): notifier_from_env gates Telegram on both env vars"
```

---

## Task 4: _alert forwards to an optional notifier

**Files:**
- Modify: `src/moonface/signal/cli.py:123-126` (the `_alert` function)
- Test: `tests/test_signal_cli.py`

The current `_alert` (cli.py lines 123-126):

```python
def _alert(args: argparse.Namespace, message: str) -> None:
    print(f"ALERT: {message}", file=sys.stderr)
    if args.alert_cmd:
        subprocess.run([*shlex.split(args.alert_cmd), message], check=False)
```

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_signal_cli.py, after the watch-mode tests (~line 257)
def test_alert_forwards_to_notifier():
    sent = []

    class FakeNotifier:
        def send(self, message):
            sent.append(message)

    args = cli.build_parser().parse_args(["--watch"])
    cli._alert(args, "baseline signal: LONG @ 100", notifier=FakeNotifier())
    assert sent == ["baseline signal: LONG @ 100"]


def test_alert_without_notifier_is_unchanged(capsys):
    args = cli.build_parser().parse_args(["--watch"])
    cli._alert(args, "data fetch failed", notifier=None)
    assert "ALERT: data fetch failed" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signal_cli.py::test_alert_forwards_to_notifier -v`
Expected: FAIL with `TypeError: _alert() got an unexpected keyword argument 'notifier'`

- [ ] **Step 3: Write minimal implementation**

Replace the `_alert` function in `src/moonface/signal/cli.py` with:

```python
def _alert(args: argparse.Namespace, message: str, notifier=None) -> None:
    print(f"ALERT: {message}", file=sys.stderr)
    if args.alert_cmd:
        subprocess.run([*shlex.split(args.alert_cmd), message], check=False)
    if notifier is not None:
        notifier.send(message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_signal_cli.py::test_alert_forwards_to_notifier tests/test_signal_cli.py::test_alert_without_notifier_is_unchanged -v`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/cli.py tests/test_signal_cli.py
git commit -m "feat(signal): _alert forwards messages to an optional notifier"
```

---

## Task 5: watch resolves and threads the notifier

**Files:**
- Modify: `src/moonface/signal/cli.py` — `watch()` signature (line 220-221) and the five in-loop `_alert(args, ...)` calls (lines 253, 255, 261, 266, 269, 275, 279)
- Modify: `src/moonface/signal/cli.py` import block (line 17-18 area) — import `notifier_from_env`
- Test: `tests/test_signal_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_signal_cli.py
def test_watch_forwards_signal_alert_to_notifier(tmp_path, monkeypatch):
    _setup_fresh(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cli, "evaluate",
        lambda strategy, bundle: cli.Signal("LONG", 100.0, 95.0, 0.01, "test"))
    sent = []

    class FakeNotifier:
        def send(self, message):
            sent.append(message)

    rc = cli.watch(_watch_args(tmp_path), iterations=1,
                   sleep_fn=lambda s: None, notifier=FakeNotifier())
    assert rc == 0
    assert any("LONG @ 100" in m for m in sent)


def test_watch_default_notifier_off_without_env(tmp_path, capsys, monkeypatch):
    _setup_fresh(tmp_path, monkeypatch)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(
        cli, "evaluate",
        lambda strategy, bundle: cli.Signal("LONG", 100.0, 95.0, 0.01, "test"))
    rc = cli.watch(_watch_args(tmp_path), iterations=1, sleep_fn=lambda s: None)
    assert rc == 0  # no env -> notifier None -> alerts still print to stderr
    assert "ALERT" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signal_cli.py::test_watch_forwards_signal_alert_to_notifier -v`
Expected: FAIL with `TypeError: watch() got an unexpected keyword argument 'notifier'`

- [ ] **Step 3: Write minimal implementation**

3a. Add the import. The existing baseline import block in cli.py is:

```python
from moonface.signal.baseline import (BaselineConfig, baseline_hash,
                                       evaluate_baseline, load_baseline_config)
```

Add directly after it:

```python
from moonface.signal.notify import notifier_from_env
```

3b. Change the `watch` signature. Current (lines 220-221):

```python
def watch(args: argparse.Namespace, *, iterations: int | None = None,
          sleep_fn=time.sleep) -> int:
```

to:

```python
def watch(args: argparse.Namespace, *, iterations: int | None = None,
          sleep_fn=time.sleep, notifier=None) -> int:
```

3c. Immediately after the docstring (before `done = 0`), resolve the default:

```python
    if notifier is None:
        notifier = notifier_from_env()
    done = 0
```

3d. Add `notifier` as the final argument to every `_alert(args, ...)` call inside
the loop. There are six call sites; each becomes `_alert(args, <message>, notifier)`:

```python
                        if sig.decision != "WAIT":
                            _alert(args,
                                   f"{strategy.status} signal: {sig.decision} @"
                                   f" {sig.price}, invalidation {sig.invalidation},"
                                   f" f={sig.fraction}", notifier)
                        gate = forward_report(read_entries(args.journal),
                                              bundle.candles, strategy)["gate"]
                        if gate["passed"]:
                            _alert(args, "forward gate PASSED — paper->live"
                                         " review is unlocked (human decision)",
                                   notifier)
                    elif use_policy:
                        sig = _emit_participation(args, policy, bundle,
                                                  _now_ms(), tf_ms)
                        if sig.kill_switch:
                            _alert(args, f"participation kill switch:"
                                         f" {sig.reason}", notifier)
                        elif sig.decision != "WAIT":
                            _alert(args, f"participation signal:"
                                         f" {sig.decision} @ {sig.price},"
                                         f" f={sig.fraction}", notifier)
                    else:
                        sig = _emit_baseline(args, cfg, bundle, _now_ms(), tf_ms)
                        if sig.decision != "WAIT":
                            _alert(args, f"baseline signal: {sig.decision} @"
                                         f" {sig.price}, conf {sig.confidence},"
                                         f" f={sig.fraction}", notifier)
            except DataError as exc:
                _alert(args, str(exc), notifier)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_signal_cli.py -v`
Expected: PASS (new tests plus all pre-existing watch tests, which pass
`notifier` defaulting to `None`)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/cli.py tests/test_signal_cli.py
git commit -m "feat(signal): watch resolves a Telegram notifier and routes alerts to it"
```

---

## Task 6: Document the env vars and config

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Add the env vars to `.env.example`**

Append to `.env.example` (current contents are the two `MOONFACE_*` lines):

```
# Optional: outbound Telegram alerts. Set BOTH to enable; used in --watch mode only.
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

- [ ] **Step 2: Add a README note**

Add a short subsection to `README.md` under the watch-mode description:

```markdown
### Telegram alerts (optional)

In `--watch` mode, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (e.g. in
`.env`) to mirror every watch alert — actionable signals, forward-gate passes,
kill-switch trips, and data errors — to a Telegram chat. If either var is unset,
Telegram is off. A send failure logs to stderr and never stops the daemon.
```

- [ ] **Step 3: Verify the docs are consistent**

Run: `grep -n "TELEGRAM" .env.example README.md`
Expected: both files mention `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md
git commit -m "docs(signal): document optional Telegram alert env vars"
```

---

## Task 7: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full signal test suite**

Run: `python -m pytest tests/test_signal_notify.py tests/test_signal_cli.py tests/test_config.py -v`
Expected: all PASS. In particular `test_config.py` (asserting no `telegram_*`
Settings fields) stays green, since this feature stores no config on `Settings`.

- [ ] **Step 2: Run the linter**

Run: `ruff check src/moonface/signal/notify.py src/moonface/signal/cli.py tests/test_signal_notify.py`
Expected: no errors.

- [ ] **Step 3: Run the whole suite for regressions**

Run: `python -m pytest -q`
Expected: all PASS (no behavior change for non-Telegram paths).

---

## Self-Review

**Spec coverage:**
- Native sender module → Task 1-3 (`notify.py`).
- stdlib urllib HTTP → Task 1 (`_post` via `urllib.request.Request`/`urlopen`).
- Transport seam for tests → Task 1 (`transport=` param).
- All `_alert()` messages routed → Task 4-5 (param + six call sites).
- Env vars `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` → Task 3, Task 6.
- Non-fatal on failure → Task 2.
- Auto-on when env set → Task 3 + Task 5 (`watch` resolves `notifier_from_env()`).
- Watch only, run() unchanged → no task touches `run()`.
- Reuse existing message text → Task 5 passes the same strings unchanged.
- `.env.example` + README → Task 6.
- Settings untouched / test_config green → Task 7 Step 1.
- Tests (factory, happy, failure, CLI integration) → Tasks 1-5 + Task 7.

**Placeholder scan:** No TBD/TODO; every code step shows complete code.

**Type consistency:** `TelegramNotifier(token, chat_id, transport=...)`, `.send(message)`, and `notifier_from_env(env=None) -> TelegramNotifier | None` are used identically across Tasks 1-5. The injected fake in CLI tests implements the same `.send(message)` interface.
