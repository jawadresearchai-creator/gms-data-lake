"""Human-readable run reports (also used as the GitHub Actions job summary)."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from .manifest import Manifest
from .runner import Outcome, human


def build(manifest: Manifest, outcome: Outcome, run_id: str, *, title: str = "Ingestion run") -> str:
    s = manifest.summary()
    lines = [
        f"# {title}",
        "",
        f"Run `{run_id}` — {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## This run",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| New or updated | {outcome.ok} |",
        f"| Unchanged (skipped) | {outcome.unchanged} |",
        f"| Failed | {outcome.failed} |",
        f"| Skipped | {outcome.skipped} |",
        f"| Transferred | {human(outcome.bytes)} |",
        "",
        "## Lake totals",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Files held | {s['files']:,} |",
        f"| Total size | {human(s['bytes'])} |",
        "",
    ]

    rows = manifest.by_domain()
    if rows:
        lines += ["## By domain", "", "| Domain | Files | Size |", "|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['domain']} | {r['n']:,} | {human(r['b'])} |")
        lines.append("")

    if outcome.errors:
        lines += ["## Failures in this run", "",
                  "| Source | Dataset | Reason |", "|---|---|---|"]
        for src, ds, msg in outcome.errors[:60]:
            lines.append(f"| `{src}` | `{ds}` | {msg.replace('|', chr(92) + '|')[:200]} |")
        if len(outcome.errors) > 60:
            lines.append(f"| … | | {len(outcome.errors) - 60} more |")
        lines.append("")

    return "\n".join(lines) + "\n"


def emit(text: str, path: Path | None = None) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text)
