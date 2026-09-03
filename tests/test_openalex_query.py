from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from gmsdl.analytics.openalex_query import execute_query, normalize_query


def _make_db(path: Path) -> None:
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE works(id INTEGER, title VARCHAR)")
    con.execute("INSERT INTO works VALUES (1,'a'),(2,'b')")
    con.close()


def test_execute_query_parquet(tmp_path: Path) -> None:
    db = tmp_path / "q.duckdb"
    _make_db(db)
    out = tmp_path / "result.parquet"
    meta = execute_query(db_path=db, sql="SELECT * FROM works ORDER BY id", output=out)
    assert meta["row_count"] == 2
    assert meta["columns"] == ["id", "title"]
    assert len(meta["sha256"]) == 64
    con = duckdb.connect()
    assert con.execute(f"SELECT COUNT(*) FROM read_parquet('{out.as_posix()}')").fetchone()[0] == 2
    con.close()


def test_rejects_non_read_only_query() -> None:
    with pytest.raises(ValueError, match="SELECT/WITH"):
        normalize_query("DELETE FROM works")
