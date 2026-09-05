from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.openalex_mart_validate import validate


def _write(path: Path, ddl: str, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t({ddl})")
    con.executemany("INSERT INTO t VALUES (" + ",".join("?" for _ in rows[0]) + ")", rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")
    con.close()


def test_validate_marts(tmp_path: Path) -> None:
    _write(tmp_path/'WORK_YEAR_METRICS'/'p.parquet', 'publication_year INTEGER, work_count BIGINT, citation_sum BIGINT, mean_citations DOUBLE', [(2024,2,10,5.0)])
    _write(tmp_path/'WORK_YEAR_TOPIC'/'p.parquet', 'publication_year INTEGER, topic_id VARCHAR, work_count BIGINT, citation_sum BIGINT, topic_score_sum DOUBLE, mean_citations DOUBLE', [(2024,'T1',2,10,1.5,5.0)])
    _write(tmp_path/'WORK_YEAR_INSTITUTION'/'p.parquet', 'publication_year INTEGER, institution_id VARCHAR, work_count BIGINT, citation_sum BIGINT, mean_citations DOUBLE', [(2024,'I1',2,10,5.0)])
    _write(tmp_path/'WORK_YEAR_COUNTRY'/'p.parquet', 'publication_year INTEGER, country_code VARCHAR, work_count BIGINT, citation_sum BIGINT, mean_citations DOUBLE', [(2024,'US',2,10,5.0)])
    _write(tmp_path/'COUNTRY_COLLAB_YEAR'/'p.parquet', 'publication_year INTEGER, country_a VARCHAR, country_b VARCHAR, work_count BIGINT, citation_sum BIGINT, mean_citations DOUBLE', [(2024,'GB','US',1,7,7.0)])
    result = validate(tmp_path)
    assert result['verified'] is True
    assert result['errors'] == []
