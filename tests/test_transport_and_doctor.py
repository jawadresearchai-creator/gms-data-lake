"""Verifies the two parts the offline engine test does not reach: the rclone
transport contract, and the doctor report. Uses a stub rclone that records the
commands it was given, so the real Drive path is exercised without credentials."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gmsdl.config import Settings
from gmsdl.doctor import check, write_report
from gmsdl.registry import Dataset, Source
from gmsdl.transport import Transport, TransportError
from mockserver import MockServer

PASS, FAIL = [], []


def check_(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  — ' + detail if detail and not cond else ''}")


STUB = """#!/usr/bin/env python3
import sys, pathlib, os
log = pathlib.Path(os.environ["RCLONE_STUB_LOG"])
log.parent.mkdir(parents=True, exist_ok=True)
with log.open("a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
args = sys.argv[1:]
if "about" in args:
    print("Total:   5 TiB\\nUsed:    463 MiB\\nFree:    4.999 TiB")
sys.exit(0)
"""


def make_stub(tmp: Path) -> str:
    p = tmp / "rclone_stub.py"
    p.write_text(STUB)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_transport(tmp: Path):
    print("\n[transport]")
    log = tmp / "rclone.log"
    os.environ["RCLONE_STUB_LOG"] = str(log)

    s = Settings()
    s.rclone_bin = make_stub(tmp)
    s.remote = "gdrive"
    s.remote_root = ""
    s.no_upload = False
    s.dry_run = False
    t = Transport(s)

    check_("rclone binary is detected on PATH", t.available())
    about = t.check_remote()
    check_("quota probe reaches the remote", "5 TiB" in about, about)

    payload = tmp / "sample.csv"
    payload.write_text("a,b\n1,2\n")
    t.upload(payload, "02_MACRO/BIS_BULK/WS_CBPOL_csv_flat.zip")
    t.upload_control(payload, "manifests/manifest_02_MACRO.sqlite")

    lines = log.read_text().splitlines()
    up = [l for l in lines if l.startswith("copyto") or " copyto " in l]
    check_("upload issues an rclone copyto", any("copyto" in l for l in lines))
    check_("raw file targets the right remote path",
           any("gdrive:01_RAW_IMMUTABLE/02_MACRO/BIS_BULK/WS_CBPOL_csv_flat.zip" in l for l in lines),
           "\n".join(lines))
    check_("manifest targets the control path",
           any("gdrive:00_CONTROL/manifests/manifest_02_MACRO.sqlite" in l for l in lines))
    check_("chunked upload is configured for large files",
           any("--drive-chunk-size 64M" in l for l in lines))
    check_("rclone is told to retry", any("--retries 5" in l for l in lines))

    # A missing binary must fail loudly with a fixable message, not silently.
    s2 = Settings()
    s2.rclone_bin = "definitely-not-installed-xyz"
    s2.no_upload = False
    s2.dry_run = False
    try:
        Transport(s2).check_remote()
        check_("missing rclone raises a clear error", False)
    except TransportError as e:
        check_("missing rclone raises a clear error", "not found on PATH" in str(e))

    # no-upload mode must not shell out at all.
    before = len(log.read_text().splitlines())
    s3 = Settings()
    s3.rclone_bin = s.rclone_bin
    s3.no_upload = True
    Transport(s3).upload(payload, "x/y.csv")
    after = len(log.read_text().splitlines())
    check_("no-upload mode performs no transfer", before == after)


def test_doctor(tmp: Path, base: str):
    print("\n[doctor]")
    import logging
    log = logging.getLogger("d")
    logging.basicConfig(level=logging.CRITICAL)

    s = Settings()
    s.http_timeout = 10
    src = Source(
        id="PROBE", name="probe", domain="TEST", kind="static",
        datasets=[
            Dataset(id="live", url=f"{base}/ok.csv"),
            Dataset(id="dead", url=f"{base}/gone"),
            Dataset(id="blocked", url=f"{base}/forbidden"),
            Dataset(id="webpage", url=f"{base}/htmlpage"),
        ],
    )
    results = check([src], s, log, workers=4)
    by = {r.dataset_id: r for r in results}
    check_("doctor probes every dataset", len(results) == 4)
    check_("live URL reported reachable", by["live"].ok)
    check_("dead URL reported failing with 404", not by["dead"].ok and by["dead"].status == 404)
    check_("blocked URL reported failing with 403", not by["blocked"].ok and by["blocked"].status == 403)
    check_("an HTML page is failed, not accepted as data",
           not by["webpage"].ok and "web page" in by["webpage"].note)
    check_("doctor reports size where the host declares one", by["live"].size is not None)

    out = tmp / "health.md"
    text = write_report(results, out)
    check_("report written to disk", out.exists())
    check_("report separates failing from reachable",
           "## Failing entries" in text and "## Reachable entries" in text)
    check_("report names each failing dataset", "`dead`" in text and "`blocked`" in text)


def test_cli_smoke():
    print("\n[cli]")
    root = Path(__file__).resolve().parents[1]
    for args, must in (
        (["plan"], "sources"),
        (["domains"], "MACRO"),
        (["--help"], "usage"),
        (["plan", "--tier", "massive"], "OPENALEX_SNAPSHOT"),
        (["plan", "--domain", "FINANCE"], "KENNETH_FRENCH_FACTORS"),
    ):
        p = subprocess.run([sys.executable, "-m", "gmsdl.cli", *args],
                           cwd=root, capture_output=True, text=True)
        check_(f"`gmsdl {' '.join(args)}` works", p.returncode == 0 and must in p.stdout,
               f"rc={p.returncode} {p.stderr[:200]}")


def main() -> int:
    with MockServer() as srv, tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_transport(tmp)
        test_doctor(tmp, srv.base)
        test_cli_smoke()
    print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed")
    for f in FAIL:
        print(f"  FAILED: {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
