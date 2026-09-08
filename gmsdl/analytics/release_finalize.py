from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import duckdb


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def human_bytes(n: int) -> str:
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f'{x:.2f} {u}'
        x /= 1024
    return f'{n} B'


def load_inventory(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('Drive inventory must be a JSON list')
    return data


def inspect_parquet(path: Path) -> tuple[int, list[tuple[str, str]]]:
    con = duckdb.connect(database=':memory:')
    try:
        rows = int(con.execute(f"SELECT COUNT(*) FROM read_parquet('{path.as_posix()}')").fetchone()[0])
        desc = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path.as_posix()}')").fetchall()
        cols = [(str(r[0]), str(r[1])) for r in desc]
        return rows, cols
    finally:
        con.close()


def parse_dataset(value: str) -> tuple[str, Path, str]:
    parts = value.split('=', 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError('dataset must be NAME=PATH=DRIVE_PATH')
    return parts[0], Path(parts[1]), parts[2]


def main() -> int:
    p = argparse.ArgumentParser(description='Freeze and document the verified SEC+OpenAlex production release')
    p.add_argument('--inventory-json', type=Path, required=True)
    p.add_argument('--qa-json', type=Path, required=True)
    p.add_argument('--dataset', action='append', default=[], type=parse_dataset)
    p.add_argument('--release-name', default='sec_openalex_v10')
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()

    a.out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    commit = os.environ.get('GITHUB_SHA', 'unknown')
    run_id = os.environ.get('GITHUB_RUN_ID', 'unknown')

    inventory = load_inventory(a.inventory_json)
    files = []
    for x in inventory:
        if x.get('IsDir'):
            continue
        path = str(x.get('Path') or x.get('Name') or '')
        size = int(x.get('Size') or 0)
        top = path.split('/', 1)[0] if '/' in path else path
        files.append({'path': path, 'size_bytes': size, 'modified': x.get('ModTime', ''), 'top_level': top})

    inv_csv = a.out_dir / 'drive_object_inventory.csv'
    with inv_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['path', 'size_bytes', 'modified', 'top_level'])
        w.writeheader(); w.writerows(files)

    top_counts: dict[str, dict[str, int]] = {}
    for r in files:
        d = top_counts.setdefault(r['top_level'], {'objects': 0, 'bytes': 0})
        d['objects'] += 1; d['bytes'] += r['size_bytes']

    qa = json.loads(a.qa_json.read_text(encoding='utf-8'))
    verified = bool(qa.get('verified')) and not qa.get('errors')
    if not verified:
        raise RuntimeError(f'QA input is not verified: {qa}')

    datasets = []
    dictionary_rows = []
    for name, path, drive_path in a.dataset:
        rows, cols = inspect_parquet(path)
        datasets.append({'name': name, 'rows': rows, 'columns': len(cols), 'drive_path': drive_path})
        for col, typ in cols:
            dictionary_rows.append({'dataset': name, 'column': col, 'type': typ, 'drive_path': drive_path})

    dict_csv = a.out_dir / 'data_dictionary.csv'
    with dict_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['dataset', 'column', 'type', 'drive_path'])
        w.writeheader(); w.writerows(dictionary_rows)

    dict_md = a.out_dir / 'DATA_DICTIONARY.md'
    lines = [f'# Data Dictionary — {a.release_name}', '', f'Generated: `{now}`', '']
    for ds in datasets:
        lines += [f"## {ds['name']}", '', f"Drive: `{ds['drive_path']}`", f"Rows: **{ds['rows']:,}**", '', '| Column | Type |', '|---|---|']
        for r in dictionary_rows:
            if r['dataset'] == ds['name']:
                lines.append(f"| `{r['column']}` | `{r['type']}` |")
        lines.append('')
    dict_md.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    prov = a.out_dir / 'PROVENANCE.md'
    prov.write_text('\n'.join([
        f'# Provenance — {a.release_name}', '',
        f'- Frozen at: `{now}`',
        f'- Git commit: `{commit}`',
        f'- GitHub Actions run: `{run_id}`',
        '- Production identity bridge: `03_RESEARCH/cross_domain/v10/SEC_OPENALEX_ORG_PRODUCTION_BRIDGE/part-0000.parquet`',
        '- Research/citation marts: v10',
        '- Topic/collaboration marts: v10',
        '- Work-mart QA: verified with zero reported errors',
        '- OpenAlex raw snapshot and curated foundation were previously checksum/object verified before this release.',
        '- SEC company, filing, filing-section, issuer-metadata, and complete-company foundations were built from their versioned workflows and retained in the lake.',
        '',
        '## Scope note', '',
        'This release freezes the current SEC + OpenAlex research scope. It does not claim that the lake is permanently complete: upstream sources evolve and future domains (for example patents) can be added as later releases.',
        '',
        '## Research semantics', '',
        '- Topic marts are multi-label; summing topic rows is not a unique-work total.',
        '- Collaboration rows are company/year/collaborator-country aggregates. The collaborator institution metric is additive across shard/work aggregates and should not be described as a globally distinct annual collaborator count without further deduplication.',
    ]) + '\n', encoding='utf-8')

    total_objects = len(files)
    total_bytes = sum(r['size_bytes'] for r in files)
    report = a.out_dir / 'COMPLETION_REPORT.md'
    report_lines = [
        f'# Production Release Completion Report — {a.release_name}', '',
        f'Frozen: `{now}`', '',
        '## Release status', '',
        '**VERIFIED / RESEARCH-READY**', '',
        f'- Drive objects inventoried: **{total_objects:,}**',
        f'- Drive bytes inventoried: **{total_bytes:,}** ({human_bytes(total_bytes)})',
        f'- QA verified: **{verified}**',
        f'- QA errors: **{len(qa.get("errors", []))}**', '',
        '## Principal research datasets', '',
        '| Dataset | Rows | Columns |', '|---|---:|---:|'
    ]
    for ds in datasets:
        report_lines.append(f"| `{ds['name']}` | {ds['rows']:,} | {ds['columns']} |")
    report_lines += ['', '## Drive inventory by top-level area', '', '| Area | Objects | Bytes |', '|---|---:|---:|']
    for area in sorted(top_counts):
        d = top_counts[area]
        report_lines.append(f"| `{area}` | {d['objects']:,} | {d['bytes']:,} |")
    report_lines += ['', '## Verification summary', '', f"- `verified`: `{qa.get('verified')}`", f"- `errors`: `{qa.get('errors', [])}`"]
    for key in ['topic_rows','collaboration_rows','topic_companies','collaboration_companies','distinct_topics','distinct_collaboration_countries','topic_min_year','topic_max_year','collaboration_min_year','collaboration_max_year']:
        if key in qa:
            report_lines.append(f"- `{key}`: `{qa[key]}`")
    report_lines += ['', '## Release decision', '', 'The SEC + OpenAlex scope is frozen as the current production research release. Subsequent source refreshes, identity expansions, or new domains should publish a new version rather than mutating this release marker.', '']
    report.write_text('\n'.join(report_lines), encoding='utf-8')

    release = {
        'release_name': a.release_name,
        'status': 'VERIFIED_RESEARCH_READY',
        'frozen_at_utc': now,
        'git_commit': commit,
        'github_run_id': run_id,
        'qa_verified': verified,
        'qa_errors': qa.get('errors', []),
        'drive_inventory': {'objects': total_objects, 'bytes': total_bytes, 'top_level': top_counts},
        'datasets': datasets,
        'artifacts': {},
    }
    for path in [inv_csv, dict_csv, dict_md, prov, report]:
        release['artifacts'][path.name] = {'sha256': sha256(path), 'bytes': path.stat().st_size}
    release_path = a.out_dir / 'RELEASE.json'
    release_path.write_text(json.dumps(release, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    print(json.dumps({
        'release_name': a.release_name,
        'status': release['status'],
        'drive_objects': total_objects,
        'drive_bytes': total_bytes,
        'datasets': {d['name']: d['rows'] for d in datasets},
        'qa_verified': verified,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
