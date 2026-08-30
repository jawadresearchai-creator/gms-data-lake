"""JSON / plain-text catalogue adapters."""
from __future__ import annotations

import datetime as dt
import re

from ..registry import Dataset, Source
from . import register


@register("worldbank_indicators")
def worldbank_indicators(source: Source, session, settings) -> list[Dataset]:
    """World Bank publishes every database as a zipped CSV bundle. The source
    list endpoint is open and needs no key."""
    p = source.params
    r = session.get("https://api.worldbank.org/v2/sources?format=json&per_page=200",
                    timeout=settings.http_timeout)
    r.raise_for_status()
    payload = r.json()
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    wanted = set(p.get("source_codes") or [])
    out: list[Dataset] = []
    for row in rows:
        code = (row.get("code") or "").strip()
        name = row.get("name", code)
        if wanted and code not in wanted:
            continue
        if str(row.get("dataavailability", "")).lower() == "n":
            continue
        url = f"https://api.worldbank.org/v2/country/all/indicator/{code}?format=json&per_page=20000"
        out.append(Dataset(id=f"WB_{code}", url=url, filename=f"worldbank_{code}.json",
                           notes=name, tier=source.tier))
        if len(out) >= int(p.get("max_datasets", 40)):
            break
    return out


@register("gdelt_window")
def gdelt_window(source: Source, session, settings) -> list[Dataset]:
    """GDELT publishes a master list of every 15-minute file ever produced.
    The full archive is measured in terabytes, so this adapter takes a bounded
    trailing window instead of the whole list â€” the previous engine's
    ENABLE_GDELT_ALL_STREAMS=True would have tried to fetch all of it."""
    p = source.params
    days = int(p.get("lookback_days", 7))
    streams = set(p.get("streams") or ["export", "gkg"])
    master = p.get("masterlist", "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt")

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    cutoff_key = cutoff.strftime("%Y%m%d")

    out: list[Dataset] = []
    with session.get(master, timeout=settings.http_timeout, stream=True) as r:
        r.raise_for_status()
        for raw in r.iter_lines(decode_unicode=True):
            if not raw:
                continue
            parts = raw.split()
            if len(parts) != 3:
                continue
            _size, _hash, url = parts
            fname = url.rsplit("/", 1)[-1]
            stamp = fname[:8]
            if not stamp.isdigit() or stamp < cutoff_key:
                continue
            kind = "export" if ".export." in fname else "gkg" if ".gkg." in fname else \
                   "mentions" if ".mentions." in fname else "other"
            if kind not in streams:
                continue
            out.append(Dataset(id=fname, url=url, filename=f"{stamp}/{fname}", tier=source.tier))
    out.sort(key=lambda d: d.id)
    cap = int(p.get("max_files", 400))
    return out[-cap:] if len(out) > cap else out


@register("fdic_api")
def fdic_api(source: Source, session, settings) -> list[Dataset]:
    """FDIC BankFind Suite serves CSV directly and needs no key."""
    p = source.params
    base = p.get("base", "https://api.fdic.gov/banks")
    limit = int(p.get("page_size", 10000))
    endpoints = p.get("endpoints") or {
        "institutions": "institutions",
        "failures": "failures",
        "locations": "locations",
        "sod": "sod",
    }
    out = []
    for name, path in endpoints.items():
        url = f"{base}/{path}?format=csv&limit={limit}&offset=0"
        out.append(Dataset(id=f"fdic_{name}", url=url, filename=f"fdic_{name}.csv", tier=source.tier))
    return out


@register("treasury_fiscaldata")
def treasury_fiscaldata(source: Source, session, settings) -> list[Dataset]:
    """Treasury's Fiscal Data API replaces the home.treasury.gov XML endpoint
    that 403s a scripted client."""
    p = source.params
    base = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    size = int(p.get("page_size", 10000))
    out = []
    for name, path in (p.get("endpoints") or {}).items():
        url = f"{base}/{path}?format=csv&page[size]={size}&page[number]=1"
        out.append(Dataset(id=f"treasury_{name}", url=url, filename=f"treasury_{name}.csv",
                           tier=source.tier))
    return out


@register("federal_register")
def federal_register(source: Source, session, settings) -> list[Dataset]:
    """govinfo publishes Federal Register bulk XML by year."""
    p = source.params
    start = int(p.get("start_year", dt.date.today().year - 5))
    end = int(p.get("end_year", dt.date.today().year))
    out = []
    for year in range(start, end + 1):
        url = f"https://www.govinfo.gov/bulkdata/FR/{year}/FR-{year}.zip"
        out.append(Dataset(id=f"FR_{year}", url=url, filename=f"FR-{year}.zip", tier=source.tier))
    return out


@register("usaspending_archive")
def usaspending_archive(source: Source, session, settings) -> list[Dataset]:
    """USAspending publishes yearly award archives on a predictable path."""
    p = source.params
    start = int(p.get("start_year", dt.date.today().year - 3))
    end = int(p.get("end_year", dt.date.today().year))
    agency = p.get("agency", "All")
    kinds = p.get("kinds") or ["Contracts", "Assistance"]
    out = []
    for year in range(start, end + 1):
        for kind in kinds:
            fname = f"FY{year}_{agency}_{kind}_Full_{dt.date.today():%Y%m%d}.zip"
            url = f"https://files.usaspending.gov/award_data_archive/{fname}"
            out.append(Dataset(id=f"usaspending_{year}_{kind}", url=url, filename=fname,
                               tier=source.tier,
                               notes="Archive filenames embed a build date; verify with `gmsdl doctor`."))
    return out


@register("faostat_domains")
def faostat_domains(source: Source, session, settings) -> list[Dataset]:
    """FAOSTAT bulk zips follow a stable path; the domain codes are listed in
    the registry rather than scraped, because the FAOSTAT front end is an SPA."""
    p = source.params
    base = p.get("base", "https://fenixservices.fao.org/faostat/static/bulkdownloads")
    out = []
    for code in p.get("domains") or []:
        fname = f"{code}_E_All_Data_(Normalized).zip"
        out.append(Dataset(id=f"faostat_{code}", url=f"{base}/{fname}",
                           filename=fname, tier=source.tier))
    return out


@register("stlouisfed_fredmd")
def stlouisfed_fredmd(source: Source, session, settings) -> list[Dataset]:
    """Resolve current FRED-MD/FRED-QD links from the St. Louis Fed page.
    Guessed future media paths may return HTML with HTTP 200, so use the
    canonical page's published dated links instead."""
    page = source.homepage or "https://www.stlouisfed.org/research/economists/mccracken/fred-databases"
    r = session.get(page, timeout=settings.http_timeout, allow_redirects=True)
    r.raise_for_status()
    html = r.text
    out: list[Dataset] = []
    for freq, suffix in (("monthly", "md"), ("quarterly", "qd")):
        pat = rf'href="([^"]*/fred-md/{freq}/(\d{{4}}-\d{{2}})-{suffix}\.csv)"'
        matches = re.findall(pat, html, flags=re.I)
        if not matches:
            continue
        href, vintage = matches[0]
        if href.startswith("/"):
            href = "https://www.stlouisfed.org" + href
        out.append(Dataset(id=f"FRED_{suffix.upper()}", url=href,
                           filename=f"fred_{suffix}_{vintage}.csv", tier=source.tier))
    return out

@register("census_bds")
def census_bds(source: Source, session, settings) -> list[Dataset]:
    """Census BDS time-series CSVs live under a year-stamped directory; the old
    path without the year returns 404."""
    p = source.params
    year = int(p.get("vintage", dt.date.today().year - 3))
    base = "https://www2.census.gov/programs-surveys/bds/tables/time-series"
    tables = p.get("tables") or ["", "_sec", "_st", "_msa", "_vcn4"]
    out = []
    for suffix in tables:
        fname = f"bds{year}{suffix}.csv"
        out.append(Dataset(id=f"bds{year}{suffix or '_national'}",
                           url=f"{base}/{year}/{fname}", filename=fname, tier=source.tier))
    return out


@register("static_expand")
def static_expand(source: Source, session, settings) -> list[Dataset]:
    """Expand a URL template over a list of codes. Covers the many hosts that
    serve one file per dataset on a predictable path (BIS, ILOSTAT, WIPO...)."""
    p = source.params
    template = p["url_template"]
    fname_template = p.get("filename_template", "{code}")
    out = []
    for entry in p.get("codes") or []:
        if isinstance(entry, dict):
            code, label = entry.get("code"), entry.get("name", "")
        else:
            code, label = entry, ""
        out.append(Dataset(id=str(code),
                           url=template.format(code=code),
                           filename=fname_template.format(code=code),
                           notes=label, tier=source.tier))
    return out
