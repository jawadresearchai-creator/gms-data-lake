"""Command line interface.

    gmsdl plan               show what a run would do, without touching the network
    gmsdl doctor             probe every registry URL and write a health report
    gmsdl run                acquire and ship to Drive
    gmsdl status             summarise the manifest
    gmsdl domains            list domains (used by the CI matrix)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from . import __version__, adapters
from .config import SETTINGS, Settings
from .doctor import check, write_report
from .manifest import Manifest
from .registry import RegistryError, TIERS, datasets_for, load_registry, select
from .report import build, emit
from .runner import human, run
from .transport import NullTransport, TransportError, get_transport

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"


def make_logger(verbose: bool) -> logging.Logger:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format=LOG_FORMAT, datefmt="%H:%M:%S", stream=sys.stdout)
    return logging.getLogger("gmsdl")


def collect_secrets() -> dict[str, str]:
    """Any environment variable is available to a source's requires_secret /
    header templating. Keys never appear in the registry itself."""
    return {k: v for k, v in os.environ.items() if v}


def load(settings: Settings, args) -> list:
    sources = load_registry(settings.registry_dir)
    return select(sources, domains=args.domain or None, source_ids=args.source or None,
                  max_tier=args.tier, include_disabled=args.include_disabled)


def cmd_domains(settings: Settings, args, log) -> int:
    import re
    sources = load_registry(settings.registry_dir)
    names = sorted({s.domain for s in sources})
    if getattr(args, "domain", None):
        names = [n for n in names if any(re.search(d, n) for d in args.domain)]
    print(json.dumps(names) if args.json else "\n".join(names))
    return 0


def cmd_plan(settings: Settings, args, log) -> int:
    sources = load(settings, args)
    total_static = 0
    print(f"{'SOURCE':<26} {'KIND':<9} {'TIER':<9} {'CADENCE':<10} DATASETS")
    print("-" * 82)
    for s in sources:
        n = len(datasets_for(s, args.tier)) if s.kind == "static" else 0
        total_static += n
        shown = str(n) if s.kind == "static" else f"via {s.adapter}"
        print(f"{s.id:<26} {s.kind:<9} {s.tier:<9} {s.cadence:<10} {shown}")
    print("-" * 82)
    print(f"{len(sources)} sources, {total_static} statically-declared datasets "
          f"(adapters enumerate more at run time)")
    missing = [s.id for s in sources if s.requires_secret and not os.environ.get(s.requires_secret)]
    if missing:
        print(f"\nWill be skipped for missing secrets: {', '.join(missing)}")
    return 0


def cmd_doctor(settings: Settings, args, log) -> int:
    sources = load(settings, args)
    log.info("probing %d source(s)", len(sources))
    results = check(sources, settings, log, max_tier=args.tier, workers=args.workers,
                    expand_adapters=not args.static_only)
    out = Path(args.output or settings.state_dir / "registry_health.md")
    text = write_report(results, out)
    emit(text)
    bad = [r for r in results if not r.ok]
    log.info("health report -> %s", out)
    log.info("%d/%d reachable", len(results) - len(bad), len(results))
    if not results:
        return 0
    if len(bad) / len(results) > args.max_failure_rate:
        log.error("failure rate %.0f%% exceeds threshold %.0f%%",
                  100 * len(bad) / len(results), 100 * args.max_failure_rate)
        return 1
    return 0


def cmd_run(settings: Settings, args, log) -> int:
    sources = load(settings, args)
    if not sources:
        log.error("no sources selected")
        return 2
    settings.ensure_dirs()

    transport = get_transport(settings)
    if not isinstance(transport, NullTransport):
        try:
            log.info("remote: %s", transport.check_remote().replace("\n", " | "))
        except TransportError as exc:
            log.error("%s", exc)
            return 3

    db_path = settings.state_dir / settings.manifest_name
    # Pull the previous manifest so conditional GET works across CI runs, which
    # start from a clean machine every time.
    if not db_path.exists():
        if transport.download_control(f"manifests/{settings.manifest_name}", db_path):
            log.info("restored manifest from Drive")
    manifest = Manifest(db_path)
    if not manifest.integrity_ok():
        log.warning("manifest failed integrity check; starting a fresh one")
        manifest.close()
        db_path.rename(db_path.with_suffix(".corrupt"))
        manifest = Manifest(db_path)

    host = "github-actions" if os.environ.get("GITHUB_ACTIONS") else "local"
    log.info("selected %d source(s), tier<=%s, host=%s", len(sources), args.tier, host)

    run_id, outcome = run(sources, settings=settings, manifest=manifest, transport=transport,
                          max_tier=args.tier, log=log, secrets=collect_secrets(), host=host)

    text = build(manifest, outcome, run_id)
    report_path = settings.state_dir / f"run_{run_id}.md"
    emit(text, report_path)
    manifest.close()

    if not isinstance(transport, NullTransport):
        try:
            transport.upload_control(db_path, f"manifests/{settings.manifest_name}")
            transport.upload_control(report_path, f"reports/run_{run_id}.md")
            log.info("manifest and report shipped to Drive")
        except TransportError as exc:
            log.error("could not ship control files: %s", exc)

    log.info("done: %d new, %d unchanged, %d failed, %s transferred",
             outcome.ok, outcome.unchanged, outcome.failed, human(outcome.bytes))
    if args.strict and outcome.failed:
        return 1
    return 0


def cmd_status(settings: Settings, args, log) -> int:
    db = settings.state_dir / settings.manifest_name
    if not db.exists():
        print("no manifest yet")
        return 0
    m = Manifest(db)
    s = m.summary()
    print(f"files held : {s['files']:,}")
    print(f"total size : {human(s['bytes'])}")
    for status, v in sorted(s["by_status"].items()):
        print(f"  {status or 'NULL':<12} {v['n']:>6}  {human(v['bytes'])}")
    print("\nby domain:")
    for r in m.by_domain():
        print(f"  {r['domain']:<45} {r['n']:>5}  {human(r['b'])}")
    fails = m.failures(args.limit)
    if fails:
        print("\nrecent failures:")
        for r in fails:
            print(f"  {r['source_id']}/{r['dataset_id']}: {(r['error'] or '')[:150]}")
    m.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gmsdl", description="Management-science data lake ingestor")
    p.add_argument("--version", action="version", version=f"gmsdl {__version__}")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--registry", help="registry directory (default ./registry)")

    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--domain", action="append", help="domain regex; repeatable")
        sp.add_argument("--source", action="append", help="explicit source id; repeatable")
        sp.add_argument("--tier", choices=sorted(TIERS, key=TIERS.get), default="core")
        sp.add_argument("--include-disabled", action="store_true")

    sp = sub.add_parser("plan", help="show what would run")
    common(sp)
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("doctor", help="probe every registry URL")
    common(sp)
    sp.add_argument("--workers", type=int, default=8)
    sp.add_argument("--output")
    sp.add_argument("--static-only", action="store_true", help="skip adapter enumeration")
    sp.add_argument("--max-failure-rate", type=float, default=0.35)
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("run", help="acquire and ship")
    common(sp)
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-upload", action="store_true")
    sp.add_argument("--strict", action="store_true", help="exit non-zero if anything failed")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("status", help="summarise the manifest")
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("domains", help="list domains")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--domain", action="append", help="filter by regex; repeatable")
    sp.set_defaults(func=cmd_domains)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log = make_logger(args.verbose)
    settings = SETTINGS
    if args.registry:
        settings.registry_dir = Path(args.registry).resolve()
    if getattr(args, "dry_run", False):
        settings.dry_run = True
    if getattr(args, "no_upload", False):
        settings.no_upload = True
    try:
        return args.func(settings, args, log)
    except RegistryError as exc:
        log.error("registry error: %s", exc)
        return 2
    except KeyboardInterrupt:
        log.warning("interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
