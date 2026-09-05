from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

REQUIRED: dict[str, set[str]] = {
    "WORK_YEAR_METRICS": {"publication_year", "work_count", "citation_sum", "mean_citations"},
    "WORK_YEAR_TOPIC": {"publication_year", "topic_id", "work_count", "citation_sum", "topic_score_sum", "mean_citations"},
    "WORK_YEAR_INSTITUTION": {"publication_year", "institution_id", "work_count", "citation_sum", "mean_citations"},
    "WORK_YEAR_COUNTRY": {"publication_year", "country_code", "work_count", "citation_sum", "mean_citations"},
    "COUNTRY_COLLAB_YEAR": {"publication_year", "country_a", "country_b", "work_count", "citation_sum", "mean_citations"},
}

KEYS: dict[str, tuple[str, ...]] = {
    "WORK_YEAR_METRICS": ("publication_year",),
    "WORK_YEAR_TOPIC": ("publication_year", "topic_id"),
    "WORK_YEAR_INSTITUTION": ("publication_year", "institution_id"),
    "WORK_YEAR_COUNTRY": ("publication_year", "country_code"),
    "COUNTRY_COLLAB_YEAR": ("publication_year", "country_a", "country_b"),
}


def _glob(root: Path, table: str) -> str:
    return (root / table / "**" / "*.parquet").as_posix()


def validate(root: Path) -> dict:
    con = duckdb.connect(database=":memory:")
    errors: list[str] = []
    tables: list[dict] = []
    try:
        for table in REQUIRED:
            files = sorted((root / table).rglob("*.parquet"))
            if not files:
                errors.append(f"{table}: no parquet files")
                continue
            rel = f"read_parquet('{_glob(root, table)}', union_by_name=true)"
            cols = {str(r[0]) for r in con.execute(f"DESCRIBE SELECT * FROM {rel}").fetchall()}
            missing = sorted(REQUIRED[table] - cols)
            if missing:
                errors.append(f"{table}: missing required columns {', '.join(missing)}")
            rows = int(con.execute(f"SELECT COUNT(*) FROM {rel}").fetchone()[0])
            key_cols = KEYS[table]
            invalid_pred = " OR ".join(f"{k} IS NULL OR CAST({k} AS VARCHAR)=''" for k in key_cols)
            invalid_keys = int(con.execute(f"SELECT COUNT(*) FROM {rel} WHERE {invalid_pred}").fetchone()[0])
            keys = ",".join(key_cols)
            duplicate_rows = int(con.execute(
                f"SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM {rel} GROUP BY {keys} HAVING COUNT(*)>1)"
            ).fetchone()[0])
            negative_metrics = int(con.execute(
                f"SELECT COUNT(*) FROM {rel} WHERE COALESCE(work_count,0)<0 OR COALESCE(citation_sum,0)<0 OR COALESCE(mean_citations,0)<0"
            ).fetchone()[0])
            bad_collab_order = 0
            if table == "COUNTRY_COLLAB_YEAR":
                bad_collab_order = int(con.execute(f"SELECT COUNT(*) FROM {rel} WHERE country_a>=country_b").fetchone()[0])
            if invalid_keys:
                errors.append(f"{table}: {invalid_keys} rows have null/empty keys")
            if duplicate_rows:
                errors.append(f"{table}: {duplicate_rows} duplicate key rows")
            if negative_metrics:
                errors.append(f"{table}: {negative_metrics} rows have negative metrics")
            if bad_collab_order:
                errors.append(f"{table}: {bad_collab_order} rows have non-canonical country pair ordering")
            min_year, max_year = con.execute(f"SELECT MIN(publication_year), MAX(publication_year) FROM {rel}").fetchone()
            tables.append({
                "table": table,
                "files": len(files),
                "rows": rows,
                "columns": sorted(cols),
                "missing_required_columns": missing,
                "invalid_key_rows": invalid_keys,
                "duplicate_rows": duplicate_rows,
                "negative_metric_rows": negative_metrics,
                "bad_collaboration_order_rows": bad_collab_order,
                "min_year": min_year,
                "max_year": max_year,
            })

        base_rel = f"read_parquet('{_glob(root, 'WORK_YEAR_METRICS')}', union_by_name=true)"
        base_years = {
            int(y): (int(w), int(c))
            for y, w, c in con.execute(f"SELECT publication_year,work_count,citation_sum FROM {base_rel}").fetchall()
            if y is not None
        }
        # Dimension marts may count a work in multiple groups, so they should never
        # have fewer grouped rows than zero; we only assert year coverage where data exists.
        for table in ("WORK_YEAR_TOPIC", "WORK_YEAR_INSTITUTION", "WORK_YEAR_COUNTRY"):
            rel = f"read_parquet('{_glob(root, table)}', union_by_name=true)"
            years = {int(r[0]) for r in con.execute(f"SELECT DISTINCT publication_year FROM {rel}").fetchall() if r[0] is not None}
            missing_years = sorted(set(base_years) - years)
            if missing_years:
                # Older years can legitimately lack structured metadata; flag only as warning.
                tables.append({"table": f"{table}__year_coverage", "warning_missing_base_years": missing_years[:50]})
    finally:
        con.close()

    return {"verified": not errors, "errors": errors, "tables": tables}


def main() -> int:
    p = argparse.ArgumentParser(description="Validate OpenAlex research marts")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = validate(args.root)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
