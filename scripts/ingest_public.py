"""Ingest public, citation-grade text into a schema-v2 catalogue.

Examples
--------
    python scripts/ingest_public.py --source wikisource --lang zh \
        --title "史記/卷001" --db data/public.db --license PD-old

    python scripts/ingest_public.py --source perseus --lang greek \
        --urn urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1 \
        --urn urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.2 \
        --db data/public.db

The catalogue is separate from the private PDF index on purpose: schema v1 and
v2 are different contracts, and writing v2 tables into a v1 file would change
what every other reader sees.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "sidecar"))

from app import config, ingest, schema                      # noqa: E402
from app.adapters import get as get_adapter                 # noqa: E402


def _titles(args):
    titles = list(args.title or [])
    if args.titles_file:
        with open(args.titles_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    titles.append(line)
    if args.query:
        # discovery needs the adapter, so it happens after construction
        titles.append(("__search__", args.query))
    return titles


def _adapter(args):
    if args.source == "wikisource":
        return get_adapter("wikisource", lang=args.lang, license=args.license,
                           min_interval=args.rate)
    if args.source == "perseus":
        return get_adapter("perseus", lang=args.lang, license=args.license,
                           min_interval=args.rate)
    raise SystemExit("unknown --source %r" % args.source)


def _documents(adapter, args):
    """Yield documents to ingest (fetching, or dry-run only)."""
    if args.source == "perseus":
        urns = list(args.urn or [])
        if not urns:
            raise SystemExit("perseus needs at least one --urn")
        yield adapter.fetch_many(urns, title=args.work_title, author=args.author,
                                 edition=args.edition,
                                 skip_errors=args.skip_errors)
        return

    titles = []
    for item in _titles(args):
        if isinstance(item, tuple):
            found = adapter.search(item[1], limit=args.search_limit)
            print("discovered:", json.dumps(found, ensure_ascii=False), file=sys.stderr)
            titles.extend(found)
        else:
            titles.append(item)
    if not titles:
        raise SystemExit("wikisource needs --title, --titles-file or --query")
    for title in titles:
        yield adapter.fetch(title, author=args.author, edition=args.edition)


def run(args, adapter=None):
    db = args.db or os.environ.get("SOCRATIC_PUBLIC_DB") or \
        os.path.join(config.DATA, "public.db")
    ver = schema.version(db)
    if ver == "v1":
        raise SystemExit(
            "%s is a v1 (scanned-PDF) catalogue. Pick a separate --db, e.g. "
            "%s/public.db; v1 and v2 are different contracts." % (db, config.DATA))
    adapter = adapter or _adapter(args)
    spec = adapter.source()
    results = []
    for doc in _documents(adapter, args):
        summary = {"document_id": doc.document_id, "title": doc.title,
                   "revision": doc.source_version,
                   "sections": len(doc.sections),
                   "chars": sum(len(s.text) for s in doc.sections)}
        if doc.metadata.get("skipped"):
            summary["skipped"] = len(doc.metadata["skipped"])
            print("skipped passages: %s" % doc.metadata["skipped"],
                  file=sys.stderr)
        if args.dry_run:
            summary["dry_run"] = True
        else:
            stats = ingest.ingest(db, doc, spec=spec, max_chars=args.chunk_chars)
            summary.update(stats)
        results.append(summary)
        print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps({"db": db, "source": spec.source_id,
                      "documents": len(results)}, ensure_ascii=False))
    return results


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", choices=("wikisource", "perseus"), required=True)
    p.add_argument("--lang", default="zh", help="zh | en | la | el | greek ...")
    p.add_argument("--db", help="v2 catalogue (default: $SOCRATIC_PUBLIC_DB or DATA/public.db)")
    p.add_argument("--title", action="append", help="wiki page title; repeatable")
    p.add_argument("--titles-file", help="UTF-8 file, one page title per line")
    p.add_argument("--query", help="search the source and ingest the hits")
    p.add_argument("--search-limit", type=int, default=10)
    p.add_argument("--urn", action="append", help="CTS URN; repeatable")
    p.add_argument("--work-title", help="document title for CTS ingest")
    p.add_argument("--author", help="author override")
    p.add_argument("--edition", help="edition override")
    p.add_argument("--license", default="CC-BY-SA-4.0",
                   help="licence recorded on the source/document")
    p.add_argument("--rate", type=float, default=1.0,
                   help="seconds between HTTP requests (Wikimedia asks for <=1/s)")
    p.add_argument("--chunk-chars", type=int, default=1200)
    p.add_argument("--skip-errors", action="store_true",
                   help="perseus: skip URNs the endpoint refuses instead of aborting")
    p.add_argument("--dry-run", action="store_true",
                   help="fetch and report, write nothing")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
