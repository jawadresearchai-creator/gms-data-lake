from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def validate_company_work_marts(
    production_bridge: Path,
    company_research_year: Path,
    company_topic_year: Path,
    company_collaboration_year: Path,
) -> dict:
    con = duckdb.connect(database=':memory:')
    errors: list[str] = []
    warnings: list[str] = []
    try:
        con.execute(f"CREATE VIEW prod AS SELECT * FROM read_parquet('{production_bridge.as_posix()}')")
        con.execute(f"CREATE VIEW research AS SELECT * FROM read_parquet('{company_research_year.as_posix()}')")
        con.execute(f"CREATE VIEW topic AS SELECT * FROM read_parquet('{company_topic_year.as_posix()}')")
        con.execute(f"CREATE VIEW collab AS SELECT * FROM read_parquet('{company_collaboration_year.as_posix()}')")

        topic_rows = int(con.execute('SELECT COUNT(*) FROM topic').fetchone()[0])
        collab_rows = int(con.execute('SELECT COUNT(*) FROM collab').fetchone()[0])
        prod_rows = int(con.execute('SELECT COUNT(*) FROM prod').fetchone()[0])

        checks: dict[str, int] = {}
        checks['topic_duplicate_keys'] = int(con.execute('''
            SELECT COUNT(*) FROM (
              SELECT canonical_company_id,publication_year,topic_id
              FROM topic GROUP BY 1,2,3 HAVING COUNT(*)>1
            )
        ''').fetchone()[0])
        checks['collaboration_duplicate_keys'] = int(con.execute('''
            SELECT COUNT(*) FROM (
              SELECT canonical_company_id,publication_year,collaborator_country_code
              FROM collab GROUP BY 1,2,3 HAVING COUNT(*)>1
            )
        ''').fetchone()[0])
        checks['topic_null_keys'] = int(con.execute("""
            SELECT COUNT(*) FROM topic
            WHERE canonical_company_id IS NULL OR canonical_company_id=''
               OR publication_year IS NULL OR topic_id IS NULL OR topic_id=''
        """).fetchone()[0])
        checks['collaboration_null_keys'] = int(con.execute("""
            SELECT COUNT(*) FROM collab
            WHERE canonical_company_id IS NULL OR canonical_company_id=''
               OR publication_year IS NULL
               OR collaborator_country_code IS NULL OR collaborator_country_code=''
        """).fetchone()[0])
        checks['topic_negative_metrics'] = int(con.execute('''
            SELECT COUNT(*) FROM topic
            WHERE work_count<0 OR citation_sum<0 OR topic_score_sum<0
        ''').fetchone()[0])
        checks['collaboration_negative_metrics'] = int(con.execute('''
            SELECT COUNT(*) FROM collab
            WHERE collaborative_work_count<0 OR collaborator_institution_count<0 OR citation_sum<0
        ''').fetchone()[0])
        checks['topic_nonproduction_leaks'] = int(con.execute('''
            SELECT COUNT(*) FROM topic t
            LEFT JOIN prod p USING (canonical_company_id)
            WHERE p.canonical_company_id IS NULL
        ''').fetchone()[0])
        checks['collaboration_nonproduction_leaks'] = int(con.execute('''
            SELECT COUNT(*) FROM collab c
            LEFT JOIN prod p USING (canonical_company_id)
            WHERE p.canonical_company_id IS NULL
        ''').fetchone()[0])
        checks['topic_institution_identity_mismatch'] = int(con.execute('''
            SELECT COUNT(*) FROM topic t
            JOIN prod p USING (canonical_company_id)
            WHERE t.openalex_institution_id<>p.openalex_institution_id
        ''').fetchone()[0])
        checks['collaboration_institution_identity_mismatch'] = int(con.execute('''
            SELECT COUNT(*) FROM collab c
            JOIN prod p USING (canonical_company_id)
            WHERE c.openalex_institution_id<>p.openalex_institution_id
        ''').fetchone()[0])

        # Topic and collaboration activity cannot exceed the company's total research
        # works/citations for the same year on any single topic/country row.
        checks['topic_row_work_exceeds_research_year'] = int(con.execute('''
            SELECT COUNT(*) FROM topic t
            JOIN research r USING (canonical_company_id,publication_year)
            WHERE t.work_count > r.work_count
        ''').fetchone()[0])
        checks['topic_row_citations_exceed_research_year'] = int(con.execute('''
            SELECT COUNT(*) FROM topic t
            JOIN research r USING (canonical_company_id,publication_year)
            WHERE t.citation_sum > r.citation_sum
        ''').fetchone()[0])
        checks['collaboration_row_work_exceeds_research_year'] = int(con.execute('''
            SELECT COUNT(*) FROM collab c
            JOIN research r USING (canonical_company_id,publication_year)
            WHERE c.collaborative_work_count > r.work_count
        ''').fetchone()[0])
        checks['collaboration_row_citations_exceed_research_year'] = int(con.execute('''
            SELECT COUNT(*) FROM collab c
            JOIN research r USING (canonical_company_id,publication_year)
            WHERE c.citation_sum > r.citation_sum
        ''').fetchone()[0])
        checks['topic_rows_without_research_year'] = int(con.execute('''
            SELECT COUNT(*) FROM topic t
            LEFT JOIN research r USING (canonical_company_id,publication_year)
            WHERE r.canonical_company_id IS NULL
        ''').fetchone()[0])
        checks['collaboration_rows_without_research_year'] = int(con.execute('''
            SELECT COUNT(*) FROM collab c
            LEFT JOIN research r USING (canonical_company_id,publication_year)
            WHERE r.canonical_company_id IS NULL
        ''').fetchone()[0])
        checks['collaborator_count_less_than_work_count_impossible'] = int(con.execute('''
            SELECT COUNT(*) FROM collab
            WHERE collaborator_institution_count < collaborative_work_count
        ''').fetchone()[0])

        for k, v in checks.items():
            if v:
                errors.append(f'{k}={v}')

        topic_companies = int(con.execute('SELECT COUNT(DISTINCT canonical_company_id) FROM topic').fetchone()[0])
        collab_companies = int(con.execute('SELECT COUNT(DISTINCT canonical_company_id) FROM collab').fetchone()[0])
        topic_years = con.execute('SELECT MIN(publication_year),MAX(publication_year) FROM topic').fetchone()
        collab_years = con.execute('SELECT MIN(publication_year),MAX(publication_year) FROM collab').fetchone()
        topic_count = int(con.execute('SELECT COUNT(DISTINCT topic_id) FROM topic').fetchone()[0])
        country_count = int(con.execute('SELECT COUNT(DISTINCT collaborator_country_code) FROM collab').fetchone()[0])

        # Aggregate sums across topics/countries can legitimately exceed company totals
        # because one work may map to multiple topics or collaborator countries.
        warnings.append('Aggregate topic/country sums are not required to equal COMPANY_RESEARCH_YEAR totals because works can belong to multiple topics and collaboration countries.')

        return {
            'verified': not errors,
            'errors': errors,
            'warnings': warnings,
            'production_bridge_rows': prod_rows,
            'topic_rows': topic_rows,
            'collaboration_rows': collab_rows,
            'topic_companies': topic_companies,
            'collaboration_companies': collab_companies,
            'distinct_topics': topic_count,
            'distinct_collaboration_countries': country_count,
            'topic_min_year': topic_years[0],
            'topic_max_year': topic_years[1],
            'collaboration_min_year': collab_years[0],
            'collaboration_max_year': collab_years[1],
            'checks': checks,
        }
    finally:
        con.close()


def main() -> int:
    p=argparse.ArgumentParser(description='Validate production-gated company topic/collaboration marts')
    p.add_argument('--production-bridge',type=Path,required=True)
    p.add_argument('--company-research-year',type=Path,required=True)
    p.add_argument('--company-topic-year',type=Path,required=True)
    p.add_argument('--company-collaboration-year',type=Path,required=True)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    result=validate_company_work_marts(a.production_bridge,a.company_research_year,a.company_topic_year,a.company_collaboration_year)
    text=json.dumps(result,indent=2,sort_keys=True)
    print(text)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(text+'\n',encoding='utf-8')
    return 0 if result['verified'] else 1

if __name__=='__main__':
    raise SystemExit(main())
