"""Adapters enumerate datasets at run time from official machine-readable
catalogues â€” SDMX dataflow lists, JSON APIs, S3 bucket listings.

They exist because the previous engine tried to discover files by crawling HTML
landing pages with BeautifulSoup. Most statistical portals (data.imf.org,
sam.gov, comtradeplus.un.org, datahub.itu.int, earthdata.nasa.gov, faostat)
are JavaScript single-page applications: the served HTML contains no data links
at all, so the crawler found nothing and the sources silently produced zero
jobs. Every adapter here talks to a documented endpoint instead.

An adapter is a callable:

    adapter(source, session, settings) -> list[Dataset]

It must never raise for a single bad entry; it returns what it could enumerate.
"""
from __future__ import annotations

from typing import Callable

from ..registry import Dataset, Source

Adapter = Callable[..., list[Dataset]]

_REGISTRY: dict[str, Adapter] = {}


def register(name: str) -> Callable[[Adapter], Adapter]:
    def deco(fn: Adapter) -> Adapter:
        _REGISTRY[name] = fn
        return fn
    return deco


def get(name: str) -> Adapter:
    if name not in _REGISTRY:
        raise KeyError(f"unknown adapter {name!r}; available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def available() -> list[str]:
    return sorted(_REGISTRY)


# Importing the modules populates the registry.
from . import sdmx, catalogues, buckets, external  # noqa: E402,F401

__all__ = ["Adapter", "Dataset", "Source", "register", "get", "available"]
