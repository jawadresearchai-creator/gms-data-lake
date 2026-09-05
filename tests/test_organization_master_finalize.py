from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.organization_master_finalize import finalize_organization_master


def test_finalize_organization_master(tmp_path: Path) -> None:
    cm = tmp_path/'cm.parquet'
    ex = tmp_path/'ex.parquet'
    sc = tmp_path/'sc.parquet'
    cand = tmp_path/'cand.parquet'
    con = duckdb.connect()
    con.execute('''CREATE TABLE cm(canonical_company_id VARCHAR,cik VARCHAR,company_name VARCHAR,primary_ticker VARCHAR,ticker_count INTEGER,in_ticker_master BOOLEAN,in_filing_universe BOOLEAN,filing_count BIGINT,first_filing_date DATE,latest_filing_date DATE,source_class VARCHAR)''')
    con.executemany('INSERT INTO cm VALUES (?,?,?,?,?,?,?,?,?,?,?)', [
        ('C1','0000000001','One','ONE',1,True,True,1,None,None,'SEC_TICKER+FILING'),
        ('C2','0000000002','Two',None,0,False,True,1,None,None,'SEC_FILING'),
        ('C3','0000000003','Three',None,0,False,True,1,None,None,'SEC_FILING'),
    ])
    con.execute(f"COPY cm TO '{cm.as_posix()}' (FORMAT PARQUET)")
    con.execute('''CREATE TABLE ex(canonical_company_id VARCHAR,cik VARCHAR,sec_name VARCHAR,primary_ticker VARCHAR,source_class VARCHAR,openalex_institution_id VARCHAR,openalex_name VARCHAR,ror VARCHAR,country_code VARCHAR,institution_type VARCHAR,normalized_name VARCHAR,sec_name_count BIGINT,openalex_name_count BIGINT,match_method VARCHAR,accepted BOOLEAN,confidence DOUBLE)''')
    con.execute("INSERT INTO ex VALUES ('C1','0000000001','One','ONE','SEC_TICKER+FILING','I1','One',NULL,'US','company','one',1,1,'NORMALIZED_EXACT',TRUE,1.0)")
    con.execute(f"COPY ex TO '{ex.as_posix()}' (FORMAT PARQUET)")
    con.execute('''CREATE TABLE sc(canonical_company_id VARCHAR,cik VARCHAR,sec_name VARCHAR,primary_ticker VARCHAR,source_class VARCHAR,openalex_institution_id VARCHAR,openalex_name VARCHAR,ror VARCHAR,country_code VARCHAR,institution_type VARCHAR,method VARCHAR,name_similarity DOUBLE,core_similarity DOUBLE,acronym_match BOOLEAN,unique_sec_core BOOLEAN,unique_openalex_core BOOLEAN,confidence DOUBLE,tier VARCHAR,accepted BOOLEAN,candidate_rank BIGINT,best_margin DOUBLE)''')
    con.execute("INSERT INTO sc VALUES ('C2','0000000002','Two',NULL,'SEC_FILING','I2','Two Ltd',NULL,'US','company','LEGAL_CORE_EXACT',1,1,FALSE,TRUE,TRUE,0.98,'HIGH',TRUE,NULL,NULL)")
    con.execute(f"COPY sc TO '{sc.as_posix()}' (FORMAT PARQUET)")
    con.execute('''CREATE TABLE cand AS SELECT * FROM sc WHERE 1=0''')
    con.execute("INSERT INTO cand VALUES ('C3','0000000003','Three',NULL,'SEC_FILING','I3','Three Labs',NULL,'US','company','FUZZY_CORE',0.91,0.91,FALSE,TRUE,TRUE,0.91,'REVIEW',FALSE,1,0.01)")
    con.execute(f"COPY cand TO '{cand.as_posix()}' (FORMAT PARQUET)")
    con.close()

    out = tmp_path/'out'
    m = finalize_organization_master(cm, ex, sc, cand, out)
    assert m['organization_rows'] == 3
    assert m['accepted_bridge_rows'] == 2
    assert m['exact_anchor_rows'] == 1
    assert m['high_confidence_scored_rows'] == 1
    assert m['review_queue_rows'] == 1
    assert m['linked_organizations'] == 2
