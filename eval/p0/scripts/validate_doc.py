import json, re, sqlite3, sys
import yaml

p = r"D:\Guo-Code\socratic-tutor\docs\DESIGN.md"
lines = open(p, encoding="utf-8").read().split("\n")

blocks, cur, start, lang = [], None, 0, ""
for i, ln in enumerate(lines, 1):
    if ln.startswith("```"):
        if cur is None:
            cur, start, lang = [], i, ln[3:].strip()
        else:
            blocks.append((lang, start, "\n".join(cur)))
            cur = None
    elif cur is not None:
        cur.append(ln)

ok = bad = 0
for lang, start, body in blocks:
    if lang in ("sql",):
        try:
            con = sqlite3.connect(":memory:")
            con.executescript(body)
            con.close(); ok += 1
        except Exception as e:
            bad += 1
            print(f"SQL FAIL line {start}: {e}")
    elif lang in ("json",):
        try:
            json.loads(body); ok += 1
        except Exception as e:
            bad += 1
            print(f"JSON FAIL line {start}: {e}")
    elif lang in ("yaml",):
        try:
            yaml.safe_load(body); ok += 1
        except Exception as e:
            bad += 1
            print(f"YAML FAIL line {start}: {e}")
print(f"blocks={len(blocks)} ok={ok} bad={bad}")
