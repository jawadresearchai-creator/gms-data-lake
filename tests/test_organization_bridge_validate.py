from __future__ import annotations

from pathlib import Path
import duckdb
from gmsdl.analytics.organization_bridge_validate import validate_bridge


def test_validate_bridge(tmp_path: Path) -> None:
    con=duckdb.connect()
    org=tmp_path/'org.parquet'; acc=tmp_path/'acc.parquet'; cand=tmp_path/'cand.parquet'; rev=tmp_path/'rev.parquet'
    con.execute('CREATE TABLE org(canonical_company_id VARCHAR,has_openalex_link BOOLEAN)')
    con.executemany('INSERT INTO org VALUES (?,?)',[('C1',True),('C2',False)])
    con.execute(f"COPY org TO '{org.as_posix()}' (FORMAT PARQUET)")
    con.execute('''CREATE TABLE acc(canonical_company_id VARCHAR,openalex_institution_id VARCHAR,confidence DOUBLE,accepted BOOLEAN,provenance VARCHAR,confidence_tier VARCHAR,match_method VARCHAR,ror VARCHAR,country_code VARCHAR,institution_type VARCHAR)''')
    con.execute("INSERT INTO acc VALUES ('C1','I1',1.0,TRUE,'exact_anchor','EXACT','NORMALIZED_EXACT','r','US','company')")
    con.execute(f"COPY acc TO '{acc.as_posix()}' (FORMAT PARQUET)")
    con.execute('''CREATE TABLE cand(canonical_company_id VARCHAR,openalex_institution_id VARCHAR,confidence DOUBLE,accepted BOOLEAN)''')
    con.execute("INSERT INTO cand VALUES ('C2','I2',0.91,FALSE)")
    con.execute(f"COPY cand TO '{cand.as_posix()}' (FORMAT PARQUET)")
    con.execute('''CREATE TABLE rev(canonical_company_id VARCHAR,openalex_institution_id VARCHAR,confidence DOUBLE,accepted BOOLEAN)''')
    con.execute("INSERT INTO rev VALUES ('C2','I2',0.91,FALSE)")
    con.execute(f"COPY rev TO '{rev.as_posix()}' (FORMAT PARQUET)")
    con.close()
    r=validate_bridge(org,acc,cand,rev)
    assert r['verified'] is True
    assert r['accepted_rows']==1
    assert r['review_queue_rows']==1
