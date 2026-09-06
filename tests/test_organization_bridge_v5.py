from __future__ import annotations
import json
from pathlib import Path
import duckdb
from gmsdl.analytics.organization_bridge_v5 import build_v5_bridge


def _write(path: Path, ddl: str, rows: list[tuple]) -> None:
    con=duckdb.connect(); con.execute(f'CREATE TABLE t({ddl})')
    if rows:
        marks=','.join('?' for _ in rows[0]); con.executemany(f'INSERT INTO t VALUES ({marks})',rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)"); con.close()


def test_build_v5_bridge(tmp_path: Path) -> None:
    v3=tmp_path/'v3.parquet'; r=tmp_path/'r.parquet'; adj=tmp_path/'adj.json'; out=tmp_path/'out'
    ddl='canonical_company_id VARCHAR,openalex_institution_id VARCHAR,reclassification_decision VARCHAR'
    _write(v3,ddl,[('C1','I1','KEEP_PRODUCTION')])
    _write(r,ddl,[('C2','I2','KEEP_REVIEW'),('C3','I3','KEEP_QUARANTINE')])
    adj.write_text(json.dumps({'policy':'x','items':[{'canonical_company_id':'C2','decision':'PROMOTE'},{'canonical_company_id':'C3','decision':'KEEP_REVIEW'}]}),encoding='utf-8')
    m=build_v5_bridge(v3,r,adj,out)
    assert m['production_v5_rows']==2
    assert m['manual_promotions']==1
    assert m['kept_under_review_company_ids']==['C3']
