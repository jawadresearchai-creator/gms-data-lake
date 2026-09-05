from __future__ import annotations

from pathlib import Path
import duckdb

from gmsdl.analytics.company_work_marts_validate import validate_company_work_marts


def _write(path: Path, ddl: str, rows: list[tuple]) -> None:
    con=duckdb.connect(); con.execute(f'CREATE TABLE t({ddl})')
    if rows:
        marks=','.join('?' for _ in rows[0]); con.executemany(f'INSERT INTO t VALUES ({marks})',rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)"); con.close()


def test_validate_company_work_marts(tmp_path: Path) -> None:
    prod=tmp_path/'prod.parquet'; research=tmp_path/'research.parquet'; topic=tmp_path/'topic.parquet'; collab=tmp_path/'collab.parquet'
    _write(prod,'canonical_company_id VARCHAR,openalex_institution_id VARCHAR',[('C1','I1')])
    _write(research,'canonical_company_id VARCHAR,publication_year INTEGER,work_count BIGINT,citation_sum BIGINT',[('C1',2024,5,20)])
    _write(topic,'canonical_company_id VARCHAR,openalex_institution_id VARCHAR,publication_year INTEGER,topic_id VARCHAR,work_count BIGINT,citation_sum BIGINT,topic_score_sum DOUBLE',[('C1','I1',2024,'T1',3,12,1.2)])
    _write(collab,'canonical_company_id VARCHAR,openalex_institution_id VARCHAR,publication_year INTEGER,collaborator_country_code VARCHAR,collaborative_work_count BIGINT,collaborator_institution_count BIGINT,citation_sum BIGINT',[('C1','I1',2024,'GB',2,3,8)])
    r=validate_company_work_marts(prod,research,topic,collab)
    assert r['verified'] is True
    assert r['errors']==[]
    assert r['topic_rows']==1
    assert r['collaboration_rows']==1
