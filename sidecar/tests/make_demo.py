import requests

BASE = "http://127.0.0.1:8765"
S = "p24demo"

requests.post(BASE + "/v1/state/init", json={
    "session_id": S, "goal": "导数", "concept": "导数"}, timeout=10).raise_for_status()
for ev in ("confirm_goal", "diagnosed", "plan_ready"):
    requests.post(BASE + "/v1/state/step", json={
        "session_id": S, "event": ev}, timeout=10).raise_for_status()
requests.post(BASE + "/v1/state/step", json={
    "session_id": S, "event": "asked",
    "text": "导数定义里的“差商的极限”指什么？",
    "rubric": "差商,极限"}, timeout=10).raise_for_status()
r = requests.post(BASE + "/v1/state/step", json={
    "session_id": S, "event": "answer", "text": "差商的极限"}, timeout=10)
r.raise_for_status()
d = r.json()
print(d["state"]["phase"], d["mastery"]["after"], d["mastery"]["level"])
print(d["summary"])
