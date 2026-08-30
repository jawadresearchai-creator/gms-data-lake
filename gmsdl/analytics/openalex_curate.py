"""Resumable OpenAlex scalar-master curation on ephemeral compute.

This worker is intentionally cloud-first. It enumerates the public OpenAlex S3
prefix only for object metadata, then pulls one already-ingested Parquet object
from Google Drive, materialises a compact scalar-only master shard with DuckDB,
uploads that shard to Drive, and deletes both local files before moving on.

Nested OpenAlex structures (authorships, topics, locations, references, etc.) are
left in raw immutable storage for a later edge-table phase. The scalar masters
provide a stable first query layer while preserving the raw lake as source of
truth.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

import requests

from gmsdl.adapters.buckets import list_bucket

OPENALEX_HOST = "openalex.s3.amazonaws.com"
OPENALEX_PREFIX = "data/parquet/"
RAW_BASE_DEFAULT = (
    "gdrive:01_RAW_IMMUTABLE/04_INNOVATION_AND_TECHNOLOGY/"
    "scientific_publications/OPENALEX_SNAPSHOT"
)
CURATED_BASE_DEFAULT = "gdrive:02_CURATED/openalex/v1"
CONTROL_BASE_DEFAULT = "gdrive:00_CONTROL/analytics/openalex"

ENTITY_MASTER = {
    "authors": "AUTHOR_MASTER",
    "awards": "AWARD_MASTER",
    "concepts": "CONCEPT_MASTER",
    "continents": "CONTINENT_MASTER",
    "countries": "COUNTRY_MASTER",
    "domains": "DOMAIN_MASTER",
    "fields": "FIELD_MASTER",
    "funders": "FUNDER_MASTER",
    "institutions": "INSTITUTION_MASTER",
    "keywords": "KEYWORD_MASTER",
    "languages": "LANGUAGE_MASTER",
    "licenses": "LICENSE_MASTER",
    "publishers": "PUBLISHER_MASTER",
    "sources": "SOURCE_MASTER",
    "subfields": "SUBFIELD_MASTER",
    "topics": "TOPIC_MASTER",
    "works": "WORK_MASTER",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    key TEXT PRIMARY KEY,
    entity TEXT NOT NULL,
    status TEXT NOT NULL,
    bytes_in INTEGER DEFAULT 0,
    bytes_out INTEGER DEFAULT 0,
    output_sha256 TEXT,
    scalar_columns INTEGER DEFAULT 0,
    error TEXT,
    updated_at TEXT NOT NULL
);
"""


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def entity_from_key(key: str) -> str | None:
    parts = key.split("/")
    if len(parts) < 4 or parts[0:2] != ["data", "parquet"]:
        return None
    return parts[2] or None


def curated_relpath(key: str) -> str | None:
    entity = entity_from_key(key)
    master = ENTITY_MASTER.get(entity or "")
    if not master or not key.endswith(".parquet"):
        return None
    tail = "/".join(key.split("/")[3:])
    return f"{master}/{tail}"


def is_scalar_duckdb_type(type_name: str) -> bool:
    t = type_name.upper()
    return not any(marker in t for marker in ("STRUCT(", "MAP(", "UNION(", "[]", "ARRAY"))


def sql_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_rclone(args: list[str], *, timeout: int = 3600) -> None:
    cmd = ["rclone", "--config", "", "--stats", "0", "--retries", "5", "--low-level-retries", "10", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"rclone failed ({proc.returncode}): {msg[:700]}")


def download_if_exists(remote: str, local: Path) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["rclone", "--config", "", "copyto", remote, str(local), "--stats", "0"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return proc.returncode == 0 and local.exists()


def open_state(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def already_done(conn: sqlite3.Connection, key: str) -> bool:
    row = conn.execute("SELECT status FROM files WHERE key=?", (key,)).fetchone()
    return bool(row and row[0] == "OK")


def record_state(
    conn: sqlite3.Connection,
    *,
    key: str,
    entity: str,
    status: str,
    bytes_in: int = 0,
    bytes_out: int = 0,
    output_sha256: str | None = None,
    scalar_columns: int = 0,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO files(key,entity,status,bytes_in,bytes_out,output_sha256,scalar_columns,error,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(key) DO UPDATE SET
          entity=excluded.entity,status=excluded.status,bytes_in=excluded.bytes_in,
          bytes_out=excluded.bytes_out,output_sha256=excluded.output_sha256,
          scalar_columns=excluded.scalar_columns,error=excluded.error,updated_at=excluded.updated_at
        """,
        (key, entity, status, bytes_in, bytes_out, output_sha256, scalar_columns, error, utcnow()),
    )
    conn.commit()


def enumerate_keys(start_after: str, max_keys: int) -> list[tuple[str, int]]:
    session = requests.Session()
    return list(
        list_bucket(
            session,
            OPENALEX_HOST,
            OPENALEX_PREFIX,
            timeout=30,
            max_keys=max_keys,
            start_after=start_after,
        )
    )


def materialize_scalar_master(raw_path: Path, out_path: Path, source_key: str) -> tuple[int, list[tuple[str, str]]]:
    import duckdb  # analytics-only dependency; keep the ingestion engine lightweight

    con = duckdb.connect(database=":memory:")
    try:
        raw_sql = sql_literal(str(raw_path))
        desc = con.execute(f"DESCRIBE SELECT * FROM read_parquet({raw_sql})").fetchall()
        columns = [(str(r[0]), str(r[1])) for r in desc]
        scalar = [name for name, typ in columns if is_scalar_duckdb_type(typ)]
        if not scalar:
            raise RuntimeError("no scalar columns discovered in Parquet schema")

        select_cols = ", ".join(sql_ident(c) for c in scalar)
        select_cols += f", {sql_literal(source_key)} AS _source_key"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_sql = sql_literal(str(out_path))
        con.execute(
            f"COPY (SELECT {select_cols} FROM read_parquet({raw_sql})) "
            f"TO {out_sql} (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        return len(scalar), columns
    finally:
        con.close()



def materialize_work_edges(raw_path: Path, out_dir: Path, source_key: str) -> dict[str, Path]:
    """Materialise the core graph edges exposed by the live OpenAlex works schema."""
    import duckdb

    con = duckdb.connect(database=":memory:")
    raw_sql = sql_literal(str(raw_path))
    source_sql = sql_literal(source_key)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    queries = {
        "CITATION_EDGES": f"""
            SELECT id AS work_id, unnest(referenced_works) AS referenced_work_id,
                   {source_sql} AS _source_key
            FROM read_parquet({raw_sql})
            WHERE referenced_works IS NOT NULL
        """,
        "WORK_TOPIC_EDGES": f"""
            SELECT w.id AS work_id, t.topic.id AS topic_id,
                   t.topic.display_name AS topic_display_name, t.topic.score AS topic_score,
                   {source_sql} AS _source_key
            FROM read_parquet({raw_sql}) AS w,
                 UNNEST(w.topics) AS t(topic)
        """,
        "WORK_AUTHOR_EDGES": f"""
            SELECT w.id AS work_id, a.authorship.author.id AS author_id,
                   a.authorship.author_position AS author_position,
                   a.authorship.is_corresponding AS is_corresponding,
                   {source_sql} AS _source_key
            FROM read_parquet({raw_sql}) AS w,
                 UNNEST(w.authorships) AS a(authorship)
        """,
        "AUTHOR_INSTITUTION_EDGES": f"""
            SELECT w.id AS work_id, a.authorship.author.id AS author_id,
                   i.institution.id AS institution_id,
                   i.institution.country_code AS institution_country_code,
                   a.authorship.author_position AS author_position,
                   a.authorship.is_corresponding AS is_corresponding,
                   {source_sql} AS _source_key
            FROM read_parquet({raw_sql}) AS w,
                 UNNEST(w.authorships) AS a(authorship),
                 UNNEST(a.authorship.institutions) AS i(institution)
        """,
        "COUNTRY_COLLAB_EDGES": f"""
            WITH work_country AS (
                SELECT DISTINCT w.id AS work_id, c.country AS country_code
                FROM read_parquet({raw_sql}) AS w,
                     UNNEST(w.authorships) AS a(authorship),
                     UNNEST(a.authorship.countries) AS c(country)
                WHERE c.country IS NOT NULL AND c.country <> ''
            )
            SELECT a.work_id, a.country_code AS country_a, b.country_code AS country_b,
                   {source_sql} AS _source_key
            FROM work_country a
            JOIN work_country b ON a.work_id = b.work_id AND a.country_code < b.country_code
        """,
    }
    try:
        for table, query in queries.items():
            path = out_dir / f"{table}.parquet"
            con.execute(
                f"COPY ({query}) TO {sql_literal(str(path))} "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            outputs[table] = path
        return outputs
    finally:
        con.close()


def write_report(path: Path, *, batch: int, rows: list[dict], started: str) -> None:
    ok = sum(1 for r in rows if r["status"] == "OK")
    skipped = sum(1 for r in rows if r["status"] == "SKIPPED")
    failed = sum(1 for r in rows if r["status"] == "FAILED")
    b_in = sum(int(r.get("bytes_in") or 0) for r in rows)
    b_out = sum(int(r.get("bytes_out") or 0) for r in rows)
    lines = [
        f"# OpenAlex curation batch {batch}",
        "",
        f"- started: {started}",
        f"- finished: {utcnow()}",
        f"- ok: {ok}",
        f"- skipped: {skipped}",
        f"- failed: {failed}",
        f"- input bytes processed: {b_in}",
        f"- curated bytes produced: {b_out}",
        "",
        "## Files",
        "",
        "| status | entity | key | scalar cols | output bytes |",
        "|---|---|---|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['status']} | {r.get('entity','')} | {r.get('key','')} | "
            f"{r.get('scalar_columns',0)} | {r.get('bytes_out',0)} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def curate_batch(*, batch: int, start_after: str, max_keys: int, strict: bool) -> int:
    if shutil.which("rclone") is None:
        raise RuntimeError("rclone not found on PATH")

    started = utcnow()
    raw_base = os.environ.get("GMSDL_OPENALEX_RAW_REMOTE", RAW_BASE_DEFAULT).rstrip("/")
    curated_base = os.environ.get("GMSDL_OPENALEX_CURATED_REMOTE", CURATED_BASE_DEFAULT).rstrip("/")
    control_base = os.environ.get("GMSDL_OPENALEX_CONTROL_REMOTE", CONTROL_BASE_DEFAULT).rstrip("/")

    with tempfile.TemporaryDirectory(prefix=f"gmsdl-openalex-curate-b{batch}-") as td:
        work = Path(td)
        state_path = work / f"openalex_curate_batch_{batch:02d}.sqlite"
        report_path = work / f"openalex_curate_batch_{batch:02d}.md"
        state_remote = f"{control_base}/{state_path.name}"
        report_remote = f"{control_base}/{report_path.name}"
        download_if_exists(state_remote, state_path)
        conn = open_state(state_path)
        rows: list[dict] = []
        failures = 0

        try:
            for key, expected_size in enumerate_keys(start_after, max_keys):
                rel = curated_relpath(key)
                entity = entity_from_key(key)
                if not rel or not entity:
                    rows.append({"status": "SKIPPED", "entity": entity or "", "key": key})
                    continue
                if already_done(conn, key):
                    rows.append({"status": "SKIPPED", "entity": entity, "key": key})
                    continue

                raw_local = work / "raw" / Path(key).name
                out_local = work / "curated" / Path(key).name
                try:
                    run_rclone(["copyto", f"{raw_base}/{key}", str(raw_local)], timeout=3600)
                    actual_in = raw_local.stat().st_size
                    if expected_size and actual_in != expected_size:
                        raise RuntimeError(f"size mismatch: expected {expected_size}, got {actual_in}")

                    scalar_count, _schema = materialize_scalar_master(raw_local, out_local, key)
                    output_files: dict[str, tuple[Path, str]] = {"MASTER": (out_local, rel)}
                    if entity == "works":
                        tail = rel.split("/", 1)[1]
                        edge_outputs = materialize_work_edges(raw_local, work / "edges", key)
                        for table, edge_path in edge_outputs.items():
                            output_files[table] = (edge_path, f"{table}/{tail}")

                    out_bytes = sum(path.stat().st_size for path, _ in output_files.values())
                    digest_material = "\n".join(
                        f"{name}:{sha256_file(path)}"
                        for name, (path, _) in sorted(output_files.items())
                    )
                    digest = hashlib.sha256(digest_material.encode("ascii")).hexdigest()
                    for path, remote_rel in output_files.values():
                        run_rclone(["copyto", str(path), f"{curated_base}/{remote_rel}"], timeout=3600)

                    record_state(
                        conn,
                        key=key,
                        entity=entity,
                        status="OK",
                        bytes_in=actual_in,
                        bytes_out=out_bytes,
                        output_sha256=digest,
                        scalar_columns=scalar_count,
                    )
                    rows.append(
                        {
                            "status": "OK",
                            "entity": entity,
                            "key": key,
                            "bytes_in": actual_in,
                            "bytes_out": out_bytes,
                            "scalar_columns": scalar_count,
                        }
                    )
                except Exception as exc:
                    failures += 1
                    record_state(conn, key=key, entity=entity, status="FAILED", error=str(exc)[:900])
                    rows.append({"status": "FAILED", "entity": entity, "key": key, "error": str(exc)[:300]})
                    if strict:
                        raise
                finally:
                    raw_local.unlink(missing_ok=True)
                    out_local.unlink(missing_ok=True)
                    edge_dir = work / "edges"
                    if edge_dir.exists():
                        shutil.rmtree(edge_dir, ignore_errors=True)

                # Checkpoint after every object so a runner interruption loses at most one file.
                run_rclone(["copyto", str(state_path), state_remote], timeout=600)
        finally:
            conn.close()
            write_report(report_path, batch=batch, rows=rows, started=started)
            run_rclone(["copyto", str(state_path), state_remote], timeout=600)
            run_rclone(["copyto", str(report_path), report_remote], timeout=600)

        return 1 if failures and strict else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Curate one deterministic OpenAlex batch from Drive")
    p.add_argument("--batch", type=int, required=True)
    p.add_argument("--start-after", default="")
    p.add_argument("--max-keys", type=int, default=500)
    p.add_argument("--strict", action="store_true")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    return curate_batch(batch=args.batch, start_after=args.start_after, max_keys=args.max_keys, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
