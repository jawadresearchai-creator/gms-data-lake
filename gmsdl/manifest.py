"""SQLite manifest.

Deliberately a plain local file. The previous engine kept SQLite on a mounted
Google Drive (FUSE) and had to grow a "self-healing" corruption recovery path;
that is a symptom, not a fix. SQLite's locking semantics are not satisfied by
Drive's FUSE layer, so the database is kept on real local disk and shipped to
Drive as an ordinary file at the end of each run.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    key             TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL,
    domain          TEXT NOT NULL,
    dataset_id      TEXT NOT NULL,
    url             TEXT,
    remote_path     TEXT,
    etag            TEXT,
    last_modified   TEXT,
    content_length  INTEGER,
    sha256          TEXT,
    bytes           INTEGER,
    status          TEXT,
    error           TEXT,
    first_seen      TEXT,
    last_checked    TEXT,
    last_changed    TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_source ON files(source_id);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);

CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    host        TEXT,
    domains     TEXT,
    started     TEXT,
    finished    TEXT,
    ok          INTEGER DEFAULT 0,
    unchanged   INTEGER DEFAULT 0,
    failed      INTEGER DEFAULT 0,
    bytes       INTEGER DEFAULT 0,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS source_health (
    source_id   TEXT,
    dataset_id  TEXT,
    checked_at  TEXT,
    http_status INTEGER,
    ok          INTEGER,
    note        TEXT,
    PRIMARY KEY (source_id, dataset_id)
);
"""


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Manifest:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.conn.commit()
        self.conn.close()

    def integrity_ok(self) -> bool:
        try:
            row = self.conn.execute("PRAGMA quick_check").fetchone()
            return bool(row) and row[0] == "ok"
        except sqlite3.DatabaseError:
            return False

    # -- files -----------------------------------------------------------
    def get(self, key: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM files WHERE key = ?", (key,)).fetchone()

    def record(self, key: str, **fields: Any) -> None:
        existing = self.get(key)
        now = utcnow()
        fields.setdefault("last_checked", now)
        if existing is None:
            fields.setdefault("first_seen", now)
            cols = ", ".join(["key", *fields])
            marks = ", ".join(["?"] * (len(fields) + 1))
            self.conn.execute(
                f"INSERT INTO files ({cols}) VALUES ({marks})", (key, *fields.values())
            )
        else:
            sets = ", ".join(f"{c} = ?" for c in fields)
            self.conn.execute(
                f"UPDATE files SET {sets} WHERE key = ?", (*fields.values(), key)
            )
        self.conn.commit()

    def unchanged_validators(self, key: str) -> tuple[str | None, str | None]:
        """Return (etag, last_modified) for a conditional GET, only when the
        previous attempt actually succeeded."""
        row = self.get(key)
        if row is None or row["status"] not in {"OK", "UNCHANGED"}:
            return None, None
        return row["etag"], row["last_modified"]

    # -- runs ------------------------------------------------------------
    def start_run(self, run_id: str, host: str, domains: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, host, domains, started) VALUES (?,?,?,?)",
            (run_id, host, domains, utcnow()),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, ok: int, unchanged: int, failed: int, size: int, notes: str = "") -> None:
        self.conn.execute(
            "UPDATE runs SET finished=?, ok=?, unchanged=?, failed=?, bytes=?, notes=? WHERE run_id=?",
            (utcnow(), ok, unchanged, failed, size, notes, run_id),
        )
        self.conn.commit()

    # -- health ----------------------------------------------------------
    def record_health(self, source_id: str, dataset_id: str, status: int | None, ok: bool, note: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO source_health "
            "(source_id, dataset_id, checked_at, http_status, ok, note) VALUES (?,?,?,?,?,?)",
            (source_id, dataset_id, utcnow(), status, int(ok), note),
        )
        self.conn.commit()

    # -- reporting -------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        cur = self.conn.execute(
            "SELECT status, COUNT(*) n, COALESCE(SUM(bytes),0) b FROM files GROUP BY status"
        )
        by_status = {r["status"]: {"n": r["n"], "bytes": r["b"]} for r in cur}
        total = self.conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(bytes),0) b FROM files WHERE status='OK'"
        ).fetchone()
        return {"by_status": by_status, "files": total["n"], "bytes": total["b"]}

    def by_domain(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT domain, COUNT(*) n, COALESCE(SUM(bytes),0) b FROM files "
            "WHERE status='OK' GROUP BY domain ORDER BY b DESC"
        ).fetchall()

    def failures(self, limit: int = 100) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT source_id, dataset_id, url, error, last_checked FROM files "
            "WHERE status='FAILED' ORDER BY last_checked DESC LIMIT ?",
            (limit,),
        ).fetchall()

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
