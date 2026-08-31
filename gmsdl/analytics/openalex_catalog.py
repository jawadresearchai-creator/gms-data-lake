from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Iterable

import duckdb

CATALOG_VERSION = "v1"

MASTER_TABLES = (
    "WORK_MASTER",
    "AUTHOR_MASTER",
    "INSTITUTION_MASTER",
    "SOURCE_MASTER",
    "TOPIC_MASTER",
    "FUNDER_MASTER",
    "PUBLISHER_MASTER",
    "COUNTRY_MASTER",
    "DOMAIN_MASTER",
    "FIELD_MASTER",
    "SUBFIELD_MASTER",
    "KEYWORD_MASTER",
    "CONCEPT_MASTER",
    "AWARD_MASTER",
    "CONTINENT_MASTER",
    "LANGUAGE_MASTER",
    "LICENSE_MASTER",
)

EDGE_TABLES = (
    "CITATION_EDGES",
    "WORK_TOPIC_EDGES",
    "WORK_AUTHOR_EDGES",
    "AUTHOR_INSTITUTION_EDGES",
    "COUNTRY_COLLAB_EDGES",
)


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def discover_tables(root: Path, requested: Iterable[str] | None = None) -> list[str]:
    allowed = set(MASTER_TABLES) | set(EDGE_TABLES)
    names = list(requested) if requested else sorted(allowed)
    unknown = sorted(set(names) - allowed)
    if unknown:
        raise ValueError(f"unknown OpenAlex catalog tables: {', '.join(unknown)}")
    return [name for name in names if any((root / name).rglob("*.parquet"))]


def build_catalog(db_path: Path, root: Path, requested: Iterable[str] | None = None) -> dict:
    tables = discover_tables(root, requested)
    if not tables:
        raise RuntimeError(f"no staged OpenAlex Parquet tables found under {root}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    created_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    try:
        con.execute("DROP TABLE IF EXISTS gms_catalog")
        con.execute(
            """
            CREATE TABLE gms_catalog(
                table_name VARCHAR PRIMARY KEY,
                table_kind VARCHAR NOT NULL,
                parquet_glob VARCHAR NOT NULL,
                catalog_version VARCHAR NOT NULL,
                created_at_utc VARCHAR NOT NULL
            )
            """
        )
        metadata = []
        for name in tables:
            glob = (root / name / "**" / "*.parquet").as_posix()
            kind = "edge" if name in EDGE_TABLES else "master"
            con.execute(f'DROP VIEW IF EXISTS "{name}"')
            con.execute(
                f'CREATE VIEW "{name}" AS SELECT * FROM read_parquet('
                f'{sql_literal(glob)}, union_by_name=true, hive_partitioning=true, filename=true)'
            )
            con.execute(
                "INSERT INTO gms_catalog VALUES(?,?,?,?,?)",
                [name, kind, glob, CATALOG_VERSION, created_at],
            )
            row_count = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            cols = [r[0] for r in con.execute(f'DESCRIBE "{name}"').fetchall()]
            metadata.append(
                {
                    "table_name": name,
                    "table_kind": kind,
                    "row_count_staged": int(row_count),
                    "columns": cols,
                    "parquet_glob": glob,
                }
            )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    return {
        "catalog_version": CATALOG_VERSION,
        "created_at_utc": created_at,
        "staging_root": root.as_posix(),
        "tables": metadata,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build a portable DuckDB catalog over staged OpenAlex curated Parquet")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--metadata", type=Path)
    p.add_argument("--table", action="append", dest="tables")
    args = p.parse_args()

    metadata = build_catalog(args.db, args.root, args.tables)
    text = json.dumps(metadata, indent=2, sort_keys=True)
    print(text)
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
