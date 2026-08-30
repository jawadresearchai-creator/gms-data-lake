"""Offline end-to-end verification. No network, no Drive, no credentials."""
from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gmsdl.config import Settings
from gmsdl.fetch import FetchError, fetch, make_session
from gmsdl.manifest import Manifest
from gmsdl.registry import RegistryError, Source, Dataset, load_registry, select
from gmsdl.runner import run
from gmsdl.transport import NullTransport
from mockserver import MockServer

LOG = logging.getLogger("test")
logging.basicConfig(level=logging.WARNING)

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  — ' + detail if detail and not cond else ''}")


def settings_for(tmp: Path, name: str = "work") -> Settings:
    s = Settings()
    s.workdir = tmp / name
    s.state_dir = tmp / "state"
    s.no_upload = True
    s.max_retries = 3
    s.http_timeout = 10
    s.max_file_bytes = 10 * 1024 * 1024   # 10 MiB ceiling for the size test
    s.ensure_dirs()
    return s


def test_fetch_paths(tmp: Path, base: str):
    print("\n[fetch]")
    s = settings_for(tmp, "work_fetch")
    sess = make_session(s)

    r = fetch(sess, f"{base}/ok.csv", s.workdir / "ok.csv", s)
    check("downloads a normal file", r.bytes > 0 and r.sha256 is not None)
    check("captures ETag for conditional GET", r.etag == '"v1"')

    r2 = fetch(sess, f"{base}/ok.csv", s.workdir / "ok2.csv", s, etag='"v1"')
    check("304 recognised as unchanged", r2.unchanged and r2.bytes == 0)

    try:
        fetch(sess, f"{base}/htmlpage", s.workdir / "h.bin", s)
        check("rejects an HTML page served as data", False)
    except FetchError as e:
        check("rejects an HTML page served as data", "HTML page" in str(e))
        check("HTML rejection carries a diagnosis", "JavaScript app shell" in e.diagnosis)

    try:
        fetch(sess, f"{base}/forbidden", s.workdir / "f.bin", s)
        check("403 raises", False)
    except FetchError as e:
        check("403 raises", e.status == 403)
        check("403 diagnosis names the real cause", "User-Agent" in e.diagnosis)
        check("403 is not retried", Handler_hits(base, "/forbidden") == 1,
              f"hits={Handler_hits(base, '/forbidden')}")

    try:
        fetch(sess, f"{base}/gone", s.workdir / "g.bin", s)
        check("404 raises", False)
    except FetchError as e:
        check("404 raises with stale-URL diagnosis", e.status == 404 and "stale" in e.diagnosis)

    try:
        fetch(sess, f"{base}/huge", s.workdir / "big.bin", s)
        check("refuses a file over the size ceiling", False)
    except FetchError as e:
        check("refuses a file over the size ceiling", "exceeds ceiling" in str(e))
    check("oversized file left nothing on disk", not (s.workdir / "big.bin").exists())

    r3 = fetch(sess, f"{base}/flaky", s.workdir / "flaky.txt", s)
    check("retries 5xx and eventually succeeds", r3.bytes > 0)

    try:
        fetch(sess, f"{base}/empty", s.workdir / "e.bin", s)
        check("rejects an empty 200 body", False)
    except FetchError as e:
        check("rejects an empty 200 body", "empty response" in str(e))

    leftovers = list(s.workdir.glob("*.part"))
    check("no .part temp files left behind", not leftovers, str(leftovers))


def Handler_hits(base: str, path: str) -> int:
    from mockserver import Handler
    return Handler.hits.get(path, 0)


def test_registry(tmp: Path):
    print("\n[registry]")
    sources = load_registry(Path(__file__).resolve().parents[1] / "registry")
    check("real registry parses", len(sources) > 40, f"{len(sources)} sources")
    ids = [s.id for s in sources]
    check("source ids are unique", len(ids) == len(set(ids)))
    check("every adapter named in the registry exists", all(
        _adapter_ok(s) for s in sources if s.kind == "adapter"))

    core = select(sources, max_tier="core")
    massive = select(sources, max_tier="massive")
    check("tiers gate the huge sources out of a core run",
          len(core) < len(massive), f"core={len(core)} massive={len(massive)}")
    check("OpenAlex is excluded from a core run",
          not any(s.id == "OPENALEX_SNAPSHOT" for s in core))
    check("disabled sources are excluded by default",
          not any(s.id == "FFIEC_CALL_REPORTS" for s in core))

    bad = tmp / "badreg"
    bad.mkdir(parents=True, exist_ok=True)
    (bad / "x.yaml").write_text("domain: D\nsources:\n  - id: A\n    kind: static\n")
    try:
        load_registry(bad)
        check("a static source with no datasets is rejected", False)
    except RegistryError:
        check("a static source with no datasets is rejected", True)

    (bad / "x.yaml").write_text(
        "domain: D\nsources:\n  - id: A\n    kind: adapter\n")
    try:
        load_registry(bad)
        check("an adapter source with no adapter name is rejected", False)
    except RegistryError:
        check("an adapter source with no adapter name is rejected", True)


def _adapter_ok(s) -> bool:
    from gmsdl import adapters
    try:
        adapters.get(s.adapter)
        return True
    except KeyError:
        print(f"      unknown adapter: {s.id} -> {s.adapter}")
        return False


def test_run_isolation(tmp: Path, base: str):
    print("\n[run isolation]")
    s = settings_for(tmp, "work_run")
    m = Manifest(tmp / "state" / "m.sqlite")

    src = Source(
        id="MIXED", name="mixed", domain="TEST", kind="static",
        datasets=[
            Dataset(id="good1", url=f"{base}/ok.csv", filename="good1.csv"),
            Dataset(id="dead", url=f"{base}/gone", filename="dead.bin"),
            Dataset(id="blocked", url=f"{base}/forbidden", filename="blocked.bin"),
            Dataset(id="webpage", url=f"{base}/htmlpage", filename="page.bin"),
            Dataset(id="good2", url=f"{base}/ok.csv?v=2", filename="good2.csv"),
        ],
    )
    run_id, out = run([src], settings=s, manifest=m, transport=NullTransport(s),
                      max_tier="core", log=LOG, secrets={})
    check("one bad URL does not stop the source", out.ok == 2, f"ok={out.ok}")
    check("all three failures are recorded", out.failed == 3, f"failed={out.failed}")
    check("failures carry a reason", all(msg for _, _, msg in out.errors))

    rows = m.failures()
    check("failures persisted to the manifest with diagnosis",
          len(rows) == 3 and all(r["error"] for r in rows))

    # Re-run: the two good ones should now be unchanged, not re-downloaded.
    _, out2 = run([src], settings=s, manifest=m, transport=NullTransport(s),
                  max_tier="core", log=LOG, secrets={})
    check("re-run skips unchanged files via conditional GET",
          out2.unchanged == 2 and out2.ok == 0, f"unchanged={out2.unchanged} ok={out2.ok}")

    residue = [p for p in s.workdir.rglob("*") if p.is_file()]
    check("workdir holds nothing after the run — no local accumulation",
          not residue, str(residue))

    check("manifest passes integrity check", m.integrity_ok())
    m.close()


def test_secret_skipping(tmp: Path, base: str):
    print("\n[secrets]")
    s = settings_for(tmp, "work_secret")
    m = Manifest(tmp / "state" / "m2.sqlite")
    src = Source(id="NEEDSKEY", name="k", domain="TEST", kind="static",
                 requires_secret="SOME_MISSING_KEY",
                 datasets=[Dataset(id="d", url=f"{base}/ok.csv", filename="d.csv")])
    _, out = run([src], settings=s, manifest=m, transport=NullTransport(s),
                 max_tier="core", log=LOG, secrets={})
    check("source without its secret is skipped, not failed",
          out.skipped == 1 and out.failed == 0)
    m.close()


def main() -> int:
    with MockServer() as srv, tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_fetch_paths(tmp, srv.base)
        test_registry(tmp)
        test_run_isolation(tmp, srv.base)
        test_secret_skipping(tmp, srv.base)

    print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for f in FAIL:
            print(f"  FAILED: {f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
