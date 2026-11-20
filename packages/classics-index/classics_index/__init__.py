"""Chapter indexes (卷 / 篇 / 回) for scanned Chinese books, from OCR of the
running header. Pure functions plus a small CLI; no storage, no OCR engine."""

from . import core, hui  # noqa: F401

# Keep in step with pyproject.toml; tests/test_version.py enforces it.
__version__ = "0.1.4"
