from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

REQUIRED_COLUMNS: dict[str, set[str]] = {
    "WORK_MASTER": {"id", "_source_key"},
    "AUTHOR_MASTER": {"id", "_source_key"},
    "INSTITUTION_MASTER": {"id", "_source_key"},
    "SOURCE_MASTER": {"id", "_source_key"},
    "TOPIC_MASTER": {"id", "_source_key"},
    "CITATION_EDGES": {"work_id", "referenced_work_id", "_source_key"},
    "WORK_TOPIC_EDGES": {"work_id", "topic_id", "topic_score", "_source_key"},
    "WORK_AUTHOR_EDGES": {"work_id", "author_id", "author_position", "is_corresponding", "_source_key"},
    "AUTHOR_INSTITUTION_EDGES": {
        "work_id",
        "author_id",
        "institution_id",
        "institution_country_code",
        "author_position",
        "is_corresponding",
        "_source_key",
    },
    "COUNTRY_COLLAB_EDGES": {"work_id", "country_a", "country_b", "_source_key"},
}

UNIQUE_KEYS: dict[str, tuple[str, ...]] = {
    "CITATION_EDGES": ("work_id", "referenced_work_id"),
    "WORK_TOPIC_EDGES": ("work_id", "topic_id"),
    "WORK_AUTHOR_EDGES": ("work_id", "author_id"),
    "AUTHOR_INSTITUTION_EDGES": ("work_id", "author_id", "institution_id"),
    "COUNTRY_COLLAB_EDGES": ("work_id", "country_a", "country_b"),
}


def _parquet_glob(root: Path, table: str) -> str:
    return (root / table / "**" / "*.parquet").as_posix()


def validate_staged(root: Path, tables: list[str] | None = None) -> dict:
    selected = tables or sorted(REQUIRED_COLUMNS)
    unknown = sorted(set(selected) - set(REQUIRED_COLUMNS))
    if unknown:
        raise ValueError(f"unknown research tables: {', '.join(unknown)}")

    con = duckdb.connect(database=":memory:")
    results: list[dict] = []
    errors: list[str] = []
    try:
        for table in selected:
            files = sorted((root / table).rglob("*.parquet"))
            if not files:
                errors.append(f"{table}: no staged Parquet files")
                continue
            glob = _parquet_glob(root, table)
            relation = f"read_parquet('{glob}', union_by_name=true, hive_partitioning=true)"
            desc = con.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
            cols = {str(r[0]) for r in desc}
            missing = sorted(REQUIRED_COLUMNS[table] - cols)
            row_count = int(con.execute(f"SELECT COUNT(*) FROM {relation}").fetchone()[0])
            null_source = int(con.execute(f"SELECT COUNT(*) FROM {relation} WHERE _source_key IS NULL OR _source_key='' ").fetchone()[0]) if "_source_key" in cols else row_count
            duplicate_rows = 0
            invalid_key_rows = 0
            key_cols = UNIQUE_KEYS.get(table)
            if key_cols and set(key_cols) <= cols and row_count:
                keys = ",".join(key_cols)
                invalid_pred = " OR ".join(f"{k} IS NULL OR CAST({k} AS VARCHAR)=''" for k in key_cols)
                valid_pred = " AND ".join(f"{k} IS NOT NULL AND CAST({k} AS VARCHAR)<>''" for k in key_cols)
                invalid_key_rows = int(
                    con.execute(f"SELECT COUNT(*) FROM {relation} WHERE {invalid_pred}").fetchone()[0]
                )
                duplicate_rows = int(
                    con.execute(
                        f"SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM {relation} WHERE {valid_pred} GROUP BY {keys} HAVING COUNT(*)>1)"
                    ).fetchone()[0]
                )
            if missing:
                errors.append(f"{table}: missing columns {', '.join(missing)}")
            if null_source:
                errors.append(f"{table}: {null_source} rows have missing _source_key")
            if invalid_key_rows:
                errors.append(f"{table}: {invalid_key_rows} rows have null/empty edge endpoints")
            if duplicate_rows:
                errors.append(f"{table}: {duplicate_rows} duplicate research-edge rows")
            results.append(
                {
                    "table": table,
                    "files": len(files),
                    "rows": row_count,
                    "columns": sorted(cols),
                    "missing_required_columns": missing,
                    "null_source_rows": null_source,
                    "invalid_key_rows": invalid_key_rows,
                    "duplicate_rows": duplicate_rows,
                }
            )
    finally:
        con.close()

    return {"verified": not errors, "errors": errors, "tables": results}


def main() -> int:
    p = argparse.ArgumentParser(description="Validate staged OpenAlex research master and edge Parquet contracts")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--table", action="append", dest="tables")
    p.add_argument("--output", type=Path)
    args = p.parse_args()

    result = validate_staged(args.root, args.tables)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
