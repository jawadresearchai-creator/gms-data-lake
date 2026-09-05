from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import duckdb

LEGAL_SUFFIXES = {
    'inc','incorporated','corp','corporation','co','company','ltd','limited','plc','llc','lp','llp',
    'sa','ag','nv','bv','spa','srl','gmbh','pte','pty','holdco'
}
STOP_ACRONYM = LEGAL_SUFFIXES | {'the','of','and','for','a','an'}


def normalize_name(value: str | None) -> str:
    if not value:
        return ''
    s = re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()
    return re.sub(r'\s+', ' ', s)


def legal_core(value: str | None) -> str:
    toks = normalize_name(value).split()
    while toks and toks[-1] in LEGAL_SUFFIXES:
        toks.pop()
    return ' '.join(toks)


def acronym(value: str | None) -> str:
    toks = [t for t in legal_core(value).split() if t not in STOP_ACRONYM]
    if len(toks) < 2:
        return ''
    return ''.join(t[0] for t in toks if t)


def compact(value: str) -> str:
    return value.replace(' ', '')


def build_scored_bridge(company_master: Path, institution_root: Path, exact_bridge: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    inst_files = sorted(institution_root.rglob('*.parquet'))
    if not inst_files:
        raise RuntimeError('no OpenAlex institution parquet files found')
    glob = (institution_root / '**' / '*.parquet').as_posix()
    con = duckdb.connect(database=':memory:')
    try:
        sec_rows = con.execute(f"SELECT canonical_company_id,cik,company_name,primary_ticker,source_class FROM read_parquet('{company_master.as_posix()}')").fetchall()
        cols = {str(r[0]) for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{glob}', union_by_name=true)").fetchall()}
        id_col = 'id' if 'id' in cols else 'institution_id'
        name_col = 'display_name' if 'display_name' in cols else 'name'
        ror_col = 'ror' if 'ror' in cols else 'NULL'
        country_col = 'country_code' if 'country_code' in cols else 'NULL'
        type_col = 'type' if 'type' in cols else ('institution_type' if 'institution_type' in cols else 'NULL')
        inst_rows = con.execute(
            f"SELECT {id_col},{name_col},{ror_col},{country_col},{type_col} FROM read_parquet('{glob}', union_by_name=true) WHERE {id_col} IS NOT NULL AND {name_col} IS NOT NULL"
        ).fetchall()
        exact_pairs = set()
        if exact_bridge.exists():
            exact_pairs = {(str(a), str(b)) for a,b in con.execute(f"SELECT canonical_company_id,openalex_institution_id FROM read_parquet('{exact_bridge.as_posix()}')").fetchall()}
    finally:
        con.close()

    sec = []
    for cid,cik,name,ticker,source_class in sec_rows:
        n = normalize_name(name); core = legal_core(name); ac = acronym(name)
        sec.append({'cid':str(cid),'cik':str(cik),'name':str(name) if name is not None else '', 'ticker':ticker,'source_class':source_class,'norm':n,'core':core,'acronym':ac})
    inst = []
    for iid,name,ror,country,itype in inst_rows:
        n = normalize_name(name); core = legal_core(name); ac = acronym(name)
        inst.append({'iid':str(iid),'name':str(name),'ror':ror,'country':country,'type':itype,'norm':n,'core':core,'acronym':ac})

    sec_core_count = Counter(x['core'] for x in sec if x['core'])
    inst_core_count = Counter(x['core'] for x in inst if x['core'])
    inst_by_core = defaultdict(list)
    for x in inst:
        if x['core']:
            inst_by_core[x['core']].append(x)

    accepted = []
    candidates = []
    matched_sec = set(a for a,_ in exact_pairs)
    matched_inst = set(b for _,b in exact_pairs)

    # Tier 1: legal-suffix normalized exact, unique on both sides.
    for s in sec:
        if s['cid'] in matched_sec or not s['core']:
            continue
        hits = inst_by_core.get(s['core'], [])
        for i in hits:
            if i['iid'] in matched_inst:
                continue
            unique = sec_core_count[s['core']] == 1 and inst_core_count[s['core']] == 1
            row = {
                'canonical_company_id':s['cid'],'cik':s['cik'],'sec_name':s['name'],'primary_ticker':s['ticker'],'source_class':s['source_class'],
                'openalex_institution_id':i['iid'],'openalex_name':i['name'],'ror':i['ror'],'country_code':i['country'],'institution_type':i['type'],
                'method':'LEGAL_CORE_EXACT','name_similarity':1.0,'core_similarity':1.0,'acronym_match':bool(s['acronym'] and s['acronym']==i['acronym']),
                'unique_sec_core':sec_core_count[s['core']]==1,'unique_openalex_core':inst_core_count[s['core']]==1,
                'confidence':0.98 if unique else 0.70,'tier':'HIGH' if unique else 'REVIEW','accepted':bool(unique),
            }
            candidates.append(row)
            if unique:
                accepted.append(row); matched_sec.add(s['cid']); matched_inst.add(i['iid'])

    # Tier 2: blocked fuzzy core matching. Keep review candidates unless score+margin are exceptional.
    blocks = defaultdict(list)
    for i in inst:
        cc = compact(i['core'])
        if len(cc) >= 4 and i['iid'] not in matched_inst:
            blocks[(cc[:4], len(cc)//5)].append(i)

    for s in sec:
        if s['cid'] in matched_sec:
            continue
        sc = compact(s['core'])
        if len(sc) < 5:
            continue
        pool = []
        bucket = len(sc)//5
        for b in (bucket-1,bucket,bucket+1):
            pool.extend(blocks.get((sc[:4],b), []))
        scored = []
        for i in pool:
            ic = compact(i['core'])
            sim = SequenceMatcher(None, sc, ic).ratio()
            if sim < 0.88:
                continue
            ac_match = bool(s['acronym'] and i['acronym'] and s['acronym']==i['acronym'])
            type_company = str(i['type']).lower() == 'company' if i['type'] is not None else False
            score = sim + (0.025 if ac_match else 0.0) + (0.01 if type_company else 0.0)
            scored.append((score,sim,ac_match,type_company,i))
        scored.sort(key=lambda x:(-x[0],x[4]['iid']))
        if not scored:
            continue
        best = scored[0]
        second = scored[1][0] if len(scored)>1 else 0.0
        margin = best[0]-second
        # Auto-accept only extremely close, strongly separated candidates.
        auto = best[1] >= 0.965 and margin >= 0.04 and (best[2] or best[3])
        for rank,(score,sim,ac_match,type_company,i) in enumerate(scored[:5], start=1):
            is_best = rank==1
            row = {
                'canonical_company_id':s['cid'],'cik':s['cik'],'sec_name':s['name'],'primary_ticker':s['ticker'],'source_class':s['source_class'],
                'openalex_institution_id':i['iid'],'openalex_name':i['name'],'ror':i['ror'],'country_code':i['country'],'institution_type':i['type'],
                'method':'FUZZY_CORE','name_similarity':float(sim),'core_similarity':float(sim),'acronym_match':bool(ac_match),
                'unique_sec_core':sec_core_count[s['core']]==1,'unique_openalex_core':inst_core_count[i['core']]==1,
                'confidence':float(min(0.97,score)) if is_best else float(min(0.89,score)),
                'tier':'HIGH' if (is_best and auto) else 'REVIEW','accepted':bool(is_best and auto),
                'candidate_rank':rank,'best_margin':float(margin) if is_best else None,
            }
            candidates.append(row)
            if is_best and auto:
                accepted.append(row); matched_sec.add(s['cid']); matched_inst.add(i['iid'])

    # Preserve exact anchors in the final accepted bridge.
    con = duckdb.connect(database=':memory:')
    try:
        if exact_bridge.exists():
            con.execute(f"CREATE TABLE exact AS SELECT *, 'EXACT' AS tier FROM read_parquet('{exact_bridge.as_posix()}')")
        else:
            con.execute("CREATE TABLE exact(canonical_company_id VARCHAR,openalex_institution_id VARCHAR,tier VARCHAR)")

        def write_rows(rows, path: Path):
            if not rows:
                path.write_bytes(b'')
                return
            import pandas as pd
            df = pd.DataFrame(rows)
            con.register('df_tmp', df)
            con.execute(f"COPY df_tmp TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            con.unregister('df_tmp')

        cand_path = out_dir/'SEC_OPENALEX_ORG_SCORED_CANDIDATES.parquet'
        acc_path = out_dir/'SEC_OPENALEX_ORG_SCORED_ACCEPTED.parquet'
        write_rows(candidates, cand_path)
        write_rows(accepted, acc_path)
    finally:
        con.close()

    method_counts = Counter(r['method'] for r in accepted)
    tier_counts = Counter(r['tier'] for r in candidates)
    manifest = {
        'version':'v2',
        'sec_company_rows':len(sec),
        'openalex_institution_rows':len(inst),
        'preserved_exact_matches':len(exact_pairs),
        'new_accepted_matches':len(accepted),
        'new_accepted_by_method':dict(method_counts),
        'candidate_rows':len(candidates),
        'candidate_tiers':dict(tier_counts),
        'total_accepted_including_exact':len(exact_pairs)+len(accepted),
        'policy':{
            'legal_core_exact':'accept only when normalized legal-core name is unique on both sides',
            'fuzzy_core':'block by first four compact characters and approximate length; auto-accept only similarity >=0.965, margin >=0.04, and acronym or OpenAlex company-type evidence',
            'fuzzy_review':'all other fuzzy candidates remain unaccepted review candidates',
        },
    }
    (out_dir/'sec_openalex_org_scored_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return manifest


def main() -> int:
    p=argparse.ArgumentParser(description='Build evidence-scored SEC/OpenAlex organization bridge')
    p.add_argument('--company-master',type=Path,required=True)
    p.add_argument('--institution-root',type=Path,required=True)
    p.add_argument('--exact-bridge',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(build_scored_bridge(a.company_master,a.institution_root,a.exact_bridge,a.out_dir),indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
