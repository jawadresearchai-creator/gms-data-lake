from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.openalex_marts import build_partials, reduce_local


def _write(path: Path, ddl: str, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t({ddl})")
    if rows:
        marks = ",".join("?" for _ in rows[0])
        con.executemany(f"INSERT INTO t VALUES ({marks})", rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()


def test_build_partials_and_country_dedup(tmp_path: Path) -> None:
    work = tmp_path / "work.parquet"
    topic = tmp_path / "topic.parquet"
    inst = tmp_path / "inst.parquet"
    collab = tmp_path / "collab.parquet"
    out = tmp_path / "out"

    _write(
        work,
        "id VARCHAR, publication_year INTEGER, cited_by_count INTEGER",
        [("W1", 2024, 10), ("W2", 2024, 4), ("W3", 2025, 1)],
    )
    _write(
        topic,
        "work_id VARCHAR, topic_id VARCHAR, topic_score DOUBLE",
        [("W1", "T1", 0.8), ("W2", "T1", 0.5), ("W3", "T2", 0.9)],
    )
    _write(
        inst,
        "work_id VARCHAR, author_id VARCHAR, institution_id VARCHAR, institution_country_code VARCHAR",
        [
            ("W1", "A1", "I1", "US"),
            ("W1", "A2", "I2", "US"),
            ("W2", "A3", "I1", "US"),
            ("W3", "A4", "I3", "GB"),
        ],
    )
    _write(
        collab,
        "work_id VARCHAR, country_a VARCHAR, country_b VARCHAR",
        [("W1", "GB", "US"), ("W3", "DE", "GB")],
    )

    counts = build_partials(work, out, topic=topic, institution=inst, collaboration=collab)
    assert set(counts) == {
        "WORK_YEAR_METRICS",
        "WORK_YEAR_TOPIC",
        "WORK_YEAR_INSTITUTION",
        "WORK_YEAR_COUNTRY",
        "COUNTRY_COLLAB_YEAR",
    }

    con = duckdb.connect()
    us = con.execute(
        f"SELECT work_count,citation_sum FROM read_parquet('{(out / 'WORK_YEAR_COUNTRY.parquet').as_posix()}') "
        "WHERE publication_year=2024 AND country_code='US'"
    ).fetchone()
    assert us == (2, 14)
    yr = con.execute(
        f"SELECT work_count,citation_sum FROM read_parquet('{(out / 'WORK_YEAR_METRICS.parquet').as_posix()}') "
        "WHERE publication_year=2024"
    ).fetchone()
    assert yr == (2, 14)
    con.close()


def test_reduce_local_sums_partials(tmp_path: Path) -> None:
    partial = tmp_path / "partials"
    out = tmp_path / "final"
    _write(
        partial / "WORK_YEAR_METRICS" / "batch=000" / "a.parquet",
        "publication_year INTEGER, work_count BIGINT, citation_sum BIGINT",
        [(2024, 2, 14), (2025, 1, 1)],
    )
    _write(
        partial / "WORK_YEAR_METRICS" / "batch=001" / "b.parquet",
        "publication_year INTEGER, work_count BIGINT, citation_sum BIGINT",
        [(2024, 3, 6)],
    )

    result = reduce_local(partial, out)
    assert result["WORK_YEAR_METRICS"] == 2
    con = duckdb.connect()
    row = con.execute(
        f"SELECT work_count,citation_sum,mean_citations FROM read_parquet('{(out / 'WORK_YEAR_METRICS.parquet').as_posix()}') "
        "WHERE publication_year=2024"
    ).fetchone()
    assert row == (5, 20, 4.0)
    con.close()
