from __future__ import annotations

import argparse
import json
from pathlib import Path
import duckdb


def build_priority_review(reclassification: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con=duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW r AS SELECT * FROM read_parquet('{reclassification.as_posix()}')")
        cols={x[0] for x in con.execute('DESCRIBE SELECT * FROM r').fetchall()}
        wanted=[
            'canonical_company_id','cik','sec_name','primary_ticker','source_class',
            'openalex_institution_id','openalex_name','ror','institution_type',
            'confidence','match_method','confidence_tier','source_bucket',
            'sec_business_country_iso2','openalex_country_iso2','country_match','country_conflict',
            'reclassification_decision','reclassification_reason'
        ]
        select=[]
        for c in wanted:
            select.append(c if c in cols else f'NULL::VARCHAR AS {c}')
        con.execute('CREATE TABLE priority AS SELECT '+','.join(select)+" FROM r WHERE reclassification_decision='REVIEW_PRIORITY' ORDER BY confidence DESC NULLS LAST, canonical_company_id")
        rows=int(con.execute('SELECT COUNT(*) FROM priority').fetchone()[0])
        if rows==0:
            raise RuntimeError('no REVIEW_PRIORITY rows found')
        outpq=out_dir/'SEC_OPENALEX_ORG_PRIORITY_REVIEW.parquet'
        outcsv=out_dir/'SEC_OPENALEX_ORG_PRIORITY_REVIEW.csv'
        con.execute(f"COPY priority TO '{outpq.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY priority TO '{outcsv.as_posix()}' (HEADER, DELIMITER ',')")
        preview=con.execute('SELECT * FROM priority').fetchall()
        names=[x[0] for x in con.execute('DESCRIBE SELECT * FROM priority').fetchall()]
    finally:
        con.close()
    items=[dict(zip(names,row)) for row in preview]
    manifest={'version':'v1','priority_review_rows':rows,'items':items}
    (out_dir/'organization_priority_review.json').write_text(json.dumps(manifest,indent=2,sort_keys=True,default=str)+'\n',encoding='utf-8')
    return manifest


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--reclassification',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(build_priority_review(a.reclassification,a.out_dir),indent=2,sort_keys=True,default=str))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
