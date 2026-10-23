"""Shared HTTP-retry wrapper for every data/ fetcher that hits a raw URL.

Moved out of research.universe_data at G4 -- data/universe.py and
data/orderbook.py both need it, and this is a data/-internal utility with no
domain of its own, not one more file each domain would otherwise duplicate."""
from __future__ import annotations

import time
import urllib.error
from typing import Any, Callable


def retrying(get: Callable[[str], Any], attempts: int = 4,
            sleep: Callable[[float], None] | None = None) -> Callable[[str], Any]:
    """Wrap a get(url) callable with retries on transient network failures
    (URLError covers timeouts/handshakes/resets; OSError the rest). HTTP
    error responses pass through -- the callers interpret those."""
    do_sleep = time.sleep if sleep is None else sleep

    def wrapped(url: str):
        for attempt in range(attempts):
            try:
                return get(url)
            except urllib.error.HTTPError:
                raise  # a served response, not a transient transport failure
            except (urllib.error.URLError, OSError, TimeoutError):
                if attempt == attempts - 1:
                    raise
                do_sleep(2.0 * (attempt + 1))
    return wrapped
