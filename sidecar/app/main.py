"""Minimal Socratic sidecar: health, search, chunks, pages, compute."""
import os
import threading
from typing import Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import (citations, classifier, config, critic, evaluations, evaluator, learner,
               pages, policy, review, search, state_machine, state_store, toc)
from .compute import ComputeError, compute

app = FastAPI(title="socratic-sidecar", version=config.VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)
_SESSIONS = {}


def _get_session(session_id):
    s = _SESSIONS.get(session_id)
    if s is not None:
        return s
    loaded, _n = state_store.load_state(session_id)
    if loaded is not None:
        _SESSIONS[session_id] = loaded
    return loaded


def require_token(x_sidecar_token: Optional[str] = Header(default=None),
                  authorization: Optional[str] = Header(default=None)):
    """Accept the project header or the community-standard Bearer form.

    X-Sidecar-Token is what the DSH plugin sends; Authorization: Bearer is what
    every other RAG gateway/MCP bridge expects, so both are honoured.
    """
    # Called directly from tests the defaults are Header markers, not strings.
    x_sidecar_token = x_sidecar_token if isinstance(x_sidecar_token, str) else None
    authorization = authorization if isinstance(authorization, str) else None

    if not config.TOKEN:
        if config.REQUIRE_AUTH:
            raise HTTPException(status_code=503, detail="sidecar token is not configured")
        return
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    if config.TOKEN not in (x_sidecar_token, bearer):
        raise HTTPException(status_code=401, detail="invalid sidecar token")


@app.on_event("startup")
def _startup():
    if config.PRELOAD and config.BGE:
        threading.Thread(target=search._load_bge, daemon=True).start()


@app.get("/health")
def health():
    """Liveness plus index status.

    A fresh install has no RAG database yet. That is a normal state on the way
    to a working deployment, not a broken service, so this always answers 200
    and reports the reason in the body instead of failing the transport.
    """
    try:
        info = search.health()
    except Exception as e:
        return {
            "ok": False,
            "reason": "no_index",
            "version": config.VERSION,
            "data": config.DATA,
            "db": config.DB,
            "vectors": config.BGE_VECTORS,
            "ids": config.BGE_IDS,
            "toc": config.toc_db(),
            "bge": "missing: " + config.BGE_VECTORS if config.BGE else "disabled",
            "chunks": 0,
            "detail": str(e)[:200],
            "hint": "按 docs/RAG-DB-SCHEMA.md 建库，或用 SOCRATIC_DB 指向已有的库",
            "cache": search.cache_stats(),
        }
    return {"ok": True, "available": True, "version": config.VERSION, **info,
            "cache": search.cache_stats()}


@app.get("/ui")
def ui():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "index.html")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="ui not built")
    return FileResponse(p, media_type="text/html")


@app.get("/v1/search", dependencies=[Depends(require_token)])
def v1_search(
    q: str = Query(..., min_length=1, max_length=200),
    view: str = Query("student"),
    limit: int = Query(8, ge=1, le=20),
    source: Optional[str] = None,
    lang: Optional[str] = None,
    book: Optional[str] = None,
    chapter: Optional[str] = None,
    session_id: Optional[str] = None,
    turn: Optional[int] = None,
    step: Optional[int] = None,
    call_id: Optional[str] = None,
):
    try:
        return search.search(q, view=view, limit=limit, source=source,
                             lang=lang, book=book, chapter=chapter,
                             toc_source=source or "library",
                             session_id=session_id,
                             turn=turn, step=step, call_id=call_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # no index yet is a precondition, not an internal error
        raise HTTPException(status_code=503,
                            detail={"code": "no_index", "detail": str(e)[:200]})


@app.get("/v1/cache", dependencies=[Depends(require_token)])
def v1_cache():
    return search.cache_stats()


@app.post("/v1/cache/clear", dependencies=[Depends(require_token)])
def v1_cache_clear():
    search.clear_cache()
    return search.cache_stats()


@app.get("/v1/chunks/{chunk_id}", dependencies=[Depends(require_token)])
def v1_chunk(chunk_id: int, view: str = Query("student")):
    if view not in ("student", "tutor"):
        raise HTTPException(status_code=400, detail="view must be student or tutor")
    vis = "tutor"
    con = search._connect()
    try:
        row = con.execute(
            "SELECT id, source, book, lang, page, text FROM chunks "
            "WHERE id = ? AND visibility = ?", (chunk_id, vis)).fetchone()
    finally:
        con.close()
    if not row:
        raise HTTPException(status_code=404, detail="chunk not found")
    image = "/v1/pages?source=%s&book=%s&page=%d" % (
        quote(row["source"]), quote(row["book"]), row["page"])
    return policy.redact({
        "chunk_id": row["id"], "source": row["source"], "book": row["book"],
        "lang": row["lang"], "page": row["page"], "text": row["text"],
        "citation": {"locator": f"{row['book']} p.{row['page']}",
                     "tier": "unknown", "page_image": image},
    })


@app.get("/v1/pages", dependencies=[Depends(require_token)])
def v1_pages(
    source: str = Query(...),
    book: str = Query(...),
    page: int = Query(..., ge=1),
    dpi: int = Query(150, ge=72, le=300),
    bbox: Optional[str] = None,
):
    box = None
    if bbox:
        try:
            box = [float(x) for x in bbox.split(",")]
            if len(box) != 4:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox must be x0,y0,x1,y1")
    try:
        data = pages.render(source, book, page, dpi=dpi, bbox=box)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="book not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(content=data, media_type="image/png")


class ReviewIn(BaseModel):
    session_id: str
    state: Optional[dict] = None
    answers: Optional[list[str]] = None
    record: bool = True


@app.get("/v1/chapter", dependencies=[Depends(require_token)])
def v1_chapter(source: str = Query("library"), book: str = Query(...),
               q: Optional[str] = None, page: Optional[int] = None):
    """One chapter by title/number, or the chapter that contains a page."""
    rows = toc.load(source, book)
    if not rows:
        raise HTTPException(status_code=404, detail="no chapter index for this book")
    if page is not None:
        row = toc.at(rows, page)
        if not row:
            raise HTTPException(status_code=404, detail="page %d is outside the index" % page)
    else:
        row = toc.find(rows, q) if q else rows[0]
        if not row:
            raise HTTPException(status_code=404, detail="chapter not found: %s" % q)
    level = row.get("level") or 1
    same = [r for r in rows if (r.get("level") or 1) == level]
    idx = same.index(row)
    prev = same[idx - 1] if idx > 0 else None
    nxt = same[idx + 1] if idx + 1 < len(same) else None
    return {"source": source, "book": book, "chapter": row,
            "prev": prev, "next": nxt,
            "pages": [{"page": p, "page_image": "/v1/pages?source=%s&book=%s&page=%d&dpi=150"
                       % (quote(source), quote(book), p)}
                      for p in range(row["page_start"], row["page_end"] + 1)]}


@app.get("/v1/books", dependencies=[Depends(require_token)])
def v1_books():
    """Volumes that carry a chapter index (built from OCR of the running header)."""
    return {"books": toc.books()}


@app.get("/v1/toc", dependencies=[Depends(require_token)])
def v1_toc(source: str = Query(...), book: str = Query(...)):
    chapters = toc.load(source, book)
    if not chapters:
        raise HTTPException(status_code=404, detail="no chapter index for this book")
    try:
        total = pages.count(source, book)
    except FileNotFoundError:
        total = None
    return {"source": source, "book": book, "pages": total, "chapters": chapters}


@app.get("/browse")
def browse():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "browse.html")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="browse page not built")
    return FileResponse(p, media_type="text/html")


@app.post("/v1/review", dependencies=[Depends(require_token)])
def v1_review(body: ReviewIn):
    """Freeze one session and review it: claims -> verdict -> error -> practice."""
    st = body.state
    if st is None:
        s = _get_session(body.session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="unknown session")
        st = s.to_dict()
    try:
        return review.review(body.session_id, st, answers=body.answers, record=body.record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ComputeIn(BaseModel):
    expression: str
    operation: str = "simplify"
    variable: str = "x"
    point: str = "0"


class StateInitIn(BaseModel):
    session_id: str
    goal: str = ""
    concept: str = ""
    lang: str = "zh"


class StateStepIn(BaseModel):
    session_id: str
    event: str
    result: Optional[str] = None
    text: Optional[str] = None
    rubric: Optional[str] = None
    expected: Optional[str] = None


class EvaluateIn(BaseModel):
    question: str
    answer: str
    rubric: Optional[str] = None
    expected: Optional[str] = None
    use_llm: bool = True


class CriticIn(BaseModel):
    text: str
    hint_level: int = 0
    has_citation: bool = False


class RewriteIn(BaseModel):
    text: str


class CitationIn(BaseModel):
    text: str
    mode: str = "soften"


class LeakIn(BaseModel):
    text: str
    hint_level: int = 0
    mode: str = "soften"


class CardIn(BaseModel):
    term: str
    definition: str = ""
    lang: str = "zh"


class CardReviewIn(BaseModel):
    rating: str


@app.get("/v1/mastery/{concept}", dependencies=[Depends(require_token)])
def get_mastery(concept: str):
    return learner.get(concept)


@app.get("/v1/mastery", dependencies=[Depends(require_token)])
def list_mastery():
    return {"mastery": learner.list_all()}


@app.post("/v1/cards", dependencies=[Depends(require_token)])
def add_card(body: CardIn):
    try:
        return learner.add_card(body.term, body.definition, body.lang)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/v1/cards/{card_id}/review", dependencies=[Depends(require_token)])
def review_card(card_id: int, body: CardReviewIn):
    try:
        return learner.review_card(card_id, body.rating)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/v1/cards/due", dependencies=[Depends(require_token)])
def cards_due(limit: int = 20):
    return {"cards": learner.due_cards(limit)}


@app.post("/v1/evaluate", dependencies=[Depends(require_token)])
def v1_evaluate(body: EvaluateIn):
    ev = evaluator.evaluate(body.question, body.answer, body.rubric, body.expected, body.use_llm)
    return ev


@app.post("/v1/critic", dependencies=[Depends(require_token)])
def v1_critic(body: CriticIn):
    return critic.check(body.text, body.hint_level, body.has_citation)


@app.post("/v1/critic/rewrite", dependencies=[Depends(require_token)])
def v1_critic_rewrite(body: RewriteIn):
    return critic.rewrite_one_question(body.text)


@app.post("/v1/critic/citation", dependencies=[Depends(require_token)])
def v1_critic_citation(body: CitationIn):
    if body.mode not in ("soften", "mark", "off"):
        raise HTTPException(status_code=400, detail="mode must be soften/mark/off")
    return critic.soften_uncited(body.text, body.mode)


@app.post("/v1/critic/leak", dependencies=[Depends(require_token)])
def v1_critic_leak(body: LeakIn):
    if body.mode not in ("soften", "mark", "off"):
        raise HTTPException(status_code=400, detail="mode must be soften/mark/off")
    return critic.soften_leak(body.text, body.hint_level, body.mode)


@app.get("/v1/evaluations/{session_id}", dependencies=[Depends(require_token)])
def v1_evaluations(session_id: str, limit: int = 50):
    return {"session_id": session_id, "evaluations": evaluations.list_for(session_id, limit)}


@app.get("/v1/citations/{session_id}", dependencies=[Depends(require_token)])
def v1_citations(session_id: str, limit: int = 20, turn: Optional[int] = None):
    return {"session_id": session_id,
            "citations": citations.list_for(session_id, limit, turn=turn)}


class ClassifyIn(BaseModel):
    text: str


@app.post("/v1/classify", dependencies=[Depends(require_token)])
def v1_classify(body: ClassifyIn):
    return classifier.classify(body.text)


@app.post("/v1/state/init", dependencies=[Depends(require_token)])
def state_init(body: StateInitIn):
    s = state_machine.init(body.session_id, goal=body.goal, concept=body.concept, lang=body.lang)
    if body.concept:
        s.mastery = learner.get(body.concept)["p"]
    state_store.create_session(body.session_id, goal=body.goal, concept=body.concept,
                               lang=body.lang, state=s)
    _SESSIONS[body.session_id] = s
    return {"state": s.to_dict(), "summary": state_machine.summary(s),
            "allowed_events": state_machine.allowed(s)}


@app.post("/v1/state/step", dependencies=[Depends(require_token)])
def state_step(body: StateStepIn):
    s = _get_session(body.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not initialized")
    ev = None
    ev_id = None
    m = None
    if body.event == "answer":
        if body.result:
            result = body.result
        else:
            ev = evaluator.evaluate(s.question or s.concept, body.text or "",
                                    rubric=body.rubric or s.rubric,
                                    expected=body.expected or s.expected)
            result = ev["result"]
        if ev is None:
            ev = {"result": result, "confidence": 1.0, "misconceptions": [],
                  "reason": "manual", "source": "manual"}
        ev_id = evaluations.save(s.session_id, s.question or s.concept,
                                 body.text or "", ev)
    else:
        result = body.result
    try:
        out = state_machine.step(s, body.event, result, text=body.text,
                                 rubric=body.rubric, expected=body.expected)
    except state_machine.InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    if body.event == "answer":
        m = learner.record(s.concept or "未设定", result, revealed=s.revealed)
        s.mastery = m["after"]
        out["summary"] = state_machine.summary(s)
        out["mastery"] = m
        out["evaluation"] = ev
        out["evaluation_id"] = ev_id
    state_store.append_event(s.session_id, body.event, {
        "event": body.event, "result": result, "text": body.text,
        "rubric": body.rubric, "expected": body.expected,
        "evaluation": ev, "evaluation_id": ev_id, "mastery": m,
    }, s)
    _SESSIONS[body.session_id] = s
    return out


@app.get("/v1/state/{session_id}", dependencies=[Depends(require_token)])
def state_get(session_id: str):
    s = _get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not initialized")
    return {"state": s.to_dict(), "summary": state_machine.summary(s),
            "allowed_events": state_machine.allowed(s)}


@app.get("/v1/state/{session_id}/events", dependencies=[Depends(require_token)])
def state_events(session_id: str):
    return {"session_id": session_id, "events": state_store.events(session_id)}


@app.post("/v1/state/{session_id}/replay", dependencies=[Depends(require_token)])
def state_replay(session_id: str):
    _SESSIONS.pop(session_id, None)
    loaded, n = state_store.load_state(session_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="session not initialized")
    _SESSIONS[session_id] = loaded
    return {"replayed": True, "events": n, "state": loaded.to_dict(),
            "summary": state_machine.summary(loaded),
            "allowed_events": state_machine.allowed(loaded)}


@app.post("/v1/compute", dependencies=[Depends(require_token)])
def v1_compute(body: ComputeIn):
    try:
        return compute(body.expression, body.operation, body.variable, body.point)
    except ComputeError as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)
