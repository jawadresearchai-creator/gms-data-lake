"""SDMX dataflow enumeration for OECD, ECB and Eurostat.

All three publish a machine-readable list of every dataflow they hold. That list
is the correct discovery mechanism; their web front-ends are SPAs.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..registry import Dataset, Source
from . import register

SDMX_NS = {
    "s21": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
    "m21": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message",
    "c21": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
}


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_dataflows(xml_bytes: bytes) -> list[tuple[str, str, str]]:
    """Return [(agency, flow_id, name)] from an SDMX 2.1 structure message.
    Namespace-agnostic on purpose: agencies differ in prefix and version."""
    out: list[tuple[str, str, str]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out
    for el in root.iter():
        if _localname(el.tag) != "Dataflow":
            continue
        flow_id = el.attrib.get("id")
        agency = el.attrib.get("agencyID", "")
        if not flow_id:
            continue
        name = flow_id
        for child in el:
            if _localname(child.tag) == "Name" and (child.text or "").strip():
                name = child.text.strip()
                break
        out.append((agency, flow_id, name))
    return out


def _filtered(flows, include: str | None, exclude: str | None, limit: int):
    inc = re.compile(include) if include else None
    exc = re.compile(exclude) if exclude else None
    kept = []
    for agency, fid, name in flows:
        if inc and not (inc.search(fid) or inc.search(name)):
            continue
        if exc and (exc.search(fid) or exc.search(name)):
            continue
        kept.append((agency, fid, name))
        if len(kept) >= limit:
            break
    return kept


@register("sdmx_oecd")
def sdmx_oecd(source: Source, session, settings) -> list[Dataset]:
    p = source.params
    catalogue = p.get("catalogue", "https://sdmx.oecd.org/public/rest/dataflow/all/all/latest")
    r = session.get(catalogue, timeout=settings.http_timeout)
    r.raise_for_status()
    flows = parse_dataflows(r.content)
    kept = _filtered(flows, p.get("include_regex"), p.get("exclude_regex"), int(p.get("max_datasets", 60)))
    fmt = p.get("format", "csvfilewithlabels")
    out = []
    for agency, fid, name in kept:
        url = f"https://sdmx.oecd.org/public/rest/data/{agency},{fid},/all?format={fmt}"
        out.append(Dataset(id=fid, url=url, filename=f"{fid}.csv", notes=name, tier=source.tier))
    return out


@register("sdmx_ecb")
def sdmx_ecb(source: Source, session, settings) -> list[Dataset]:
    p = source.params
    catalogue = p.get("catalogue", "https://data-api.ecb.europa.eu/service/dataflow/ECB?format=structure")
    r = session.get(catalogue, timeout=settings.http_timeout)
    r.raise_for_status()
    flows = parse_dataflows(r.content)
    kept = _filtered(flows, p.get("include_regex"), p.get("exclude_regex"), int(p.get("max_datasets", 40)))
    out = []
    for _agency, fid, name in kept:
        url = f"https://data-api.ecb.europa.eu/service/data/{fid}?format=csvdata"
        out.append(Dataset(id=fid, url=url, filename=f"{fid}.csv", notes=name, tier=source.tier,
                           max_bytes=int(p["max_bytes"]) if p.get("max_bytes") else None))
    return out


@register("eurostat")
def eurostat(source: Source, session, settings) -> list[Dataset]:
    """Eurostat retired the old bulk-download listing. The replacement is the
    dissemination API: a plain-text table of contents, then one TSV per dataset."""
    p = source.params
    toc_url = p.get("catalogue", "https://ec.europa.eu/eurostat/api/dissemination/catalogue/toc/txt")
    r = session.get(toc_url, timeout=settings.http_timeout)
    r.raise_for_status()

    include = re.compile(p["include_regex"]) if p.get("include_regex") else None
    limit = int(p.get("max_datasets", 80))
    out: list[Dataset] = []
    seen: set[str] = set()

    for line in r.text.splitlines():
        # TOC rows are tab-separated; the dataset code is the second field.
        parts = [c.strip() for c in line.split("\t")]
        if len(parts) < 2:
            continue
        code = parts[1]
        if not re.fullmatch(r"[a-z0-9_]{4,40}", code) or code in seen:
            continue
        title = parts[0]
        if include and not include.search(code):
            continue
        seen.add(code)
        url = (
            "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
            f"{code}/?format=TSV&compressed=true"
        )
        out.append(Dataset(id=code, url=url, filename=f"{code}.tsv.gz", notes=title, tier=source.tier))
        if len(out) >= limit:
            break
    return out
