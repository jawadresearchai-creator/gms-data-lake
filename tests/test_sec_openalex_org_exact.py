from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.sec_openalex_org_exact import build_exact_bridge


def test_exact_org_bridge_unique_only(tmp_path: Path) -> None:
    cm = tmp_path / 'cm.parquet'
    inst_root = tmp_path / 'inst'
    inst_root.mkdir()
    inst = inst_root / 'part.parquet'
    con = duckdb.connect()
    con.execute('''CREATE TABLE cm(canonical_company_id VARCHAR,cik VARCHAR,company_name VARCHAR,primary_ticker VARCHAR,ticker_count INTEGER,in_ticker_master BOOLEAN,in_filing_universe BOOLEAN,filing_count BIGINT,first_filing_date DATE,latest_filing_date DATE,source_class VARCHAR)''')
    con.executemany('INSERT INTO cm VALUES (?,?,?,?,?,?,?,?,?,?,?)', [
        ('C1','0000000001','Apple, Inc.','AAPL',1,True,True,1,None,None,'SEC_TICKER+FILING'),
        ('C2','0000000002','Common Name',None,0,False,True,1,None,None,'SEC_FILING'),
    ])
    con.execute(f"COPY cm TO '{cm.as_posix()}' (FORMAT PARQUET)")
    con.execute('CREATE TABLE inst(id VARCHAR,display_name VARCHAR,ror VARCHAR,country_code VARCHAR,type VARCHAR)')
    con.executemany('INSERT INTO inst VALUES (?,?,?,?,?)', [
        ('I1','Apple Inc','https://ror.org/1','US','company'),
        ('I2','Common Name',None,'US','company'),
        ('I3','Common-Name',None,'GB','education'),
    ])
    con.execute(f"COPY inst TO '{inst.as_posix()}' (FORMAT PARQUET)")
    con.close()

    out = tmp_path / 'out'
    m = build_exact_bridge(cm, inst_root, out)
    assert m['candidate_rows'] == 3
    assert m['accepted_rows'] == 1
    assert m['ambiguous_candidate_rows'] == 2

    con = duckdb.connect()
    row = con.execute(f"SELECT sec_name,openalex_name,confidence FROM read_parquet('{(out/'SEC_OPENALEX_ORG_EXACT_BRIDGE.parquet').as_posix()}')").fetchone()
    assert row == ('Apple, Inc.', 'Apple Inc', 1.0)
    con.close()
