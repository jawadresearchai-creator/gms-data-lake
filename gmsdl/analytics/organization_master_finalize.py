from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def finalize_organization_master(
    company_master: Path,
    exact_bridge: Path,
    scored_accepted: Path,
    scored_candidates: Path,
    out_dir: Path,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW cm AS SELECT * FROM read_parquet('{company_master.as_posix()}')")
        con.execute(f"CREATE VIEW ex AS SELECT * FROM read_parquet('{exact_bridge.as_posix()}')")
        con.execute(f"CREATE VIEW sc AS SELECT * FROM read_parquet('{scored_accepted.as_posix()}')")
        con.execute(f"CREATE VIEW cand AS SELECT * FROM read_parquet('{scored_candidates.as_posix()}')")

        # Normalize schemas into one accepted bridge. Exact anchors take precedence.
        con.execute('''
            CREATE TABLE accepted_union AS
            SELECT
              canonical_company_id,
              cik,
              sec_name,
              primary_ticker,
              source_class,
              openalex_institution_id,
              openalex_name,
              ror,
              country_code,
              institution_type,
              match_method,
              confidence,
              'EXACT' AS confidence_tier,
              TRUE AS accepted,
              'exact_anchor' AS provenance
            FROM ex
            UNION ALL
            SELECT
              s.canonical_company_id,
              s.cik,
              s.sec_name,
              s.primary_ticker,
              s.source_class,
              s.openalex_institution_id,
              s.openalex_name,
              s.ror,
              s.country_code,
              s.institution_type,
              s.method AS match_method,
              s.confidence,
              s.tier AS confidence_tier,
              s.accepted,
              'scored_matcher' AS provenance
            FROM sc s
            WHERE s.accepted
              AND NOT EXISTS (
                SELECT 1 FROM ex e
                WHERE e.canonical_company_id=s.canonical_company_id
                   OR e.openalex_institution_id=s.openalex_institution_id
              )
        ''')

        dup_company = int(con.execute('''
            SELECT COUNT(*) FROM (
              SELECT canonical_company_id FROM accepted_union GROUP BY canonical_company_id HAVING COUNT(*)>1
            )
        ''').fetchone()[0])
        dup_inst = int(con.execute('''
            SELECT COUNT(*) FROM (
              SELECT openalex_institution_id FROM accepted_union GROUP BY openalex_institution_id HAVING COUNT(*)>1
            )
        ''').fetchone()[0])
        null_keys = int(con.execute("SELECT COUNT(*) FROM accepted_union WHERE canonical_company_id IS NULL OR canonical_company_id='' OR openalex_institution_id IS NULL OR openalex_institution_id='' ").fetchone()[0])
        if dup_company or dup_inst or null_keys:
            raise RuntimeError(f'organization bridge QA failed: duplicate_company={dup_company} duplicate_openalex={dup_inst} null_keys={null_keys}')

        con.execute('''
            CREATE TABLE organization_master AS
            SELECT
              c.canonical_company_id AS canonical_org_id,
              c.canonical_company_id,
              c.cik,
              c.company_name,
              c.primary_ticker,
              c.ticker_count,
              c.in_ticker_master,
              c.in_filing_universe,
              c.filing_count,
              c.source_class,
              a.openalex_institution_id,
              a.openalex_name,
              a.ror,
              a.country_code AS openalex_country_code,
              a.institution_type AS openalex_institution_type,
              a.match_method,
              a.confidence AS match_confidence,
              a.confidence_tier,
              a.provenance AS match_provenance,
              (a.openalex_institution_id IS NOT NULL) AS has_openalex_link
            FROM cm c
            LEFT JOIN accepted_union a USING (canonical_company_id)
        ''')

        # Review queue: best unaccepted candidate per SEC company, excluding already accepted links.
        con.execute('''
            CREATE TABLE review_queue AS
            WITH ranked AS (
              SELECT c.*,
                     ROW_NUMBER() OVER (
                       PARTITION BY canonical_company_id
                       ORDER BY confidence DESC NULLS LAST, candidate_rank ASC NULLS LAST, openalex_institution_id
                     ) AS rn
              FROM cand c
              WHERE NOT accepted
            )
            SELECT r.*
            FROM ranked r
            WHERE rn=1
              AND NOT EXISTS (
                SELECT 1 FROM accepted_union a
                WHERE a.canonical_company_id=r.canonical_company_id
              )
        ''')

        org_rows = int(con.execute('SELECT COUNT(*) FROM organization_master').fetchone()[0])
        linked_rows = int(con.execute('SELECT COUNT(*) FROM organization_master WHERE has_openalex_link').fetchone()[0])
        unlinked_rows = org_rows - linked_rows
        exact_rows = int(con.execute("SELECT COUNT(*) FROM accepted_union WHERE confidence_tier='EXACT'").fetchone()[0])
        high_rows = int(con.execute("SELECT COUNT(*) FROM accepted_union WHERE confidence_tier='HIGH'").fetchone()[0])
        review_rows = int(con.execute('SELECT COUNT(*) FROM review_queue').fetchone()[0])
        accepted_rows = int(con.execute('SELECT COUNT(*) FROM accepted_union').fetchone()[0])

        if org_rows != int(con.execute('SELECT COUNT(*) FROM cm').fetchone()[0]):
            raise RuntimeError('organization master row count does not match complete company master')

        con.execute(f"COPY organization_master TO '{(out_dir/'ORGANIZATION_MASTER.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY accepted_union TO '{(out_dir/'SEC_OPENALEX_ORG_BRIDGE.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY review_queue TO '{(out_dir/'SEC_OPENALEX_ORG_REVIEW_QUEUE.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    manifest = {
        'version': 'v1',
        'organization_rows': org_rows,
        'accepted_bridge_rows': accepted_rows,
        'exact_anchor_rows': exact_rows,
        'high_confidence_scored_rows': high_rows,
        'linked_organizations': linked_rows,
        'unlinked_organizations': unlinked_rows,
        'review_queue_rows': review_rows,
        'policy': {
            'accepted': 'exact anchors plus scored rows explicitly marked accepted by the matcher',
            'one_to_one': True,
            'review_queue': 'best unaccepted scored candidate per still-unlinked SEC company',
            'canonical_org_id': 'inherits canonical SEC company id SEC_CIK:<10-digit-CIK>',
        },
    }
    (out_dir/'organization_master_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description='Finalize canonical organization master from SEC/OpenAlex bridge outputs')
    p.add_argument('--company-master', type=Path, required=True)
    p.add_argument('--exact-bridge', type=Path, required=True)
    p.add_argument('--scored-accepted', type=Path, required=True)
    p.add_argument('--scored-candidates', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(finalize_organization_master(a.company_master, a.exact_bridge, a.scored_accepted, a.scored_candidates, a.out_dir), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
