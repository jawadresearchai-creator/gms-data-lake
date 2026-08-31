from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def summarize(raw_manifest: Path, state_dir: Path) -> dict[str, int]:
    raw = sqlite3.connect(raw_manifest)
    raw_count, raw_bytes = raw.execute(
        "SELECT COUNT(*), COALESCE(SUM(bytes),0) FROM files "
        "WHERE source_id='OPENALEX_SNAPSHOT' AND status='OK'"
    ).fetchone()
    raw.close()

    rows = 0
    ok = 0
    failed = 0
    bytes_in = 0
    bytes_out = 0
    keys: set[str] = set()

    dbs = sorted(state_dir.glob("openalex_curate_batch_*.sqlite"))
    if len(dbs) != 15:
        raise RuntimeError(f"expected 15 curation state databases, found {len(dbs)}")

    for db in dbs:
        con = sqlite3.connect(db)
        for key, status, b_in, b_out in con.execute(
            "SELECT key,status,COALESCE(bytes_in,0),COALESCE(bytes_out,0) FROM files"
        ):
            rows += 1
            keys.add(key)
            if status == "OK":
                ok += 1
                bytes_in += int(b_in or 0)
                bytes_out += int(b_out or 0)
            elif status == "FAILED":
                failed += 1
        con.close()

    return {
        "raw_count": int(raw_count),
        "raw_bytes": int(raw_bytes),
        "state_rows": rows,
        "distinct_keys": len(keys),
        "state_ok": ok,
        "state_failed": failed,
        "state_bytes_in": bytes_in,
        "state_bytes_out": bytes_out,
    }


def validate(summary: dict[str, int]) -> list[str]:
    errors: list[str] = []
    if summary["state_failed"] != 0:
        errors.append("failed curation records exist")
    if summary["state_rows"] != summary["distinct_keys"]:
        errors.append("duplicate source keys exist across batch states")
    if summary["state_ok"] != summary["raw_count"]:
        errors.append("curated source-key count does not match raw OpenAlex count")
    if summary["state_bytes_in"] != summary["raw_bytes"]:
        errors.append("curated input bytes do not match verified raw bytes")
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
