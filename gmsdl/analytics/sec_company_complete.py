from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def build_complete_company_master(company_master: Path, filing_master: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW cm AS SELECT * FROM read_parquet('{company_master.as_posix()}')")
        con.execute(f"CREATE VIEW fm AS SELECT * FROM read_parquet('{filing_master.as_posix()}')")
        con.execute('''
            CREATE TABLE company_complete AS
            WITH filing_names AS (
              SELECT canonical_company_id, cik,
                     arg_max(company_name_at_filing, filing_date) AS filing_company_name,
                     COUNT(*)::BIGINT AS filing_count,
                     MIN(filing_date) AS first_filing_date,
                     MAX(filing_date) AS latest_filing_date
              FROM fm
              GROUP BY canonical_company_id, cik
            ), ids AS (
              SELECT canonical_company_id FROM cm
              UNION
              SELECT canonical_company_id FROM filing_names
            )
            SELECT ids.canonical_company_id,
                   COALESCE(cm.cik, f.cik) AS cik,
                   COALESCE(cm.company_name, f.filing_company_name) AS company_name,
                   cm.primary_ticker,
                   COALESCE(cm.ticker_count, 0)::INTEGER AS ticker_count,
                   (cm.canonical_company_id IS NOT NULL) AS in_ticker_master,
                   (f.canonical_company_id IS NOT NULL) AS in_filing_universe,
                   COALESCE(f.filing_count, 0)::BIGINT AS filing_count,
                   f.first_filing_date,
                   f.latest_filing_date,
                   CASE
                     WHEN cm.canonical_company_id IS NOT NULL AND f.canonical_company_id IS NOT NULL THEN 'SEC_TICKER+FILING'
                     WHEN cm.canonical_company_id IS NOT NULL THEN 'SEC_TICKER'
                     ELSE 'SEC_FILING'
                   END AS source_class
            FROM ids
            LEFT JOIN cm USING (canonical_company_id)
            LEFT JOIN filing_names f USING (canonical_company_id)
        ''')
        con.execute('''
            CREATE TABLE company_filing_complete AS
            SELECT f.canonical_company_id,
                   f.canonical_filing_id,
                   f.cik,
                   f.accession,
                   f.filing_date,
                   c.company_name,
                   c.primary_ticker,
                   c.ticker_count,
                   c.source_class
            FROM fm f
            JOIN company_complete c USING (canonical_company_id)
        ''')

        company_rows = int(con.execute('SELECT COUNT(*) FROM company_complete').fetchone()[0])
        filing_rows = int(con.execute('SELECT COUNT(*) FROM company_filing_complete').fetchone()[0])
        ticker_rows = int(con.execute('SELECT COUNT(*) FROM company_complete WHERE in_ticker_master').fetchone()[0])
        filing_companies = int(con.execute('SELECT COUNT(*) FROM company_complete WHERE in_filing_universe').fetchone()[0])
        filing_only = int(con.execute("SELECT COUNT(*) FROM company_complete WHERE source_class='SEC_FILING'").fetchone()[0])
        dup_ids = int(con.execute('SELECT COUNT(*)-COUNT(DISTINCT canonical_company_id) FROM company_complete').fetchone()[0])
        null_keys = int(con.execute("SELECT COUNT(*) FROM company_complete WHERE canonical_company_id IS NULL OR canonical_company_id='' OR cik IS NULL OR cik='' ").fetchone()[0])
        uncovered = int(con.execute('''SELECT COUNT(*) FROM fm f LEFT JOIN company_complete c USING (canonical_company_id) WHERE c.canonical_company_id IS NULL''').fetchone()[0])
        if dup_ids or null_keys or uncovered:
            raise RuntimeError(f'complete company QA failed: dup_ids={dup_ids} null_keys={null_keys} uncovered_filings={uncovered}')

        company_out = out_dir / 'COMPANY_MASTER_COMPLETE.parquet'
        bridge_out = out_dir / 'COMPANY_FILING_BRIDGE_COMPLETE.parquet'
        con.execute(f"COPY company_complete TO '{company_out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY company_filing_complete TO '{bridge_out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    manifest = {
        'version': 'v1',
        'company_rows': company_rows,
        'ticker_master_companies': ticker_rows,
        'filing_universe_companies': filing_companies,
        'filing_only_companies_added': filing_only,
        'company_filing_rows': filing_rows,
        'uncovered_filings': uncovered,
        'source_classes': ['SEC_TICKER', 'SEC_TICKER+FILING', 'SEC_FILING'],
        'key_contract': {
            'canonical_company_id': 'SEC_CIK:<10-digit-zero-padded-CIK>',
            'company_filing_bridge_key': ['canonical_company_id', 'canonical_filing_id'],
        },
    }
    (out_dir / 'company_complete_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description='Complete SEC company master with filing-only issuers')
    p.add_argument('--company-master', type=Path, required=True)
    p.add_argument('--filing-master', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    args = p.parse_args()
    result = build_complete_company_master(args.company_master, args.filing_master, args.out_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
