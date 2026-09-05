from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

ALLOWED_METHODS = {'NORMALIZED_EXACT', 'LEGAL_CORE_EXACT'}
MIN_CONFIDENCE = 0.98


def promote_bridge(accepted_bridge: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW acc AS SELECT * FROM read_parquet('{accepted_bridge.as_posix()}')")
        con.execute('''
            CREATE TABLE classified AS
            SELECT *,
              CASE
                WHEN confidence < 0.98 THEN 'LOW_CONFIDENCE'
                WHEN match_method NOT IN ('NORMALIZED_EXACT','LEGAL_CORE_EXACT') THEN 'METHOD_NOT_PRODUCTION_APPROVED'
                WHEN institution_type IS NULL OR lower(institution_type)<>'company' THEN 'OPENALEX_TYPE_NOT_COMPANY'
                WHEN ror IS NULL OR trim(ror)='' THEN 'ROR_MISSING'
                ELSE NULL
              END AS quarantine_reason
            FROM acc
        ''')
        con.execute('CREATE TABLE production AS SELECT * EXCLUDE(quarantine_reason) FROM classified WHERE quarantine_reason IS NULL')
        con.execute('CREATE TABLE quarantine AS SELECT * FROM classified WHERE quarantine_reason IS NOT NULL')

        total = int(con.execute('SELECT COUNT(*) FROM acc').fetchone()[0])
        production = int(con.execute('SELECT COUNT(*) FROM production').fetchone()[0])
        quarantined = int(con.execute('SELECT COUNT(*) FROM quarantine').fetchone()[0])
        dup_company = int(con.execute('''SELECT COUNT(*) FROM (SELECT canonical_company_id FROM production GROUP BY canonical_company_id HAVING COUNT(*)>1)''').fetchone()[0])
        dup_inst = int(con.execute('''SELECT COUNT(*) FROM (SELECT openalex_institution_id FROM production GROUP BY openalex_institution_id HAVING COUNT(*)>1)''').fetchone()[0])
        bad_conf = int(con.execute('SELECT COUNT(*) FROM production WHERE confidence<0.98').fetchone()[0])
        bad_type = int(con.execute("SELECT COUNT(*) FROM production WHERE institution_type IS NULL OR lower(institution_type)<>'company'").fetchone()[0])
        missing_ror = int(con.execute("SELECT COUNT(*) FROM production WHERE ror IS NULL OR trim(ror)='' ").fetchone()[0])
        bad_method = int(con.execute("SELECT COUNT(*) FROM production WHERE match_method NOT IN ('NORMALIZED_EXACT','LEGAL_CORE_EXACT')").fetchone()[0])
        if dup_company or dup_inst or bad_conf or bad_type or missing_ror or bad_method:
            raise RuntimeError(f'production bridge QA failed: dup_company={dup_company} dup_inst={dup_inst} bad_conf={bad_conf} bad_type={bad_type} missing_ror={missing_ror} bad_method={bad_method}')

        reasons = {str(k): int(v) for k,v in con.execute('SELECT quarantine_reason,COUNT(*) FROM quarantine GROUP BY quarantine_reason ORDER BY quarantine_reason').fetchall()}
        methods = {str(k): int(v) for k,v in con.execute('SELECT match_method,COUNT(*) FROM production GROUP BY match_method ORDER BY match_method').fetchall()}
        countries = {str(k): int(v) for k,v in con.execute("SELECT COALESCE(country_code,'<NULL>'),COUNT(*) FROM production GROUP BY 1 ORDER BY 2 DESC").fetchall()}

        con.execute(f"COPY production TO '{(out_dir/'SEC_OPENALEX_ORG_PRODUCTION_BRIDGE.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY quarantine TO '{(out_dir/'SEC_OPENALEX_ORG_QUARANTINE.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    manifest = {
        'version':'v1',
        'accepted_name_logic_rows':total,
        'production_approved_rows':production,
        'quarantined_rows':quarantined,
        'production_policy':{
            'min_confidence':MIN_CONFIDENCE,
            'allowed_methods':sorted(ALLOWED_METHODS),
            'required_openalex_type':'company',
            'ror_required':True,
            'country_required':False,
        },
        'quarantine_reason_counts':reasons,
        'production_method_counts':methods,
        'production_country_counts':countries,
    }
    (out_dir/'organization_bridge_promotion_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return manifest


def main() -> int:
    p=argparse.ArgumentParser(description='Promote validated SEC/OpenAlex links to production or quarantine')
    p.add_argument('--accepted-bridge',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(promote_bridge(a.accepted_bridge,a.out_dir),indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
