from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import duckdb

CURATED_DEFAULT = "gdrive:02_CURATED/openalex/v1"
PARTIAL_DEFAULT = "gdrive:03_RESEARCH/cross_domain/v1/_partials/company_work_marts"
TARGET_DEFAULT = "gdrive:03_RESEARCH/cross_domain/v1"
CONTROL_DEFAULT = "gdrive:00_CONTROL/analytics/cross_domain/company_work_marts"

STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
  relpath TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  topic_rows INTEGER DEFAULT 0,
  collaboration_rows INTEGER DEFAULT 0,
  processed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _lit(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def _run(args: list[str], *, capture: bool = False, check: bool = True) -> str:
    p = subprocess.run(["rclone", *args], text=True, capture_output=capture, check=False)
    if check and p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "rclone failed").strip())
    return p.stdout if capture else ""


def _download_optional(remote: str, local: Path) -> bool:
    p = subprocess.run(["rclone", "copyto", remote, str(local), "--stats", "0"], text=True, capture_output=True)
    return p.returncode == 0 and local.exists()


def _safe_name(relpath: str) -> str:
    return hashlib.sha256(relpath.encode("utf-8")).hexdigest()[:16] + ".parquet"


def build_shard_partials(
    production_bridge: Path,
    work: Path,
    author_institution: Path,
    out_dir: Path,
    *,
    topic: Path | None = None,
) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=":memory:")
    counts = {"COMPANY_TOPIC_YEAR": 0, "COMPANY_COLLABORATION_YEAR": 0}
    try:
        con.execute(f"CREATE VIEW prod AS SELECT canonical_company_id,openalex_institution_id FROM read_parquet({_lit(production_bridge.as_posix())})")
        con.execute(f"CREATE VIEW w AS SELECT id,publication_year,cited_by_count FROM read_parquet({_lit(work.as_posix())})")
        con.execute(f"CREATE VIEW ai AS SELECT * FROM read_parquet({_lit(author_institution.as_posix())})")
        cols = {str(r[0]) for r in con.execute("DESCRIBE SELECT * FROM ai").fetchall()}
        if not {"work_id", "institution_id"} <= cols:
            raise RuntimeError("AUTHOR_INSTITUTION_EDGES shard missing work_id/institution_id")
        country_expr = "institution_country_code" if "institution_country_code" in cols else "NULL::VARCHAR"
        con.execute(f'''
            CREATE TEMP TABLE target_work AS
            SELECT DISTINCT p.canonical_company_id,p.openalex_institution_id,a.work_id
            FROM ai a JOIN prod p ON a.institution_id=p.openalex_institution_id
        ''')
        target_count = int(con.execute("SELECT COUNT(*) FROM target_work").fetchone()[0])
        if target_count == 0:
            return counts

        if topic and topic.exists():
            con.execute(f"CREATE VIEW wt AS SELECT * FROM read_parquet({_lit(topic.as_posix())})")
            tcols = {str(r[0]) for r in con.execute("DESCRIBE SELECT * FROM wt").fetchall()}
            if {"work_id", "topic_id"} <= tcols:
                topic_score = "COALESCE(t.topic_score,0)" if "topic_score" in tcols else "0"
                topic_out = out_dir / "COMPANY_TOPIC_YEAR.parquet"
                con.execute(f'''
                    COPY (
                      SELECT tw.canonical_company_id,
                             tw.openalex_institution_id,
                             w.publication_year,
                             t.topic_id,
                             COUNT(DISTINCT tw.work_id)::BIGINT AS work_count,
                             SUM(COALESCE(w.cited_by_count,0))::BIGINT AS citation_sum,
                             SUM({topic_score})::DOUBLE AS topic_score_sum
                      FROM target_work tw
                      JOIN w ON w.id=tw.work_id
                      JOIN wt t ON t.work_id=tw.work_id
                      WHERE w.publication_year IS NOT NULL AND t.topic_id IS NOT NULL
                      GROUP BY tw.canonical_company_id,tw.openalex_institution_id,w.publication_year,t.topic_id
                    ) TO {_lit(topic_out.as_posix())} (FORMAT PARQUET, COMPRESSION ZSTD)
                ''')
                counts["COMPANY_TOPIC_YEAR"] = int(con.execute(f"SELECT COUNT(*) FROM read_parquet({_lit(topic_out.as_posix())})").fetchone()[0])

        collab_out = out_dir / "COMPANY_COLLABORATION_YEAR.parquet"
        con.execute(f'''
            COPY (
              WITH pairs AS (
                SELECT DISTINCT tw.canonical_company_id,
                       tw.openalex_institution_id,
                       tw.work_id,
                       a2.institution_id AS collaborator_institution_id,
                       {country_expr.replace('institution_country_code','a2.institution_country_code')} AS collaborator_country_code
                FROM target_work tw
                JOIN ai a2 ON a2.work_id=tw.work_id
                WHERE a2.institution_id IS NOT NULL
                  AND a2.institution_id<>tw.openalex_institution_id
                  AND {country_expr.replace('institution_country_code','a2.institution_country_code')} IS NOT NULL
                  AND CAST({country_expr.replace('institution_country_code','a2.institution_country_code')} AS VARCHAR)<>''
              )
              , work_country AS (
                SELECT p.canonical_company_id,
                       p.openalex_institution_id,
                       p.work_id,
                       p.collaborator_country_code,
                       COUNT(DISTINCT p.collaborator_institution_id)::BIGINT AS collaborator_institution_count
                FROM pairs p
                GROUP BY p.canonical_company_id,p.openalex_institution_id,p.work_id,p.collaborator_country_code
              )
              SELECT p.canonical_company_id,
                     p.openalex_institution_id,
                     w.publication_year,
                     p.collaborator_country_code,
                     COUNT(*)::BIGINT AS collaborative_work_count,
                     SUM(p.collaborator_institution_count)::BIGINT AS collaborator_institution_count,
                     SUM(COALESCE(w.cited_by_count,0))::BIGINT AS citation_sum
              FROM work_country p
              JOIN w ON w.id=p.work_id
              WHERE w.publication_year IS NOT NULL
              GROUP BY p.canonical_company_id,p.openalex_institution_id,w.publication_year,p.collaborator_country_code
            ) TO {_lit(collab_out.as_posix())} (FORMAT PARQUET, COMPRESSION ZSTD)
        ''')
        counts["COMPANY_COLLABORATION_YEAR"] = int(con.execute(f"SELECT COUNT(*) FROM read_parquet({_lit(collab_out.as_posix())})").fetchone()[0])
    finally:
        con.close()
    return counts


def map_batch(batch: int, batches: int, production_bridge: Path) -> int:
    curated = os.environ.get("GMSDL_OPENALEX_CURATED_REMOTE", CURATED_DEFAULT).rstrip("/")
    partial = os.environ.get("GMSDL_COMPANY_WORK_PARTIAL_REMOTE", PARTIAL_DEFAULT).rstrip("/")
    control = os.environ.get("GMSDL_COMPANY_WORK_CONTROL_REMOTE", CONTROL_DEFAULT).rstrip("/")
    listing = _run(["lsf", f"{curated}/WORK_MASTER", "--files-only", "--recursive"], capture=True)
    paths = sorted(x.strip() for x in listing.splitlines() if x.strip().endswith(".parquet"))
    selected = [p for i,p in enumerate(paths) if i % batches == batch]
    if not selected:
        return 0

    with tempfile.TemporaryDirectory(prefix=f"company-work-{batch:03d}-") as td:
        root = Path(td)
        state = root / f"company_work_batch_{batch:03d}.sqlite"
        state_remote = f"{control}/{state.name}"
        _download_optional(state_remote, state)
        db = sqlite3.connect(state)
        db.executescript(STATE_SCHEMA)
        db.commit()
        try:
            for relpath in selected:
                if db.execute("SELECT 1 FROM files WHERE relpath=? AND status='OK'", (relpath,)).fetchone():
                    continue
                work = root/'work.parquet'; ai = root/'ai.parquet'; topic = root/'topic.parquet'
                for p in (work,ai,topic):
                    if p.exists(): p.unlink()
                _run(["copyto", f"{curated}/WORK_MASTER/{relpath}", str(work), "--stats", "0"])
                if not _download_optional(f"{curated}/AUTHOR_INSTITUTION_EDGES/{relpath}", ai):
                    db.execute("INSERT OR REPLACE INTO files(relpath,status) VALUES(?,?)", (relpath,'OK'))
                    db.commit(); _run(["copyto",str(state),state_remote,"--stats","0"]); continue
                _download_optional(f"{curated}/WORK_TOPIC_EDGES/{relpath}", topic)
                out = root/'out'
                if out.exists(): shutil.rmtree(out)
                counts = build_shard_partials(production_bridge,work,ai,out,topic=topic if topic.exists() else None)
                fname = _safe_name(relpath)
                for mart,n in counts.items():
                    src = out/f"{mart}.parquet"
                    if n>0 and src.exists():
                        _run(["copyto",str(src),f"{partial}/{mart}/batch={batch:03d}/{fname}","--stats","0"])
                db.execute("INSERT OR REPLACE INTO files(relpath,status,topic_rows,collaboration_rows) VALUES(?,?,?,?)", (relpath,'OK',counts['COMPANY_TOPIC_YEAR'],counts['COMPANY_COLLABORATION_YEAR']))
                db.commit(); _run(["copyto",str(state),state_remote,"--stats","0"])
        finally:
            db.close()
    return 0


def reduce_local(partial_root: Path, out_dir: Path) -> dict[str,int]:
    out_dir.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(database=':memory:')
    result={}
    try:
        specs={
          'COMPANY_TOPIC_YEAR':(['canonical_company_id','openalex_institution_id','publication_year','topic_id'],['work_count','citation_sum','topic_score_sum']),
          'COMPANY_COLLABORATION_YEAR':(['canonical_company_id','openalex_institution_id','publication_year','collaborator_country_code'],['collaborative_work_count','collaborator_institution_count','citation_sum']),
        }
        for mart,(keys,sums) in specs.items():
            files=list((partial_root/mart).rglob('*.parquet'))
            if not files: continue
            glob=(partial_root/mart/'**'/'*.parquet').as_posix()
            group=','.join(keys)
            select=','.join(keys+[f'SUM({x}) AS {x}' for x in sums])
            dst=out_dir/f'{mart}.parquet'
            con.execute(f"COPY (SELECT {select} FROM read_parquet({_lit(glob)},union_by_name=true) GROUP BY {group}) TO {_lit(dst.as_posix())} (FORMAT PARQUET, COMPRESSION ZSTD)")
            result[mart]=int(con.execute(f"SELECT COUNT(*) FROM read_parquet({_lit(dst.as_posix())})").fetchone()[0])
    finally:
        con.close()
    return result


def reduce_remote() -> int:
    partial=os.environ.get('GMSDL_COMPANY_WORK_PARTIAL_REMOTE',PARTIAL_DEFAULT).rstrip('/')
    target=os.environ.get('GMSDL_COMPANY_WORK_TARGET_REMOTE',TARGET_DEFAULT).rstrip('/')
    with tempfile.TemporaryDirectory(prefix='company-work-reduce-') as td:
        root=Path(td); local=root/'partials'; out=root/'out'
        _run(['copy',partial,str(local),'--stats','0'])
        result=reduce_local(local,out)
        if set(result)!={'COMPANY_TOPIC_YEAR','COMPANY_COLLABORATION_YEAR'}:
            raise RuntimeError(f'missing reduced marts: {result}')
        manifest={'version':'v1','marts':result,'identity_policy':'production-approved SEC/OpenAlex bridge only'}
        for mart in result:
            _run(['copyto',str(out/f'{mart}.parquet'),f'{target}/{mart}/part-0000.parquet','--stats','0'])
        mf=root/'company_work_marts_manifest.json'; mf.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        _run(['copyto',str(mf),'gdrive:00_CONTROL/analytics/cross_domain/company_work_marts_manifest.json','--stats','0'])
        print(json.dumps(manifest,indent=2,sort_keys=True))
    return 0


def main() -> int:
    p=argparse.ArgumentParser(description='Build work-level company topic/collaboration marts')
    sub=p.add_subparsers(dest='command',required=True)
    m=sub.add_parser('map'); m.add_argument('--batch',type=int,required=True); m.add_argument('--batches',type=int,default=120); m.add_argument('--production-bridge',type=Path,required=True)
    sub.add_parser('reduce')
    a=p.parse_args()
    if a.command=='map': return map_batch(a.batch,a.batches,a.production_bridge)
    return reduce_remote()

if __name__=='__main__':
    raise SystemExit(main())
