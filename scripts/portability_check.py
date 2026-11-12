"""Cross-platform portability scan for code (not docs/tests/data).

  python scripts/portability_check.py [--root .]

Flags Windows-only APIs, drive-letter paths, POSIX absolute paths and
shell=True. Exit 1 means a portability problem.
"""
import argparse
import os
import re
import sys

PATTERNS = {
    "windows-drive": re.compile(r"[A-Za-z]:\\"),
    "windows-api": re.compile(r"WinDLL|windll|msvcrt|winreg|os\.startfile|CREATE_NO_WINDOW"),
    "posix-absolute": re.compile(r"(?<![\w:])/(?:home|Users|tmp|var|opt|srv)/"),
    "shell-true": re.compile(r"shell\s*=\s*True"),
}
SKIP_DIRS = {".git", ".venv-bge", ".venv-ocr", ".venv-paddle-gpu", "data",
             "models", "dist", "build", "node_modules", "__pycache__",
             ".tmp-testenv", ".tmp-test2", ".tmp-mpl", ".tmp-pip", "tests",
             "tmp", ".uv-cache", "cache"}
SKIP_FILES = {"scripts/publish_lint.py", "scripts/portability_check.py"}
EXTS = {".py", ".js", ".mjs", ".toml", ".yml", ".yaml", ".json"}


def files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace("\\", "/")
            if rel in SKIP_FILES:
                continue
            if os.path.splitext(name)[1].lower() in EXTS:
                yield path, rel


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    hits = []
    for path, rel in files(root):
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    hits.append((rel, lineno, name, line.strip()[:120]))
    for rel, lineno, name, line in hits:
        print("FAIL %-18s %s:%d  %s" % (name, rel, lineno, line))
    print("PORTABLE" if not hits else "NOT PORTABLE: %d hits" % len(hits))
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
