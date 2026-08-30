"""Transport to Google Drive via rclone.

Why rclone rather than the Drive Python client: rclone's Drive backend already
implements chunked resumable upload, exponential backoff on Drive's quota
errors, server-side checksum verification and idempotent re-runs. Reimplementing
that in the engine is the kind of code that fails at 2 a.m. on a 1.5 GB file.

Auth note that matters: files must be written by *your own* Google account via
an OAuth refresh token. A Google service account has no Drive storage quota of
its own, so uploading with one into a shared folder fails with
storageQuotaExceeded no matter how much space the folder's owner has.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import Settings


class TransportError(RuntimeError):
    pass


class Transport:
    def __init__(self, settings: Settings):
        self.s = settings

    # -- availability ----------------------------------------------------
    def available(self) -> bool:
        return shutil.which(self.s.rclone_bin) is not None

    def require(self) -> None:
        if not self.available():
            raise TransportError(
                f"rclone binary {self.s.rclone_bin!r} not found on PATH. "
                "Install it (see SETUP.md) or set GMSDL_NO_UPLOAD=1 to run acquisition only."
            )

    def _base_args(self) -> list[str]:
        args = [
            self.s.rclone_bin,
            "--config", "",              # force env-var-only config
            "--drive-chunk-size", "64M",
            "--drive-acknowledge-abuse",
            "--retries", "5",
            "--low-level-retries", "10",
            "--timeout", "5m",
            "--transfers", "2",
            "--checkers", "4",
            "--stats", "0",
        ]
        if self.s.rclone_extra:
            args.extend(self.s.rclone_extra.split())
        return args

    def _run(self, extra: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
        cmd = self._base_args() + extra
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if check and proc.returncode != 0:
            raise TransportError(
                f"rclone failed ({proc.returncode}): {(proc.stderr or proc.stdout or '').strip()[:800]}"
            )
        return proc

    # -- operations ------------------------------------------------------
    def check_remote(self) -> str:
        """Confirm the remote is reachable and return the account's quota line."""
        self.require()
        proc = self._run(["about", f"{self.s.remote}:"], check=False)
        if proc.returncode != 0:
            raise TransportError(
                f"cannot reach remote {self.s.remote!r}: {(proc.stderr or '').strip()[:400]}\n"
                "Check the RCLONE_CONFIG_GDRIVE_* environment variables / GitHub secrets."
            )
        return proc.stdout.strip()

    def upload(self, local: Path, remote_rel: str) -> None:
        """Copy one local file to <remote_root>/<raw_prefix>/<remote_rel>."""
        if self.s.no_upload or self.s.dry_run:
            return
        self.require()
        target = f"{self.s.raw_remote}/{remote_rel}"
        self._run(["copyto", str(local), target])

    def upload_control(self, local: Path, name: str) -> None:
        if self.s.no_upload or self.s.dry_run:
            return
        self.require()
        self._run(["copyto", str(local), f"{self.s.control_remote}/{name}"])

    def download_control(self, name: str, local: Path) -> bool:
        """Pull a control file back (the manifest at the start of a run)."""
        if self.s.no_upload or self.s.dry_run:
            return False
        if not self.available():
            return False
        local.parent.mkdir(parents=True, exist_ok=True)
        proc = self._run(["copyto", f"{self.s.control_remote}/{name}", str(local)], check=False)
        return proc.returncode == 0 and local.exists()


class NullTransport(Transport):
    """Used by tests, --no-upload runs, and `doctor`."""

    def available(self) -> bool:
        return True

    def require(self) -> None:
        return

    def check_remote(self) -> str:
        return "(no-upload mode)"

    def upload(self, local: Path, remote_rel: str) -> None:
        return

    def upload_control(self, local: Path, name: str) -> None:
        return

    def download_control(self, name: str, local: Path) -> bool:
        return False


def get_transport(settings: Settings) -> Transport:
    if settings.no_upload or settings.dry_run:
        return NullTransport(settings)
    return Transport(settings)
