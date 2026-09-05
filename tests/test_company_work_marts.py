from __future__ import annotations

from pathlib import Path
import duckdb

from gmsdl.analytics.company_work_marts import build_shard_partials, reduce_local


def _write(path: Path, ddl: str, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con=duckdb.connect(); con.execute(f'CREATE TABLE t({ddl})')
    if rows:
        marks=','.join('?' for _ in rows[0]); con.executemany(f'INSERT INTO t VALUES ({marks})',rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)"); con.close()


def test_build_shard_partials_deduplicates_collaboration_citations(tmp_path: Path) -> None:
    prod=tmp_path/'prod.parquet'; work=tmp_path/'work.parquet'; ai=tmp_path/'ai.parquet'; topic=tmp_path/'topic.parquet'; out=tmp_path/'out'
    _write(prod,'canonical_company_id VARCHAR, openalex_institution_id VARCHAR',[('C1','I1')])
    _write(work,'id VARCHAR, publication_year INTEGER, cited_by_count INTEGER',[('W1',2024,10),('W2',2024,4)])
    _write(ai,'work_id VARCHAR, author_id VARCHAR, institution_id VARCHAR, institution_country_code VARCHAR',[
        ('W1','A1','I1','US'),('W1','A2','I1','US'),('W1','A3','I2','GB'),('W1','A4','I3','GB'),
        ('W2','A5','I1','US'),('W2','A6','I4','DE')])
    _write(topic,'work_id VARCHAR, topic_id VARCHAR, topic_score DOUBLE',[('W1','T1',0.8),('W2','T1',0.7),('W2','T2',0.5)])
    counts=build_shard_partials(prod,work,ai,out,topic=topic)
    assert counts['COMPANY_TOPIC_YEAR']==2
    assert counts['COMPANY_COLLABORATION_YEAR']==2
    con=duckdb.connect()
    gb=con.execute(f"SELECT collaborative_work_count,collaborator_institution_count,citation_sum FROM read_parquet('{(out/'COMPANY_COLLABORATION_YEAR.parquet').as_posix()}') WHERE collaborator_country_code='GB'").fetchone()
    assert gb==(1,2,10)
    t1=con.execute(f"SELECT work_count,citation_sum FROM read_parquet('{(out/'COMPANY_TOPIC_YEAR.parquet').as_posix()}') WHERE topic_id='T1'").fetchone()
    assert t1==(2,14)
    con.close()


def test_reduce_local(tmp_path: Path) -> None:
    partial=tmp_path/'partials'; out=tmp_path/'out'
    _write(partial/'COMPANY_TOPIC_YEAR'/'batch=000'/'a.parquet','canonical_company_id VARCHAR,openalex_institution_id VARCHAR,publication_year INTEGER,topic_id VARCHAR,work_count BIGINT,citation_sum BIGINT,topic_score_sum DOUBLE',[('C1','I1',2024,'T1',2,14,1.5)])
    _write(partial/'COMPANY_TOPIC_YEAR'/'batch=001'/'b.parquet','canonical_company_id VARCHAR,openalex_institution_id VARCHAR,publication_year INTEGER,topic_id VARCHAR,work_count BIGINT,citation_sum BIGINT,topic_score_sum DOUBLE',[('C1','I1',2024,'T1',1,2,0.4)])
    _write(partial/'COMPANY_COLLABORATION_YEAR'/'batch=000'/'a.parquet','canonical_company_id VARCHAR,openalex_institution_id VARCHAR,publication_year INTEGER,collaborator_country_code VARCHAR,collaborative_work_count BIGINT,collaborator_institution_count BIGINT,citation_sum BIGINT',[('C1','I1',2024,'GB',1,2,10)])
    r=reduce_local(partial,out)
    assert r['COMPANY_TOPIC_YEAR']==1
    assert r['COMPANY_COLLABORATION_YEAR']==1
    con=duckdb.connect(); row=con.execute(f"SELECT work_count,citation_sum FROM read_parquet('{(out/'COMPANY_TOPIC_YEAR.parquet').as_posix()}')").fetchone(); con.close()
    assert row==(3,16)
