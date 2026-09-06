from __future__ import annotations

import argparse
import json
from pathlib import Path
import duckdb


def compare(v2: Path, v3: Path, v3_bridge: Path) -> dict:
    con=duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW a AS SELECT * FROM read_parquet('{v2.as_posix()}')")
        con.execute(f"CREATE VIEW b AS SELECT * FROM read_parquet('{v3.as_posix()}')")
        con.execute(f"CREATE VIEW bridge AS SELECT * FROM read_parquet('{v3_bridge.as_posix()}')")
        rows=con.execute('''
            SELECT b.canonical_company_id,
                   ANY_VALUE(b.company_name) AS company_name,
                   ANY_VALUE(b.openalex_institution_id) AS openalex_institution_id,
                   COUNT(*) AS company_year_rows,
                   MIN(b.publication_year) AS min_year,
                   MAX(b.publication_year) AS max_year,
                   SUM(b.work_count)::BIGINT AS summed_work_count,
                   SUM(b.citation_sum)::BIGINT AS summed_citation_sum
            FROM b
            WHERE NOT EXISTS (SELECT 1 FROM a WHERE a.canonical_company_id=b.canonical_company_id)
            GROUP BY b.canonical_company_id
            ORDER BY b.canonical_company_id
        ''').fetchall()
        cols=[x[0] for x in con.execute('DESCRIBE SELECT canonical_company_id,ANY_VALUE(company_name) company_name,ANY_VALUE(openalex_institution_id) openalex_institution_id,COUNT(*) company_year_rows,MIN(publication_year) min_year,MAX(publication_year) max_year,SUM(work_count) summed_work_count,SUM(citation_sum) summed_citation_sum FROM b GROUP BY canonical_company_id').fetchall()]
        items=[dict(zip(cols,r)) for r in rows]
        all_promoted=con.execute("SELECT canonical_company_id,openalex_institution_id,sec_name,openalex_name FROM bridge WHERE canonical_company_id IN ('SEC_CIK:0001549107','SEC_CIK:0001089113') ORDER BY canonical_company_id").fetchall()
        promoted_cols=['canonical_company_id','openalex_institution_id','sec_name','openalex_name']
        promoted=[dict(zip(promoted_cols,r)) for r in all_promoted]
    finally:
        con.close()
    return {'new_companies_with_research':len(items),'new_research_companies':items,'manual_promotions_in_v3':promoted}


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--v2',type=Path,required=True)
    p.add_argument('--v3',type=Path,required=True)
    p.add_argument('--v3-bridge',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(compare(a.v2,a.v3,a.v3_bridge),indent=2,sort_keys=True,default=str))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
