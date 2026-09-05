from __future__ import annotations

import json
import zipfile
from pathlib import Path

import duckdb

from gmsdl.analytics.sec_issuer_metadata import build_issuer_metadata


def test_build_issuer_metadata(tmp_path: Path) -> None:
    cm=tmp_path/'cm.parquet'; z=tmp_path/'submissions.zip'; out=tmp_path/'out'
    con=duckdb.connect()
    con.execute('''CREATE TABLE cm(canonical_company_id VARCHAR,cik VARCHAR,company_name VARCHAR,primary_ticker VARCHAR,source_class VARCHAR)''')
    con.executemany('INSERT INTO cm VALUES (?,?,?,?,?)',[
        ('SEC_CIK:0000000001','0000000001','One Inc','ONE','SEC_TICKER+FILING'),
        ('SEC_CIK:0000000002','0000000002','Two LLC',None,'SEC_FILING'),
    ])
    con.execute(f"COPY cm TO '{cm.as_posix()}' (FORMAT PARQUET)")
    con.close()
    payload={
        'name':'One Inc','entityType':'operating','sic':'1234','sicDescription':'Widgets',
        'stateOfIncorporation':'DE','stateOfIncorporationDescription':'DELAWARE','phone':'123',
        'addresses':{
            'business':{'street1':'1 Main','city':'Boston','stateOrCountry':'MA','zipCode':'02101','stateOrCountryDescription':'MASSACHUSETTS','isForeignLocation':False},
            'mailing':{'street1':'PO Box 1','city':'Boston','stateOrCountry':'MA','zipCode':'02101','stateOrCountryDescription':'MASSACHUSETTS','isForeignLocation':False},
        },
    }
    with zipfile.ZipFile(z,'w',compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('CIK0000000001.json',json.dumps(payload))
    m=build_issuer_metadata(cm,z,out)
    assert m['company_master_rows']==2
    assert m['matched_submission_records']==1
    assert m['missing_submission_records']==1
    assert m['business_state_or_country_present']==1
    con=duckdb.connect()
    row=con.execute(f"SELECT business_state_or_country,state_of_incorporation FROM read_parquet('{(out/'SEC_ISSUER_METADATA.parquet').as_posix()}')").fetchone()
    assert row==('MA','DE')
    con.close()
