from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def rank_unresolved(reclassification: Path, adjudication_v3: Path, adjudication_v4: Path, adjudication_v5: Path, adjudication_v6: Path, adjudication_v7: Path, adjudication_v8: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    a3=json.loads(adjudication_v3.read_text(encoding='utf-8'))
    a4=json.loads(adjudication_v4.read_text(encoding='utf-8'))
    a5=json.loads(adjudication_v5.read_text(encoding='utf-8'))
    a6=json.loads(adjudication_v6.read_text(encoding='utf-8'))
    a7=json.loads(adjudication_v7.read_text(encoding='utf-8'))
    a8=json.loads(adjudication_v8.read_text(encoding='utf-8'))
    final_decisions={}
    for item in a3.get('items',[]):
        final_decisions[item['canonical_company_id']]=item.get('decision')
    for item in a4.get('items',[]):
        final_decisions[item['canonical_company_id']]=item.get('decision')
    for item in a5.get('items',[]):
        final_decisions[item['canonical_company_id']]=item.get('decision')
    for item in a6.get('items',[]):
        final_decisions[item['canonical_company_id']]=item.get('decision')
    for item in a7.get('items',[]):
        final_decisions[item['canonical_company_id']]=item.get('decision')
    for item in a8.get('items',[]):
        final_decisions[item['canonical_company_id']]=item.get('decision')
    excluded={cid for cid,d in final_decisions.items() if d in {'PROMOTE','REJECT'}}

    con=duckdb.connect(database=':memory:')
    try:
        con.execute(f"CREATE VIEW r AS SELECT * FROM read_parquet('{reclassification.as_posix()}')")
        con.execute('CREATE TEMP TABLE excluded(canonical_company_id VARCHAR)')
        if excluded:
            con.executemany('INSERT INTO excluded VALUES (?)',[(x,) for x in sorted(excluded)])
        con.execute('''
            CREATE TABLE unresolved AS
            WITH base AS (
              SELECT r.*,
                CASE WHEN lower(COALESCE(institution_type,''))='company' THEN 1 ELSE 0 END AS type_company,
                CASE WHEN ror IS NOT NULL AND trim(ror)<>'' THEN 1 ELSE 0 END AS has_ror,
                CASE WHEN country_match THEN 1 ELSE 0 END AS has_country_match,
                CASE WHEN country_conflict THEN 1 ELSE 0 END AS has_country_conflict,
                CASE
                  WHEN match_method='NORMALIZED_EXACT' THEN 3
                  WHEN match_method='LEGAL_CORE_EXACT' THEN 2
                  WHEN match_method='FUZZY_CORE' THEN 1
                  ELSE 0
                END AS method_score
              FROM r
              WHERE reclassification_decision NOT IN ('KEEP_PRODUCTION','PROMOTE','REJECT')
                AND NOT EXISTS (SELECT 1 FROM excluded e WHERE e.canonical_company_id=r.canonical_company_id)
            )
            SELECT *,
              (
                COALESCE(confidence,0)*100
                + type_company*12
                + has_ror*8
                + has_country_match*15
                - has_country_conflict*100
                + method_score*5
                + CASE WHEN source_bucket='quarantine' THEN 3 ELSE 0 END
              ) AS review_score,
              CASE
                WHEN has_country_conflict=1 THEN 'BLOCKED_COUNTRY_CONFLICT'
                WHEN has_country_match=1 AND type_company=1 AND has_ror=1 AND confidence>=0.93 THEN 'TIER_A_STRONG'
                WHEN has_country_match=1 AND has_ror=1 AND confidence>=0.90 THEN 'TIER_B_GOOD'
                WHEN has_ror=1 AND confidence>=0.90 THEN 'TIER_C_MODERATE'
                ELSE 'TIER_D_LOW'
              END AS review_tier
            FROM base
        ''')
        con.execute('''
            CREATE TABLE ranked AS
            SELECT *, ROW_NUMBER() OVER (
              ORDER BY
                CASE review_tier
                  WHEN 'TIER_A_STRONG' THEN 1
                  WHEN 'TIER_B_GOOD' THEN 2
                  WHEN 'TIER_C_MODERATE' THEN 3
                  WHEN 'TIER_D_LOW' THEN 4
                  ELSE 5
                END,
                review_score DESC,
                canonical_company_id
            ) AS review_rank
            FROM unresolved
        ''')
        rows=int(con.execute('SELECT COUNT(*) FROM ranked').fetchone()[0])
        tier_counts={str(k):int(v) for k,v in con.execute('SELECT review_tier,COUNT(*) FROM ranked GROUP BY 1 ORDER BY 1').fetchall()}
        top=con.execute('''
            SELECT review_rank,review_tier,canonical_company_id,sec_name,openalex_name,confidence,match_method,
                   institution_type,ror,sec_business_country_iso2,openalex_country_iso2,country_match,country_conflict,
                   reclassification_decision,reclassification_reason,review_score
            FROM ranked ORDER BY review_rank LIMIT 20
        ''').fetchall()
        cols=[x[0] for x in con.execute('''DESCRIBE SELECT review_rank,review_tier,canonical_company_id,sec_name,openalex_name,confidence,match_method,institution_type,ror,sec_business_country_iso2,openalex_country_iso2,country_match,country_conflict,reclassification_decision,reclassification_reason,review_score FROM ranked''').fetchall()]
        items=[dict(zip(cols,r)) for r in top]
        pq=out_dir/'SEC_OPENALEX_ORG_UNRESOLVED_RANKED.parquet'
        csv=out_dir/'SEC_OPENALEX_ORG_UNRESOLVED_RANKED.csv'
        con.execute(f"COPY ranked TO '{pq.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY ranked TO '{csv.as_posix()}' (HEADER, DELIMITER ',')")
    finally:
        con.close()
    manifest={'version':'v1','unresolved_rows':rows,'tier_counts':tier_counts,'top20':items}
    (out_dir/'organization_unresolved_rank_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True,default=str)+'\n',encoding='utf-8')
    return manifest


def main() -> int:
    p=argparse.ArgumentParser(description='Rank unresolved SEC/OpenAlex organization candidates for batch adjudication')
    p.add_argument('--reclassification',type=Path,required=True)
    p.add_argument('--adjudication-v3',type=Path,required=True)
    p.add_argument('--adjudication-v4',type=Path,required=True)
    p.add_argument('--adjudication-v5',type=Path,required=True)
    p.add_argument('--adjudication-v6',type=Path,required=True)
    p.add_argument('--adjudication-v7',type=Path,required=True)
    p.add_argument('--adjudication-v8',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(rank_unresolved(a.reclassification,a.adjudication_v3,a.adjudication_v4,a.adjudication_v5,a.adjudication_v6,a.adjudication_v7,a.adjudication_v8,a.out_dir),indent=2,sort_keys=True,default=str))
    return 0

if __name__=='__main__':
    raise SystemExit(main())

