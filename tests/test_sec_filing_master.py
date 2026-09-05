from __future__ import annotations

from pathlib import Path

import duckdb

from gmsdl.analytics.sec_filing_master import build_filing_master


def _write_idx(path: Path, rows: list[str]) -> None:
    path.write_text(
        'Description\nCIK|Company Name|Form Type|Date Filed|Filename\n' + '\n'.join(rows) + '\n',
        encoding='latin-1',
    )


def test_build_filing_master(tmp_path: Path) -> None:
    idx1 = tmp_path / 'master_2023_q1.idx'
    idx2 = tmp_path / 'master_2024_q1.idx'
    _write_idx(idx1, [
        '320193|Apple Inc.|10-K|2023-10-10|edgar/data/320193/0000320193-23-000106.txt',
        '789019|Microsoft Corp|10-K|2023-07-27|edgar/data/789019/0000950170-23-035122.txt',
    ])
    _write_idx(idx2, [
        '320193|Apple Inc.|10-K|2024-02-01|edgar/data/320193/0000320193-24-000010.txt',
        '111111|Outside Cutoff|10-K|2024-04-01|edgar/data/111111/0000000000-24-000001.txt',
    ])

    cm = tmp_path / 'company.parquet'
    con = duckdb.connect()
    con.execute('CREATE TABLE c(canonical_company_id VARCHAR, cik VARCHAR, company_name VARCHAR, primary_ticker VARCHAR, ticker_count INTEGER)')
    con.executemany('INSERT INTO c VALUES (?,?,?,?,?)', [
        ('SEC_CIK:0000320193', '0000320193', 'Apple Inc.', 'AAPL', 1),
        ('SEC_CIK:0000789019', '0000789019', 'Microsoft Corp', 'MSFT', 1),
    ])
    con.execute(f"COPY c TO '{cm.as_posix()}' (FORMAT PARQUET)")
    con.close()

    out = tmp_path / 'out'
    manifest = build_filing_master([idx1, idx2], cm, out, expected=2)
    assert manifest['filing_rows'] == 2
    assert manifest['company_master_matches'] == 2
    assert manifest['company_master_unmatched'] == 0

    con = duckdb.connect()
    row = con.execute(
        f"SELECT accession, filing_date FROM read_parquet('{(out/'FILING_MASTER.parquet').as_posix()}') "
        "WHERE cik='0000320193'"
    ).fetchone()
    assert row[0] == '0000320193-24-000010'
    bridge = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{(out/'COMPANY_FILING_BRIDGE.parquet').as_posix()}') WHERE matched_company_master"
    ).fetchone()[0]
    assert bridge == 2
    con.close()

def test_same_day_selection_preserves_first_index_row(tmp_path: Path) -> None:
    idx = tmp_path / 'master.idx'
    _write_idx(idx, [
        '123|Co|10-K|2024-02-01|edgar/data/123/first.txt',
        '123|Co|10-K|2024-02-01|edgar/data/123/second.txt',
    ])
    from gmsdl.analytics.sec_filing_master import build_universe
    rows = build_universe([idx])
    assert len(rows) == 1
    assert rows[0].filename == 'edgar/data/123/first.txt'
