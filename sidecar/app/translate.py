"""Query translation for v2 public corpora.

Chinese questions about Greek/Latin texts rarely share tokens with the source.
This module expands a query into search variants:

* a curated offline glossary (default, deterministic, no key);
* optionally an OpenAI-compatible LLM (DeepSeek by default) when a key exists.

The output is only used for retrieval. It never becomes an answer and is not
shown to the student as evidence.
"""
import json
import os
import re
import threading
import urllib.error
import urllib.request

from . import config

DEFAULT_TARGETS = ("zh-classical", "greek", "latin", "en")
ALL_TARGETS = set(DEFAULT_TARGETS)

# Words that carry no retrieval signal. Removing them before measuring OOV is
# what keeps "阿喀琉斯的愤怒" (all terms known) from looking unknown.
_FUNCTION_PHRASES = sorted([
    "为什么", "為什麼", "为何", "為何", "怎么样", "怎麼樣", "什么", "什麼",
    "是谁", "是誰", "如何", "多少", "哪里", "哪裡", "哪个", "哪個",
    "以及", "但是", "因为", "因為", "所以", "可以", "一个", "一個",
    "这个", "這個", "那个", "那個", "他们", "他們", "我们", "我們",
    "你们", "你們", "自己", "之间", "之間", "之后", "之後", "之前",
    "以后", "以後", "以前", "之子", "之女", "之神", "之王",
], key=len, reverse=True)
_FUNCTION_CHARS = set(
    "的了之与與和及其而所於于为為是在有无無不也者曰何谁誰哪吗嗎呢着著"
    "被把将將从從到对對中上下这這那个個年时時后後前又亦皆得能可会會要就都只更最多大少"
    "一二三四五六七八九十百千万萬"
)
_ASCII_WORD = re.compile(r"[A-Za-z\u0370-\u03ff\u1f00-\u1fff]{3,}")
_CJK_RUN = re.compile(r"[\u3400-\u9fff]{2,}")

# Chinese-history questions target the zh-classical documents directly; an
# LLM that is asked for Greek/Latin/English keywords cannot help them and its
# variants only add noise. This is a domain gate, not a linguistic one.
ZH_HISTORY_MARKERS = (
    "史記", "史记", "本紀", "本纪", "世家", "列傳", "列传",
    "黃帝", "黄帝", "軒轅", "轩辕", "堯", "尧", "舜", "禹",
    "紂王", "纣王", "妲己", "比干", "箕子", "微子", "成湯", "成汤",
    "盤庚", "盘庚", "伊尹", "太甲", "武丁", "傅說", "傅说",
    "周文王", "周武王", "周成王", "周康王", "周昭王", "周穆王",
    "周厲王", "周厉王", "周宣王", "周幽王", "周平王", "周桓王",
    "齊桓公", "齐桓公", "楚莊王", "楚庄王", "秦穆公", "秦繆公",
    "秦孝公", "商鞅", "秦惠文王", "秦昭襄王", "秦始皇", "秦二世",
    "趙高", "赵高", "三家分晉", "三家分晋", "犬戎", "褒姒",
    "后稷", "太伯", "季歷", "季历", "召公", "管叔", "蔡叔",
    "姜原", "公劉", "公刘", "伯夷", "叔齊", "叔齐", "百里傒",
)

_GLOSSARY = None
_GLOSSARY_LOCK = threading.Lock()
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 256


def _glossary():
    global _GLOSSARY
    if _GLOSSARY is not None:
        return _GLOSSARY
    with _GLOSSARY_LOCK:
        if _GLOSSARY is not None:
            return _GLOSSARY
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "glossary.json")
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            _GLOSSARY = data if isinstance(data, list) else []
        except (OSError, ValueError):
            _GLOSSARY = []
        return _GLOSSARY


def clear_cache():
    with _CACHE_LOCK:
        _CACHE.clear()


def corpus_languages():
    """Languages present in the configured catalogue (v1 chunks or v2 docs)."""
    from . import schema
    try:
        con = schema.connect()
        try:
            ver = config.schema_version()
            if ver == "v2":
                rows = con.execute(
                    "SELECT DISTINCT lang FROM documents WHERE lang IS NOT NULL"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT DISTINCT lang FROM chunks WHERE visibility='tutor'"
                ).fetchall()
        finally:
            con.close()
        return {str(r[0]) for r in rows if r[0]}
    except Exception:
        return set()


def _key_spans(query):
    spans = []
    for entry in _glossary():
        for key in entry.get("keys") or []:
            key = str(key)
            if not key:
                continue
            if key.isascii():
                pattern = r"(?<![A-Za-z])" + re.escape(key) + r"(?![A-Za-z])"
                for match in re.finditer(pattern, query, re.IGNORECASE):
                    spans.append(match.span())
            else:
                start = query.find(key)
                while start >= 0:
                    spans.append((start, start + len(key)))
                    start = query.find(key, start + 1)
    return spans


def oov_terms(query):
    """Content fragments the glossary does not cover.

    Used to decide whether an ``auto`` translation should spend an LLM call:
    known terms stay offline, unknown names/epithets go to the LLM.
    """
    query = (query or "").strip()
    if not query:
        return []
    chars = list(query)
    for start, end in _key_spans(query):
        for i in range(start, end):
            chars[i] = " "
    residual = re.sub(r"[^\w\u3400-\u9fff]+", " ", "".join(chars))
    for phrase in _FUNCTION_PHRASES:
        residual = residual.replace(phrase, " ")
    for char in _FUNCTION_CHARS:
        residual = residual.replace(char, " ")
    out = [run for run in _CJK_RUN.findall(residual) if run.strip()]
    for word in _ASCII_WORD.findall(residual):
        if word.lower() not in {p.lower() for p in _FUNCTION_PHRASES}:
            out.append(word)
    return out


def needs_llm(query):
    if any(marker in (query or "") for marker in ZH_HISTORY_MARKERS):
        return False
    return bool(oov_terms(query))


def _ascii_match(key, query):
    if not key.isascii():
        return key in query
    pattern = r"(?<![A-Za-z])" + re.escape(key) + r"(?![A-Za-z])"
    return re.search(pattern, query, re.IGNORECASE) is not None


def glossary_expand(query, targets):
    terms = {t: [] for t in targets}
    for entry in _glossary():
        keys = entry.get("keys") or []
        if not any(_ascii_match(str(k), query) for k in keys):
            continue
        for target in targets:
            for value in entry.get(target) or []:
                if value and value not in terms[target]:
                    terms[target].append(str(value))
    variants = []
    for target in targets:
        text = " ".join(terms[target]).strip()
        if text and text.lower() != query.strip().lower():
            variants.append({"lang": target, "text": text,
                             "source": "glossary", "terms": terms[target]})
    return variants


def _key():
    key = (config.LLM_KEY or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
    if key:
        return key
    try:
        with open(r"D:\Guo-Code\deepseek API key.txt", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _parse_variants(text, targets):
    i, j = text.find("["), text.rfind("]")
    if i < 0 or j <= i:
        return []
    try:
        data = json.loads(text[i:j + 1])
    except ValueError:
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        lang = str(item.get("lang") or "").strip().lower()
        body = str(item.get("text") or "").strip()
        if lang in targets and body and len(body) <= 200:
            out.append({"lang": lang, "text": body, "source": "llm"})
    return out


def _http_json(url, data, headers, timeout):
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def llm_expand(query, targets, opener=None, style=None):
    key = _key()
    if not key:
        return []
    if style == "v1":
        prompt = (
            "Translate this Chinese/English question into short search keywords for "
            "a Greek/Latin corpus that mixes Homer, Attic prose (Plato, Thucydides, "
            "Herodotus), tragedy (Sophocles, Euripides) and Virgil. Return JSON only: "
            'an array of objects {"lang":"greek|la|en","text":"keywords"}. Use the '
            "original script (Greek for greek, Latin for latin, English for en). Give "
            "2-5 content words per language. For Greek prefer standard Attic forms for "
            "prose and include the nominative singular plus one inflected form; for "
            "Homer use epic forms. For proper names give the standard Greek/Latin "
            "spelling in the original script. Do not answer the question. Question: "
            + query
        )
    else:
        prompt = (
            "Translate this Chinese/English question into short search keywords for "
            "Homeric/Virgilian classical texts. Return JSON only: an array of objects "
            '{"lang":"greek|la|en","text":"keywords"}. Use the original script '
            "(Greek for greek, Latin for latin, English for en). Give 2-5 keywords "
            "per language and include the forms that actually occur in epic: "
            "Greek inflections (-οιο/-ου/-ην/-α), Latin inflections (-is/-i/-em), "
            "and common epithets (e.g. Saturnia for Juno, ἀργυρότοξος for Apollo). "
            "For proper names give the standard Greek/Latin spelling, not a similar "
            "but different name. Do not answer the question. Question: " + query
        )
    payload = json.dumps({
        "model": config.LLM_MODEL,
        "temperature": 0,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    url = config.LLM_BASE.rstrip("/") + "/chat/completions"
    headers = {"Authorization": "Bearer " + key,
               "Content-Type": "application/json"}
    try:
        body = (opener or _http_json)(url, payload, headers,
                                      config.TRANSLATE_TIMEOUT)
        content = body["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, ValueError, IndexError,
            TypeError, TimeoutError, OSError):
        return []
    alias = {"la": "latin", "grc": "greek", "gr": "greek", "english": "en"}
    out = []
    for item in _parse_variants(content, set(targets) | set(alias)):
        item["lang"] = alias.get(item["lang"], item["lang"])
        if item["lang"] in targets:
            out.append(item)
    return out


def expand(query, targets=None, style=None):
    """Return translated search variants for ``query``.

    ``targets`` is normally the set of languages actually present in the
    catalogue; passing None falls back to all supported targets.
    """
    mode = str(config.TRANSLATE or "auto").lower()
    if mode == "off" or not (query or "").strip():
        return []
    raw = list(targets or corpus_languages() or DEFAULT_TARGETS)
    order = {t: i for i, t in enumerate(DEFAULT_TARGETS)}
    targets = sorted({t for t in raw if t in ALL_TARGETS},
                     key=lambda t: order.get(t, len(order)))
    if not targets:
        return []
    cache_key = (query, tuple(sorted(targets)), mode, style)
    with _CACHE_LOCK:
        if cache_key in _CACHE:
            return list(_CACHE[cache_key])

    variants = []
    if mode in ("auto", "glossary", "llm"):
        variants.extend(glossary_expand(query, targets))
    if mode in ("auto", "llm"):
        # auto is OOV-gated: known terms are already covered by the glossary,
        # so an LLM call there only adds latency and noise.
        if mode == "llm" or needs_llm(query):
            if style is None:
                variants.extend(llm_expand(query, targets))
            else:
                variants.extend(llm_expand(query, targets, style=style))

    seen = set()
    out = []
    for v in variants:
        token = (v["lang"], v["text"].casefold())
        if token in seen:
            continue
        seen.add(token)
        out.append(v)
    with _CACHE_LOCK:
        _CACHE[cache_key] = out
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
    return list(out)
