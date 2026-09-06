from __future__ import annotations

import argparse
import json
from pathlib import Path
import duckdb


def compare(base: Path, candidate: Path, candidate_bridge: Path) -> dict:
    con=duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW a AS SELECT * FROM read_parquet('{base.as_posix()}')")
        con.execute(f"CREATE VIEW b AS SELECT * FROM read_parquet('{candidate.as_posix()}')")
        con.execute(f"CREATE VIEW bridge AS SELECT * FROM read_parquet('{candidate_bridge.as_posix()}')")
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
            ORDER BY summed_work_count DESC, b.canonical_company_id
        ''').fetchall()
        cols=[x[0] for x in con.execute('''
            DESCRIBE SELECT canonical_company_id,ANY_VALUE(company_name) company_name,
            ANY_VALUE(openalex_institution_id) openalex_institution_id,COUNT(*) company_year_rows,
            MIN(publication_year) min_year,MAX(publication_year) max_year,
            SUM(work_count) summed_work_count,SUM(citation_sum) summed_citation_sum
            FROM b GROUP BY canonical_company_id
        ''').fetchall()]
        items=[dict(zip(cols,r)) for r in rows]
        base_companies=int(con.execute('SELECT COUNT(DISTINCT canonical_company_id) FROM a').fetchone()[0])
        candidate_companies=int(con.execute('SELECT COUNT(DISTINCT canonical_company_id) FROM b').fetchone()[0])
        bridge_rows=int(con.execute('SELECT COUNT(*) FROM bridge').fetchone()[0])
        new_rows=int(con.execute('''SELECT COUNT(*) FROM b WHERE NOT EXISTS (SELECT 1 FROM a WHERE a.canonical_company_id=b.canonical_company_id)''').fetchone()[0])
        new_works=sum(int(x['summed_work_count']) for x in items)
        new_citations=sum(int(x['summed_citation_sum']) for x in items)
    finally:
        con.close()
    return {
        'base_research_companies':base_companies,
        'candidate_research_companies':candidate_companies,
        'candidate_bridge_rows':bridge_rows,
        'new_companies_with_research':len(items),
        'new_company_year_rows':new_rows,
        'new_summed_work_count':new_works,
        'new_summed_citation_sum':new_citations,
        'new_research_companies':items,
    }


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--candidate-bridge',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(compare(a.base,a.candidate,a.candidate_bridge),indent=2,sort_keys=True,default=str))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
