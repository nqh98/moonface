from __future__ import annotations

import json
import sqlite3
import time

from moonface.kernel.spec import HypothesisSpec, canonical_json, spec_hash

MAX_ATTEMPTS = 3

DOMAIN_STATUSES = {"active", "blocked", "awaiting_gate", "lockbox_open",
                   "closed_positive", "closed_negative", "shelved"}

_TRANSITIONS = {
    "pending": {"screened", "rejected", "anomaly"},
    "screened": {"oos_pass", "rejected"},
    "oos_pass": {"corrected_survivor", "rejected"},
    "corrected_survivor": {"lockbox_pass", "lockbox_fail"},
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    grid_size INTEGER NOT NULL DEFAULT 0,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    fence_ts INTEGER NOT NULL,
    lockbox_touched INTEGER NOT NULL DEFAULT 0,
    stage3_done INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (name, version)
);
CREATE TABLE IF NOT EXISTS hypotheses (
    spec_hash TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    version INTEGER NOT NULL,
    spec_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    stage_results_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    updated_ts INTEGER NOT NULL
);
"""


class TransitionError(RuntimeError):
    pass


class GridFrozenError(RuntimeError):
    pass


class LockboxAlreadyTouchedError(RuntimeError):
    pass


def _now_ms() -> int:
    return int(time.time() * 1000)


class Store:
    """Single source of truth for the research program. All status changes go
    through advance()/record_error() so the machine in _TRANSITIONS is enforced;
    the lockbox flag has no unset path by construction."""

    def __init__(self, path: str) -> None:
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)

    # -- domains ----------------------------------------------------------
    def register_domain(self, name: str, version: int, status: str, config: dict,
                        start_ms: int, end_ms: int, fence_ts: int) -> None:
        if status not in DOMAIN_STATUSES:
            raise ValueError(f"unknown domain status {status!r}")
        self._db.execute(
            "INSERT INTO domains (name, version, status, config_json, start_ms,"
            " end_ms, fence_ts) VALUES (?,?,?,?,?,?,?)",
            (name, version, status, json.dumps(config, sort_keys=True),
             start_ms, end_ms, fence_ts))
        self._db.commit()

    def domain(self, name: str, version: int) -> dict | None:
        row = self._db.execute(
            "SELECT * FROM domains WHERE name=? AND version=?",
            (name, version)).fetchone()
        return self._domain_dict(row) if row is not None else None

    def domains_in_order(self) -> list[dict]:
        rows = self._db.execute("SELECT * FROM domains ORDER BY rowid").fetchall()
        return [self._domain_dict(r) for r in rows]

    def set_domain_status(self, name: str, version: int, status: str) -> None:
        if status not in DOMAIN_STATUSES:
            raise ValueError(f"unknown domain status {status!r}")
        self._db.execute("UPDATE domains SET status=? WHERE name=? AND version=?",
                         (status, name, version))
        self._db.commit()

    def touch_lockbox(self, name: str, version: int) -> None:
        d = self.domain(name, version)
        if d is None:
            raise KeyError(f"unknown domain {name} v{version}")
        if d["lockbox_touched"]:
            raise LockboxAlreadyTouchedError(
                f"{name} v{version}: the lockbox tail was already spent")
        self._db.execute(
            "UPDATE domains SET lockbox_touched=1 WHERE name=? AND version=?",
            (name, version))
        self._db.commit()

    def mark_stage3_done(self, name: str, version: int) -> None:
        self._db.execute(
            "UPDATE domains SET stage3_done=1 WHERE name=? AND version=?",
            (name, version))
        self._db.commit()

    # -- hypotheses --------------------------------------------------------
    def insert_grid(self, name: str, version: int,
                    specs: list[HypothesisSpec]) -> int:
        existing = self._db.execute(
            "SELECT COUNT(*) FROM hypotheses WHERE domain=? AND version=?",
            (name, version)).fetchone()[0]
        if existing:
            raise GridFrozenError(
                f"{name} v{version} already has {existing} rows; register a new"
                " version instead of mutating a started grid")
        now = _now_ms()
        for s in specs:
            self._db.execute(
                "INSERT INTO hypotheses (spec_hash, domain, version, spec_json,"
                " status, updated_ts) VALUES (?,?,?,?, 'pending', ?)",
                (spec_hash(s), name, version, canonical_json(s), now))
        self._db.execute(
            "UPDATE domains SET grid_size=? WHERE name=? AND version=?",
            (len(specs), name, version))
        self._db.commit()
        return len(specs)

    def rows(self, name: str, version: int, status: str | None = None) -> list[dict]:
        if status is None:
            cur = self._db.execute(
                "SELECT * FROM hypotheses WHERE domain=? AND version=?"
                " ORDER BY rowid", (name, version))
        else:
            cur = self._db.execute(
                "SELECT * FROM hypotheses WHERE domain=? AND version=? AND status=?"
                " ORDER BY rowid", (name, version, status))
        return [self._row_dict(r) for r in cur.fetchall()]

    def row(self, h: str) -> dict:
        r = self._db.execute(
            "SELECT * FROM hypotheses WHERE spec_hash=?", (h,)).fetchone()
        if r is None:
            raise KeyError(f"unknown hypothesis {h}")
        return self._row_dict(r)

    def advance(self, h: str, new_status: str, stage_result: dict) -> None:
        cur = self.row(h)
        allowed = _TRANSITIONS.get(cur["status"], set())
        if new_status not in allowed:
            raise TransitionError(f"{cur['status']} -> {new_status} is not allowed")
        merged = {**cur["stage_results"], **stage_result}
        self._db.execute(
            "UPDATE hypotheses SET status=?, stage_results_json=?, updated_ts=?"
            " WHERE spec_hash=?",
            (new_status, json.dumps(merged, sort_keys=True), _now_ms(), h))
        self._db.commit()

    def record_error(self, h: str, message: str) -> None:
        cur = self.row(h)
        attempts = cur["attempts"] + 1
        status = "error" if attempts >= MAX_ATTEMPTS else cur["status"]
        self._db.execute(
            "UPDATE hypotheses SET attempts=?, error=?, status=?, updated_ts=?"
            " WHERE spec_hash=?", (attempts, message, status, _now_ms(), h))
        self._db.commit()

    def reset_errors(self, name: str, version: int) -> int:
        """Return errored rows to 'pending' with a clean attempt budget. Only
        legal for rows that never produced a result (status='error' means
        every attempt raised); stage results of other rows are untouched."""
        cur = self._db.execute(
            "UPDATE hypotheses SET status='pending', attempts=0, error=NULL,"
            " updated_ts=? WHERE domain=? AND version=? AND status='error'",
            (_now_ms(), name, version))
        self._db.commit()
        return cur.rowcount

    def counts(self, name: str, version: int) -> dict[str, int]:
        cur = self._db.execute(
            "SELECT status, COUNT(*) FROM hypotheses WHERE domain=? AND version=?"
            " GROUP BY status", (name, version))
        return {status: n for status, n in cur.fetchall()}

    # -- store queries -------------------------------------------------------
    def all_content_keys(self) -> set[str]:
        """Domain/version-independent identity of every tested hypothesis.
        spec_hash covers domain+version, so cross-program dedup must use this."""
        out: set[str] = set()
        for (sj,) in self._db.execute("SELECT spec_json FROM hypotheses"):
            d = json.loads(sj)
            out.add(json.dumps(
                {k: d[k] for k in ("asset", "entry", "exit", "fraction")},
                sort_keys=True, separators=(",", ":")))
        return out

    def lineage_trial_count(self, name: str) -> int:
        return self._db.execute(
            "SELECT COUNT(*) FROM hypotheses WHERE domain=?", (name,)).fetchone()[0]

    def max_version(self, name: str) -> int:
        v = self._db.execute(
            "SELECT MAX(version) FROM domains WHERE name=?", (name,)).fetchone()[0]
        return v or 0

    def lineage_survivor_versions(self, name: str) -> int:
        return self._db.execute(
            "SELECT COUNT(DISTINCT version) FROM hypotheses WHERE domain=? AND"
            " status IN ('corrected_survivor','lockbox_pass','lockbox_fail')",
            (name,)).fetchone()[0]

    # -- row shaping -------------------------------------------------------
    @staticmethod
    def _domain_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["config"] = json.loads(d.pop("config_json"))
        d["lockbox_touched"] = bool(d["lockbox_touched"])
        d["stage3_done"] = bool(d["stage3_done"])
        return d

    @staticmethod
    def _row_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["stage_results"] = json.loads(d.pop("stage_results_json"))
        return d
