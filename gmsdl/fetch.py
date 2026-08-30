"""Streaming HTTP acquisition.

Design rules, each of which corresponds to a concrete failure in the previous
engine:

  * A contact-bearing, browser-plausible User-Agent. A default python-requests
    UA is hard-403'd by files.stlouisfed.org, home.treasury.gov, unctad.org and
    others, and SEC requires a contact address by policy.
  * Streamed to disk in chunks and never held in memory.
  * A pre-flight size probe against a disk ceiling, so a surprise 40 GB file
    cannot fill the runner.
  * Conditional GET (If-None-Match / If-Modified-Since) so a weekly re-run
    transfers only what actually changed.
  * HTML sniffing: a 200 response that is actually a login or error page is a
    failure, not a dataset. The previous engine stored those as data.
  * Retries with backoff on 429/5xx and on connection resets only. A 403 or 404
    is reported immediately with a diagnosis instead of being retried four times.
"""
from __future__ import annotations

import hashlib
import os
import random
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

from .config import Settings

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504, 522, 524}
HTML_SNIFF_BYTES = 2048
HTML_MARKERS = (b"<!doctype html", b"<html", b"<head>", b"<HTML")


class FetchError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, diagnosis: str = ""):
        super().__init__(message)
        self.status = status
        self.diagnosis = diagnosis


@dataclass
class FetchResult:
    path: Path | None
    bytes: int
    sha256: str | None
    etag: str | None
    last_modified: str | None
    status: int
    unchanged: bool = False


def make_session(settings: Settings, extra_headers: dict[str, str] | None = None) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            # Real-browser Accept/Accept-Language matter: several statistical
            # agencies gate on them in addition to User-Agent.
            "User-Agent": settings.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )
    if extra_headers:
        s.headers.update(extra_headers)
    adapter = HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=0)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def diagnose(status: int, url: str) -> str:
    """Turn an HTTP status into an actionable note. The previous engine logged
    bare '403 Client Error' thirteen times and left the cause unidentified."""
    host = url.split("/")[2] if "://" in url else url
    if status == 403:
        return (
            f"403 from {host}: the host is refusing the client, not the request. "
            "Usually User-Agent/bot filtering or a geo block. Try a browser-like "
            "UA, add a Referer header, or use the host's official API instead."
        )
    if status == 404:
        return f"404 from {host}: the URL is stale. The dataset almost certainly moved; re-derive it from the host's current catalogue."
    if status == 401:
        return f"401 from {host}: credentials required. Check the source's requires_secret entry."
    if status == 429:
        return f"429 from {host}: rate limited. Lower rate_limit_per_sec for this source."
    if 500 <= status < 600:
        return f"{status} from {host}: server-side fault, transient. Safe to retry on the next run."
    return f"HTTP {status} from {host}."


def free_bytes(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 1 << 62


def probe(session: requests.Session, url: str, timeout: int) -> tuple[int | None, dict[str, str]]:
    """HEAD probe. Many hosts refuse HEAD; fall back to a 1-byte ranged GET,
    which is far cheaper than downloading to find out the size."""
    try:
        r = session.head(url, timeout=timeout, allow_redirects=True)
        if r.status_code < 400:
            return r.status_code, dict(r.headers)
    except requests.RequestException:
        pass
    try:
        r = session.get(url, timeout=timeout, stream=True, headers={"Range": "bytes=0-0"})
        headers = dict(r.headers)
        r.close()
        return r.status_code, headers
    except requests.RequestException:
        return None, {}


def _expected_size(headers: dict[str, str]) -> int | None:
    rng = headers.get("Content-Range") or headers.get("content-range")
    if rng and "/" in rng:
        tail = rng.rsplit("/", 1)[-1].strip()
        if tail.isdigit():
            return int(tail)
    cl = headers.get("Content-Length") or headers.get("content-length")
    if cl and cl.isdigit():
        return int(cl)
    return None


def looks_like_html(head: bytes) -> bool:
    lowered = head[:HTML_SNIFF_BYTES].lstrip().lower()
    return any(lowered.startswith(m.lower()) for m in HTML_MARKERS)


def fetch(
    session: requests.Session,
    url: str,
    dest: Path,
    settings: Settings,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
    max_bytes: int | None = None,
    expect_html: bool = False,
) -> FetchResult:
    """Download url to dest, streaming, with conditional GET and a size ceiling."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    ceiling = max_bytes or settings.max_file_bytes

    cond: dict[str, str] = {}
    if etag:
        cond["If-None-Match"] = etag
    if last_modified:
        cond["If-Modified-Since"] = last_modified

    last_exc: Exception | None = None
    for attempt in range(settings.max_retries + 1):
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with session.get(
                url, timeout=settings.http_timeout, stream=True, headers=cond, allow_redirects=True
            ) as r:
                if r.status_code == 304:
                    return FetchResult(None, 0, None, etag, last_modified, 304, unchanged=True)

                if r.status_code in RETRYABLE_STATUS:
                    raise FetchError(
                        f"HTTP {r.status_code}", status=r.status_code, diagnosis=diagnose(r.status_code, url)
                    )
                if r.status_code >= 400:
                    # Non-retryable: report at once with a diagnosis.
                    raise FetchError(
                        f"HTTP {r.status_code}",
                        status=r.status_code,
                        diagnosis=diagnose(r.status_code, url),
                    ) from None

                declared = _expected_size(dict(r.headers))
                if declared is not None and declared > ceiling:
                    raise FetchError(
                        f"declared size {declared:,} B exceeds ceiling {ceiling:,} B",
                        status=r.status_code,
                        diagnosis="Raise max_bytes for this dataset or move it to a higher tier.",
                    )

                room = free_bytes(dest.parent) - (256 * 1024**2)
                if declared is not None and declared > room:
                    raise FetchError(
                        f"declared size {declared:,} B exceeds free disk {room:,} B",
                        diagnosis="Increase runner disk or lower concurrency.",
                    )

                digest = hashlib.sha256()
                written = 0
                head = b""
                with tmp.open("wb") as fh:
                    for chunk in r.iter_content(chunk_size=settings.chunk_bytes):
                        if not chunk:
                            continue
                        if len(head) < HTML_SNIFF_BYTES:
                            head += chunk[: HTML_SNIFF_BYTES - len(head)]
                        written += len(chunk)
                        if written > ceiling:
                            raise FetchError(
                                f"stream exceeded ceiling {ceiling:,} B mid-transfer",
                                diagnosis="Server sent no Content-Length and the file is larger than allowed.",
                            )
                        digest.update(chunk)
                        fh.write(chunk)

                if written == 0:
                    raise FetchError("empty response body", status=r.status_code,
                                     diagnosis="Host returned 200 with no content; likely an API misuse.")

                if not expect_html and looks_like_html(head):
                    raise FetchError(
                        "response is an HTML page, not a dataset",
                        status=r.status_code,
                        diagnosis=(
                            "The host answered 200 with a web page — typically a consent wall, "
                            "a search form, or a JavaScript app shell. This URL is not a direct "
                            "download; find the host's real file or API endpoint."
                        ),
                    )

                tmp.replace(dest)
                return FetchResult(
                    path=dest,
                    bytes=written,
                    sha256=digest.hexdigest(),
                    etag=r.headers.get("ETag"),
                    last_modified=r.headers.get("Last-Modified"),
                    status=r.status_code,
                )

        except FetchError as exc:
            last_exc = exc
            if exc.status in RETRYABLE_STATUS and attempt < settings.max_retries:
                time.sleep(min(60, (2**attempt) + random.random()))
                continue
            break
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < settings.max_retries:
                time.sleep(min(60, (2**attempt) + random.random()))
                continue
            break
        finally:
            if tmp.exists():
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    if isinstance(last_exc, FetchError):
        raise last_exc
    raise FetchError(
        f"{type(last_exc).__name__}: {last_exc}",
        diagnosis="Network or DNS failure. If it persists the host may have been retired.",
    )
