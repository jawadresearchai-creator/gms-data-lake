from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from gmsdl.analytics.release_finalize import main


def _parquet(path: Path, ddl: str, rows: list[tuple]) -> None:
    con = duckdb.connect()
    con.execute(f'CREATE TABLE t({ddl})')
    if rows:
        marks = ','.join('?' for _ in rows[0])
        con.executemany(f'INSERT INTO t VALUES ({marks})', rows)
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")
    con.close()


def test_release_finalize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inv = tmp_path / 'inventory.json'
    inv.write_text(json.dumps([
        {'Path': '00_CONTROL/a.json', 'Size': 10, 'ModTime': '2026-09-08T00:00:00Z'},
        {'Path': '03_RESEARCH/x.parquet', 'Size': 20, 'ModTime': '2026-09-08T00:00:00Z'},
    ]), encoding='utf-8')
    qa = tmp_path / 'qa.json'
    qa.write_text(json.dumps({'verified': True, 'errors': [], 'topic_rows': 2}), encoding='utf-8')
    ds = tmp_path / 'ds.parquet'
    _parquet(ds, 'id VARCHAR,value BIGINT', [('a', 1), ('b', 2)])
    out = tmp_path / 'out'
    monkeypatch.setattr('sys.argv', [
        'release_finalize', '--inventory-json', str(inv), '--qa-json', str(qa),
        '--dataset', f'TEST={ds}=03_RESEARCH/TEST/part-0000.parquet',
        '--out-dir', str(out),
    ])
    assert main() == 0
    release = json.loads((out / 'RELEASE.json').read_text(encoding='utf-8'))
    assert release['status'] == 'VERIFIED_RESEARCH_READY'
    assert release['drive_inventory']['objects'] == 2
    assert release['drive_inventory']['bytes'] == 30
    assert release['datasets'][0]['rows'] == 2
    assert (out / 'DATA_DICTIONARY.md').exists()
    assert (out / 'drive_object_inventory.csv').exists()


def test_release_finalize_rejects_unverified_qa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inv = tmp_path / 'inventory.json'; inv.write_text('[]', encoding='utf-8')
    qa = tmp_path / 'qa.json'; qa.write_text(json.dumps({'verified': False, 'errors': ['x']}), encoding='utf-8')
    ds = tmp_path / 'ds.parquet'; _parquet(ds, 'id INTEGER', [(1,)])
    monkeypatch.setattr('sys.argv', [
        'release_finalize', '--inventory-json', str(inv), '--qa-json', str(qa),
        '--dataset', f'TEST={ds}=03_RESEARCH/TEST/part-0000.parquet', '--out-dir', str(tmp_path / 'out')
    ])
    with pytest.raises(RuntimeError):
        main()
