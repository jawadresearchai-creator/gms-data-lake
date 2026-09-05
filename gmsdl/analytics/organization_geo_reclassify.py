from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import duckdb

US_STATE_CODES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR','VI','GU','AS','MP'
}

# Common EDGAR foreign state/country descriptions that appear in submissions.
# Mapping by normalized description avoids ambiguous state/country codes such as CA.
COUNTRY_NAME_TO_ISO2 = {
    'AUSTRALIA':'AU','AUSTRIA':'AT','BELGIUM':'BE','BERMUDA':'BM','BRAZIL':'BR','CANADA':'CA',
    'CAYMAN ISLANDS':'KY','CHINA':'CN','DENMARK':'DK','FINLAND':'FI','FRANCE':'FR','GERMANY':'DE',
    'HONG KONG':'HK','INDIA':'IN','IRELAND':'IE','ISRAEL':'IL','ITALY':'IT','JAPAN':'JP','JERSEY':'JE',
    'LUXEMBOURG':'LU','MEXICO':'MX','NETHERLANDS':'NL','NEW ZEALAND':'NZ','NORWAY':'NO',
    'REPUBLIC OF KOREA':'KR','SINGAPORE':'SG','SOUTH AFRICA':'ZA','SPAIN':'ES','SWEDEN':'SE',
    'SWITZERLAND':'CH','TAIWAN':'TW','UNITED ARAB EMIRATES':'AE','UNITED KINGDOM':'GB',
    'UNITED STATES':'US','UNITED STATES OF AMERICA':'US','VIRGIN ISLANDS BRITISH':'VG',
}


def _norm_desc(value: str | None) -> str:
    if not value:
        return ''
    s = re.sub(r'\s*\([^)]*\)\s*', ' ', str(value).upper())
    s = re.sub(r'[^A-Z0-9]+', ' ', s).strip()
    return re.sub(r'\s+', ' ', s)


def sec_country_iso2(state_or_country: str | None, description: str | None, is_foreign: object) -> str | None:
    code = (str(state_or_country).strip().upper() if state_or_country is not None else '')
    foreign = None
    if isinstance(is_foreign, bool):
        foreign = is_foreign
    elif is_foreign is not None:
        foreign = str(is_foreign).strip().lower() in {'1','true','t','yes','y'}
    if foreign is False and code in US_STATE_CODES:
        return 'US'
    desc = _norm_desc(description)
    if desc in COUNTRY_NAME_TO_ISO2:
        return COUNTRY_NAME_TO_ISO2[desc]
    # Some descriptions include qualifiers; prefer longest explicit country-name prefix.
    for name, iso in sorted(COUNTRY_NAME_TO_ISO2.items(), key=lambda kv: -len(kv[0])):
        if desc.startswith(name + ' ') or desc.endswith(' ' + name):
            return iso
    return None


def reclassify(
    issuer_metadata: Path,
    production_bridge: Path,
    quarantine: Path,
    review_queue: Path,
    out_dir: Path,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=':memory:')
    try:
        meta_rows = con.execute(f"SELECT canonical_company_id,business_state_or_country,business_state_or_country_description,business_is_foreign_location FROM read_parquet('{issuer_metadata.as_posix()}')").fetchall()
        meta_country = {str(cid): sec_country_iso2(code, desc, foreign) for cid,code,desc,foreign in meta_rows}
        production = con.execute(f"SELECT * FROM read_parquet('{production_bridge.as_posix()}')").fetchdf()
        quarantined = con.execute(f"SELECT * FROM read_parquet('{quarantine.as_posix()}')").fetchdf()
        review = con.execute(f"SELECT * FROM read_parquet('{review_queue.as_posix()}')").fetchdf()
    finally:
        con.close()

    def classify(df, source: str):
        records = []
        for row in df.to_dict(orient='records'):
            cid = str(row.get('canonical_company_id'))
            sec_country = meta_country.get(cid)
            oa_country = row.get('country_code')
            oa_country = str(oa_country).strip().upper() if oa_country not in (None, '') else None
            country_comparable = bool(sec_country and oa_country)
            country_match = bool(country_comparable and sec_country == oa_country)
            country_conflict = bool(country_comparable and sec_country != oa_country)
            institution_type = str(row.get('institution_type') or '').strip().lower()
            ror_present = bool(str(row.get('ror') or '').strip())
            confidence = float(row.get('confidence') or 0.0)
            method = str(row.get('match_method') or row.get('method') or '')

            decision = 'KEEP_REVIEW'
            reason = 'insufficient_positive_evidence'
            if country_conflict:
                decision, reason = 'REJECT', 'sec_openalex_country_conflict'
            elif source == 'accepted':
                decision, reason = 'KEEP_PRODUCTION', 'production_link_no_country_conflict'
            elif source == 'quarantine':
                if institution_type == 'company' and ror_present and confidence >= 0.98 and (country_match or not country_comparable):
                    decision, reason = 'PROMOTE', 'corporate_type_ror_high_confidence_no_country_conflict'
                elif country_match and ror_present and confidence >= 0.98:
                    decision, reason = 'REVIEW_PRIORITY', 'country_match_ror_high_confidence_but_noncompany_type'
                else:
                    decision, reason = 'KEEP_QUARANTINE', 'metadata_gate_not_cleared'
            else:
                if country_match and institution_type == 'company' and ror_present and confidence >= 0.965:
                    decision, reason = 'PROMOTE', 'country_match_company_type_ror_high_confidence'
                elif country_match and ror_present and confidence >= 0.93:
                    decision, reason = 'REVIEW_PRIORITY', 'country_match_ror_moderate_confidence'
                else:
                    decision, reason = 'KEEP_REVIEW', 'review_evidence_not_sufficient'

            row.update({
                'source_bucket': source,
                'sec_business_country_iso2': sec_country,
                'openalex_country_iso2': oa_country,
                'country_comparable': country_comparable,
                'country_match': country_match,
                'country_conflict': country_conflict,
                'reclassification_decision': decision,
                'reclassification_reason': reason,
            })
            records.append(row)
        return records

    records = classify(production, 'accepted') + classify(quarantined, 'quarantine') + classify(review, 'review')
    if not records:
        raise RuntimeError('reclassification produced zero records')

    import pandas as pd
    all_df = pd.DataFrame(records)
    con = duckdb.connect(database=':memory:')
    try:
        con.register('all_df', all_df)
        out_all = out_dir/'SEC_OPENALEX_ORG_GEO_RECLASSIFICATION.parquet'
        con.execute(f"COPY all_df TO '{out_all.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        prod_df = all_df[all_df['reclassification_decision'].isin(['KEEP_PRODUCTION','PROMOTE'])].copy()
        con.register('prod_df', prod_df)
        out_prod = out_dir/'SEC_OPENALEX_ORG_PRODUCTION_BRIDGE_V2.parquet'
        con.execute(f"COPY prod_df TO '{out_prod.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()

    decisions = {str(k): int(v) for k,v in all_df['reclassification_decision'].value_counts().to_dict().items()}
    sources = {str(k): int(v) for k,v in all_df['source_bucket'].value_counts().to_dict().items()}
    comparable = int(all_df['country_comparable'].sum())
    matches = int(all_df['country_match'].sum())
    conflicts = int(all_df['country_conflict'].sum())
    promoted = int((all_df['reclassification_decision']=='PROMOTE').sum())
    manifest = {
        'version':'v2',
        'input_rows':len(all_df),
        'source_bucket_counts':sources,
        'decision_counts':decisions,
        'country_comparable_rows':comparable,
        'country_match_rows':matches,
        'country_conflict_rows':conflicts,
        'newly_promoted_rows':promoted,
        'production_v2_rows':int(len(prod_df)),
        'policy':'country contradictions block promotion; positive geography supplements but does not replace type/ROR/confidence evidence',
    }
    (out_dir/'organization_geo_reclassification_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return manifest


def main() -> int:
    p=argparse.ArgumentParser(description='Reclassify SEC/OpenAlex organization matches using SEC issuer geography')
    p.add_argument('--issuer-metadata',type=Path,required=True)
    p.add_argument('--production-bridge',type=Path,required=True)
    p.add_argument('--quarantine',type=Path,required=True)
    p.add_argument('--review-queue',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(reclassify(a.issuer_metadata,a.production_bridge,a.quarantine,a.review_queue,a.out_dir),indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
