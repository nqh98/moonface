"""Outbound Telegram alerts for the moonface-feed broadcaster (and,
historically, the retired v2.2 signal CLI).

Transport-only: this module turns an alert string into a Telegram Bot API
call. It knows nothing about signals, and a send failure never propagates —
the watch daemon must outlive a notification outage."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping

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

    def __init__(self, token: str, chat_id: str,
                 transport: Callable[[str, str], None] = _post) -> None:
        self._url = _API.format(token=token)
        self._chat_id = chat_id
        self._transport = transport

    def send(self, message: str) -> None:
        body = json.dumps({"chat_id": self._chat_id, "text": message})
        try:
            self._transport(self._url, body)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            print(f"TELEGRAM SEND FAILED: {exc!r}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - never kill the daemon
            print(f"TELEGRAM SEND FAILED: {exc!r}", file=sys.stderr)


def notifier_from_env(env: Mapping[str, str] | None = None) -> TelegramNotifier | None:
    """A notifier iff both a bot token and a chat id are present and non-blank,
    else None (Telegram silently off). Reads the plain TELEGRAM_* names, falling
    back to the MOONFACE_TELEGRAM_* prefixed form used in this repo's .env."""
    if env is None:
        env = os.environ
    token = (env.get("TELEGRAM_BOT_TOKEN")
             or env.get("MOONFACE_TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (env.get("TELEGRAM_CHAT_ID")
               or env.get("MOONFACE_TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        return None
    return TelegramNotifier(token, chat_id)
