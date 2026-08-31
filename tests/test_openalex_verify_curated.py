from __future__ import annotations

import sqlite3
from pathlib import Path

from gmsdl.analytics.openalex_verify_curated import summarize, validate


def _make_raw(path: Path, rows: list[tuple[str, int, str, str]]) -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE files(key TEXT, bytes INTEGER, source_id TEXT, status TEXT)")
    con.executemany("INSERT INTO files VALUES(?,?,?,?)", rows)
    con.commit()
    con.close()


def _make_state(path: Path, rows: list[tuple[str, str, int, int]]) -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE files(key TEXT, status TEXT, bytes_in INTEGER, bytes_out INTEGER)")
    con.executemany("INSERT INTO files VALUES(?,?,?,?)", rows)
    con.commit()
    con.close()


def test_curated_reconciliation(tmp_path: Path) -> None:
    raw = tmp_path / "raw.sqlite"
    states = tmp_path / "states"
    states.mkdir()
    _make_raw(
        raw,
        [
            ("data/parquet/authors/a.parquet", 10, "OPENALEX_SNAPSHOT", "OK"),
            ("data/parquet/works/b.parquet", 20, "OPENALEX_SNAPSHOT", "OK"),
        ],
    )
    for batch in range(1, 16):
        rows = []
        if batch == 1:
            rows = [("data/parquet/authors/a.parquet", "OK", 10, 4)]
        elif batch == 2:
            rows = [("data/parquet/works/b.parquet", "OK", 20, 8)]
        _make_state(states / f"openalex_curate_batch_{batch:02d}.sqlite", rows)

    summary = summarize(raw, states)
    assert summary["raw_count"] == 2
    assert summary["state_ok"] == 2
    assert summary["state_bytes_in"] == 30
    assert summary["state_bytes_out"] == 12
    assert validate(summary) == []


def test_curated_reconciliation_detects_missing_source(tmp_path: Path) -> None:
    raw = tmp_path / "raw.sqlite"
    states = tmp_path / "states"
    states.mkdir()
    _make_raw(raw, [("data/parquet/works/a.parquet", 10, "OPENALEX_SNAPSHOT", "OK")])
    for batch in range(1, 16):
        _make_state(states / f"openalex_curate_batch_{batch:02d}.sqlite", [])

    errors = validate(summarize(raw, states))
    assert "curated source-key count does not match raw OpenAlex count" in errors
    assert "curated input bytes do not match verified raw bytes" in errors
