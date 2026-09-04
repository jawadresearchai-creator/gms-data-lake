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
PARTIAL_DEFAULT = "gdrive:03_RESEARCH/openalex/v1/marts/_partials"
MART_DEFAULT = "gdrive:03_RESEARCH/openalex/v1/marts"
CONTROL_DEFAULT = "gdrive:00_CONTROL/analytics/openalex/marts"

MARTS = (
    "WORK_YEAR_METRICS",
    "WORK_YEAR_TOPIC",
    "WORK_YEAR_INSTITUTION",
    "WORK_YEAR_COUNTRY",
    "COUNTRY_COLLAB_YEAR",
)

STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
  relpath TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  outputs INTEGER DEFAULT 0,
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


def _cols(con: duckdb.DuckDBPyConnection, path: Path) -> set[str]:
    return {str(r[0]) for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet({_lit(path.as_posix())})").fetchall()}


def build_partials(
    work: Path,
    out_dir: Path,
    *,
    topic: Path | None = None,
    institution: Path | None = None,
    collaboration: Path | None = None,
) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=":memory:")
    counts: dict[str, int] = {}
    try:
        wc = _cols(con, work)
        required = {"id", "publication_year"}
        if not required <= wc:
            raise RuntimeError(f"WORK_MASTER shard missing required columns: {sorted(required - wc)}")
        cited = "COALESCE(cited_by_count,0)" if "cited_by_count" in wc else "0"
        wrel = f"read_parquet({_lit(work.as_posix())})"

        queries: dict[str, str] = {
            "WORK_YEAR_METRICS": f"""
                SELECT publication_year,
                       COUNT(*)::BIGINT AS work_count,
                       SUM({cited})::BIGINT AS citation_sum
                FROM {wrel}
                WHERE publication_year IS NOT NULL
                GROUP BY publication_year
            """,
        }

        if topic and topic.exists():
            tc = _cols(con, topic)
            if {"work_id", "topic_id"} <= tc:
                score = "COALESCE(e.topic_score,0)" if "topic_score" in tc else "0"
                queries["WORK_YEAR_TOPIC"] = f"""
                    SELECT w.publication_year, e.topic_id,
                           COUNT(DISTINCT w.id)::BIGINT AS work_count,
                           SUM({cited.replace('cited_by_count','w.cited_by_count')})::BIGINT AS citation_sum,
                           SUM({score})::DOUBLE AS topic_score_sum
                    FROM {wrel} w
                    JOIN read_parquet({_lit(topic.as_posix())}) e ON e.work_id=w.id
                    WHERE w.publication_year IS NOT NULL AND e.topic_id IS NOT NULL
                    GROUP BY w.publication_year, e.topic_id
                """

        if institution and institution.exists():
            ic = _cols(con, institution)
            if {"work_id", "institution_id"} <= ic:
                base = f"""
                    WITH x AS (
                      SELECT DISTINCT w.id AS work_id, w.publication_year,
                             {cited.replace('cited_by_count','w.cited_by_count')} AS cited_by_count,
                             e.institution_id,
                             {('e.institution_country_code' if 'institution_country_code' in ic else 'NULL')} AS country_code
                      FROM {wrel} w
                      JOIN read_parquet({_lit(institution.as_posix())}) e ON e.work_id=w.id
                      WHERE w.publication_year IS NOT NULL AND e.institution_id IS NOT NULL
                    )
                """
                queries["WORK_YEAR_INSTITUTION"] = base + """
                    SELECT publication_year, institution_id,
                           COUNT(DISTINCT work_id)::BIGINT AS work_count,
                           SUM(cited_by_count)::BIGINT AS citation_sum
                    FROM x GROUP BY publication_year, institution_id
                """
                if "institution_country_code" in ic:
                    queries["WORK_YEAR_COUNTRY"] = f"""
                        WITH x AS (
                          SELECT DISTINCT w.id AS work_id, w.publication_year,
                                 {cited.replace('cited_by_count','w.cited_by_count')} AS cited_by_count,
                                 e.institution_country_code AS country_code
                          FROM {wrel} w
                          JOIN read_parquet({_lit(institution.as_posix())}) e ON e.work_id=w.id
                          WHERE w.publication_year IS NOT NULL
                            AND e.institution_country_code IS NOT NULL
                            AND e.institution_country_code <> ''
                        )
                        SELECT publication_year, country_code,
                               COUNT(*)::BIGINT AS work_count,
                               SUM(cited_by_count)::BIGINT AS citation_sum
                        FROM x GROUP BY publication_year, country_code
                    """

        if collaboration and collaboration.exists():
            cc = _cols(con, collaboration)
            if {"work_id", "country_a", "country_b"} <= cc:
                queries["COUNTRY_COLLAB_YEAR"] = f"""
                    SELECT w.publication_year, e.country_a, e.country_b,
                           COUNT(DISTINCT w.id)::BIGINT AS work_count,
                           SUM({cited.replace('cited_by_count','w.cited_by_count')})::BIGINT AS citation_sum
                    FROM {wrel} w
                    JOIN read_parquet({_lit(collaboration.as_posix())}) e ON e.work_id=w.id
                    WHERE w.publication_year IS NOT NULL
                      AND e.country_a IS NOT NULL AND e.country_b IS NOT NULL
                      AND e.country_a <> '' AND e.country_b <> '' AND e.country_a < e.country_b
                    GROUP BY w.publication_year, e.country_a, e.country_b
                """

        for name, sql in queries.items():
            dst = out_dir / f"{name}.parquet"
            con.execute(f"COPY ({sql}) TO {_lit(dst.as_posix())} (FORMAT PARQUET, COMPRESSION ZSTD)")
            counts[name] = int(con.execute(f"SELECT COUNT(*) FROM read_parquet({_lit(dst.as_posix())})").fetchone()[0])
    finally:
        con.close()
    return counts


def _safe_relname(relpath: str) -> str:
    h = hashlib.sha256(relpath.encode("utf-8")).hexdigest()[:16]
    return f"{h}.parquet"


def map_batch(batch: int, batches: int) -> int:
    if shutil.which("rclone") is None:
        raise RuntimeError("rclone not found on PATH")
    curated = os.environ.get("GMSDL_OPENALEX_CURATED_REMOTE", CURATED_DEFAULT).rstrip("/")
    partial = os.environ.get("GMSDL_OPENALEX_MART_PARTIAL_REMOTE", PARTIAL_DEFAULT).rstrip("/")
    control = os.environ.get("GMSDL_OPENALEX_MART_CONTROL_REMOTE", CONTROL_DEFAULT).rstrip("/")

    listing = _run(["lsf", f"{curated}/WORK_MASTER", "--files-only", "--recursive"], capture=True)
    paths = sorted(x.strip() for x in listing.splitlines() if x.strip().endswith(".parquet"))
    selected = [p for i, p in enumerate(paths) if i % batches == batch]
    if not selected:
        print(f"batch {batch}: no WORK_MASTER shards selected")
        return 0

    with tempfile.TemporaryDirectory(prefix=f"gmsdl-marts-{batch:03d}-") as td:
        root = Path(td)
        state = root / f"openalex_marts_batch_{batch:03d}.sqlite"
        state_remote = f"{control}/{state.name}"
        _download_optional(state_remote, state)
        con = sqlite3.connect(state)
        con.executescript(STATE_SCHEMA)
        con.commit()
        try:
            for relpath in selected:
                if con.execute("SELECT 1 FROM files WHERE relpath=? AND status='OK'", (relpath,)).fetchone():
                    continue
                work = root / "work.parquet"
                topic = root / "topic.parquet"
                inst = root / "inst.parquet"
                collab = root / "collab.parquet"
                for p in (work, topic, inst, collab):
                    if p.exists():
                        p.unlink()
                _run(["copyto", f"{curated}/WORK_MASTER/{relpath}", str(work), "--stats", "0"])
                _download_optional(f"{curated}/WORK_TOPIC_EDGES/{relpath}", topic)
                _download_optional(f"{curated}/AUTHOR_INSTITUTION_EDGES/{relpath}", inst)
                _download_optional(f"{curated}/COUNTRY_COLLAB_EDGES/{relpath}", collab)

                out = root / "out"
                if out.exists():
                    shutil.rmtree(out)
                counts = build_partials(
                    work,
                    out,
                    topic=topic if topic.exists() else None,
                    institution=inst if inst.exists() else None,
                    collaboration=collab if collab.exists() else None,
                )
                fname = _safe_relname(relpath)
                for mart in counts:
                    _run(["copyto", str(out / f"{mart}.parquet"), f"{partial}/{mart}/batch={batch:03d}/{fname}", "--stats", "0"])
                con.execute("INSERT OR REPLACE INTO files(relpath,status,outputs) VALUES(?,?,?)", (relpath, "OK", len(counts)))
                con.commit()
                _run(["copyto", str(state), state_remote, "--stats", "0"])
            _run(["copyto", str(state), state_remote, "--stats", "0"])
        finally:
            con.close()
    return 0


def reduce_local(partial_root: Path, output_root: Path) -> dict[str, int]:
    output_root.mkdir(parents=True, exist_ok=True)
    specs = {
        "WORK_YEAR_METRICS": (["publication_year"], ["work_count", "citation_sum"]),
        "WORK_YEAR_TOPIC": (["publication_year", "topic_id"], ["work_count", "citation_sum", "topic_score_sum"]),
        "WORK_YEAR_INSTITUTION": (["publication_year", "institution_id"], ["work_count", "citation_sum"]),
        "WORK_YEAR_COUNTRY": (["publication_year", "country_code"], ["work_count", "citation_sum"]),
        "COUNTRY_COLLAB_YEAR": (["publication_year", "country_a", "country_b"], ["work_count", "citation_sum"]),
    }
    con = duckdb.connect(database=":memory:")
    result: dict[str, int] = {}
    try:
        for mart, (keys, sums) in specs.items():
            files = list((partial_root / mart).rglob("*.parquet"))
            if not files:
                continue
            glob = (partial_root / mart / "**" / "*.parquet").as_posix()
            select = ", ".join(keys + [f"SUM({c}) AS {c}" for c in sums])
            group = ", ".join(keys)
            extras = ", CAST(citation_sum AS DOUBLE)/NULLIF(work_count,0) AS mean_citations" if "citation_sum" in sums else ""
            sql = f"SELECT {select} FROM read_parquet({_lit(glob)}, union_by_name=true) GROUP BY {group}"
            final = f"SELECT *{extras} FROM ({sql}) q"
            dst = output_root / f"{mart}.parquet"
            con.execute(f"COPY ({final}) TO {_lit(dst.as_posix())} (FORMAT PARQUET, COMPRESSION ZSTD)")
            result[mart] = int(con.execute(f"SELECT COUNT(*) FROM read_parquet({_lit(dst.as_posix())})").fetchone()[0])
    finally:
        con.close()
    return result


def reduce_remote() -> int:
    if shutil.which("rclone") is None:
        raise RuntimeError("rclone not found on PATH")
    partial = os.environ.get("GMSDL_OPENALEX_MART_PARTIAL_REMOTE", PARTIAL_DEFAULT).rstrip("/")
    target = os.environ.get("GMSDL_OPENALEX_MART_REMOTE", MART_DEFAULT).rstrip("/")
    with tempfile.TemporaryDirectory(prefix="gmsdl-marts-reduce-") as td:
        root = Path(td)
        local_partial = root / "partials"
        local_out = root / "out"
        _run(["copy", partial, str(local_partial), "--stats", "0"])
        result = reduce_local(local_partial, local_out)
        metadata = root / "mart_manifest.json"
        metadata.write_text(json.dumps({"version": "v1", "marts": result}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for mart in result:
            _run(["copyto", str(local_out / f"{mart}.parquet"), f"{target}/{mart}/part-0000.parquet", "--stats", "0"])
        _run(["copyto", str(metadata), f"{target}/mart_manifest.json", "--stats", "0"])
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Build resumable OpenAlex research marts")
    sub = p.add_subparsers(dest="command", required=True)
    m = sub.add_parser("map")
    m.add_argument("--batch", type=int, required=True)
    m.add_argument("--batches", type=int, default=60)
    sub.add_parser("reduce")
    args = p.parse_args()
    if args.command == "map":
        if args.batch < 0 or args.batch >= args.batches:
            p.error("--batch must satisfy 0 <= batch < batches")
        return map_batch(args.batch, args.batches)
    return reduce_remote()


if __name__ == "__main__":
    raise SystemExit(main())
