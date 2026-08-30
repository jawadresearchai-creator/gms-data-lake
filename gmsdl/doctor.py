"""Registry health check.

This is the piece the previous setup was missing entirely. A data lake built on
seventy third-party download URLs is a living thing: hosts retire (bulkdata.uspto.gov),
paths gain a year segment (Census BDS), agencies migrate to an API (Eurostat,
Treasury, FRED-MD), and clients get blocked (ITU, UNCTAD). `doctor` probes every
registry entry cheaply, writes a report and exits non-zero if the failure rate
crosses a threshold — so the registry is verifiable on a schedule rather than
verified once and left to rot.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from . import adapters
from .config import Settings
from .fetch import diagnose, make_session, probe
from .registry import Source, datasets_for


@dataclass
class Probe:
    source_id: str
    dataset_id: str
    url: str
    status: int | None
    ok: bool
    note: str
    size: int | None = None


def _probe_one(args) -> Probe:
    src, ds, settings = args
    session = make_session(settings, src.headers)
    try:
        status, headers = probe(session, ds.url, min(45, settings.http_timeout))
    except Exception as exc:  # noqa: BLE001
        return Probe(src.id, ds.id, ds.url, None, False, f"{type(exc).__name__}: {exc}"[:300])

    if status is None:
        return Probe(src.id, ds.id, ds.url, None, False, "no response (DNS or connection failure)")

    ctype = (headers.get("Content-Type") or headers.get("content-type") or "").split(";")[0]
    size = None
    for h in ("Content-Length", "content-length"):
        if headers.get(h, "").isdigit():
            size = int(headers[h])
            break

    if status >= 400:
        return Probe(src.id, ds.id, ds.url, status, False, diagnose(status, ds.url), size)
    if ctype.startswith("text/html"):
        return Probe(src.id, ds.id, ds.url, status, False,
                     "200 but Content-Type is text/html — this is a web page, not a file", size)
    return Probe(src.id, ds.id, ds.url, status, True, ctype or "ok", size)


def check(sources: list[Source], settings: Settings, log, *, max_tier: str = "extended",
          workers: int = 8, expand_adapters: bool = True) -> list[Probe]:
    jobs = []
    for src in sources:
        if src.kind == "static":
            for ds in datasets_for(src, max_tier):
                jobs.append((src, ds, settings))
        elif expand_adapters:
            session = make_session(settings, src.headers)
            try:
                found = adapters.get(src.adapter)(src, session, settings)
            except Exception as exc:  # noqa: BLE001
                log.warning("%s: adapter %s failed: %s", src.id, src.adapter, exc)
                continue
            # Probe a sample rather than every enumerated file.
            for ds in found[: int(src.params.get("doctor_sample", 3))]:
                jobs.append((src, ds, settings))

    results: list[Probe] = []
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(_probe_one, jobs):
            results.append(res)
            mark = "ok " if res.ok else "FAIL"
            log.info("%s %-22s %-28s %s", mark, res.source_id, res.dataset_id[:28], res.note[:90])
    return results


def write_report(results: list[Probe], path: Path) -> str:
    ok = [r for r in results if r.ok]
    bad = [r for r in results if not r.ok]
    lines = [
        "# Registry health report",
        "",
        f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
        "",
        f"- Checked: **{len(results)}**",
        f"- Reachable: **{len(ok)}**",
        f"- Failing: **{len(bad)}**",
        "",
    ]
    if bad:
        lines += ["## Failing entries", "",
                  "| Source | Dataset | Status | Diagnosis |",
                  "|---|---|---|---|"]
        for r in sorted(bad, key=lambda x: (x.source_id, x.dataset_id)):
            note = r.note.replace("|", "\\|")[:180]
            lines.append(f"| `{r.source_id}` | `{r.dataset_id}` | {r.status or '-'} | {note} |")
        lines.append("")
    lines += ["## Reachable entries", "", "| Source | Dataset | Size | Type |", "|---|---|---|---|"]
    for r in sorted(ok, key=lambda x: (x.source_id, x.dataset_id)):
        size = f"{r.size:,}" if r.size else "—"
        lines.append(f"| `{r.source_id}` | `{r.dataset_id}` | {size} | {r.note[:40]} |")

    text = "\n".join(lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text
