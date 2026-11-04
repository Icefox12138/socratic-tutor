"""P0 6-class security attack suite (local sidecar)."""
import json
import os
import subprocess
import sys
import time

import requests

ROOT = r"D:\Guo-Code\socratic-tutor"
SIDE = os.path.join(ROOT, "sidecar")
BASE = "http://127.0.0.1:8765"
AUTH = "http://127.0.0.1:8766"
TOKEN = "sec-test-token"
H = {"X-Sidecar-Token": TOKEN}


def wait(url, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if requests.get(url + "/health", timeout=2).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def main():
    env = os.environ.copy()
    env.update({"SOCRATIC_TOKEN": TOKEN, "SOCRATIC_REQUIRE_AUTH": "1",
                "SOCRATIC_BGE": "0", "SOCRATIC_PRELOAD": "0"})
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                             "--host", "127.0.0.1", "--port", "8766"],
                            cwd=SIDE, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = {"cases": []}
    try:
        if not wait(AUTH):
            raise RuntimeError("auth sidecar did not start")
        cases = out["cases"]

        def add(name, ok, detail):
            cases.append({"name": name, "ok": bool(ok), "detail": detail})

        r = requests.get(AUTH + "/v1/search", params={"q": "微分", "view": "answer_key"},
                         headers=H, timeout=10)
        add("越权 view=answer_key", r.status_code == 400, {"status": r.status_code})

        r = requests.get(AUTH + "/v1/search", params={"q": "微分"}, timeout=10)
        add("无 token 访问检索", r.status_code == 401, {"status": r.status_code})

        r = requests.get(AUTH + "/v1/search", params={"q": "微分"},
                         headers={"X-Sidecar-Token": "forged"}, timeout=10)
        add("伪造 token", r.status_code == 401, {"status": r.status_code})

        r = requests.get(AUTH + "/v1/pages", params={
            "source": "library", "book": "../../Windows/win.ini", "page": 1},
            headers=H, timeout=10)
        add("路径穿越", r.status_code in (400, 404),
            {"status": r.status_code, "bytes": len(r.content),
             "png": r.content[:8] == b"\x89PNG\r\n\x1a\n"})

        r = requests.post(AUTH + "/v1/compute", json={
            "expression": "__import__('os').system('whoami')", "operation": "simplify"},
            headers=H, timeout=10)
        add("代码注入 __import__", r.status_code == 400, {"status": r.status_code})

        r = requests.post(AUTH + "/v1/compute", json={
            "expression": "x" * 400, "operation": "simplify"}, headers=H, timeout=10)
        add("资源耗尽（超长表达式）", r.status_code == 400, {"status": r.status_code})

        requests.post(AUTH + "/v1/state/init", json={
            "session_id": "sec-s1", "goal": "g", "concept": "c"}, headers=H, timeout=10)
        requests.post(AUTH + "/v1/state/step", json={
            "session_id": "sec-s1", "event": "confirm_goal"}, headers=H, timeout=10)
        r1 = requests.get(AUTH + "/v1/state/sec-s1", headers=H, timeout=10)
        r2 = requests.get(AUTH + "/v1/state/sec-s2", headers=H, timeout=10)
        add("跨会话状态隔离", r1.status_code == 200 and r2.status_code == 404,
            {"s1": r1.status_code, "s2": r2.status_code})

        out["ok"] = all(c["ok"] for c in cases)
        out["n"] = len(cases)
        out["passed"] = sum(1 for c in cases if c["ok"])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    dst = os.path.join(ROOT, "eval", "p0", "security")
    os.makedirs(dst, exist_ok=True)
    json.dump(out, open(os.path.join(dst, "security-results.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
