"""Declarative source registry.

Every source lives in a YAML file under registry/. The engine never contains
source-specific URLs: adding a source is a data edit, not a code edit. That is
what makes the registry safe to hand to another agent.

Two kinds of source:

  kind: static   -- a fixed list of datasets with known, stable URLs.
  kind: adapter  -- datasets are enumerated at run time by an official API or
                    catalogue endpoint (SDMX dataflow lists, S3 listings, JSON
                    catalogues). Never by scraping HTML: most statistical
                    portals are JavaScript single-page apps and an HTML crawler
                    finds zero links on them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

VALID_KINDS = {"static", "adapter"}
VALID_CADENCE = {"daily", "weekly", "monthly", "quarterly", "annual", "static", "on_demand"}

# Datasets tagged with a tier above the active tier are registered but skipped.
# This is how a 660 GB OpenAlex snapshot lives in the registry without ever
# being pulled by a routine weekly run.
TIERS = {"core": 0, "extended": 1, "bulk": 2, "massive": 3}


class RegistryError(ValueError):
    pass


@dataclass
class Dataset:
    id: str
    url: str | None = None
    filename: str | None = None
    notes: str = ""
    tier: str = "core"
    max_bytes: int | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def resolved_filename(self) -> str:
        if self.filename:
            return self.filename
        if not self.url:
            return f"{self.id}.bin"
        tail = self.url.split("?")[0].rstrip("/").split("/")[-1]
        return tail or f"{self.id}.bin"


@dataclass
class Source:
    id: str
    name: str
    domain: str
    kind: str = "static"
    subdomain: str = ""
    adapter: str | None = None
    cadence: str = "monthly"
    license: str = ""
    homepage: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    requires_secret: str | None = None
    tier: str = "core"
    enabled: bool = True
    rate_limit_per_sec: float = 0.0
    datasets: list[Dataset] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def remote_dir(self) -> str:
        parts = [self.domain, self.id]
        if self.subdomain:
            parts = [self.domain, self.subdomain, self.id]
        return "/".join(parts)


def _as_dataset(raw: Any, source_tier: str) -> Dataset:
    if isinstance(raw, str):
        return Dataset(id=raw, url=raw, tier=source_tier)
    if not isinstance(raw, dict):
        raise RegistryError(f"dataset must be a mapping or string, got {type(raw).__name__}")
    ds = Dataset(
        id=str(raw["id"]),
        url=raw.get("url"),
        filename=raw.get("filename"),
        notes=raw.get("notes", ""),
        tier=raw.get("tier", source_tier),
        max_bytes=raw.get("max_bytes"),
        params=raw.get("params", {}) or {},
    )
    if ds.tier not in TIERS:
        raise RegistryError(f"dataset {ds.id}: unknown tier {ds.tier!r}")
    return ds


def _as_source(raw: dict[str, Any], domain: str, path: Path) -> Source:
    try:
        sid = str(raw["id"])
    except KeyError as exc:
        raise RegistryError(f"{path}: source is missing 'id'") from exc

    kind = raw.get("kind", "static")
    if kind not in VALID_KINDS:
        raise RegistryError(f"{path}:{sid}: unknown kind {kind!r}")

    tier = raw.get("tier", "core")
    if tier not in TIERS:
        raise RegistryError(f"{path}:{sid}: unknown tier {tier!r}")

    cadence = raw.get("cadence", "monthly")
    if cadence not in VALID_CADENCE:
        raise RegistryError(f"{path}:{sid}: unknown cadence {cadence!r}")

    src = Source(
        id=sid,
        name=raw.get("name", sid),
        domain=domain,
        kind=kind,
        subdomain=raw.get("subdomain", ""),
        adapter=raw.get("adapter"),
        cadence=cadence,
        license=raw.get("license", ""),
        homepage=raw.get("homepage", ""),
        headers=raw.get("headers", {}) or {},
        requires_secret=raw.get("requires_secret"),
        tier=tier,
        enabled=bool(raw.get("enabled", True)),
        rate_limit_per_sec=float(raw.get("rate_limit_per_sec", 0) or 0),
        params=raw.get("params", {}) or {},
        notes=raw.get("notes", ""),
    )
    src.datasets = [_as_dataset(d, tier) for d in (raw.get("datasets") or [])]

    if kind == "static" and not src.datasets:
        raise RegistryError(f"{path}:{sid}: static source has no datasets")
    if kind == "adapter" and not src.adapter:
        raise RegistryError(f"{path}:{sid}: adapter source has no 'adapter' name")
    for ds in src.datasets:
        if kind == "static" and not ds.url:
            raise RegistryError(f"{path}:{sid}:{ds.id}: static dataset has no url")
    return src


def load_registry(registry_dir: Path) -> list[Source]:
    """Parse and validate every YAML file in registry_dir."""
    registry_dir = Path(registry_dir)
    if not registry_dir.is_dir():
        raise RegistryError(f"registry directory not found: {registry_dir}")

    sources: list[Source] = []
    seen: dict[str, Path] = {}
    for path in sorted(registry_dir.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
        domain = doc.get("domain")
        if not domain:
            raise RegistryError(f"{path}: missing top-level 'domain'")
        for raw in doc.get("sources") or []:
            src = _as_source(raw, domain, path)
            if src.id in seen:
                raise RegistryError(f"duplicate source id {src.id!r} in {path} and {seen[src.id]}")
            seen[src.id] = path
            sources.append(src)
    if not sources:
        raise RegistryError(f"no sources found in {registry_dir}")
    return sources


def select(
    sources: Iterable[Source],
    *,
    domains: list[str] | None = None,
    source_ids: list[str] | None = None,
    max_tier: str = "core",
    include_disabled: bool = False,
) -> list[Source]:
    """Filter sources for a run."""
    ceiling = TIERS[max_tier]
    out = []
    for s in sources:
        if not s.enabled and not include_disabled:
            continue
        if domains and not any(re.search(d, s.domain) for d in domains):
            continue
        if source_ids and s.id not in source_ids:
            continue
        if TIERS[s.tier] > ceiling:
            continue
        out.append(s)
    return out


def datasets_for(src: Source, max_tier: str = "core") -> list[Dataset]:
    ceiling = TIERS[max_tier]
    return [d for d in src.datasets if TIERS[d.tier] <= ceiling]


def domains(sources: Iterable[Source]) -> list[str]:
    return sorted({s.domain for s in sources})
