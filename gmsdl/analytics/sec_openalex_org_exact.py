from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def _name_expr(col: str) -> str:
    # Normalized-exact: lower-case, punctuation -> spaces, collapse whitespace.
    # Legal suffix words (inc, corp, plc, etc.) are intentionally retained.
    return f"trim(regexp_replace(lower(regexp_replace(trim({col}), '[^a-zA-Z0-9]+', ' ', 'g')), '\\s+', ' ', 'g'))"


def _columns(con: duckdb.DuckDBPyConnection, relation_sql: str) -> set[str]:
    return {str(r[0]) for r in con.execute(f'DESCRIBE SELECT * FROM {relation_sql}').fetchall()}


def build_exact_bridge(company_master: Path, institution_root: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(institution_root.rglob('*.parquet'))
    if not files:
        raise RuntimeError('no OpenAlex institution parquet files found')

    glob = (institution_root / '**' / '*.parquet').as_posix()
    con = duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW sec AS SELECT * FROM read_parquet('{company_master.as_posix()}')")
        inst_rel = f"read_parquet('{glob}', union_by_name=true)"
        cols = _columns(con, inst_rel)
        id_col = 'id' if 'id' in cols else ('institution_id' if 'institution_id' in cols else None)
        name_col = 'display_name' if 'display_name' in cols else ('name' if 'name' in cols else None)
        if not id_col or not name_col:
            raise RuntimeError(f'OpenAlex institution schema missing id/name columns; columns={sorted(cols)}')
        ror = 'ror' if 'ror' in cols else 'NULL::VARCHAR AS ror'
        country = 'country_code' if 'country_code' in cols else 'NULL::VARCHAR AS country_code'
        typ = 'type' if 'type' in cols else ('institution_type' if 'institution_type' in cols else 'NULL::VARCHAR AS institution_type')
        typ_select = f'{typ} AS institution_type' if typ in {'type','institution_type'} else typ

        con.execute(f'''
            CREATE VIEW inst AS
            SELECT {id_col} AS openalex_institution_id,
                   {name_col} AS openalex_name,
                   {ror if ' AS ' in ror else ror},
                   {country if ' AS ' in country else country},
                   {typ_select}
            FROM {inst_rel}
            WHERE {id_col} IS NOT NULL AND {name_col} IS NOT NULL AND trim({name_col})<>''
        ''')
        con.execute(f'''
            CREATE VIEW sec_norm AS
            SELECT canonical_company_id, cik, company_name AS sec_name,
                   primary_ticker, ticker_count, source_class,
                   {_name_expr('company_name')} AS normalized_name
            FROM sec
            WHERE company_name IS NOT NULL AND trim(company_name)<>''
        ''')
        con.execute(f'''
            CREATE VIEW inst_norm AS
            SELECT openalex_institution_id, openalex_name, ror, country_code, institution_type,
                   {_name_expr('openalex_name')} AS normalized_name
            FROM inst
        ''')
        con.execute('''
            CREATE TABLE candidates AS
            WITH sc AS (
              SELECT normalized_name, COUNT(*) AS sec_name_count FROM sec_norm GROUP BY normalized_name
            ), ic AS (
              SELECT normalized_name, COUNT(*) AS openalex_name_count FROM inst_norm GROUP BY normalized_name
            )
            SELECT s.canonical_company_id, s.cik, s.sec_name, s.primary_ticker, s.ticker_count, s.source_class,
                   i.openalex_institution_id, i.openalex_name, i.ror, i.country_code, i.institution_type,
                   s.normalized_name,
                   sc.sec_name_count, ic.openalex_name_count,
                   'NORMALIZED_EXACT' AS match_method,
                   CASE WHEN sc.sec_name_count=1 AND ic.openalex_name_count=1 THEN TRUE ELSE FALSE END AS accepted,
                   CASE WHEN sc.sec_name_count=1 AND ic.openalex_name_count=1 THEN 1.0 ELSE 0.0 END AS confidence
            FROM sec_norm s
            JOIN inst_norm i USING (normalized_name)
            JOIN sc USING (normalized_name)
            JOIN ic USING (normalized_name)
            WHERE s.normalized_name<>''
        ''')
        con.execute('CREATE TABLE accepted AS SELECT * FROM candidates WHERE accepted')

        sec_rows = int(con.execute('SELECT COUNT(*) FROM sec').fetchone()[0])
        inst_rows = int(con.execute('SELECT COUNT(*) FROM inst').fetchone()[0])
        candidate_rows = int(con.execute('SELECT COUNT(*) FROM candidates').fetchone()[0])
        accepted_rows = int(con.execute('SELECT COUNT(*) FROM accepted').fetchone()[0])
        accepted_sec = int(con.execute('SELECT COUNT(DISTINCT canonical_company_id) FROM accepted').fetchone()[0])
        accepted_inst = int(con.execute('SELECT COUNT(DISTINCT openalex_institution_id) FROM accepted').fetchone()[0])
        ambiguous_rows = candidate_rows - accepted_rows
        dup_sec = int(con.execute('SELECT COUNT(*)-COUNT(DISTINCT canonical_company_id) FROM accepted').fetchone()[0])
        dup_inst = int(con.execute('SELECT COUNT(*)-COUNT(DISTINCT openalex_institution_id) FROM accepted').fetchone()[0])
        if dup_sec or dup_inst:
            raise RuntimeError(f'accepted exact bridge is not one-to-one: duplicate_sec={dup_sec} duplicate_openalex={dup_inst}')

        cand_out = out_dir / 'SEC_OPENALEX_ORG_EXACT_CANDIDATES.parquet'
        acc_out = out_dir / 'SEC_OPENALEX_ORG_EXACT_BRIDGE.parquet'
        con.execute(f"COPY candidates TO '{cand_out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY accepted TO '{acc_out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    manifest = {
        'version': 'v1',
        'method': 'NORMALIZED_EXACT',
        'normalization': 'lowercase; punctuation to spaces; collapse whitespace; retain legal suffix words',
        'acceptance_rule': 'normalized name unique on both SEC and OpenAlex sides',
        'sec_company_rows': sec_rows,
        'openalex_institution_rows': inst_rows,
        'candidate_rows': candidate_rows,
        'accepted_rows': accepted_rows,
        'accepted_sec_companies': accepted_sec,
        'accepted_openalex_institutions': accepted_inst,
        'ambiguous_candidate_rows': ambiguous_rows,
        'accepted_confidence': 1.0,
        'fuzzy_matching_used': False,
    }
    (out_dir / 'sec_openalex_org_exact_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description='Build precision-first exact SEC/OpenAlex organization bridge')
    p.add_argument('--company-master', type=Path, required=True)
    p.add_argument('--institution-root', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    args = p.parse_args()
    result = build_exact_bridge(args.company_master, args.institution_root, args.out_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
