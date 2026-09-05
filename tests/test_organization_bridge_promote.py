from __future__ import annotations
from pathlib import Path
import duckdb
from gmsdl.analytics.organization_bridge_promote import promote_bridge

def test_promote_bridge(tmp_path: Path) -> None:
    src=tmp_path/'acc.parquet'; out=tmp_path/'out'
    con=duckdb.connect()
    con.execute('''CREATE TABLE acc(canonical_company_id VARCHAR,openalex_institution_id VARCHAR,confidence DOUBLE,match_method VARCHAR,institution_type VARCHAR,ror VARCHAR,country_code VARCHAR)''')
    con.executemany('INSERT INTO acc VALUES (?,?,?,?,?,?,?)',[
        ('C1','I1',1.0,'NORMALIZED_EXACT','company','r1','US'),
        ('C2','I2',0.98,'LEGAL_CORE_EXACT','education','r2','US'),
        ('C3','I3',0.97,'FUZZY_CORE','company','r3','GB'),
    ])
    con.execute(f"COPY acc TO '{src.as_posix()}' (FORMAT PARQUET)")
    con.close()
    m=promote_bridge(src,out)
    assert m['production_approved_rows']==1
    assert m['quarantined_rows']==2
    assert m['quarantine_reason_counts']['OPENALEX_TYPE_NOT_COMPANY']==1
    assert m['quarantine_reason_counts']['LOW_CONFIDENCE']==1
