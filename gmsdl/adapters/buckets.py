"""Public S3 bucket listing, without boto3.

OpenAlex and several AWS Open Data sets are readable anonymously over plain
HTTPS using the ListObjectsV2 REST API, so the engine needs no AWS credentials
and no extra dependency.

Size discipline matters here: the full OpenAlex snapshot is over 660 GB. These
datasets are registered at tier `massive` and are skipped by every routine run;
they are pulled only by an explicit backfill.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from ..registry import Dataset, Source
from . import register

S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def list_bucket(session, host: str, prefix: str, timeout: int, max_keys: int = 5000, start_after: str = ""):
    """Yield (key, size) for a public bucket prefix."""
    token = None
    fetched = 0
    while True:
        params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        elif start_after:
            params["start-after"] = start_after
        r = session.get(f"https://{host}/", params=params, timeout=timeout)
        r.raise_for_status()
        root = ET.fromstring(r.content)

        for c in root.findall("s3:Contents", S3_NS):
            key_el = c.find("s3:Key", S3_NS)
            size_el = c.find("s3:Size", S3_NS)
            if key_el is None or not key_el.text:
                continue
            size = int(size_el.text) if size_el is not None and size_el.text else 0
            yield key_el.text, size
            fetched += 1
            if fetched >= max_keys:
                return

        truncated = root.find("s3:IsTruncated", S3_NS)
        if truncated is None or (truncated.text or "").lower() != "true":
            return
        nxt = root.find("s3:NextContinuationToken", S3_NS)
        if nxt is None or not nxt.text:
            return
        token = nxt.text


@register("s3_public")
def s3_public(source: Source, session, settings) -> list[Dataset]:
    p = source.params
    host = p.get("host", "openalex.s3.amazonaws.com")
    prefix = p.get("prefix", "")
    include = p.get("include_suffix")
    max_keys = int(os.environ.get("GMSDL_S3_MAX_KEYS") or p.get("max_keys", 2000))
    max_total = int(os.environ.get("GMSDL_S3_MAX_TOTAL_BYTES") or p.get("max_total_bytes", 20 * 1024**3))
    start_after = os.environ.get("GMSDL_S3_START_AFTER", "").strip()

    out: list[Dataset] = []
    total = 0
    for key, size in list_bucket(session, host, prefix, settings.http_timeout, max_keys, start_after):
        if include and not key.endswith(tuple(include if isinstance(include, list) else [include])):
            continue
        if total + size > max_total:
            break
        total += size
        out.append(
            Dataset(id=key, url=f"https://{host}/{key}", filename=key, tier=source.tier,
                    max_bytes=max(size * 2, 1024**2))
        )
    return out
