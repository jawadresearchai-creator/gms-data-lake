from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import duckdb

START_DATE = date(2023, 1, 1)
CUTOFF_DATE = date(2024, 3, 15)
EXPECTED_FILINGS = 7361


@dataclass(frozen=True)
class Filing:
    cik: str
    company_name: str
    form: str
    filing_date: date
    filename: str

    @property
    def accession(self) -> str:
        return Path(self.filename).stem

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace('-', '')

    @property
    def canonical_filing_id(self) -> str:
        return f"SEC_ACCESSION:{self.accession_nodash}"

    @property
    def canonical_company_id(self) -> str:
        return f"SEC_CIK:{self.cik}"

    @property
    def sec_url(self) -> str:
        return f"https://www.sec.gov/Archives/{self.filename}"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_master_idx(path: Path) -> list[Filing]:
    text = path.read_text(encoding='latin-1', errors='replace')
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith('CIK|Company Name|Form Type|Date Filed|Filename'):
            start = i + 1
            break
    if start is None:
        raise ValueError(f'Could not find EDGAR master.idx header in {path}')
    out: list[Filing] = []
    for line in lines[start:]:
        parts = line.split('|')
        if len(parts) != 5:
            continue
        cik, company, form, filed_s, filename = parts
        try:
            filed = datetime.strptime(filed_s, '%Y-%m-%d').date()
        except ValueError:
            continue
        out.append(Filing(
            cik=str(cik).strip().zfill(10),
            company_name=company.strip(),
            form=form.strip(),
            filing_date=filed,
            filename=filename.strip(),
        ))
    return out


def build_universe(index_paths: list[Path]) -> list[Filing]:
    filings: list[Filing] = []
    for path in index_paths:
        filings.extend(parse_master_idx(path))
    eligible = [f for f in filings if f.form == '10-K' and START_DATE <= f.filing_date <= CUTOFF_DATE]
    latest: dict[str, Filing] = {}
    for f in eligible:
        old = latest.get(f.cik)
        if old is None or (f.filing_date, f.filename) > (old.filing_date, old.filename):
            latest[f.cik] = f
    return sorted(latest.values(), key=lambda f: (f.cik, f.filing_date, f.filename))


def build_filing_master(index_paths: list[Path], company_master: Path, out_dir: Path, expected: int = EXPECTED_FILINGS) -> dict:
    filings = build_universe(index_paths)
    if len(filings) != expected:
        raise RuntimeError(f'frozen filing universe mismatch: expected {expected}, got {len(filings)}')

    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=':memory:')
    try:
        con.execute('''
            CREATE TABLE filing_master(
                canonical_filing_id VARCHAR,
                accession VARCHAR,
                accession_nodash VARCHAR,
                cik VARCHAR,
                canonical_company_id VARCHAR,
                company_name_at_filing VARCHAR,
                form VARCHAR,
                filing_date DATE,
                filing_year INTEGER,
                sec_filename VARCHAR,
                sec_url VARCHAR
            )
        ''')
        rows = [(
            f.canonical_filing_id,
            f.accession,
            f.accession_nodash,
            f.cik,
            f.canonical_company_id,
            f.company_name,
            f.form,
            f.filing_date.isoformat(),
            f.filing_date.year,
            f.filename,
            f.sec_url,
        ) for f in filings]
        con.executemany('INSERT INTO filing_master VALUES (?,?,?,?,?,?,?,?,?,?,?)', rows)

        con.execute(f"CREATE VIEW company_master AS SELECT * FROM read_parquet('{company_master.as_posix()}')")
        con.execute('''
            CREATE TABLE company_filing_bridge AS
            SELECT f.canonical_company_id,
                   f.canonical_filing_id,
                   f.cik,
                   f.accession,
                   f.filing_date,
                   CASE WHEN c.canonical_company_id IS NOT NULL THEN TRUE ELSE FALSE END AS matched_company_master
            FROM filing_master f
            LEFT JOIN company_master c USING (canonical_company_id)
        ''')

        duplicate_filing = int(con.execute('SELECT COUNT(*)-COUNT(DISTINCT canonical_filing_id) FROM filing_master').fetchone()[0])
        duplicate_accession = int(con.execute('SELECT COUNT(*)-COUNT(DISTINCT accession_nodash) FROM filing_master').fetchone()[0])
        duplicate_cik = int(con.execute('SELECT COUNT(*)-COUNT(DISTINCT cik) FROM filing_master').fetchone()[0])
        null_keys = int(con.execute("SELECT COUNT(*) FROM filing_master WHERE canonical_filing_id IS NULL OR canonical_filing_id='' OR cik IS NULL OR cik='' OR accession_nodash IS NULL OR accession_nodash='' ").fetchone()[0])
        matched = int(con.execute('SELECT COUNT(*) FROM company_filing_bridge WHERE matched_company_master').fetchone()[0])
        unmatched = len(filings) - matched

        if duplicate_filing or duplicate_accession or duplicate_cik or null_keys:
            raise RuntimeError(
                f'filing QA failed: duplicate_filing={duplicate_filing} duplicate_accession={duplicate_accession} '
                f'duplicate_cik={duplicate_cik} null_keys={null_keys}'
            )

        filing_path = out_dir / 'FILING_MASTER.parquet'
        bridge_path = out_dir / 'COMPANY_FILING_BRIDGE.parquet'
        con.execute(f"COPY filing_master TO '{filing_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY company_filing_bridge TO '{bridge_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    manifest = {
        'version': 'v1',
        'study_boundary': {
            'form': '10-K',
            'start_date': START_DATE.isoformat(),
            'cutoff_date': CUTOFF_DATE.isoformat(),
            'selection': 'latest eligible 10-K per CIK',
        },
        'filing_rows': len(filings),
        'unique_ciks': len({f.cik for f in filings}),
        'unique_accessions': len({f.accession_nodash for f in filings}),
        'company_master_matches': matched,
        'company_master_unmatched': unmatched,
        'source_indexes': [
            {'name': p.name, 'bytes': p.stat().st_size, 'sha256': _sha256(p)} for p in index_paths
        ],
        'key_contract': {
            'canonical_filing_id': 'SEC_ACCESSION:<accession-without-dashes>',
            'canonical_company_id': 'SEC_CIK:<10-digit-zero-padded-CIK>',
            'bridge_key': ['canonical_company_id', 'canonical_filing_id'],
        },
    }
    (out_dir / 'filing_master_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description='Build frozen SEC 10-K filing master and company bridge')
    p.add_argument('--index', action='append', type=Path, required=True, dest='indexes')
    p.add_argument('--company-master', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--expected-filings', type=int, default=EXPECTED_FILINGS)
    args = p.parse_args()
    result = build_filing_master(args.indexes, args.company_master, args.out_dir, args.expected_filings)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
