from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def validate_bridge(org_master: Path, accepted_bridge: Path, scored_candidates: Path, review_queue: Path) -> dict:
    con = duckdb.connect(database=':memory:')
    errors: list[str] = []
    warnings: list[str] = []
    try:
        con.execute(f"CREATE VIEW org AS SELECT * FROM read_parquet('{org_master.as_posix()}')")
        con.execute(f"CREATE VIEW acc AS SELECT * FROM read_parquet('{accepted_bridge.as_posix()}')")
        con.execute(f"CREATE VIEW cand AS SELECT * FROM read_parquet('{scored_candidates.as_posix()}')")
        con.execute(f"CREATE VIEW review AS SELECT * FROM read_parquet('{review_queue.as_posix()}')")

        org_rows = int(con.execute('SELECT COUNT(*) FROM org').fetchone()[0])
        accepted_rows = int(con.execute('SELECT COUNT(*) FROM acc').fetchone()[0])
        linked_org_rows = int(con.execute('SELECT COUNT(*) FROM org WHERE has_openalex_link').fetchone()[0])
        review_rows = int(con.execute('SELECT COUNT(*) FROM review').fetchone()[0])

        dup_company = int(con.execute('''SELECT COUNT(*) FROM (SELECT canonical_company_id FROM acc GROUP BY canonical_company_id HAVING COUNT(*)>1)''').fetchone()[0])
        dup_openalex = int(con.execute('''SELECT COUNT(*) FROM (SELECT openalex_institution_id FROM acc GROUP BY openalex_institution_id HAVING COUNT(*)>1)''').fetchone()[0])
        null_keys = int(con.execute("SELECT COUNT(*) FROM acc WHERE canonical_company_id IS NULL OR canonical_company_id='' OR openalex_institution_id IS NULL OR openalex_institution_id='' ").fetchone()[0])
        bad_conf = int(con.execute("SELECT COUNT(*) FROM acc WHERE confidence IS NULL OR confidence<0.965 OR confidence>1.0").fetchone()[0])
        nonaccepted = int(con.execute("SELECT COUNT(*) FROM acc WHERE NOT accepted").fetchone()[0])
        exact_not_one = int(con.execute("SELECT COUNT(*) FROM acc WHERE provenance='exact_anchor' AND ABS(confidence-1.0)>1e-12").fetchone()[0])
        scored_bad_tier = int(con.execute("SELECT COUNT(*) FROM acc WHERE provenance='scored_matcher' AND confidence_tier<>'HIGH'").fetchone()[0])
        org_link_mismatch = int(con.execute('''
            SELECT COUNT(*) FROM (
              SELECT o.canonical_company_id,
                     o.has_openalex_link,
                     (a.canonical_company_id IS NOT NULL) AS bridge_link
              FROM org o LEFT JOIN acc a USING (canonical_company_id)
            ) x WHERE has_openalex_link<>bridge_link
        ''').fetchone()[0])

        # An accepted scored match must not be dominated by another candidate for the same company.
        dominated = int(con.execute('''
            SELECT COUNT(*)
            FROM acc a
            JOIN cand c ON c.canonical_company_id=a.canonical_company_id
            WHERE a.provenance='scored_matcher'
              AND NOT c.accepted
              AND c.confidence > a.confidence + 1e-12
        ''').fetchone()[0])

        # Review rows must remain excluded from accepted bridge and must be explicitly unaccepted.
        review_promoted = int(con.execute('''
            SELECT COUNT(*) FROM review r JOIN acc a USING (canonical_company_id)
        ''').fetchone()[0])
        review_marked_accepted = int(con.execute('SELECT COUNT(*) FROM review WHERE accepted').fetchone()[0])

        checks = {
            'duplicate_sec_company_links': dup_company,
            'duplicate_openalex_institution_links': dup_openalex,
            'null_accepted_keys': null_keys,
            'accepted_confidence_outside_policy': bad_conf,
            'accepted_rows_marked_unaccepted': nonaccepted,
            'exact_anchor_confidence_not_one': exact_not_one,
            'scored_accepted_not_high_tier': scored_bad_tier,
            'organization_master_link_flag_mismatches': org_link_mismatch,
            'accepted_matches_dominated_by_stronger_candidate': dominated,
            'review_companies_already_promoted': review_promoted,
            'review_rows_marked_accepted': review_marked_accepted,
        }
        for name, value in checks.items():
            if value:
                errors.append(f'{name}={value}')

        method_counts = {str(k): int(v) for k,v in con.execute('SELECT match_method,COUNT(*) FROM acc GROUP BY match_method ORDER BY match_method').fetchall()}
        provenance_counts = {str(k): int(v) for k,v in con.execute('SELECT provenance,COUNT(*) FROM acc GROUP BY provenance ORDER BY provenance').fetchall()}
        type_counts = {str(k): int(v) for k,v in con.execute("SELECT COALESCE(institution_type,'<NULL>'),COUNT(*) FROM acc GROUP BY 1 ORDER BY 2 DESC").fetchall()}
        ror_present = int(con.execute("SELECT COUNT(*) FROM acc WHERE ror IS NOT NULL AND trim(ror)<>''").fetchone()[0])
        country_present = int(con.execute("SELECT COUNT(*) FROM acc WHERE country_code IS NOT NULL AND trim(country_code)<>''").fetchone()[0])
        non_company_type = int(con.execute("SELECT COUNT(*) FROM acc WHERE institution_type IS NOT NULL AND lower(institution_type)<>'company'").fetchone()[0])
        if non_company_type:
            warnings.append(f'{non_company_type} accepted OpenAlex links have institution_type other than company; retained for audit, not automatically rejected')
        if country_present < accepted_rows:
            warnings.append(f'{accepted_rows-country_present} accepted OpenAlex links have no country_code')
        warnings.append('SEC issuer country/address is not present in COMPANY_MASTER_COMPLETE, so cross-source country consistency is not yet testable')

        if linked_org_rows != accepted_rows:
            errors.append(f'linked_org_rows={linked_org_rows} differs from accepted_rows={accepted_rows}')

        result = {
            'verified': not errors,
            'errors': errors,
            'warnings': warnings,
            'organization_rows': org_rows,
            'accepted_rows': accepted_rows,
            'linked_organization_rows': linked_org_rows,
            'review_queue_rows': review_rows,
            'checks': checks,
            'accepted_method_counts': method_counts,
            'accepted_provenance_counts': provenance_counts,
            'accepted_openalex_type_counts': type_counts,
            'accepted_with_ror': ror_present,
            'accepted_with_country_code': country_present,
            'country_cross_source_validation_available': False,
        }
    finally:
        con.close()
    return result


def main() -> int:
    p = argparse.ArgumentParser(description='Validate accepted SEC/OpenAlex organization links before research use')
    p.add_argument('--organization-master', type=Path, required=True)
    p.add_argument('--accepted-bridge', type=Path, required=True)
    p.add_argument('--scored-candidates', type=Path, required=True)
    p.add_argument('--review-queue', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    result = validate_bridge(a.organization_master, a.accepted_bridge, a.scored_candidates, a.review_queue)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text+'\n', encoding='utf-8')
    return 0 if result['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
