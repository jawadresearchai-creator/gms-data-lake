"""Run orchestration.

The controlling idea is per-source isolation. The previous engine was a single
1,770-line cell: one bad URL, one unexpected HTML page, one exception in a
helper, and the whole run died with nothing written. Here every source and every
dataset is wrapped, failures are recorded with a diagnosis and the run keeps
going. Nothing is ever held on local disk beyond the file currently in flight.
"""
from __future__ import annotations

import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import adapters
from .config import Settings
from .fetch import FetchError, fetch, make_session
from .manifest import Manifest
from .registry import Dataset, Source, datasets_for
from .transport import Transport


@dataclass
class Outcome:
    ok: int = 0
    unchanged: int = 0
    failed: int = 0
    skipped: int = 0
    bytes: int = 0
    errors: list[tuple[str, str, str]] = field(default_factory=list)  # source, dataset, message

    def merge(self, other: "Outcome") -> None:
        self.ok += other.ok
        self.unchanged += other.unchanged
        self.failed += other.failed
        self.skipped += other.skipped
        self.bytes += other.bytes
        self.errors.extend(other.errors)


def file_key(src: Source, ds: Dataset) -> str:
    return f"{src.id}/{ds.id}"


def remote_path(src: Source, ds: Dataset) -> str:
    return f"{src.remote_dir()}/{ds.resolved_filename()}"


def enumerate_datasets(src: Source, session, settings: Settings, max_tier: str) -> list[Dataset]:
    """Static sources return their declared datasets; adapter sources call out
    to an official catalogue endpoint."""
    if src.kind == "static":
        return datasets_for(src, max_tier)
    fn = adapters.get(src.adapter)
    found = fn(src, session, settings)
    ceiling = {"core": 0, "extended": 1, "bulk": 2, "massive": 3}[max_tier]
    tiers = {"core": 0, "extended": 1, "bulk": 2, "massive": 3}
    return [d for d in found if tiers[d.tier] <= ceiling]


def run_source(
    src: Source,
    *,
    settings: Settings,
    manifest: Manifest,
    transport: Transport,
    max_tier: str,
    log,
    deadline: float,
    secrets: dict[str, str],
) -> Outcome:
    out = Outcome()

    if src.requires_secret and not secrets.get(src.requires_secret):
        log.warning("%s: skipped, missing secret %s", src.id, src.requires_secret)
        out.skipped += 1
        return out

    headers = dict(src.headers)
    for k, v in headers.items():
        if isinstance(v, str) and v.startswith("$"):
            headers[k] = secrets.get(v[1:], "")
    session = make_session(settings, headers)

    try:
        datasets = enumerate_datasets(src, session, settings, max_tier)
    except Exception as exc:
        log.error("%s: enumeration failed: %s", src.id, exc)
        out.failed += 1
        out.errors.append((src.id, "<enumerate>", f"{type(exc).__name__}: {exc}"))
        manifest.record_health(src.id, "<enumerate>", None, False, str(exc)[:400])
        return out

    log.info("%s: %d dataset(s)", src.id, len(datasets))
    interval = 1.0 / src.rate_limit_per_sec if src.rate_limit_per_sec > 0 else 0.0

    for ds in datasets:
        if time.time() > deadline:
            log.warning("%s: run budget exhausted, stopping cleanly", src.id)
            out.skipped += len(datasets) - (out.ok + out.unchanged + out.failed)
            break

        key = file_key(src, ds)
        rel = remote_path(src, ds)
        etag, lastmod = manifest.unchanged_validators(key)
        local = settings.workdir / src.id / ds.resolved_filename()

        try:
            if settings.dry_run:
                log.info("  [dry-run] %s -> %s", ds.url, rel)
                out.skipped += 1
                continue

            result = fetch(
                session, ds.url, local, settings,
                etag=etag, last_modified=lastmod,
                max_bytes=ds.max_bytes,
                expect_html=bool(ds.params.get("expect_html")),
            )

            if result.unchanged:
                manifest.record(key, source_id=src.id, domain=src.domain, dataset_id=ds.id,
                                url=ds.url, remote_path=rel, status="UNCHANGED")
                out.unchanged += 1
                log.info("  = %s (unchanged)", ds.id)
            else:
                transport.upload(result.path, rel)
                manifest.record(
                    key, source_id=src.id, domain=src.domain, dataset_id=ds.id, url=ds.url,
                    remote_path=rel, etag=result.etag, last_modified=result.last_modified,
                    content_length=result.bytes, sha256=result.sha256, bytes=result.bytes,
                    status="OK", error=None, last_changed=None,
                )
                out.ok += 1
                out.bytes += result.bytes
                log.info("  + %s (%s)", ds.id, human(result.bytes))

        except FetchError as exc:
            msg = f"{exc} — {exc.diagnosis}"
            manifest.record(key, source_id=src.id, domain=src.domain, dataset_id=ds.id,
                            url=ds.url, remote_path=rel, status="FAILED", error=msg[:900])
            manifest.record_health(src.id, ds.id, exc.status, False, msg[:400])
            out.failed += 1
            out.errors.append((src.id, ds.id, msg))
            log.warning("  ! %s: %s", ds.id, msg)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            manifest.record(key, source_id=src.id, domain=src.domain, dataset_id=ds.id,
                            url=ds.url, remote_path=rel, status="FAILED", error=msg[:900])
            out.failed += 1
            out.errors.append((src.id, ds.id, msg))
            log.warning("  ! %s: %s", ds.id, msg)
            log.debug(traceback.format_exc())
        finally:
            # The streaming contract: local copy dies as soon as it is shipped.
            try:
                if local.exists():
                    local.unlink()
            except OSError:
                pass
            if interval:
                time.sleep(interval)

    return out


def run(
    sources: list[Source],
    *,
    settings: Settings,
    manifest: Manifest,
    transport: Transport,
    max_tier: str,
    log,
    secrets: dict[str, str],
    host: str = "local",
) -> tuple[str, Outcome]:
    run_id = uuid.uuid4().hex[:12]
    domains = ",".join(sorted({s.domain for s in sources}))
    manifest.start_run(run_id, host, domains)
    deadline = time.time() + settings.run_budget_seconds

    total = Outcome()
    for src in sources:
        log.info("--- %s (%s)", src.id, src.domain)
        result = run_source(
            src, settings=settings, manifest=manifest, transport=transport,
            max_tier=max_tier, log=log, deadline=deadline, secrets=secrets,
        )
        total.merge(result)
        if time.time() > deadline:
            log.warning("run budget exhausted; remaining sources deferred to next run")
            break

    manifest.finish_run(run_id, total.ok, total.unchanged, total.failed, total.bytes)
    return run_id, total


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:,.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"
