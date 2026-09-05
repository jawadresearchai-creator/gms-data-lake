from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.sec_company_complete import build_complete_company_master


def test_complete_company_master(tmp_path: Path) -> None:
    cm = tmp_path / 'cm.parquet'
    fm = tmp_path / 'fm.parquet'
    con = duckdb.connect()
    con.execute('CREATE TABLE cm(canonical_company_id VARCHAR,cik VARCHAR,company_name VARCHAR,primary_ticker VARCHAR,ticker_count INTEGER)')
    con.executemany('INSERT INTO cm VALUES (?,?,?,?,?)', [
        ('SEC_CIK:0000000001','0000000001','Listed A','AAA',1),
        ('SEC_CIK:0000000002','0000000002','Ticker Only','BBB',1),
    ])
    con.execute(f"COPY cm TO '{cm.as_posix()}' (FORMAT PARQUET)")
    con.execute('''CREATE TABLE fm(canonical_filing_id VARCHAR,accession VARCHAR,accession_nodash VARCHAR,cik VARCHAR,canonical_company_id VARCHAR,company_name_at_filing VARCHAR,form VARCHAR,filing_date DATE,filing_year INTEGER,sec_filename VARCHAR,sec_url VARCHAR)''')
    con.executemany('INSERT INTO fm VALUES (?,?,?,?,?,?,?,?,?,?,?)', [
        ('F1','a','a','0000000001','SEC_CIK:0000000001','Listed A','10-K','2024-01-01',2024,'x','u'),
        ('F2','b','b','0000000003','SEC_CIK:0000000003','Private C','10-K','2024-02-01',2024,'y','v'),
    ])
    con.execute(f"COPY fm TO '{fm.as_posix()}' (FORMAT PARQUET)")
    con.close()

    out = tmp_path / 'out'
    m = build_complete_company_master(cm, fm, out)
    assert m['company_rows'] == 3
    assert m['filing_only_companies_added'] == 1
    assert m['company_filing_rows'] == 2
    assert m['uncovered_filings'] == 0

    con = duckdb.connect()
    row = con.execute(f"SELECT source_class,ticker_count FROM read_parquet('{(out/'COMPANY_MASTER_COMPLETE.parquet').as_posix()}') WHERE cik='0000000003'").fetchone()
    assert row == ('SEC_FILING', 0)
    con.close()
