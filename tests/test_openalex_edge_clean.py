from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.openalex_edge_clean import clean_edge_file


def _write(path: Path, ddl: str, rows: list[tuple]) -> None:
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t({ddl})")
    if rows:
        con.executemany(
            f"INSERT INTO t VALUES ({','.join('?' for _ in rows[0])})",
            rows,
        )
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")
    con.close()


def test_clean_work_author_edges(tmp_path: Path) -> None:
    src = tmp_path / "in.parquet"
    dst = tmp_path / "out.parquet"
    _write(
        src,
        "work_id VARCHAR, author_id VARCHAR, author_position VARCHAR, is_corresponding BOOLEAN, _source_key VARCHAR",
        [
            ("W1", "A1", "middle", False, "k"),
            ("W1", "A1", "first", True, "k"),
            ("W1", None, "last", False, "k"),
            ("W2", "A2", "last", False, "k"),
        ],
    )
    rows_in, rows_out = clean_edge_file("WORK_AUTHOR_EDGES", src, dst)
    assert rows_in == 4
    assert rows_out == 2
    con = duckdb.connect()
    row = con.execute(
        f"SELECT author_position,is_corresponding FROM read_parquet('{dst.as_posix()}') WHERE work_id='W1'"
    ).fetchone()
    assert row == ("first", True)
    con.close()


def test_clean_topic_and_institution_edges(tmp_path: Path) -> None:
    topic_src = tmp_path / "topic_in.parquet"
    topic_dst = tmp_path / "topic_out.parquet"
    _write(
        topic_src,
        "work_id VARCHAR, topic_id VARCHAR, topic_display_name VARCHAR, topic_score DOUBLE, _source_key VARCHAR",
        [("W1", "T1", "AI", 0.8, "k"), ("W1", "T1", "AI", 0.9, "k"), ("W1", None, "x", 1.0, "k")],
    )
    _, n = clean_edge_file("WORK_TOPIC_EDGES", topic_src, topic_dst)
    assert n == 1
    con = duckdb.connect()
    assert con.execute(f"SELECT topic_score FROM read_parquet('{topic_dst.as_posix()}')").fetchone()[0] == 0.9
    con.close()

    inst_src = tmp_path / "inst_in.parquet"
    inst_dst = tmp_path / "inst_out.parquet"
    _write(
        inst_src,
        "work_id VARCHAR, author_id VARCHAR, institution_id VARCHAR, institution_country_code VARCHAR, author_position VARCHAR, is_corresponding BOOLEAN, _source_key VARCHAR",
        [
            ("W1", "A1", "I1", "US", "middle", False, "k"),
            ("W1", "A1", "I1", "US", "first", True, "k"),
            ("W1", "A1", None, "US", "first", True, "k"),
        ],
    )
    _, n = clean_edge_file("AUTHOR_INSTITUTION_EDGES", inst_src, inst_dst)
    assert n == 1


def test_clean_citations_are_distinct_and_non_null(tmp_path: Path) -> None:
    src = tmp_path / "c_in.parquet"
    dst = tmp_path / "c_out.parquet"
    _write(
        src,
        "work_id VARCHAR, referenced_work_id VARCHAR, _source_key VARCHAR",
        [("W1", "W0", "k"), ("W1", "W0", "k"), ("W1", None, "k")],
    )
    _, n = clean_edge_file("CITATION_EDGES", src, dst)
    assert n == 1
