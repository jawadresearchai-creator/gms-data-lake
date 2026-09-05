from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def build_company_year_marts(org_master: Path, work_year_institution: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW org AS SELECT * FROM read_parquet('{org_master.as_posix()}')")
        con.execute(f"CREATE VIEW wyi AS SELECT * FROM read_parquet('{work_year_institution.as_posix()}')")

        linked_orgs = int(con.execute("SELECT COUNT(*) FROM org WHERE has_openalex_link").fetchone()[0])
        if linked_orgs == 0:
            raise RuntimeError('organization master has zero accepted OpenAlex links')

        dup_links = int(con.execute('''
            SELECT COUNT(*) FROM (
              SELECT openalex_institution_id FROM org
              WHERE has_openalex_link
              GROUP BY openalex_institution_id HAVING COUNT(*)>1
            )
        ''').fetchone()[0])
        if dup_links:
            raise RuntimeError(f'organization master has {dup_links} duplicate OpenAlex institution links')

        con.execute('''
            CREATE TABLE company_research_year AS
            SELECT
              o.canonical_org_id,
              o.canonical_company_id,
              o.cik,
              o.company_name,
              o.primary_ticker,
              o.openalex_institution_id,
              o.openalex_name,
              o.ror,
              o.openalex_country_code,
              o.openalex_institution_type,
              o.match_method,
              o.match_confidence,
              o.confidence_tier,
              w.publication_year,
              SUM(w.work_count)::BIGINT AS work_count,
              SUM(w.citation_sum)::BIGINT AS citation_sum,
              CAST(SUM(w.citation_sum) AS DOUBLE)/NULLIF(SUM(w.work_count),0) AS mean_citations
            FROM org o
            JOIN wyi w ON w.institution_id=o.openalex_institution_id
            WHERE o.has_openalex_link
            GROUP BY
              o.canonical_org_id,o.canonical_company_id,o.cik,o.company_name,o.primary_ticker,
              o.openalex_institution_id,o.openalex_name,o.ror,o.openalex_country_code,
              o.openalex_institution_type,o.match_method,o.match_confidence,o.confidence_tier,
              w.publication_year
        ''')

        con.execute('''
            CREATE TABLE company_citation_year AS
            SELECT
              canonical_org_id,
              canonical_company_id,
              cik,
              company_name,
              primary_ticker,
              openalex_institution_id,
              publication_year,
              work_count,
              citation_sum,
              mean_citations AS citations_per_work,
              match_method,
              match_confidence,
              confidence_tier
            FROM company_research_year
        ''')

        research_rows = int(con.execute('SELECT COUNT(*) FROM company_research_year').fetchone()[0])
        citation_rows = int(con.execute('SELECT COUNT(*) FROM company_citation_year').fetchone()[0])
        companies_with_research = int(con.execute('SELECT COUNT(DISTINCT canonical_org_id) FROM company_research_year').fetchone()[0])
        years = con.execute('SELECT MIN(publication_year),MAX(publication_year) FROM company_research_year').fetchone()
        duplicate_keys = int(con.execute('''
            SELECT COUNT(*) FROM (
              SELECT canonical_org_id,publication_year FROM company_research_year
              GROUP BY canonical_org_id,publication_year HAVING COUNT(*)>1
            )
        ''').fetchone()[0])
        negative = int(con.execute('''SELECT COUNT(*) FROM company_research_year WHERE work_count<0 OR citation_sum<0 OR mean_citations<0''').fetchone()[0])
        review_leak = int(con.execute('''SELECT COUNT(*) FROM company_research_year WHERE confidence_tier NOT IN ('EXACT','HIGH')''').fetchone()[0])
        if duplicate_keys or negative or review_leak:
            raise RuntimeError(f'company-year QA failed: duplicate_keys={duplicate_keys} negative_metrics={negative} review_leak={review_leak}')

        research_out = out_dir/'COMPANY_RESEARCH_YEAR.parquet'
        citation_out = out_dir/'COMPANY_CITATION_YEAR.parquet'
        con.execute(f"COPY company_research_year TO '{research_out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY company_citation_year TO '{citation_out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    manifest = {
        'version':'v1',
        'input_linked_organizations':linked_orgs,
        'companies_with_research_rows':companies_with_research,
        'companies_without_research_rows':linked_orgs-companies_with_research,
        'company_research_year_rows':research_rows,
        'company_citation_year_rows':citation_rows,
        'min_publication_year':years[0],
        'max_publication_year':years[1],
        'identity_policy':'accepted ORGANIZATION_MASTER links only; review queue excluded',
        'qa':{
            'duplicate_company_year_keys':duplicate_keys,
            'negative_metric_rows':negative,
            'review_candidate_leak_rows':review_leak,
        },
    }
    (out_dir/'company_research_year_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return manifest


def main() -> int:
    p=argparse.ArgumentParser(description='Build SEC/OpenAlex company-year research marts')
    p.add_argument('--organization-master',type=Path,required=True)
    p.add_argument('--work-year-institution',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(build_company_year_marts(a.organization_master,a.work_year_institution,a.out_dir),indent=2,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
