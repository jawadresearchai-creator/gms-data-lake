from __future__ import annotations

from pathlib import Path
import duckdb

from gmsdl.analytics.organization_geo_reclassify import reclassify, sec_country_iso2


def _write(path: Path, ddl: str, rows: list[tuple]) -> None:
    con=duckdb.connect(); con.execute(f'CREATE TABLE t({ddl})')
    if rows:
        marks=','.join('?' for _ in rows[0]); con.executemany(f'INSERT INTO t VALUES ({marks})',rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)"); con.close()


def test_sec_country_iso2() -> None:
    assert sec_country_iso2('CA','CALIFORNIA',False)=='US'
    assert sec_country_iso2('A0','CANADA (FEDERAL LEVEL)',True)=='CA'
    assert sec_country_iso2('X9','UNITED KINGDOM',True)=='GB'


def test_geo_reclassification(tmp_path: Path) -> None:
    meta=tmp_path/'meta.parquet'; prod=tmp_path/'prod.parquet'; quarantine=tmp_path/'q.parquet'; review=tmp_path/'r.parquet'; out=tmp_path/'out'
    _write(meta,'canonical_company_id VARCHAR,business_state_or_country VARCHAR,business_state_or_country_description VARCHAR,business_is_foreign_location BOOLEAN',[
        ('C1','CA','CALIFORNIA',False),('C2','A0','CANADA (FEDERAL LEVEL)',True),('C3','NY','NEW YORK',False)])
    base='canonical_company_id VARCHAR,openalex_institution_id VARCHAR,confidence DOUBLE,match_method VARCHAR,institution_type VARCHAR,ror VARCHAR,country_code VARCHAR'
    _write(prod,base,[('C1','I1',1.0,'NORMALIZED_EXACT','company','r1','GB')])
    _write(quarantine,base+',quarantine_reason VARCHAR',[('C2','I2',0.98,'LEGAL_CORE_EXACT','education','r2','CA','OPENALEX_TYPE_NOT_COMPANY')])
    _write(review,'canonical_company_id VARCHAR,openalex_institution_id VARCHAR,confidence DOUBLE,method VARCHAR,institution_type VARCHAR,ror VARCHAR,country_code VARCHAR,accepted BOOLEAN',[
        ('C3','I3',0.97,'FUZZY_CORE','company','r3','US',False)])
    m=reclassify(meta,prod,quarantine,review,out)
    assert m['input_rows']==3
    assert m['country_conflict_rows']==1
    assert m['newly_promoted_rows']==1
    assert m['production_v2_rows']==1
    assert m['decision_counts']['REJECT']==1
    assert m['decision_counts']['REVIEW_PRIORITY']==1
    assert m['decision_counts']['PROMOTE']==1
