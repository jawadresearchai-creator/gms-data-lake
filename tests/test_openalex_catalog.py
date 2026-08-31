from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.openalex_catalog import build_catalog


def _write_parquet(path: Path, rows: list[tuple[int, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE t(id INTEGER, label VARCHAR)")
    con.executemany("INSERT INTO t VALUES (?,?)", rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()


def test_build_catalog_over_staged_tables(tmp_path: Path) -> None:
    root = tmp_path / "curated"
    _write_parquet(root / "WORK_MASTER" / "sample.parquet", [(1, "a"), (2, "b")])
    _write_parquet(root / "TOPIC_MASTER" / "sample.parquet", [(7, "topic")])

    db = tmp_path / "openalex.duckdb"
    meta = build_catalog(db, root)
    assert {t["table_name"] for t in meta["tables"]} == {"WORK_MASTER", "TOPIC_MASTER"}

    con = duckdb.connect(str(db), read_only=True)
    assert con.execute('SELECT COUNT(*) FROM "WORK_MASTER"').fetchone()[0] == 2
    assert con.execute('SELECT COUNT(*) FROM "TOPIC_MASTER"').fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM gms_catalog").fetchone()[0] == 2
    con.close()
