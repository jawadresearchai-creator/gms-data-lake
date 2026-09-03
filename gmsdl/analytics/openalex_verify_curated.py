from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


# Keep verification aligned with the v1 curated layer implemented by
# openalex_curate.  The raw OPENALEX_SNAPSHOT manifest also contains legacy
# JSONL objects, Parquet manifest.json files, and a handful of Parquet entity
# families that v1 intentionally does not materialise.
SUPPORTED_ENTITIES = {
    "authors",
    "awards",
    "concepts",
    "continents",
    "countries",
    "domains",
    "fields",
    "funders",
    "institutions",
    "keywords",
    "languages",
    "licenses",
    "publishers",
    "sources",
    "subfields",
    "topics",
    "works",
}


def _entity_from_dataset_id(dataset_id: str) -> str | None:
    parts = dataset_id.split("/")
    if len(parts) < 4 or parts[:2] != ["data", "parquet"]:
        return None
    return parts[2] or None


def summarize(raw_manifest: Path, state_dir: Path) -> dict[str, int]:
    raw = sqlite3.connect(raw_manifest)
    raw_rows = raw.execute(
        "SELECT dataset_id, COALESCE(bytes,0) FROM files "
        "WHERE source_id='OPENALEX_SNAPSHOT' AND status='OK' "
        "AND dataset_id LIKE 'data/parquet/%.parquet'"
    ).fetchall()
    raw.close()

    raw_by_key = {
        str(key): int(b or 0)
        for key, b in raw_rows
        if _entity_from_dataset_id(str(key)) in SUPPORTED_ENTITIES
    }

    dbs = sorted(state_dir.glob("openalex_curate_batch_*.sqlite"))
    if len(dbs) != 15:
        raise RuntimeError(f"expected 15 curation state databases, found {len(dbs)}")

    rows = 0
    duplicate_rows = 0
    records: dict[str, tuple[str, int, int]] = {}
    for db in dbs:
        con = sqlite3.connect(db)
        for key, status, b_in, b_out in con.execute(
            "SELECT key,status,COALESCE(bytes_in,0),COALESCE(bytes_out,0) FROM files"
        ):
            rows += 1
            key = str(key)
            current = records.get(key)
            candidate = (str(status), int(b_in or 0), int(b_out or 0))
            if current is not None:
                duplicate_rows += 1
                # Recovery runs can legitimately leave the same source key in
                # more than one batch-state DB. Prefer a successful record.
                if current[0] == "OK":
                    continue
            records[key] = candidate
        con.close()

    state_ok_keys = {
        key for key, (status, _b_in, _b_out) in records.items() if status == "OK"
    }
    failed_keys = {
        key for key, (status, _b_in, _b_out) in records.items() if status == "FAILED"
    }
    missing_keys = set(raw_by_key) - state_ok_keys
    unexpected_keys = state_ok_keys - set(raw_by_key)

    matched_ok = state_ok_keys & set(raw_by_key)
    bytes_in = sum(records[key][1] for key in matched_ok)
    bytes_out = sum(records[key][2] for key in matched_ok)

    return {
        "raw_count": len(raw_by_key),
        "raw_bytes": sum(raw_by_key.values()),
        "state_rows": rows,
        "distinct_keys": len(records),
        "duplicate_rows": duplicate_rows,
        "state_ok": len(state_ok_keys),
        "state_failed": len(failed_keys),
        "state_bytes_in": bytes_in,
        "state_bytes_out": bytes_out,
        "missing_keys": len(missing_keys),
        "unexpected_keys": len(unexpected_keys),
    }


def validate(summary: dict[str, int]) -> list[str]:
    errors: list[str] = []
    if summary["state_failed"] != 0:
        errors.append("failed curation records exist")
    if summary["missing_keys"] != 0:
        errors.append("supported raw Parquet source keys are missing from curation state")
    if summary["unexpected_keys"] != 0:
        errors.append("curation state contains keys outside the supported raw Parquet set")
    if summary["state_ok"] != summary["raw_count"]:
        errors.append("curated source-key count does not match supported raw Parquet count")
    if summary["state_bytes_in"] != summary["raw_bytes"]:
        errors.append("curated input bytes do not match supported verified raw Parquet bytes")
    if summary["state_bytes_out"] <= 0:
        errors.append("curated output bytes are zero")
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--raw-manifest", type=Path, required=True)
    p.add_argument("--state-dir", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()

    summary = summarize(args.raw_manifest, args.state_dir)
    errors = validate(summary)
    payload = {**summary, "errors": errors, "verified": not errors}
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
