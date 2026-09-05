from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

EXPECTED_ROWS = 22077
EXPECTED_FILINGS = 7359
EXPECTED_SECTIONS = {"Item1", "Item1A", "Item7"}


def build_section_bridge(section_index: Path, filing_master: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=":memory:")
    try:
        con.execute(f"CREATE VIEW idx AS SELECT * FROM read_csv_auto('{section_index.as_posix()}', header=true, all_varchar=true)")
        con.execute(f"CREATE VIEW fm AS SELECT * FROM read_parquet('{filing_master.as_posix()}')")

        idx_rows = int(con.execute("SELECT COUNT(*) FROM idx").fetchone()[0])
        idx_filings = int(con.execute("SELECT COUNT(DISTINCT cik) FROM idx").fetchone()[0])
        if idx_rows != EXPECTED_ROWS:
            raise RuntimeError(f"section row mismatch: expected {EXPECTED_ROWS}, got {idx_rows}")
        if idx_filings != EXPECTED_FILINGS:
            raise RuntimeError(f"section filing mismatch: expected {EXPECTED_FILINGS}, got {idx_filings}")

        sections = {r[0] for r in con.execute("SELECT DISTINCT section FROM idx").fetchall()}
        if sections != EXPECTED_SECTIONS:
            raise RuntimeError(f"unexpected section universe: {sorted(sections)}")

        bad_per_filing = int(con.execute("SELECT COUNT(*) FROM (SELECT cik FROM idx GROUP BY cik HAVING COUNT(*)<>3 OR COUNT(DISTINCT section)<>3)").fetchone()[0])
        if bad_per_filing:
            raise RuntimeError(f"{bad_per_filing} filings do not have exactly three distinct section rows")

        con.execute('''
            CREATE TABLE filing_section_bridge AS
            SELECT
                f.canonical_filing_id,
                f.canonical_company_id,
                f.cik,
                f.accession,
                f.filing_date,
                f.company_name_at_filing,
                i.section,
                i.extract_status,
                TRY_CAST(i.word_count AS BIGINT) AS word_count,
                TRY_CAST(i.char_count AS BIGINT) AS char_count,
                i.text_sha256,
                TRY_CAST(i.raw_bytes AS BIGINT) AS raw_bytes,
                i.raw_sha256,
                i.parser_version,
                i.filename AS sec_filename,
                i.sec_url
            FROM idx i
            JOIN fm f
              ON f.cik = i.cik
             AND f.sec_filename = i.filename
        ''')

        bridge_rows = int(con.execute("SELECT COUNT(*) FROM filing_section_bridge").fetchone()[0])
        bridge_filings = int(con.execute("SELECT COUNT(DISTINCT canonical_filing_id) FROM filing_section_bridge").fetchone()[0])
        duplicate_keys = int(con.execute("SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM filing_section_bridge GROUP BY canonical_filing_id,section HAVING COUNT(*)>1)").fetchone()[0])
        null_keys = int(con.execute("SELECT COUNT(*) FROM filing_section_bridge WHERE canonical_filing_id IS NULL OR section IS NULL OR section='' ").fetchone()[0])
        if bridge_rows != EXPECTED_ROWS or bridge_filings != EXPECTED_FILINGS or duplicate_keys or null_keys:
            raise RuntimeError(
                f"section bridge QA failed: rows={bridge_rows} filings={bridge_filings} duplicate_keys={duplicate_keys} null_keys={null_keys}"
            )

        status_rows = con.execute("SELECT extract_status, COUNT(*) FROM filing_section_bridge GROUP BY extract_status ORDER BY extract_status").fetchall()
        missing_filings = [r[0] for r in con.execute("SELECT canonical_filing_id FROM fm WHERE canonical_filing_id NOT IN (SELECT DISTINCT canonical_filing_id FROM filing_section_bridge) ORDER BY canonical_filing_id").fetchall()]

        out_path = out_dir / "FILING_SECTION_BRIDGE.parquet"
        con.execute(f"COPY filing_section_bridge TO '{out_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    manifest = {
        "version": "v1",
        "section_rows": bridge_rows,
        "covered_filings": bridge_filings,
        "expected_filing_master_rows": 7361,
        "uncovered_filings": len(missing_filings),
        "uncovered_filing_ids": missing_filings,
        "sections": sorted(EXPECTED_SECTIONS),
        "extract_status_counts": {str(k): int(v) for k, v in status_rows},
        "key_contract": {
            "primary_key": ["canonical_filing_id", "section"],
            "join_to_filing_master": "canonical_filing_id",
            "join_to_company_master": "canonical_company_id",
        },
    }
    (out_dir / "filing_section_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description="Build SEC filing-section bridge from Event Study extraction metadata")
    p.add_argument("--section-index", type=Path, required=True)
    p.add_argument("--filing-master", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()
    result = build_section_bridge(args.section_index, args.filing_master, args.out_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
