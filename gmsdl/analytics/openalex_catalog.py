from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Iterable

import duckdb

CATALOG_VERSION = "v2"
DATA_SCHEMA = "oa"
META_SCHEMA = "gms_meta"

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

LOOKUP_MACROS = {
    "WORK_MASTER": ("work", "id"),
    "AUTHOR_MASTER": ("author", "id"),
    "INSTITUTION_MASTER": ("institution", "id"),
    "SOURCE_MASTER": ("source", "id"),
    "TOPIC_MASTER": ("topic", "id"),
}


def sql_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def discover_tables(root: Path, requested: Iterable[str] | None = None) -> list[str]:
    allowed = set(MASTER_TABLES) | set(EDGE_TABLES)
    names = list(requested) if requested else sorted(allowed)
    unknown = sorted(set(names) - allowed)
    if unknown:
        raise ValueError(f"unknown OpenAlex catalog tables: {', '.join(unknown)}")
    return [name for name in names if any((root / name).rglob("*.parquet"))]


def _column_names(con: duckdb.DuckDBPyConnection, relation: str) -> list[str]:
    return [str(r[0]) for r in con.execute(f"DESCRIBE {relation}").fetchall()]


def _create_lookup_macro(
    con: duckdb.DuckDBPyConnection,
    *,
    table: str,
    macro: str,
    id_column: str,
) -> bool:
    relation = f"{sql_ident(DATA_SCHEMA)}.{sql_ident(table)}"
    if id_column not in _column_names(con, relation):
        return False
    con.execute(
        f"CREATE OR REPLACE MACRO {sql_ident(DATA_SCHEMA)}.{sql_ident(macro)}(entity_id) AS TABLE "
        f"SELECT * FROM {relation} WHERE {sql_ident(id_column)} = entity_id"
    )
    return True


def _create_join_macros(con: duckdb.DuckDBPyConnection, tables: set[str]) -> list[str]:
    created: list[str] = []
    if {"WORK_TOPIC_EDGES", "TOPIC_MASTER"} <= tables:
        edge_cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."WORK_TOPIC_EDGES"'))
        topic_cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."TOPIC_MASTER"'))
        if {"work_id", "topic_id"} <= edge_cols and "id" in topic_cols:
            con.execute(
                f"CREATE OR REPLACE MACRO {sql_ident(DATA_SCHEMA)}.work_topics(target_work_id) AS TABLE "
                f"SELECT e.*, t.* EXCLUDE (id) FROM {sql_ident(DATA_SCHEMA)}.\"WORK_TOPIC_EDGES\" e "
                f"LEFT JOIN {sql_ident(DATA_SCHEMA)}.\"TOPIC_MASTER\" t ON t.id=e.topic_id "
                f"WHERE e.work_id=target_work_id"
            )
            created.append("work_topics")

    if {"WORK_AUTHOR_EDGES", "AUTHOR_MASTER"} <= tables:
        edge_cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."WORK_AUTHOR_EDGES"'))
        author_cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."AUTHOR_MASTER"'))
        if {"work_id", "author_id"} <= edge_cols and "id" in author_cols:
            con.execute(
                f"CREATE OR REPLACE MACRO {sql_ident(DATA_SCHEMA)}.work_authors(target_work_id) AS TABLE "
                f"SELECT e.*, a.* EXCLUDE (id) FROM {sql_ident(DATA_SCHEMA)}.\"WORK_AUTHOR_EDGES\" e "
                f"LEFT JOIN {sql_ident(DATA_SCHEMA)}.\"AUTHOR_MASTER\" a ON a.id=e.author_id "
                f"WHERE e.work_id=target_work_id"
            )
            created.append("work_authors")

    if {"WORK_AUTHOR_EDGES", "WORK_MASTER"} <= tables:
        edge_cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."WORK_AUTHOR_EDGES"'))
        work_cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."WORK_MASTER"'))
        if {"work_id", "author_id"} <= edge_cols and "id" in work_cols:
            con.execute(
                f"CREATE OR REPLACE MACRO {sql_ident(DATA_SCHEMA)}.author_works(target_author_id) AS TABLE "
                f"SELECT e.*, w.* EXCLUDE (id) FROM {sql_ident(DATA_SCHEMA)}.\"WORK_AUTHOR_EDGES\" e "
                f"LEFT JOIN {sql_ident(DATA_SCHEMA)}.\"WORK_MASTER\" w ON w.id=e.work_id "
                f"WHERE e.author_id=target_author_id"
            )
            con.execute(
                f"CREATE OR REPLACE MACRO {sql_ident(DATA_SCHEMA)}.coauthors(target_author_id) AS TABLE "
                f"SELECT b.author_id AS coauthor_id, COUNT(DISTINCT a.work_id) AS shared_work_count "
                f"FROM {sql_ident(DATA_SCHEMA)}.\"WORK_AUTHOR_EDGES\" a "
                f"JOIN {sql_ident(DATA_SCHEMA)}.\"WORK_AUTHOR_EDGES\" b ON a.work_id=b.work_id "
                f"WHERE a.author_id=target_author_id AND b.author_id<>target_author_id "
                f"GROUP BY b.author_id ORDER BY shared_work_count DESC, coauthor_id"
            )
            created.extend(["author_works", "coauthors"])

    if {"AUTHOR_INSTITUTION_EDGES", "WORK_MASTER"} <= tables:
        edge_cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."AUTHOR_INSTITUTION_EDGES"'))
        work_cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."WORK_MASTER"'))
        if {"work_id", "institution_id"} <= edge_cols and "id" in work_cols:
            con.execute(
                f"CREATE OR REPLACE MACRO {sql_ident(DATA_SCHEMA)}.institution_works(target_institution_id) AS TABLE "
                f"SELECT e.*, w.* EXCLUDE (id) FROM {sql_ident(DATA_SCHEMA)}.\"AUTHOR_INSTITUTION_EDGES\" e "
                f"LEFT JOIN {sql_ident(DATA_SCHEMA)}.\"WORK_MASTER\" w ON w.id=e.work_id "
                f"WHERE e.institution_id=target_institution_id"
            )
            created.append("institution_works")

    if "COUNTRY_COLLAB_EDGES" in tables:
        cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."COUNTRY_COLLAB_EDGES"'))
        if {"country_a", "country_b", "work_id"} <= cols:
            con.execute(
                f"CREATE OR REPLACE MACRO {sql_ident(DATA_SCHEMA)}.country_collaborations(target_country_code) AS TABLE "
                f"SELECT work_id, country_a, country_b, "
                f"CASE WHEN country_a=target_country_code THEN country_b ELSE country_a END AS partner_country, _source_key "
                f"FROM {sql_ident(DATA_SCHEMA)}.\"COUNTRY_COLLAB_EDGES\" "
                f"WHERE country_a=target_country_code OR country_b=target_country_code"
            )
            created.append("country_collaborations")

    if "CITATION_EDGES" in tables:
        cols = set(_column_names(con, f'{sql_ident(DATA_SCHEMA)}."CITATION_EDGES"'))
        if {"work_id", "referenced_work_id"} <= cols:
            con.execute(
                f"CREATE OR REPLACE MACRO {sql_ident(DATA_SCHEMA)}.references_from(target_work_id) AS TABLE "
                f"SELECT * FROM {sql_ident(DATA_SCHEMA)}.\"CITATION_EDGES\" WHERE work_id=target_work_id"
            )
            con.execute(
                f"CREATE OR REPLACE MACRO {sql_ident(DATA_SCHEMA)}.citations_to(target_work_id) AS TABLE "
                f"SELECT * FROM {sql_ident(DATA_SCHEMA)}.\"CITATION_EDGES\" WHERE referenced_work_id=target_work_id"
            )
            created.extend(["references_from", "citations_to"])
    return created


def build_catalog(
    db_path: Path,
    root: Path,
    requested: Iterable[str] | None = None,
    required: Iterable[str] | None = None,
) -> dict:
    tables = discover_tables(root, requested)
    if not tables:
        raise RuntimeError(f"no staged OpenAlex Parquet tables found under {root}")

    required_names = list(required or [])
    allowed = set(MASTER_TABLES) | set(EDGE_TABLES)
    unknown_required = sorted(set(required_names) - allowed)
    if unknown_required:
        raise ValueError(f"unknown required OpenAlex tables: {', '.join(unknown_required)}")
    missing_required = sorted(set(required_names) - set(tables))
    if missing_required:
        raise RuntimeError(f"required OpenAlex tables not staged: {', '.join(missing_required)}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    created_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    metadata: list[dict] = []
    macros: list[str] = []
    try:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {sql_ident(DATA_SCHEMA)}")
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {sql_ident(META_SCHEMA)}")
        con.execute(f"DROP TABLE IF EXISTS {sql_ident(META_SCHEMA)}.catalog")
        con.execute(
            f"""
            CREATE TABLE {sql_ident(META_SCHEMA)}.catalog(
                table_name VARCHAR PRIMARY KEY,
                table_kind VARCHAR NOT NULL,
                parquet_glob VARCHAR NOT NULL,
                row_count BIGINT NOT NULL,
                source_file_count BIGINT NOT NULL,
                column_count INTEGER NOT NULL,
                catalog_version VARCHAR NOT NULL,
                created_at_utc VARCHAR NOT NULL
            )
            """
        )
        con.execute(f"DROP TABLE IF EXISTS {sql_ident(META_SCHEMA)}.columns")
        con.execute(
            f"""
            CREATE TABLE {sql_ident(META_SCHEMA)}.columns(
                table_name VARCHAR NOT NULL,
                ordinal_position INTEGER NOT NULL,
                column_name VARCHAR NOT NULL,
                column_type VARCHAR NOT NULL,
                nullable VARCHAR,
                PRIMARY KEY(table_name, ordinal_position)
            )
            """
        )

        for name in tables:
            glob = (root / name / "**" / "*.parquet").as_posix()
            kind = "edge" if name in EDGE_TABLES else "master"
            qualified = f"{sql_ident(DATA_SCHEMA)}.{sql_ident(name)}"
            con.execute(f"DROP VIEW IF EXISTS {qualified}")
            con.execute(
                f"CREATE VIEW {qualified} AS SELECT * FROM read_parquet("
                f"{sql_literal(glob)}, union_by_name=true, hive_partitioning=true, filename=true)"
            )
            # Backward-compatible top-level view for existing notebooks/scripts.
            con.execute(f'DROP VIEW IF EXISTS {sql_ident(name)}')
            con.execute(f'CREATE VIEW {sql_ident(name)} AS SELECT * FROM {qualified}')

            row_count = int(con.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0])
            file_count = int(con.execute(f"SELECT COUNT(DISTINCT filename) FROM {qualified}").fetchone()[0])
            desc = con.execute(f"DESCRIBE {qualified}").fetchall()
            columns = [str(r[0]) for r in desc]
            for ordinal, row in enumerate(desc, start=1):
                con.execute(
                    f"INSERT INTO {sql_ident(META_SCHEMA)}.columns VALUES(?,?,?,?,?)",
                    [name, ordinal, str(row[0]), str(row[1]), str(row[2]) if len(row) > 2 else None],
                )
            con.execute(
                f"INSERT INTO {sql_ident(META_SCHEMA)}.catalog VALUES(?,?,?,?,?,?,?,?)",
                [name, kind, glob, row_count, file_count, len(columns), CATALOG_VERSION, created_at],
            )
            metadata.append(
                {
                    "table_name": name,
                    "table_kind": kind,
                    "row_count_staged": row_count,
                    "source_file_count": file_count,
                    "columns": columns,
                    "parquet_glob": glob,
                }
            )

        # Compatibility aliases retained for v1 clients.
        con.execute("DROP VIEW IF EXISTS gms_catalog")
        con.execute(f"CREATE VIEW gms_catalog AS SELECT * FROM {sql_ident(META_SCHEMA)}.catalog")
        con.execute(f"CREATE OR REPLACE VIEW {sql_ident(DATA_SCHEMA)}.catalog AS SELECT * FROM {sql_ident(META_SCHEMA)}.catalog")
        con.execute(f"CREATE OR REPLACE VIEW {sql_ident(DATA_SCHEMA)}.columns AS SELECT * FROM {sql_ident(META_SCHEMA)}.columns")
        con.execute(
            f"CREATE OR REPLACE VIEW {sql_ident(DATA_SCHEMA)}.table_counts AS "
            f"SELECT table_name, table_kind, row_count, source_file_count, column_count "
            f"FROM {sql_ident(META_SCHEMA)}.catalog ORDER BY table_kind, table_name"
        )

        table_set = set(tables)
        for table, (macro, id_column) in LOOKUP_MACROS.items():
            if table in table_set and _create_lookup_macro(
                con, table=table, macro=macro, id_column=id_column
            ):
                macros.append(macro)
        macros.extend(_create_join_macros(con, table_set))
        con.execute("CHECKPOINT")
    finally:
        con.close()

    return {
        "catalog_version": CATALOG_VERSION,
        "created_at_utc": created_at,
        "staging_root": root.as_posix(),
        "data_schema": DATA_SCHEMA,
        "metadata_schema": META_SCHEMA,
        "tables": metadata,
        "macros": sorted(macros),
        "required_tables": sorted(required_names),
        "validated": True,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build a research-facing DuckDB catalog over staged OpenAlex curated Parquet")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--metadata", type=Path)
    p.add_argument("--table", action="append", dest="tables")
    p.add_argument("--require-table", action="append", dest="required")
    args = p.parse_args()

    metadata = build_catalog(args.db, args.root, args.tables, args.required)
    text = json.dumps(metadata, indent=2, sort_keys=True)
    print(text)
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
