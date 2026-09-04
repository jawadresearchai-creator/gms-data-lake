from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import duckdb

CURATED_BASE_DEFAULT = "gdrive:02_CURATED/openalex/v1"
CONTROL_BASE_DEFAULT = "gdrive:00_CONTROL/analytics/openalex/edge_clean"
EDGE_TABLES = (
    "CITATION_EDGES",
    "WORK_TOPIC_EDGES",
    "WORK_AUTHOR_EDGES",
    "AUTHOR_INSTITUTION_EDGES",
    "COUNTRY_COLLAB_EDGES",
)
CLEAN_TABLES = (
    "WORK_TOPIC_EDGES",
    "WORK_AUTHOR_EDGES",
    "AUTHOR_INSTITUTION_EDGES",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
  table_name TEXT NOT NULL,
  relpath TEXT NOT NULL,
  status TEXT NOT NULL,
  rows_in INTEGER DEFAULT 0,
  rows_out INTEGER DEFAULT 0,
  bytes_out INTEGER DEFAULT 0,
  sha256 TEXT,
  PRIMARY KEY(table_name, relpath)
);
"""


def _lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def clean_edge_file(table: str, src: Path, dst: Path) -> tuple[int, int]:
    if table not in EDGE_TABLES:
        raise ValueError(f"unknown edge table: {table}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    rel = f"read_parquet({_lit(src.as_posix())})"
    if table == "CITATION_EDGES":
        query = f"""SELECT DISTINCT work_id, referenced_work_id, _source_key FROM {rel}
                    WHERE work_id IS NOT NULL AND referenced_work_id IS NOT NULL"""
    elif table == "WORK_TOPIC_EDGES":
        query = f"""SELECT * FROM {rel}
                    WHERE work_id IS NOT NULL AND topic_id IS NOT NULL
                    QUALIFY ROW_NUMBER() OVER (
                      PARTITION BY work_id, topic_id
                      ORDER BY topic_score DESC NULLS LAST, topic_display_name NULLS LAST
                    )=1"""
    elif table == "WORK_AUTHOR_EDGES":
        query = f"""SELECT * FROM {rel}
                    WHERE work_id IS NOT NULL AND author_id IS NOT NULL
                    QUALIFY ROW_NUMBER() OVER (
                      PARTITION BY work_id, author_id
                      ORDER BY COALESCE(is_corresponding,FALSE) DESC,
                        CASE author_position WHEN 'first' THEN 1 WHEN 'last' THEN 2 WHEN 'middle' THEN 3 ELSE 4 END,
                        author_position NULLS LAST
                    )=1"""
    elif table == "AUTHOR_INSTITUTION_EDGES":
        query = f"""SELECT * FROM {rel}
                    WHERE work_id IS NOT NULL AND author_id IS NOT NULL AND institution_id IS NOT NULL
                    QUALIFY ROW_NUMBER() OVER (
                      PARTITION BY work_id, author_id, institution_id
                      ORDER BY COALESCE(is_corresponding,FALSE) DESC,
                        institution_country_code NULLS LAST, author_position NULLS LAST
                    )=1"""
    else:
        query = f"""SELECT DISTINCT * FROM {rel}
                    WHERE work_id IS NOT NULL AND country_a IS NOT NULL AND country_b IS NOT NULL
                      AND country_a <> '' AND country_b <> '' AND country_a < country_b"""

    con = duckdb.connect(database=":memory:")
    try:
        rows_in = int(con.execute(f"SELECT COUNT(*) FROM {rel}").fetchone()[0])
        con.execute(f"COPY ({query}) TO {_lit(dst.as_posix())} (FORMAT PARQUET, COMPRESSION ZSTD)")
        rows_out = int(con.execute(f"SELECT COUNT(*) FROM read_parquet({_lit(dst.as_posix())})").fetchone()[0])
    finally:
        con.close()
    return rows_in, rows_out


def _run(args: list[str], *, capture: bool = False) -> str:
    p = subprocess.run(["rclone", *args], check=True, text=True, capture_output=capture)
    return p.stdout if capture else ""


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_if_exists(remote: str, local: Path) -> None:
    p = subprocess.run(["rclone", "copyto", remote, str(local)], text=True, capture_output=True)
    if p.returncode != 0 and "not found" not in (p.stderr or "").lower():
        raise RuntimeError(p.stderr.strip() or f"rclone failed for {remote}")


def clean_batch(batch: int, batches: int) -> int:
    if shutil.which("rclone") is None:
        raise RuntimeError("rclone not found on PATH")
    curated = os.environ.get("GMSDL_OPENALEX_CURATED_REMOTE", CURATED_BASE_DEFAULT).rstrip("/")
    control = os.environ.get("GMSDL_OPENALEX_EDGE_CLEAN_CONTROL", CONTROL_BASE_DEFAULT).rstrip("/")
    listing = _run(["lsf", f"{curated}/WORK_MASTER", "--files-only", "--recursive"], capture=True)
    paths = sorted(x.strip() for x in listing.splitlines() if x.strip().endswith(".parquet"))
    if not paths:
        raise RuntimeError("WORK_MASTER has no Parquet shards")
    selected = [p for i, p in enumerate(paths) if i % batches == batch]

    with tempfile.TemporaryDirectory(prefix=f"gmsdl-edge-clean-{batch:02d}-") as td:
        root = Path(td)
        state = root / f"openalex_edge_clean_batch_{batch:02d}.sqlite"
        state_remote = f"{control}/{state.name}"
        _download_if_exists(state_remote, state)
        con = sqlite3.connect(state)
        con.executescript(SCHEMA)
        con.commit()
        processed = 0
        try:
            for relpath in selected:
                for table in CLEAN_TABLES:
                    done = con.execute(
                        "SELECT 1 FROM files WHERE table_name=? AND relpath=? AND status='OK'",
                        (table, relpath),
                    ).fetchone()
                    if done:
                        continue
                    src = root / "in.parquet"
                    dst = root / "out.parquet"
                    for p in (src, dst):
                        if p.exists():
                            p.unlink()
                    remote = f"{curated}/{table}/{relpath}"
                    _run(["copyto", remote, str(src), "--stats", "0"])
                    rows_in, rows_out = clean_edge_file(table, src, dst)
                    digest = _sha(dst)
                    _run(["copyto", str(dst), remote, "--stats", "0"])
                    con.execute(
                        "INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?,?)",
                        (table, relpath, "OK", rows_in, rows_out, dst.stat().st_size, digest),
                    )
                    con.commit()
                    processed += 1
                    if processed % 10 == 0:
                        _run(["copyto", str(state), state_remote, "--stats", "0"])
            _run(["copyto", str(state), state_remote, "--stats", "0"])
        finally:
            con.close()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Resumably normalize existing OpenAlex derived edge shards")
    p.add_argument("--batch", type=int, required=True)
    p.add_argument("--batches", type=int, default=30)
    args = p.parse_args()
    if args.batch < 0 or args.batch >= args.batches:
        p.error("--batch must satisfy 0 <= batch < batches")
    return clean_batch(args.batch, args.batches)


if __name__ == "__main__":
    raise SystemExit(main())
