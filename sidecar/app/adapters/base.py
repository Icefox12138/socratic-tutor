"""Shared shapes for public-corpus adapters.

An adapter turns one external reference (a Wikisource title, a CTS URN, …) into
a :class:`Document` whose sections already carry a typed locator. Nothing in
this package writes to the database; ingestion is a separate step so fetching
and storing can be retried independently.
"""
from dataclasses import dataclass, field


class FetchError(RuntimeError):
    """The source refused, or returned something the adapter cannot parse."""


@dataclass
class Section:
    title: str
    text: str
    locator: dict
    ordinal: int = 0
    quality: str | None = None


@dataclass
class Document:
    document_id: str
    source_id: str
    title: str
    sections: list[Section]
    lang: str = "zh"
    author: str | None = None
    edition: str | None = None
    script: str | None = None
    license: str = "unknown"
    provenance: str = ""
    canonical_url: str = ""
    metadata: dict = field(default_factory=dict)
    source_version: str = ""


@dataclass
class SourceSpec:
    source_id: str
    adapter: str
    base_url: str
    license: str = "unknown"
    redistribution: str = "unknown"
    rate_limit: float | None = 1.0
    auth_env: str | None = None
    config: dict = field(default_factory=dict)
