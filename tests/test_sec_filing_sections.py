from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

import gmsdl.analytics.sec_filing_sections as mod


def test_build_section_bridge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, 'EXPECTED_ROWS', 6)
    monkeypatch.setattr(mod, 'EXPECTED_FILINGS', 2)

    idx = tmp_path / 'idx.csv'
    pd.DataFrame([
        ['0000000001','Co A','2024-01-01','edgar/data/1/a.txt','u1','10','r1','Item1','OK','5','20','t1','v1'],
        ['0000000001','Co A','2024-01-01','edgar/data/1/a.txt','u1','10','r1','Item1A','NOT_FOUND','0','0','','v1'],
        ['0000000001','Co A','2024-01-01','edgar/data/1/a.txt','u1','10','r1','Item7','OK','7','30','t7','v1'],
        ['0000000002','Co B','2024-01-02','edgar/data/2/b.txt','u2','20','r2','Item1','OK','2','10','u1','v1'],
        ['0000000002','Co B','2024-01-02','edgar/data/2/b.txt','u2','20','r2','Item1A','OK','3','12','u2','v1'],
        ['0000000002','Co B','2024-01-02','edgar/data/2/b.txt','u2','20','r2','Item7','OK','4','16','u3','v1'],
    ], columns=['cik','company','filing_date','filename','sec_url','raw_bytes','raw_sha256','section','extract_status','word_count','char_count','text_sha256','parser_version']).to_csv(idx,index=False)

    fm = tmp_path / 'fm.parquet'
    con = duckdb.connect()
    con.execute('''CREATE TABLE f(canonical_filing_id VARCHAR, accession VARCHAR, accession_nodash VARCHAR, cik VARCHAR, canonical_company_id VARCHAR, company_name_at_filing VARCHAR, form VARCHAR, filing_date DATE, filing_year INTEGER, sec_filename VARCHAR, sec_url VARCHAR)''')
    con.executemany('INSERT INTO f VALUES (?,?,?,?,?,?,?,?,?,?,?)', [
        ('F1','a','a','0000000001','C1','Co A','10-K','2024-01-01',2024,'edgar/data/1/a.txt','u1'),
        ('F2','b','b','0000000002','C2','Co B','10-K','2024-01-02',2024,'edgar/data/2/b.txt','u2'),
        ('F3','c','c','0000000003','C3','Co C','10-K','2024-01-03',2024,'edgar/data/3/c.txt','u3'),
    ])
    con.execute(f"COPY f TO '{fm.as_posix()}' (FORMAT PARQUET)")
    con.close()

    out = tmp_path / 'out'
    manifest = mod.build_section_bridge(idx, fm, out)
    assert manifest['section_rows'] == 6
    assert manifest['covered_filings'] == 2
    assert manifest['uncovered_filings'] == 1
    assert manifest['extract_status_counts'] == {'NOT_FOUND': 1, 'OK': 5}
