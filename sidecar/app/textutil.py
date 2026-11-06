"""Text normalisation, tokenisation and chunking shared by the catalog readers.

The v1 tokeniser is kept exactly as it was: the 167k-chunk index was built with
it, and changing it would silently change recall. v2 adds a tokeniser that also
recognises polytonic Greek and accented Latin, because public corpora are clean
text and there is no BGE vector to fall back on.
"""
import re
import unicodedata

CJK = re.compile(r"[\u3400-\u9fff]+")
# v1: the index stores two-or-more lowercase ASCII letters for Latin/Greek.
WORD = re.compile(r"[a-z]{2,}")
# v2: letters from Latin (incl. accents), Greek and Greek Extended.
WORD_V2 = re.compile(
    r"[A-Za-z\u00c0-\u024f\u0370-\u03ff\u1f00-\u1fff]{2,}"
)

_CONTROL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\ufeff]")
_SPACES = re.compile(r"[ \t\u00a0\u3000]+")
_BLANKS = re.compile(r"\n[ \t]*\n[\s]*")


def tokens(s: str):
    """v1 tokenisation: Chinese bigrams plus ASCII words."""
    out = []
    for run in CJK.findall(s or ""):
        if len(run) == 1:
            out.append(run)
        else:
            out.extend(run[i:i + 2] for i in range(len(run) - 1))
    out.extend(WORD.findall((s or "").lower()))
    return list(dict.fromkeys(out))


def fold_diacritics(s: str) -> str:
    """Strip combining marks so polytonic Greek and accented Latin retrieve.

    ``θεὰ`` and ``θεά`` are the same word for retrieval but different strings;
    the stored quotation keeps its accents, only the index/query tokens fold.
    Final sigma is folded too: ``θεός`` and ``θεὸς`` must collide.
    """
    out = "".join(ch for ch in unicodedata.normalize("NFD", s or "")
                  if not unicodedata.combining(ch))
    return out.replace("\u03c2", "\u03c3")


def tokens_v2(s: str):
    """v2 tokenisation: Chinese bigrams plus folded Latin/Greek words."""
    out = []
    for run in CJK.findall(s or ""):
        if len(run) == 1:
            out.append(run)
        else:
            out.extend(run[i:i + 2] for i in range(len(run) - 1))
    out.extend(WORD_V2.findall(fold_diacritics(s).lower()))
    # Deduplicate without losing order: repeated terms add no signal to BM25.
    return list(dict.fromkeys(out))


def clean_text(s: str) -> str:
    """Make rendered/OCR text quotable: kill control chars, collapse blanks."""
    s = unicodedata.normalize("NFC", s or "")
    s = _ZERO_WIDTH.sub("", s)
    s = _CONTROL.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _SPACES.sub(" ", s)
    s = _BLANKS.sub("\n\n", s)
    return s.strip()


def chunk_paragraphs(text: str, max_chars: int = 1200):
    """Split a section into citation-sized chunks, paragraph first.

    Returns ``(chunk, char_start, char_end)`` triples whose offsets point into
    the cleaned section text, so a caller can cite a character range.
    """
    text = clean_text(text)
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    pieces = []
    for para in paragraphs:
        if len(para) <= max_chars:
            pieces.append(para)
            continue
        # Long paragraph: break on sentence enders, then hard-split what is left.
        buf = ""
        for sentence in re.split(r"(?<=[。！？；.!?;])\s*", para):
            if not sentence:
                continue
            if len(buf) + len(sentence) <= max_chars:
                buf += sentence
                continue
            if buf:
                pieces.append(buf)
            while len(sentence) > max_chars:
                pieces.append(sentence[:max_chars])
                sentence = sentence[max_chars:]
            buf = sentence
        if buf:
            pieces.append(buf)

    out = []
    cursor = 0
    for piece in pieces:
        start = text.find(piece, cursor)
        if start < 0:                      # defensive: text changed under us
            start = cursor
        end = start + len(piece)
        out.append((piece, start, end))
        cursor = end
    return out
