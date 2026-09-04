from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.openalex_research_validate import validate_staged


def _write(path: Path, ddl: str, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t({ddl})")
    if rows:
        placeholders = ",".join("?" for _ in rows[0])
        con.executemany(f"INSERT INTO t VALUES ({placeholders})", rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")
    con.close()


def test_validate_research_tables(tmp_path: Path) -> None:
    root = tmp_path / "stage"
    _write(root / "WORK_MASTER" / "a.parquet", "id VARCHAR, _source_key VARCHAR", [("W1", "k1")])
    _write(
        root / "CITATION_EDGES" / "a.parquet",
        "work_id VARCHAR, referenced_work_id VARCHAR, _source_key VARCHAR",
        [("W1", "W0", "k1")],
    )
    result = validate_staged(root, ["WORK_MASTER", "CITATION_EDGES"])
    assert result["verified"] is True
    assert not result["errors"]


def test_duplicate_edge_fails(tmp_path: Path) -> None:
    root = tmp_path / "stage"
    _write(
        root / "WORK_TOPIC_EDGES" / "a.parquet",
        "work_id VARCHAR, topic_id VARCHAR, topic_score DOUBLE, _source_key VARCHAR",
        [("W1", "T1", 0.9, "k1"), ("W1", "T1", 0.8, "k1")],
    )
    result = validate_staged(root, ["WORK_TOPIC_EDGES"])
    assert result["verified"] is False
    assert any("duplicate" in e for e in result["errors"])
