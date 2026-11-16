"""Fetch public reference data once; the data project never touches the network.

`rag-build` (the private data project) needs a handful of public artefacts:
Perseus edition XML for gold comparison, archive.org item metadata for licence
and file inventory, Wikisource page wikitext. Fetching belongs to the runtime:

  * one place carries the User-Agent, the timeout and the licence note;
  * inputs are replayable files, not implicit live state;
  * the data project stays offline and only processes what is on disk.

    python scripts/fetch_public.py perseus --text tlg0059.tlg002 \
        --edition perseus-grc2 --out D:/Guo-Code/rag-build/eval/p0/gold/apology.xml
    python scripts/fetch_public.py archive-meta \
        --identifier Teubner-Edition-Collection --out .../gold/teubner-meta.json
    python scripts/fetch_public.py wikisource --lang zh --title "史記/卷001" \
        --out .../gold/shiji-001.json

Perseus TEI is CC BY-SA 4.0, not public domain: keep attribution when a derived
file leaves the machine, and do not commit fetched editions to this repository.
"""
import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "dsh-socratic/1.0 (+https://github.com/Icefox12138/socratic-tutor)")
PERSEUS_REPO = {"greek": "canonical-greekLit", "latin": "canonical-latinLit"}


def _get(url, timeout=60.0, retries=2):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:                      # network, HTTP, timeout
            last = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise SystemExit("fetch failed for %s: %s: %s" % (url, type(last).__name__, last))


def perseus_url(text, edition, lang):
    repo = PERSEUS_REPO[lang]
    parts = text.split(".")
    if len(parts) != 2:
        raise SystemExit("--text must look like tlg0059.tlg002, got %r" % text)
    return ("https://raw.githubusercontent.com/PerseusDL/%s/master/data/%s/%s/%s.%s.xml"
            % (repo, parts[0], parts[1], text, edition))


def archive_meta_url(identifier):
    return "https://archive.org/metadata/%s" % urllib.parse.quote(identifier)


def wikisource_url(lang, title):
    return ("https://%s.wikisource.org/w/api.php?action=query&prop=revisions"
            "&rvprop=content&rvslots=main&format=json&titles=%s"
            % (lang, urllib.parse.quote(title)))


def _write(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()[:16]
    print("wrote %s  %d bytes  sha256:%s" % (target, len(payload), digest))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("perseus", help="one Perseus/Canonical edition XML")
    p.add_argument("--text", required=True, help="tlg0059.tlg002")
    p.add_argument("--edition", default="perseus-grc2")
    p.add_argument("--lang", choices=sorted(PERSEUS_REPO), default="greek")
    p.add_argument("--out", required=True)

    a = sub.add_parser("archive-meta", help="archive.org item metadata JSON")
    a.add_argument("--identifier", required=True)
    a.add_argument("--out", required=True)

    w = sub.add_parser("wikisource", help="one Wikisource page as wikitext JSON")
    w.add_argument("--lang", default="zh")
    w.add_argument("--title", required=True)
    w.add_argument("--out", required=True)

    for name, item in (("perseus", p), ("archive-meta", a), ("wikisource", w)):
        item.add_argument("--timeout", type=float, default=60.0)
        item.add_argument("--dry-run", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "perseus":
        url = perseus_url(args.text, args.edition, args.lang)
    elif args.cmd == "archive-meta":
        url = archive_meta_url(args.identifier)
    else:
        url = wikisource_url(args.lang, args.title)

    if args.dry_run:
        print(url)
        return 0
    payload = _get(url, timeout=args.timeout)
    if args.cmd == "archive-meta":
        payload = json.dumps(json.loads(payload.decode("utf-8")),
                             ensure_ascii=False, indent=1).encode("utf-8")
    _write(args.out, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
