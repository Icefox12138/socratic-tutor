#!/usr/bin/env python
"""Pre-publication lint for the packages in this repo.

  python scripts/publish_lint.py [--root .] [--json]

Checks, per package: license, metadata, absolute paths, secrets, and
non-public data files. Exit code 1 means "do not publish yet".
"""
import argparse
import json
import os
import re
import sys

ABS_WIN = re.compile(r"[A-Za-z]:\\[^\s\"'<>|)]+")
ABS_POSIX = re.compile(r"(?<![\w:])/(?:home|Users|tmp|var|opt|srv)/[^\s\"'<>|)]+")
SECRET = re.compile(r"sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}")
DATA_EXT = {".npy", ".npz", ".pdf", ".db", ".sqlite", ".zst", ".parquet"}
SKIP_DIRS = {"__pycache__", "node_modules", ".git", "dist", "build", ".pytest_cache", "tests"}


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield os.path.join(dirpath, name)


def text_files(root):
    for path in walk(root):
        if os.path.splitext(path)[1] in {".py", ".js", ".mjs", ".toml", ".json", ".md", ".yml", ".yaml", ".txt"}:
            yield path


def check_package(path, repo_root):
    name = os.path.basename(path.rstrip("\\/"))
    rows = []

    def add(check, ok, detail=""):
        rows.append({"package": name, "check": check, "ok": bool(ok), "detail": detail})

    has_license = any(os.path.exists(os.path.join(p, "LICENSE")) or
                      os.path.exists(os.path.join(p, "LICENSE.md"))
                      for p in (path, repo_root))
    add("license", has_license, "LICENSE at package or repo root")

    meta = None
    if os.path.exists(os.path.join(path, "pyproject.toml")):
        meta = open(os.path.join(path, "pyproject.toml"), encoding="utf-8").read()
        add("metadata", "description" in meta and "version" in meta, "pyproject.toml")
        add("license field", re.search(r"^license\s*=", meta, re.M) is not None, "pyproject [project].license")
    elif os.path.exists(os.path.join(path, "package.json")):
        meta = open(os.path.join(path, "package.json"), encoding="utf-8").read()
        pkg = json.loads(meta)
        add("metadata", all(k in pkg for k in ("description", "version", "license")),
            "package.json description/version/license")

    abs_hits, secrets, data = [], [], []
    for f in text_files(path):
        for i, line in enumerate(open(f, encoding="utf-8", errors="ignore"), 1):
            if ABS_WIN.search(line) or ABS_POSIX.search(line):
                abs_hits.append("%s:%d" % (os.path.relpath(f, path), i))
            if SECRET.search(line):
                secrets.append("%s:%d" % (os.path.relpath(f, path), i))
    for f in walk(path):
        if os.path.splitext(f)[1].lower() in DATA_EXT:
            data.append(os.path.relpath(f, path))
    add("no absolute paths", not abs_hits, ", ".join(abs_hits[:3]) or "clean")
    add("no secrets", not secrets, ", ".join(secrets[:3]) or "clean")
    add("no data files", not data, ", ".join(data[:3]) or "clean")
    return rows


IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
# Derived directories hold renders of book pages (gitignored by convention);
# a directory named "pages" is always a render cache, never a published asset.
SKIP_FOR_ASSETS = {"__pycache__", "node_modules", ".git", "dist", "build", ".venv-bge",
                   ".venv-ocr", ".venv-mineru", ".venv-paddle-gpu", "out", "cache", "tmp",
                   "vert", "pages"}


def check_assets(repo):
    """Every image that would enter git needs a provenance line, none blocked."""
    manifest_path = os.path.join(repo, "docs", "assets", "SOURCES.md")
    manifest = ""
    if os.path.exists(manifest_path):
        manifest = open(manifest_path, encoding="utf-8").read()
    rows = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_FOR_ASSETS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() not in IMAGE_EXT:
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), repo).replace("\\", "/")
            # match the full path, or the bare file name inside backticks;
            # a plain substring test would let "shot.png" match "screenshot-demo.png"
            line = next((l for l in manifest.splitlines()
                         if rel in l or ("`" + name + "`") in l), None)
            if line is None:
                rows.append({"package": "assets", "check": "provenance", "ok": False,
                             "detail": rel + " (not in docs/assets/SOURCES.md)"})
            elif "⛔" in line:
                rows.append({"package": "assets", "check": "provenance", "ok": False,
                             "detail": rel + " (blocked: copyrighted)"})
            else:
                rows.append({"package": "assets", "check": "provenance", "ok": True,
                             "detail": rel})
    if not rows:
        rows.append({"package": "assets", "check": "provenance", "ok": True,
                     "detail": "no images in the repo"})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--scope", default="artifacts", choices=["artifacts", "source", "all"],
                    help="artifacts: what goes into the packages; source: what would enter git")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    repo = os.path.abspath(args.root)
    pkgs_dir = os.path.join(repo, "packages")
    roots = [os.path.join(pkgs_dir, d) for d in sorted(os.listdir(pkgs_dir))
             if os.path.isdir(os.path.join(pkgs_dir, d))]
    plugin = os.path.join(repo, "plugin-socratic")
    if os.path.isdir(plugin):
        roots.append(plugin)

    rows = []
    if args.scope in ("artifacts", "all"):
        for p in roots:
            rows.extend(check_package(p, repo))
    if args.scope in ("source", "all"):
        rows.extend(check_assets(repo))
    failed = [r for r in rows if not r["ok"]]
    for r in rows:
        print("%s %-16s %-16s %s" % ("ok  " if r["ok"] else "FAIL", r["package"], r["check"], r["detail"]))
    if args.json:
        print(json.dumps({"ok": not failed, "rows": rows}, ensure_ascii=False, indent=1))
    print("PUBLISH READY" if not failed else "NOT READY: %d blocking checks" % len(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
