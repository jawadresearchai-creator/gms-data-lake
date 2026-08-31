"""Sentinel adapters for sources handled outside the generic URL ingestion engine.

These adapters intentionally enumerate no downloadable URL datasets. They exist so
registry validation remains strict while dedicated workflows can own sources whose
transport model is not HTTP-file based (for example BigQuery) or whose use is
credential/rate-limited validation only (for example EPO OPS).
"""
from __future__ import annotations

import logging

from . import register

log = logging.getLogger(__name__)


@register("bigquery_public")
def bigquery_public(source, session, settings):
    log.info("%s is handled by its dedicated BigQuery workflow", source.id)
    return []


@register("external_validation")
def external_validation(source, session, settings):
    log.info("%s is a validation/enrichment source and has no generic bulk enumeration", source.id)
    return []
