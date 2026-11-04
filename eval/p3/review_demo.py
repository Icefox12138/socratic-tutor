"""End-to-end P3 review against a live sidecar: init -> ask -> answer -> review."""
import json
import urllib.request

BASE = "http://127.0.0.1:8765"


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    sid = "p3-demo"
    post("/v1/state/init", {"session_id": sid, "goal": "导数", "concept": "derivative", "lang": "zh"})
    for ev in ("confirm_goal", "diagnosed", "plan_ready"):
        post("/v1/state/step", {"session_id": sid, "event": ev})
    post("/v1/state/step", {"session_id": sid, "event": "asked",
                            "text": "求 x^3 的导数", "expected": "3*x**2"})
    post("/v1/state/step", {"session_id": sid, "event": "answer",
                            "result": "wrong", "text": "我算的是 4x^2。"})
    rep = post("/v1/review", {"session_id": sid})
    print(json.dumps({
        "claims": [{"text": c["text"], "verdict": c["verdict"], "error": c["error"],
                    "attribution": c["attribution"], "evidence": c["evidence"]}
                   for c in rep["claims"]],
        "summary": rep["summary"],
        "practice": rep["practice"],
        "digest": rep["digest"],
    }, ensure_ascii=False, indent=1))
    ok = (rep["summary"]["incorrect"] == 1 and rep["claims"][0]["error"] == "arithmetic"
          and len(rep["practice"]) == 1)
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
