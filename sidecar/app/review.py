"""Session review v1: claims -> verdict -> error class -> attribution -> practice.

What it is: a deterministic pass over one finished session. It takes the
student's own statements, decides which of them are checkable claims, compares
each claim with the session's recorded expected answer, and turns a mismatch
into a labelled error plus a re-practice card.

What it is not: an LLM judge. Every verdict here is reproducible from the
session snapshot; when the snapshot cannot settle a claim the verdict is
"undetermined" and the claim is never counted as an error.
"""
import hashlib
import json
import re
import sqlite3
import time
import unicodedata

from . import config, learner

# The eight error classes from DESIGN §10.4. "concept" is the residual class:
# a mismatch that none of the structural tests can name.
ERRORS = ("sign", "arithmetic", "formula", "condition",
          "unit", "misread", "incomplete", "concept")
ATTRIBUTIONS = ("student", "question", "material", "curriculum")

QUESTION_MARK = re.compile(r"[?？]|什么|为什么|怎么|如何|是否|吗$|what|why|how|whether", re.I)
UNIT = re.compile(r"(?<![A-Za-z])(cm|mm|km|m|kg|g|s|ms|h|min|mol|L|mL|N|J|W|V|A|Pa|Hz)(?![A-Za-z])")
SETISH = re.compile(r"^\s*[\[\(\{].*[\]\)\}]\s*$")


def _norm(text):
    t = unicodedata.normalize("NFKC", str(text or ""))
    t = t.replace("−", "-").replace("×", "*").replace("÷", "/").replace("^", "**")
    t = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", t)  # \frac{a}{b} leftovers
    t = re.sub(r"\s+", " ", t).strip()
    return t.rstrip(".。;；")


# A claim must at least look like maths before sympy is allowed to see it:
# sympy happily turns "我认为是切线斜率" into a Symbol, which would make prose
# gradeable - the exact failure mode this review must not have.
MATHSY = re.compile(r"[0-9A-Za-z+\-*/^().=]")
MATH_RUN = re.compile(r"[0-9A-Za-z+\-*/^().=]+")
ASCII_SYMBOL = re.compile(r"[A-Za-z][A-Za-z0-9_]*$")


def _sympy():
    import sympy
    return sympy


def _expr(text):
    """Parse '3x^2' / 'x**3/3' into a sympy expression, or raise ValueError."""
    from sympy.parsing.sympy_parser import (implicit_multiplication_application,
                                            parse_expr, standard_transformations)
    if not MATHSY.search(text):
        raise ValueError("not maths")
    expr = parse_expr(text, transformations=standard_transformations
                      + (implicit_multiplication_application,), evaluate=True)
    for sym in expr.free_symbols:
        if not ASCII_SYMBOL.match(str(sym)):
            raise ValueError("non-ascii symbol")
    return expr


def _parse_value(text):
    """Parse an answer into a comparable value.

    Returns ("set", frozenset) for solution lists, ("expr", sympy expr) for a
    scalar expression, or (None, None) when the text is not maths at all.
    """
    t = _norm(text)
    if not t:
        return None, None
    sympy = _sympy()
    if SETISH.match(t):
        inner = t.strip("[](){} ")
        if not inner:
            return "set", frozenset()
        parts = [p.strip() for p in re.split(r"[,;，；]", inner) if p.strip()]
        try:
            vals = frozenset(_expr(p) for p in parts)
            return ("set", vals) if len(vals) == len(parts) else (None, None)
        except Exception:
            return None, None
    try:
        expr = _expr(t)
        if expr.free_symbols or expr.is_number:
            return "expr", expr
    except Exception:
        pass
    # A claim often carries prose around the maths ("那应该是 3x^2"); parse the
    # longest maths-looking run instead of failing the whole sentence. A bare
    # letter is not a run: it must carry a digit or an operator.
    for cand in sorted(set(MATH_RUN.findall(t)), key=len, reverse=True):
        if not re.search(r"[0-9+\-*/^().]", cand):
            continue
        try:
            expr = _expr(cand)
        except Exception:
            continue
        if expr.free_symbols or expr.is_number:
            return "expr", expr
    return None, None


def _equal(a, b):
    sympy = _sympy()
    try:
        if a[0] == "set" and b[0] == "set":
            return set(a[1]) == set(b[1])
        if a[0] == "expr" and b[0] == "expr":
            return sympy.simplify(a[1] - b[1]) == 0
    except Exception:
        return False
    return False


def judge(claim, expected):
    """correct / partial / incorrect / undetermined + a short evidence string."""
    if not str(expected or "").strip():
        return "undetermined", "no expected answer recorded"
    ck, ek = _parse_value(claim), _parse_value(expected)
    if ck[0] and ek[0]:
        if _equal(ck, ek):
            return "correct", "matches the recorded answer"
        return "incorrect", "differs from the recorded answer"
    # Non-maths answers: only exact agreement is evidence.
    a, b = _norm(claim).lower(), _norm(expected).lower()
    if a and a == b:
        return "correct", "text matches"
    return "undetermined", "not comparable as maths and not an exact text match"


def _terms(expr):
    """Additive terms of an expression: {x**2, 2*x, 1} for x**2 + 2*x + 1."""
    try:
        return set(expr.args) if expr.is_Add else {expr}
    except Exception:
        return {expr}


def _lead_degree(expr):
    sympy = _sympy()
    try:
        if not expr.free_symbols:
            return 0
        return max(sympy.degree(expr, s) for s in expr.free_symbols if sympy.degree(expr, s) >= 0)
    except Exception:
        return None


def classify(claim, expected):
    """Name the error class of an incorrect claim; None when no evidence."""
    ck, ek = _parse_value(claim), _parse_value(expected)
    text = _norm(claim)
    if (ck[0] is None and UNIT.search(text)
            and not UNIT.search(_norm(expected))):
        return "unit"
    if ck[0] is None or ek[0] is None:
        if _norm(expected) and text and text in _norm(expected) and len(text) < len(_norm(expected)):
            return "incomplete"
        return "concept"
    if ck[0] != ek[0]:
        return "formula" if ck[0] == "expr" else "incomplete"
    c, e = ck[1], ek[1]
    sympy = _sympy()
    if ck[0] == "set":
        c, e = set(c), set(e)
        if not c:
            return "incomplete"
        if c < e:
            return "condition"          # a case was dropped
        if e < c:
            return "formula"            # an extra, unsupported solution
        return "concept"
    try:
        if sympy.simplify(c + e) == 0:
            return "sign"
    except Exception:
        pass
    # Terms first: a dropped term is not "a different variable".
    ct, et = _terms(c), _terms(e)
    if ct < et:
        return "incomplete"
    if ct & et:
        pass
    try:
        if c.free_symbols - e.free_symbols:
            return "misread"            # answered a different quantity
    except Exception:
        pass
    if c.is_number and e.is_number:
        try:
            ratio = abs(float(c / e))
            if ratio >= 1000 or ratio <= 0.001:
                return "unit"           # magnitude slip, likely unit conversion
            return "arithmetic"
        except Exception:
            return "concept"
    try:
        diff = sympy.simplify(c - e)
        if sympy.simplify(c / e).is_number and not diff.is_number:
            return "arithmetic"         # same structure, different coefficient
        if diff.is_number:
            return "arithmetic"
        dc, de = _lead_degree(c), _lead_degree(e)
        if dc is not None and de is not None and dc != de:
            return "formula"
    except Exception:
        return "concept"
    return "formula"


def attribute(state, claim, verdict, expected):
    """student / question / material / curriculum, most actionable first."""
    question = str((state or {}).get("question") or "").strip()
    if not str(expected or "").strip():
        return "question"               # nothing to grade against
    if len(question) < 8 and verdict == "incorrect":
        return "question"               # too short to be unambiguous
    if str((state or {}).get("lang") or "") in ("greek", "grc"):
        return "material"               # K5: text layer unusable by policy
    try:
        m = learner.get(str((state or {}).get("concept") or "unknown"))
        if m["p"] < 0.35 and int((state or {}).get("wrong_streak") or 0) >= 2:
            return "curriculum"         # prerequisite never established
    except Exception:
        pass
    return "student"


def extract_claims(text):
    """Split a student turn into claims; questions and meta talk are skipped."""
    out = []
    raw = str(text or "")
    for sentence in re.split(r"(?<=[。！？!?；;\n])|(?<=\.)\s+", raw):
        s = _norm(sentence)
        if len(s) < 4:
            continue
        if QUESTION_MARK.search(s):
            out.append({"text": s, "claim": False, "reason": "question"})
            continue
        if re.search(r"(意思是|换句话说|也就是|i mean|in other words)", s, re.I):
            out.append({"text": s, "claim": False, "reason": "paraphrase"})
            continue
        out.append({"text": s, "claim": True, "reason": ""})
    return out


def _store(session_id, payload, path=None):
    p = path or config.STATE_DB
    con = sqlite3.connect(p)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS reviews ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, digest TEXT,"
            "n INTEGER, accuracy REAL, report TEXT, created_at REAL)")
        con.execute("INSERT INTO reviews(session_id,digest,n,accuracy,report,created_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (session_id, payload["digest"], payload["summary"]["n_claims"],
                     payload["summary"]["accuracy"], json.dumps(payload, ensure_ascii=False),
                     time.time()))
        con.commit()
    finally:
        con.close()


def review(session_id, state, answers=None, record=True, path=None):
    """Build the review report for one session.

    state    : the frozen state snapshot (question / expected / concept / lang)
    answers  : ["...", ...] student turns; defaults to state["history"] texts
    """
    answers = answers if answers is not None else [
        h.get("text") for h in (state or {}).get("history") or [] if h.get("text")]
    expected = (state or {}).get("expected") or ""
    claims, judged = [], []
    for turn in answers:
        for c in extract_claims(turn):
            if not c["claim"]:
                claims.append({**c, "verdict": "not_a_claim"})
                continue
            verdict, evidence = judge(c["text"], expected)
            error = classify(c["text"], expected) if verdict == "incorrect" else None
            attribution = attribute(state, c["text"], verdict, expected) if verdict in (
                "incorrect", "partial") else None
            claims.append({**c, "verdict": verdict, "evidence": evidence,
                           "error": error, "attribution": attribution})
            judged.append(claims[-1])

    n = len(judged)
    n_und = sum(1 for c in judged if c["verdict"] == "undetermined")
    n_ok = sum(1 for c in judged if c["verdict"] == "correct")
    accuracy = round(n_ok / n, 4) if n else None
    errors = {}
    for c in judged:
        if c["error"]:
            errors[c["error"]] = errors.get(c["error"], 0) + 1
    practice = []
    for c in judged:
        if c["verdict"] in ("incorrect", "partial"):
            practice.append({"kind": "card", "term": str((state or {}).get("concept") or "unknown"),
                             "definition": expected, "error": c["error"],
                             "lang": (state or {}).get("lang") or "zh"})
    payload = {
        "session_id": session_id,
        "concept": (state or {}).get("concept") or "",
        "question": (state or {}).get("question") or "",
        "expected": expected,
        "claims": claims,
        "summary": {"n_claims": n, "correct": n_ok,
                    "incorrect": sum(1 for c in judged if c["verdict"] == "incorrect"),
                    "partial": sum(1 for c in judged if c["verdict"] == "partial"),
                    "undetermined": n_und,
                    "undetermined_rate": round(n_und / n, 4) if n else 0.0,
                    "accuracy": accuracy,
                    "errors": errors},
        "practice": practice,
        "frozen_at": time.time(),
    }
    payload["digest"] = hashlib.sha1(
        json.dumps({"c": claims, "e": expected}, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    if record:
        _store(session_id, payload, path=path)
    return payload
