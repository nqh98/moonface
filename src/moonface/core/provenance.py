"""The provenance triple: registration_hash, data_fingerprint, code_hash.

Three sha256 stamps -- what was frozen, what data ran, what code computed it
-- so any two runs of the same lane can be diffed and the delta attributed to
params, data, or code (spec section 3.2). Reuses the sha256-of-canonical-JSON
construction already established by kernel.spec.spec_hash and
signal.engine.config.engine_hash, generalized here to any JSON-able
registration dict and any set of source files, not one dataclass or one
engine config shape."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def registration_hash(registration: dict) -> str:
    """sha256 of the canonical (sorted-key) JSON of a lane's registration
    dict."""
    canonical = json.dumps(registration, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def raw_series_fingerprint(points: list[tuple[int, float]]) -> str:
    """sha256 over a (timestamp, value) series -- the non-Candle analog of
    core.stats.series_fingerprint, for metric histories (OI, funding, L/S
    ratio) that aren't OHLCV candles."""
    h = hashlib.sha256()
    for ts, v in points:
        h.update(f"{ts},{v}\n".encode())
    return h.hexdigest()


def data_fingerprint(series_by_key: dict[str, str]) -> str:
    """sha256 of the sorted {key: series_fingerprint} mapping, so a
    multi-asset lane's fingerprint covers every series it read. Callers
    compute each series's own fingerprint first (core.stats.series_fingerprint
    for a candle stream, raw_series_fingerprint for a raw metric series) and
    pass the {asset_or_field: digest} mapping in here."""
    canonical = json.dumps(series_by_key, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def code_hash(module_paths: list[str]) -> str:
    """sha256 of the concatenated source of the given modules, sorted by
    path so the digest is independent of call order. Paths are read as given
    (repo-relative or absolute); a change to any listed file's bytes changes
    the hash."""
    h = hashlib.sha256()
    for p in sorted(module_paths):
        h.update(p.encode())
        h.update(b"\x00")
        h.update(Path(p).read_bytes())
    return h.hexdigest()
