from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import duckdb


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def normalize_cik(value: object) -> str:
    s = str(value).strip()
    if s.endswith('.0'):
        s = s[:-2]
    if not s.isdigit():
        raise ValueError(f'invalid CIK: {value!r}')
    return s.zfill(10)


def _load_tickers(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    rows: list[dict] = []
    if isinstance(raw, dict):
        iterable = raw.values()
    elif isinstance(raw, list):
        iterable = raw
    else:
        raise ValueError('unexpected company_tickers JSON shape')
    for row in iterable:
        if not isinstance(row, dict):
            continue
        cik = row.get('cik_str', row.get('cik'))
        ticker = row.get('ticker')
        title = row.get('title', row.get('name'))
        if cik is None or not ticker:
            continue
        rows.append({
            'cik': normalize_cik(cik),
            'company_name': (str(title).strip() if title is not None else None),
            'ticker': str(ticker).strip().upper(),
            'exchange': None,
            'source': 'company_tickers',
        })
    return rows


def _load_exchange(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    rows: list[dict] = []
    if isinstance(raw, dict) and isinstance(raw.get('fields'), list) and isinstance(raw.get('data'), list):
        fields = [str(x) for x in raw['fields']]
        iterable = [dict(zip(fields, row)) for row in raw['data']]
    elif isinstance(raw, list):
        iterable = raw
    else:
        raise ValueError('unexpected company_tickers_exchange JSON shape')
    for row in iterable:
        if not isinstance(row, dict):
            continue
        cik = row.get('cik', row.get('cik_str'))
        ticker = row.get('ticker')
        name = row.get('name', row.get('title'))
        exchange = row.get('exchange')
        if cik is None or not ticker:
            continue
        rows.append({
            'cik': normalize_cik(cik),
            'company_name': (str(name).strip() if name is not None else None),
            'ticker': str(ticker).strip().upper(),
            'exchange': (str(exchange).strip() if exchange not in (None, '') else None),
            'source': 'company_tickers_exchange',
        })
    return rows


def build_company_master(tickers_json: Path, exchange_json: Path, out_dir: Path) -> dict:
    rows = _load_tickers(tickers_json) + _load_exchange(exchange_json)
    if not rows:
        raise RuntimeError('SEC identifier inputs produced zero rows')

    by_pair: dict[tuple[str, str], dict] = {}
    names: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r['company_name']:
            names[r['cik']].append(r['company_name'])
        key = (r['cik'], r['ticker'])
        old = by_pair.get(key)
        if old is None:
            by_pair[key] = dict(r)
        else:
            # Prefer the exchange-bearing record while preserving a non-empty name.
            if not old.get('exchange') and r.get('exchange'):
                old['exchange'] = r['exchange']
            if not old.get('company_name') and r.get('company_name'):
                old['company_name'] = r['company_name']
            old['source'] = '+'.join(sorted(set(old['source'].split('+')) | {r['source']}))

    company_rows: list[tuple] = []
    for cik in sorted({r['cik'] for r in rows}):
        candidates = [n for n in names.get(cik, []) if n]
        # Choose the most frequently occurring SEC-provided name; tie-break deterministically.
        name = None
        if candidates:
            counts = Counter(candidates)
            name = sorted(counts, key=lambda n: (-counts[n], n))[0]
        tickers = sorted(t for c, t in by_pair if c == cik)
        company_rows.append((f'SEC_CIK:{cik}', cik, name, tickers[0] if tickers else None, len(tickers)))

    bridge_rows = [
        (f'SEC_CIK:{cik}', cik, ticker, r.get('exchange'), r.get('company_name'), r.get('source'))
        for (cik, ticker), r in sorted(by_pair.items())
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=':memory:')
    try:
        con.execute('CREATE TABLE company_master(canonical_company_id VARCHAR, cik VARCHAR, company_name VARCHAR, primary_ticker VARCHAR, ticker_count INTEGER)')
        con.executemany('INSERT INTO company_master VALUES (?,?,?,?,?)', company_rows)
        con.execute('CREATE TABLE cik_ticker_bridge(canonical_company_id VARCHAR, cik VARCHAR, ticker VARCHAR, exchange VARCHAR, company_name VARCHAR, source VARCHAR)')
        con.executemany('INSERT INTO cik_ticker_bridge VALUES (?,?,?,?,?,?)', bridge_rows)
        company_path = out_dir / 'COMPANY_MASTER.parquet'
        bridge_path = out_dir / 'CIK_TICKER_BRIDGE.parquet'
        con.execute(f"COPY company_master TO '{company_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY cik_ticker_bridge TO '{bridge_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")

        duplicate_company = con.execute('SELECT COUNT(*)-COUNT(DISTINCT canonical_company_id) FROM company_master').fetchone()[0]
        duplicate_bridge = con.execute("SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM cik_ticker_bridge GROUP BY cik,ticker HAVING COUNT(*)>1)").fetchone()[0]
        null_keys = con.execute("SELECT COUNT(*) FROM company_master WHERE cik IS NULL OR cik='' OR canonical_company_id IS NULL OR canonical_company_id='' ").fetchone()[0]
    finally:
        con.close()

    if duplicate_company or duplicate_bridge or null_keys:
        raise RuntimeError(f'identifier QA failed: duplicate_company={duplicate_company} duplicate_bridge={duplicate_bridge} null_keys={null_keys}')

    manifest = {
        'version': 'v1',
        'company_rows': len(company_rows),
        'bridge_rows': len(bridge_rows),
        'source_files': {
            tickers_json.name: {'sha256': _sha256(tickers_json), 'bytes': tickers_json.stat().st_size},
            exchange_json.name: {'sha256': _sha256(exchange_json), 'bytes': exchange_json.stat().st_size},
        },
        'key_contract': {
            'canonical_company_id': 'SEC_CIK:<10-digit-zero-padded-CIK>',
            'cik': '10-digit zero-padded SEC CIK',
            'ticker_bridge_key': ['cik', 'ticker'],
        },
    }
    (out_dir / 'company_master_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description='Build canonical SEC company master and CIK/ticker bridge')
    p.add_argument('--tickers', type=Path, required=True)
    p.add_argument('--exchange', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    args = p.parse_args()
    result = build_company_master(args.tickers, args.exchange, args.out_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
