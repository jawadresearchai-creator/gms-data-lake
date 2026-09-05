from __future__ import annotations

from pathlib import Path
import duckdb
from gmsdl.analytics.company_research_year import build_company_year_marts


def test_build_company_year_marts(tmp_path: Path) -> None:
    org=tmp_path/'org.parquet'; prod=tmp_path/'prod.parquet'; wyi=tmp_path/'wyi.parquet'
    con=duckdb.connect()
    con.execute('''CREATE TABLE org(canonical_org_id VARCHAR,canonical_company_id VARCHAR,cik VARCHAR,company_name VARCHAR,primary_ticker VARCHAR,has_openalex_link BOOLEAN)''')
    con.executemany('INSERT INTO org VALUES (?,?,?,?,?,?)',[
        ('C1','C1','0000000001','One','ONE',True),
        ('C2','C2','0000000002','Two',None,True),
    ])
    con.execute(f"COPY org TO '{org.as_posix()}' (FORMAT PARQUET)")
    con.execute('''CREATE TABLE prod(canonical_company_id VARCHAR,openalex_institution_id VARCHAR,openalex_name VARCHAR,ror VARCHAR,country_code VARCHAR,institution_type VARCHAR,match_method VARCHAR,confidence DOUBLE,confidence_tier VARCHAR)''')
    con.execute("INSERT INTO prod VALUES ('C1','I1','One Research','r1','US','company','NORMALIZED_EXACT',1.0,'EXACT')")
    con.execute(f"COPY prod TO '{prod.as_posix()}' (FORMAT PARQUET)")
    con.execute('''CREATE TABLE wyi(publication_year INTEGER,institution_id VARCHAR,work_count BIGINT,citation_sum BIGINT,mean_citations DOUBLE)''')
    con.executemany('INSERT INTO wyi VALUES (?,?,?,?,?)',[(2023,'I1',2,10,5.0),(2024,'I1',3,9,3.0),(2024,'I2',100,500,5.0)])
    con.execute(f"COPY wyi TO '{wyi.as_posix()}' (FORMAT PARQUET)")
    con.close()
    out=tmp_path/'out'
    m=build_company_year_marts(org,prod,wyi,out)
    assert m['input_production_organizations']==1
    assert m['companies_with_research_rows']==1
    assert m['company_research_year_rows']==2
    assert m['qa']['nonproduction_leak_rows']==0
