from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def build_v7_bridge(v6_bridge: Path, reclassification: Path, adjudication: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    decisions = json.loads(adjudication.read_text(encoding='utf-8'))
    promote_ids = [x['canonical_company_id'] for x in decisions.get('items', []) if x.get('decision') == 'PROMOTE']
    non_promote_ids = [x['canonical_company_id'] for x in decisions.get('items', []) if x.get('decision') != 'PROMOTE']

    con = duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW base AS SELECT * FROM read_parquet('{v6_bridge.as_posix()}')")
        con.execute(f"CREATE VIEW r AS SELECT * FROM read_parquet('{reclassification.as_posix()}')")
        con.execute('CREATE TEMP TABLE promote_ids(canonical_company_id VARCHAR)')
        if promote_ids:
            con.executemany('INSERT INTO promote_ids VALUES (?)', [(x,) for x in promote_ids])

        con.execute('''
            CREATE TABLE promoted AS
            SELECT r.*
            FROM r
            JOIN promote_ids p USING (canonical_company_id)
            WHERE NOT EXISTS (
              SELECT 1 FROM base b WHERE b.canonical_company_id=r.canonical_company_id
            )
        ''')
        found = int(con.execute('SELECT COUNT(*) FROM promoted').fetchone()[0])
        if found != len(promote_ids):
            raise RuntimeError(f'expected {len(promote_ids)} new manual promotions, found {found}')

        con.execute('''
            CREATE TABLE v7 AS
            SELECT * FROM base
            UNION BY NAME
            SELECT * FROM promoted
        ''')
        total = int(con.execute('SELECT COUNT(*) FROM v7').fetchone()[0])
        base_rows = int(con.execute('SELECT COUNT(*) FROM base').fetchone()[0])
        dup_company = int(con.execute('''SELECT COUNT(*) FROM (SELECT canonical_company_id FROM v7 GROUP BY canonical_company_id HAVING COUNT(*)>1)''').fetchone()[0])
        dup_inst = int(con.execute('''SELECT COUNT(*) FROM (SELECT openalex_institution_id FROM v7 GROUP BY openalex_institution_id HAVING COUNT(*)>1)''').fetchone()[0])
        null_keys = int(con.execute("SELECT COUNT(*) FROM v7 WHERE canonical_company_id IS NULL OR canonical_company_id='' OR openalex_institution_id IS NULL OR openalex_institution_id='' ").fetchone()[0])
        if dup_company or dup_inst or null_keys:
            raise RuntimeError(f'v7 bridge QA failed: duplicate_company={dup_company} duplicate_openalex={dup_inst} null_keys={null_keys}')

        out = out_dir / 'SEC_OPENALEX_ORG_PRODUCTION_BRIDGE_V7.parquet'
        con.execute(f"COPY v7 TO '{out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    manifest = {
        'version': 'v7',
        'v6_rows': base_rows,
        'manual_promotions': found,
        'production_v7_rows': total,
        'promoted_company_ids': promote_ids,
        'kept_or_rejected_company_ids': non_promote_ids,
        'adjudication_policy': decisions.get('policy'),
    }
    (out_dir / 'organization_bridge_v7_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description='Build v7 production organization bridge from manual adjudication')
    p.add_argument('--v6-bridge', type=Path, required=True)
    p.add_argument('--reclassification', type=Path, required=True)
    p.add_argument('--adjudication', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(build_v7_bridge(a.v6_bridge, a.reclassification, a.adjudication, a.out_dir), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
