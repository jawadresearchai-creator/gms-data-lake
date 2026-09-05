from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import duckdb


def normalize_cik(value: object) -> str:
    s = str(value).strip()
    if s.endswith('.0'):
        s = s[:-2]
    if not s.isdigit():
        raise ValueError(f'invalid CIK {value!r}')
    return s.zfill(10)


def _address(obj: dict | None) -> dict:
    obj = obj or {}
    return {
        'street1': obj.get('street1'),
        'street2': obj.get('street2'),
        'city': obj.get('city'),
        'state_or_country': obj.get('stateOrCountry'),
        'zip_code': obj.get('zipCode'),
        'state_or_country_description': obj.get('stateOrCountryDescription'),
        'is_foreign_location': obj.get('isForeignLocation'),
        'foreign_state_territory': obj.get('foreignStateTerritory'),
        'country': obj.get('country'),
    }


def build_issuer_metadata(company_master: Path, submissions_zip: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=':memory:')
    try:
        cm = con.execute(f"SELECT canonical_company_id,cik,company_name,primary_ticker,source_class FROM read_parquet('{company_master.as_posix()}')").fetchall()
    finally:
        con.close()
    targets = {normalize_cik(cik): (str(cid), name, ticker, source_class) for cid,cik,name,ticker,source_class in cm}

    rows: list[dict] = []
    with zipfile.ZipFile(submissions_zip) as zf:
        names = {Path(n).name: n for n in zf.namelist() if n.lower().endswith('.json')}
        for cik, (cid, cm_name, ticker, source_class) in sorted(targets.items()):
            expected = f'CIK{cik}.json'
            member = names.get(expected)
            if not member:
                continue
            data = json.loads(zf.read(member))
            business = _address((data.get('addresses') or {}).get('business'))
            mailing = _address((data.get('addresses') or {}).get('mailing'))
            rows.append({
                'canonical_company_id': cid,
                'cik': cik,
                'company_name': cm_name,
                'primary_ticker': ticker,
                'source_class': source_class,
                'sec_entity_name': data.get('name'),
                'entity_type': data.get('entityType'),
                'sic': data.get('sic'),
                'sic_description': data.get('sicDescription'),
                'owner_org': data.get('ownerOrg'),
                'ein': data.get('ein'),
                'lei': data.get('lei'),
                'description': data.get('description'),
                'website': data.get('website'),
                'investor_website': data.get('investorWebsite'),
                'category': data.get('category'),
                'fiscal_year_end': data.get('fiscalYearEnd'),
                'state_of_incorporation': data.get('stateOfIncorporation'),
                'state_of_incorporation_description': data.get('stateOfIncorporationDescription'),
                'phone': data.get('phone'),
                'business_street1': business['street1'],
                'business_street2': business['street2'],
                'business_city': business['city'],
                'business_state_or_country': business['state_or_country'],
                'business_zip_code': business['zip_code'],
                'business_state_or_country_description': business['state_or_country_description'],
                'business_is_foreign_location': business['is_foreign_location'],
                'business_foreign_state_territory': business['foreign_state_territory'],
                'business_country': business['country'],
                'mailing_street1': mailing['street1'],
                'mailing_street2': mailing['street2'],
                'mailing_city': mailing['city'],
                'mailing_state_or_country': mailing['state_or_country'],
                'mailing_zip_code': mailing['zip_code'],
                'mailing_state_or_country_description': mailing['state_or_country_description'],
                'mailing_is_foreign_location': mailing['is_foreign_location'],
                'mailing_foreign_state_territory': mailing['foreign_state_territory'],
                'mailing_country': mailing['country'],
            })

    con = duckdb.connect(database=':memory:')
    try:
        if not rows:
            raise RuntimeError('SEC submissions archive yielded zero target issuer records')
        cols = list(rows[0])
        defs = []
        for c in cols:
            sample = next((r[c] for r in rows if r.get(c) is not None), None)
            typ = 'BOOLEAN' if isinstance(sample, bool) else 'VARCHAR'
            defs.append(f'"{c}" {typ}')
        con.execute('CREATE TABLE meta(' + ','.join(defs) + ')')
        marks = ','.join('?' for _ in cols)
        con.executemany('INSERT INTO meta VALUES (' + marks + ')', [[r.get(c) for c in cols] for r in rows])

        matched = int(con.execute('SELECT COUNT(*) FROM meta').fetchone()[0])
        dup = int(con.execute('SELECT COUNT(*)-COUNT(DISTINCT canonical_company_id) FROM meta').fetchone()[0])
        null_keys = int(con.execute("SELECT COUNT(*) FROM meta WHERE canonical_company_id IS NULL OR canonical_company_id='' OR cik IS NULL OR cik='' ").fetchone()[0])
        business_geo = int(con.execute("SELECT COUNT(*) FROM meta WHERE business_state_or_country IS NOT NULL AND trim(business_state_or_country)<>''").fetchone()[0])
        business_desc = int(con.execute("SELECT COUNT(*) FROM meta WHERE business_state_or_country_description IS NOT NULL AND trim(business_state_or_country_description)<>''").fetchone()[0])
        mailing_geo = int(con.execute("SELECT COUNT(*) FROM meta WHERE mailing_state_or_country IS NOT NULL AND trim(mailing_state_or_country)<>''").fetchone()[0])
        incorp_geo = int(con.execute("SELECT COUNT(*) FROM meta WHERE state_of_incorporation IS NOT NULL AND trim(state_of_incorporation)<>''").fetchone()[0])
        if dup or null_keys:
            raise RuntimeError(f'issuer metadata QA failed: duplicate_company={dup} null_keys={null_keys}')

        out_path = out_dir/'SEC_ISSUER_METADATA.parquet'
        con.execute(f"COPY meta TO '{out_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    manifest = {
        'version': 'v1',
        'company_master_rows': len(targets),
        'matched_submission_records': matched,
        'missing_submission_records': len(targets)-matched,
        'business_state_or_country_present': business_geo,
        'business_state_or_country_description_present': business_desc,
        'mailing_state_or_country_present': mailing_geo,
        'state_of_incorporation_present': incorp_geo,
        'source': 'SEC EDGAR bulk submissions.zip',
        'key_contract': {'canonical_company_id': 'SEC_CIK:<10-digit-CIK>', 'cik': '10-digit zero-padded CIK'},
    }
    (out_dir/'sec_issuer_metadata_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return manifest


def main() -> int:
    p=argparse.ArgumentParser(description='Extract SEC issuer country/address metadata from submissions.zip')
    p.add_argument('--company-master',type=Path,required=True)
    p.add_argument('--submissions-zip',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(build_issuer_metadata(a.company_master,a.submissions_zip,a.out_dir),indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
