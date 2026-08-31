"""Bounded Google Patents BigQuery export to Drive.

The source table is patents-public-data.patents.publications. Queries are always
explicit-column, jurisdiction/year bounded, and dry-run before execution. The
worker streams Arrow record batches into a local Parquet file on an ephemeral
runner, uploads that one partition to Drive with rclone, then deletes it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

TABLE = "patents-public-data.patents.publications"
REMOTE_BASE = "gdrive:01_RAW_IMMUTABLE/04_INNOVATION_AND_TECHNOLOGY/patents/GOOGLE_PATENTS_PUBLIC"
CONTROL_BASE = "gdrive:00_CONTROL/analytics/google_patents"

COLUMNS = [
    "publication_number", "application_number", "country_code", "kind_code",
    "application_kind", "application_number_formatted", "pct_number", "family_id",
    "title_localized", "abstract_localized", "publication_date", "filing_date",
    "grant_date", "priority_date", "priority_claim", "inventor",
    "inventor_harmonized", "assignee", "assignee_harmonized", "examiner",
    "uspc", "ipc", "cpc", "fi", "fterm", "citation", "entity_status", "art_unit",
]


def build_sql(country: str, year: int) -> str:
    lo = year * 10000 + 101
    hi = year * 10000 + 1231
    cols = ",\n  ".join(COLUMNS)
    return f"""SELECT\n  {cols}\nFROM `{TABLE}`\nWHERE country_code = @country\n  AND publication_date BETWEEN @lo AND @hi\n"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rclone_copy(local: Path, remote: str) -> None:
    cmd = ["rclone", "--config", "", "copyto", str(local), remote,
           "--stats", "0", "--retries", "5", "--low-level-retries", "10"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout or "rclone failed")[-1000:])


def export_partition(*, project: str, country: str, year: int,
                     max_bytes_billed: int, execute: bool) -> dict:
    from google.cloud import bigquery
    import pyarrow.parquet as pq

    client = bigquery.Client(project=project)
    sql = build_sql(country, year)
    params = [
        bigquery.ScalarQueryParameter("country", "STRING", country),
        bigquery.ScalarQueryParameter("lo", "INT64", year * 10000 + 101),
        bigquery.ScalarQueryParameter("hi", "INT64", year * 10000 + 1231),
    ]
    dry_cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False,
                                      query_parameters=params)
    dry_job = client.query(sql, job_config=dry_cfg)
    billed = int(dry_job.total_bytes_processed or 0)
    result = {
        "table": TABLE, "country": country, "year": year,
        "dry_run_bytes": billed, "max_bytes_billed": max_bytes_billed,
        "executed": False,
    }
    if billed > max_bytes_billed:
        raise RuntimeError(
            f"dry-run would process {billed:,} bytes, above cap {max_bytes_billed:,}"
        )
    if not execute:
        return result

    cfg = bigquery.QueryJobConfig(
        query_parameters=params,
        maximum_bytes_billed=max_bytes_billed,
        use_query_cache=True,
    )
    job = client.query(sql, job_config=cfg)
    rows = job.result(page_size=10000)

    remote_base = os.environ.get("GMSDL_GOOGLE_PATENTS_REMOTE", REMOTE_BASE).rstrip("/")
    control_base = os.environ.get("GMSDL_GOOGLE_PATENTS_CONTROL_REMOTE", CONTROL_BASE).rstrip("/")
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    with tempfile.TemporaryDirectory(prefix=f"gmsdl-patents-{country}-{year}-") as td:
        out = Path(td) / f"publications_{country}_{year}.parquet"
        writer = None
        row_count = 0
        try:
            for batch in rows.to_arrow_iterable(max_queue_size=1):
                if writer is None:
                    writer = pq.ParquetWriter(out, batch.schema, compression="zstd")
                writer.write_batch(batch)
                row_count += batch.num_rows
        finally:
            if writer is not None:
                writer.close()
        if writer is None:
            raise RuntimeError("query returned zero rows")

        digest = sha256_file(out)
        remote = f"{remote_base}/country={country}/publication_year={year}/{out.name}"
        rclone_copy(out, remote)
        report = Path(td) / f"google_patents_{country}_{year}.json"
        result.update({
            "executed": True, "rows": row_count, "output_bytes": out.stat().st_size,
            "sha256": digest, "remote": remote, "completed_at": stamp,
            "job_bytes_processed": int(job.total_bytes_processed or 0),
            "job_bytes_billed": int(job.total_bytes_billed or 0),
        })
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        rclone_copy(report, f"{control_base}/{report.name}")
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--country", default="US")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--max-bytes-billed", type=int, default=100_000_000_000)
    p.add_argument("--execute", action="store_true")
    a = p.parse_args()
    print(json.dumps(export_partition(project=a.project, country=a.country, year=a.year,
                                      max_bytes_billed=a.max_bytes_billed,
                                      execute=a.execute), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
