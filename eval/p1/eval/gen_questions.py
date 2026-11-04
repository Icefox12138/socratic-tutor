import json
import os
import random
import sqlite3
import time

import requests

BASE = r"D:\Guo-Code"
D = os.path.join(BASE, "socratic-tutor", "eval", "p1", "eval")
os.makedirs(D, exist_ok=True)
DB = os.path.join(BASE, "socratic-tutor", "eval", "p1", "ingest", "search.db")
KEY = open(os.path.join(BASE, "deepseek API key.txt"), encoding="utf-8").read().strip()
URL = "https://api.deepseek.com/chat/completions"
random.seed(7)

con = sqlite3.connect(DB)
quotas = [
    ("steadman", "greek", 12),
    ("steadman", "latin", 12),
    ("library", "zh", 50),
    ("library", "en", 10),
    ("teubner_conte", "latin", 8),
    ("library", "zh", 8),  # extra zh for 100
]
rows = []
for source, lang, n in quotas:
    data = con.execute(
        "SELECT id, source, book, lang, page, text FROM chunks "
        "WHERE visibility='tutor' AND source=? AND lang=? AND length(text) BETWEEN 200 AND 900 "
        "ORDER BY RANDOM() LIMIT ?", (source, lang, n)).fetchall()
    rows.extend(data)
con.close()

PROMPT = """你是学生。下面是一段{lang_name}文本。请用{ask_lang}提一个你读到这里会问的问题。
要求：
1. 不要照抄原文连续 8 个词/8 个字以上；
2. 问题要具体，指向这段内容的核心；
3. 只输出问题本身，不要解释。
文本：
{chunk}
"""

LANG_NAME = {"zh": "中文", "en": "英文", "greek": "古希腊语", "latin": "拉丁语"}
ASK = {"zh": "中文", "en": "英文", "greek": "英文", "latin": "英文"}

out = []
for i, (cid, source, book, lang, page, text) in enumerate(rows, 1):
    prompt = PROMPT.format(lang_name=LANG_NAME.get(lang, lang), ask_lang=ASK.get(lang, "英文"),
                           chunk=text[:800])
    try:
        r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                          json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                                "temperature": 0.3, "max_tokens": 80}, timeout=60)
        r.raise_for_status()
        q = r.json()["choices"][0]["message"]["content"].strip().replace("\n", " ")
    except Exception as e:
        q = f"(generation failed: {e})"
    out.append({"id": i, "chunk_id": cid, "source": source, "book": book, "lang": lang,
                "page": page, "question": q})
    if i % 10 == 0:
        print(i, flush=True)

json.dump(out, open(os.path.join(D, "questions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done", len(out))
