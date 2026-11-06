"""Adapter registry.

Adapters are constructed from a source id plus keyword arguments; the registry
keeps the CLI and the ingest tests from hard-coding classes. Add a new corpus by
implementing ``fetch()`` and registering it here — the schema does not change.
"""
from .base import Document, FetchError, Section, SourceSpec
from .cts import CtsAdapter, passage, work_urn
from .wikisource import MediaWikiClient, WikisourceAdapter, extract_sections

__all__ = [
    "Document", "FetchError", "Section", "SourceSpec",
    "CtsAdapter", "MediaWikiClient", "WikisourceAdapter",
    "extract_sections", "passage", "work_urn",
    "get", "register", "names",
]

_REGISTRY = {
    "wikisource": WikisourceAdapter,
    "mediawiki": WikisourceAdapter,
    "perseus": CtsAdapter,
    "cts": CtsAdapter,
}


def register(name, cls):
    _REGISTRY[name] = cls


def names():
    return sorted(_REGISTRY)


def get(name, **kwargs):
    try:
        cls = _REGISTRY[name.lower()]
    except KeyError:
        raise KeyError("unknown adapter %r (known: %s)" % (name, ", ".join(names())))
    return cls(**kwargs)
