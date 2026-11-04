"""Page-image-only policy.

Some languages cannot be served as text. Loeb / Steadman Greek was measured at
70.9-94.0% CER by the three local OCR engines (P1-3c), and the Steadman text
layer interleaves English commentary with Greek lemmas, so quoting it as "the
source" would manufacture citations the page image does not support.

The rule is enforced here, in the serving path, not in the prompt: a hit whose
language is listed in SOCRATIC_IMAGE_ONLY_LANGS comes back as a citation plus a
page image, with the text field emptied. The catalog keeps the stored text for
retrieval (FTS / BGE / rerank); it just never reaches a caller.
"""
import os

# "greek" is how the catalog spells it; "grc" is accepted so callers can use
# the ISO 639-3 code without changing the stored value.
DEFAULT_LANGS = ("greek", "grc")


def _configured():
    raw = os.environ.get("SOCRATIC_IMAGE_ONLY_LANGS", "")
    if raw.strip() == "":
        return set(DEFAULT_LANGS)
    return {s.strip() for s in raw.split(",") if s.strip()}


LANGS = _configured()


def reload():
    """Re-read the env var (tests flip it without restarting the process)."""
    global LANGS
    LANGS = _configured()
    return LANGS


def image_only(lang):
    return str(lang or "").strip().lower() in LANGS


def redact(result):
    """Empty the text of an image-only hit; annotate why.

    Returns a new dict so cached payloads keep their raw text for reranking.
    """
    if not result or not image_only(result.get("lang")):
        return result
    out = dict(result)
    out["text"] = ""
    out["image_only"] = True
    out["text_omitted"] = "page-image-only: no reliable text layer or OCR"
    cit = dict(out.get("citation") or {})
    cit["image_only"] = True
    out["citation"] = cit
    return out


def health():
    return {"image_only_langs": sorted(LANGS)}
