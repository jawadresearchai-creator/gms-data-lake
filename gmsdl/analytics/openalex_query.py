from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import duckdb


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalize_query(sql: str) -> str:
    text = sql.strip().rstrip(";").strip()
    if not text:
        raise ValueError("query is empty")
    lowered = text.lstrip().lower()
    if not (lowered.startswith("select ") or lowered.startswith("with ")):
        raise ValueError("research query runner accepts SELECT/WITH queries only")
    return text


def execute_query(
    *,
    db_path: Path,
    sql: str,
    output: Path,
    fmt: str = "parquet",
) -> dict:
    query = normalize_query(sql)
    fmt = fmt.lower()
    if fmt not in {"parquet", "csv", "json"}:
        raise ValueError(f"unsupported output format: {fmt}")

    output.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        row_count = int(con.execute(f"SELECT COUNT(*) FROM ({query}) AS q").fetchone()[0])
        out = sql_literal(output.as_posix())
        if fmt == "parquet":
            con.execute(f"COPY ({query}) TO {out} (FORMAT PARQUET, COMPRESSION ZSTD)")
        elif fmt == "csv":
            con.execute(f"COPY ({query}) TO {out} (FORMAT CSV, HEADER TRUE)")
        else:
            con.execute(f"COPY ({query}) TO {out} (FORMAT JSON, ARRAY TRUE)")
        columns = [str(r[0]) for r in con.execute(f"DESCRIBE ({query})").fetchall()]
    finally:
        con.close()

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {
        "executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "database": db_path.as_posix(),
        "output": output.as_posix(),
        "format": fmt,
        "row_count": row_count,
        "columns": columns,
        "sha256": digest,
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Execute a read-only OpenAlex research query against a staged DuckDB catalog")
    p.add_argument("--db", type=Path, required=True)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--sql")
    source.add_argument("--sql-file", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--format", choices=["parquet", "csv", "json"], default="parquet")
    p.add_argument("--metadata", type=Path)
    args = p.parse_args()

    sql = args.sql if args.sql is not None else args.sql_file.read_text(encoding="utf-8")
    metadata = execute_query(db_path=args.db, sql=sql, output=args.output, fmt=args.format)
    text = json.dumps(metadata, indent=2, sort_keys=True)
    print(text)
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
