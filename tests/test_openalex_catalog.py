from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from gmsdl.analytics.openalex_catalog import build_catalog


def _write_parquet(path: Path, ddl: str, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t({ddl})")
    placeholders = ",".join("?" for _ in rows[0]) if rows else ""
    if rows:
        con.executemany(f"INSERT INTO t VALUES ({placeholders})", rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()


def test_build_catalog_over_staged_tables(tmp_path: Path) -> None:
    root = tmp_path / "curated"
    _write_parquet(root / "WORK_MASTER" / "sample.parquet", "id VARCHAR, title VARCHAR", [("W1", "a"), ("W2", "b")])
    _write_parquet(root / "TOPIC_MASTER" / "sample.parquet", "id VARCHAR, display_name VARCHAR", [("T7", "topic")])

    db = tmp_path / "openalex.duckdb"
    meta = build_catalog(db, root)
    assert {t["table_name"] for t in meta["tables"]} == {"WORK_MASTER", "TOPIC_MASTER"}
    assert meta["catalog_version"] == "v2"
    assert set(meta["macros"]) >= {"work", "topic"}

    con = duckdb.connect(str(db), read_only=True)
    assert con.execute('SELECT COUNT(*) FROM oa."WORK_MASTER"').fetchone()[0] == 2
    assert con.execute('SELECT COUNT(*) FROM "TOPIC_MASTER"').fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM gms_catalog").fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM gms_meta.columns").fetchone()[0] >= 4
    assert con.execute("SELECT COUNT(*) FROM oa.work('W1')").fetchone()[0] == 1
    assert con.execute("SELECT row_count FROM oa.table_counts WHERE table_name='WORK_MASTER'").fetchone()[0] == 2
    con.close()


def test_research_join_macros(tmp_path: Path) -> None:
    root = tmp_path / "curated"
    _write_parquet(root / "WORK_MASTER" / "w.parquet", "id VARCHAR, title VARCHAR", [("W1", "Paper 1"), ("W2", "Paper 2")])
    _write_parquet(root / "AUTHOR_MASTER" / "a.parquet", "id VARCHAR, display_name VARCHAR", [("A1", "Ada"), ("A2", "Grace")])
    _write_parquet(root / "TOPIC_MASTER" / "t.parquet", "id VARCHAR, display_name VARCHAR", [("T1", "AI")])
    _write_parquet(root / "WORK_AUTHOR_EDGES" / "wa.parquet", "work_id VARCHAR, author_id VARCHAR", [("W1", "A1"), ("W1", "A2"), ("W2", "A1")])
    _write_parquet(root / "WORK_TOPIC_EDGES" / "wt.parquet", "work_id VARCHAR, topic_id VARCHAR", [("W1", "T1")])
    _write_parquet(root / "AUTHOR_INSTITUTION_EDGES" / "ai.parquet", "work_id VARCHAR, author_id VARCHAR, institution_id VARCHAR", [("W1", "A1", "I1")])
    _write_parquet(root / "COUNTRY_COLLAB_EDGES" / "cc.parquet", "work_id VARCHAR, country_a VARCHAR, country_b VARCHAR, _source_key VARCHAR", [("W1", "PK", "US", "k")])
    _write_parquet(root / "CITATION_EDGES" / "c.parquet", "work_id VARCHAR, referenced_work_id VARCHAR", [("W1", "W0"), ("W2", "W1")])

    db = tmp_path / "openalex.duckdb"
    meta = build_catalog(db, root)
    assert set(meta["macros"]) >= {
        "work_authors", "work_topics", "references_from", "citations_to",
        "author_works", "coauthors", "institution_works", "country_collaborations"
    }

    con = duckdb.connect(str(db), read_only=True)
    assert con.execute("SELECT display_name FROM oa.work_authors('W1') ORDER BY display_name").fetchone()[0] == "Ada"
    assert con.execute("SELECT display_name FROM oa.work_topics('W1')").fetchone()[0] == "AI"
    assert con.execute("SELECT title FROM oa.author_works('A1') ORDER BY work_id").fetchone()[0] == "Paper 1"
    assert con.execute("SELECT coauthor_id,shared_work_count FROM oa.coauthors('A1')").fetchone() == ("A2", 1)
    assert con.execute("SELECT title FROM oa.institution_works('I1')").fetchone()[0] == "Paper 1"
    assert con.execute("SELECT partner_country FROM oa.country_collaborations('PK')").fetchone()[0] == "US"
    assert con.execute("SELECT referenced_work_id FROM oa.references_from('W1')").fetchone()[0] == "W0"
    assert con.execute("SELECT work_id FROM oa.citations_to('W1')").fetchone()[0] == "W2"
    con.close()


def test_required_table_validation(tmp_path: Path) -> None:
    root = tmp_path / "curated"
    _write_parquet(root / "WORK_MASTER" / "sample.parquet", "id VARCHAR", [("W1",)])
    with pytest.raises(RuntimeError, match="required OpenAlex tables not staged"):
        build_catalog(tmp_path / "x.duckdb", root, required=["WORK_MASTER", "AUTHOR_MASTER"])
