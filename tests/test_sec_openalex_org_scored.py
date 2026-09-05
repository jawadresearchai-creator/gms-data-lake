from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.sec_openalex_org_scored import build_scored_bridge


def test_scored_org_bridge(tmp_path: Path) -> None:
    cm = tmp_path/'cm.parquet'
    inst_root = tmp_path/'inst'; inst_root.mkdir()
    inst = inst_root/'part.parquet'
    exact = tmp_path/'exact.parquet'
    con = duckdb.connect()
    con.execute('''CREATE TABLE cm(canonical_company_id VARCHAR,cik VARCHAR,company_name VARCHAR,primary_ticker VARCHAR,ticker_count INTEGER,in_ticker_master BOOLEAN,in_filing_universe BOOLEAN,filing_count BIGINT,first_filing_date DATE,latest_filing_date DATE,source_class VARCHAR)''')
    con.executemany('INSERT INTO cm VALUES (?,?,?,?,?,?,?,?,?,?,?)', [
        ('C0','0000000000','Exact Anchor Inc','EX',1,True,True,1,None,None,'SEC_TICKER+FILING'),
        ('C1','0000000001','Alpha Technologies Corporation','ALP',1,True,True,1,None,None,'SEC_TICKER+FILING'),
        ('C2','0000000002','Beta Systems Holdings',None,0,False,True,1,None,None,'SEC_FILING'),
    ])
    con.execute(f"COPY cm TO '{cm.as_posix()}' (FORMAT PARQUET)")
    con.execute('CREATE TABLE inst(id VARCHAR,display_name VARCHAR,ror VARCHAR,country_code VARCHAR,type VARCHAR)')
    con.executemany('INSERT INTO inst VALUES (?,?,?,?,?)', [
        ('I0','Exact Anchor Inc',None,'US','company'),
        ('I1','Alpha Technologies',None,'US','company'),
        ('I2','Beta System Holdings',None,'US','company'),
        ('I3','Beta Systems Holding',None,'US','education'),
    ])
    con.execute(f"COPY inst TO '{inst.as_posix()}' (FORMAT PARQUET)")
    con.execute('CREATE TABLE ex(canonical_company_id VARCHAR,openalex_institution_id VARCHAR)')
    con.execute("INSERT INTO ex VALUES ('C0','I0')")
    con.execute(f"COPY ex TO '{exact.as_posix()}' (FORMAT PARQUET)")
    con.close()

    out = tmp_path/'out'
    m = build_scored_bridge(cm, inst_root, exact, out)
    assert m['preserved_exact_matches'] == 1
    assert m['new_accepted_matches'] >= 1
    assert m['new_accepted_by_method']['LEGAL_CORE_EXACT'] == 1
    assert m['total_accepted_including_exact'] >= 2
