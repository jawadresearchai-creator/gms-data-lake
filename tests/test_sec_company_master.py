from __future__ import annotations

import json
from pathlib import Path

import duckdb

from gmsdl.analytics.sec_company_master import build_company_master, normalize_cik


def test_normalize_cik() -> None:
    assert normalize_cik(320193) == '0000320193'
    assert normalize_cik('1652044') == '0001652044'


def test_build_company_master(tmp_path: Path) -> None:
    tickers = tmp_path / 'company_tickers.json'
    exchange = tmp_path / 'company_tickers_exchange.json'
    out = tmp_path / 'out'
    tickers.write_text(json.dumps({
        '0': {'cik_str': 320193, 'ticker': 'AAPL', 'title': 'Apple Inc.'},
        '1': {'cik_str': 789019, 'ticker': 'MSFT', 'title': 'Microsoft Corp'},
    }), encoding='utf-8')
    exchange.write_text(json.dumps({
        'fields': ['cik', 'name', 'ticker', 'exchange'],
        'data': [
            [320193, 'Apple Inc.', 'AAPL', 'Nasdaq'],
            [789019, 'Microsoft Corp', 'MSFT', 'Nasdaq'],
            [789019, 'Microsoft Corp', 'MSF', 'Other'],
        ],
    }), encoding='utf-8')

    manifest = build_company_master(tickers, exchange, out)
    assert manifest['company_rows'] == 2
    assert manifest['bridge_rows'] == 3

    con = duckdb.connect()
    row = con.execute(f"SELECT cik,primary_ticker,ticker_count FROM read_parquet('{(out/'COMPANY_MASTER.parquet').as_posix()}') WHERE company_name='Microsoft Corp'").fetchone()
    assert row == ('0000789019', 'MSF', 2)
    bridge = con.execute(f"SELECT exchange FROM read_parquet('{(out/'CIK_TICKER_BRIDGE.parquet').as_posix()}') WHERE cik='0000320193' AND ticker='AAPL'").fetchone()
    assert bridge == ('Nasdaq',)
    con.close()
