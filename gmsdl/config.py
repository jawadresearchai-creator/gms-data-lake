"""Runtime configuration. Everything is env-driven so the same code runs on
GitHub Actions, Colab, or a laptop with no edits."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # --- identity -------------------------------------------------------
    # Several government sources (SEC above all) require a contact-bearing
    # User-Agent and will hard-403 a default python-requests UA.
    contact_email: str = field(
        default_factory=lambda: os.environ.get("GMSDL_CONTACT_EMAIL", "research@example.org")
    )
    project_name: str = "GlobalManagementScienceDataLake"

    # --- filesystem -----------------------------------------------------
    workdir: Path = field(
        default_factory=lambda: Path(os.environ.get("GMSDL_WORKDIR", "./_work")).resolve()
    )
    registry_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("GMSDL_REGISTRY_DIR", "./registry")).resolve()
    )
    state_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("GMSDL_STATE_DIR", "./_state")).resolve()
    )

    # --- disk ceiling ---------------------------------------------------
    # The whole point of the streaming design: never hold more than this on
    # local disk. Default 6 GiB fits a GitHub runner and any laptop.
    max_workdir_bytes: int = field(default_factory=lambda: _int("GMSDL_MAX_WORKDIR_BYTES", 6 * 1024**3))
    # Refuse any single file larger than this unless the dataset opts in.
    max_file_bytes: int = field(default_factory=lambda: _int("GMSDL_MAX_FILE_BYTES", 5 * 1024**3))

    # --- transport ------------------------------------------------------
    remote: str = field(default_factory=lambda: os.environ.get("GMSDL_RCLONE_REMOTE", "gdrive"))
    remote_root: str = field(
        default_factory=lambda: os.environ.get(
            "GMSDL_REMOTE_ROOT", "GLOBAL_MULTIDISCIPLINARY_MANAGEMENT_SCIENCE_DATA_LAKE"
        )
    )
    raw_prefix: str = field(default_factory=lambda: os.environ.get("GMSDL_RAW_PREFIX", "01_RAW_IMMUTABLE"))
    control_prefix: str = field(default_factory=lambda: os.environ.get("GMSDL_CONTROL_PREFIX", "00_CONTROL"))
    rclone_bin: str = field(default_factory=lambda: os.environ.get("GMSDL_RCLONE_BIN", "rclone"))
    rclone_extra: str = field(default_factory=lambda: os.environ.get("GMSDL_RCLONE_EXTRA", ""))

    # --- network --------------------------------------------------------
    http_timeout: int = field(default_factory=lambda: _int("GMSDL_HTTP_TIMEOUT", 120))
    max_retries: int = field(default_factory=lambda: _int("GMSDL_MAX_RETRIES", 4))
    chunk_bytes: int = field(default_factory=lambda: _int("GMSDL_CHUNK_BYTES", 4 * 1024**2))

    # Each CI matrix job owns its own manifest file, so parallel domain jobs
    # never race for one SQLite blob on Drive.
    manifest_name: str = field(
        default_factory=lambda: os.environ.get("GMSDL_MANIFEST_NAME", "manifest.sqlite")
    )

    # --- behaviour ------------------------------------------------------
    dry_run: bool = field(default_factory=lambda: _bool("GMSDL_DRY_RUN", False))
    # Skip upload entirely (used by tests and by `doctor`).
    no_upload: bool = field(default_factory=lambda: _bool("GMSDL_NO_UPLOAD", False))
    # Per-run wall-clock budget; the runner stops cleanly before a CI timeout.
    run_budget_seconds: int = field(default_factory=lambda: _int("GMSDL_RUN_BUDGET_SECONDS", 5 * 3600))

    @property
    def user_agent(self) -> str:
        return f"{self.project_name}/2.0 (+{self.contact_email})"

    def _remote_path(self, *parts: str) -> str:
        segs = [p.strip("/") for p in (self.remote_root, *parts) if p and p.strip("/")]
        return f"{self.remote}:" + "/".join(segs)

    @property
    def raw_remote(self) -> str:
        return self._remote_path(self.raw_prefix)

    @property
    def control_remote(self) -> str:
        return self._remote_path(self.control_prefix)

    def ensure_dirs(self) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)


SETTINGS = Settings()
