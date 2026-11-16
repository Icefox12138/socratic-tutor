"""Docs audit: broken relative links, orphan docs, and stale numbers.

    python scripts/docs_audit.py <root> [<root> ...]

Read-only. Prints three sections per project: broken links, docs not referenced
by any other doc, and lines whose numbers contradict the current state.

Run it from the repository root after touching docs, e.g.

    python scripts/docs_audit.py . D:/Guo-Code/rag-build

Orphans that only matter for navigation are worth fixing in the docs index;
ones that are entry points (README/SECURITY/.github templates) can be ignored.
"""
import os
import re
import sys

LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
STALE = [
    (re.compile(r"sidecar\s*\*\*?264|264/264"), "sidecar tests are 352 now"),
    (re.compile(r"12 个工具|12 工具"), "the plugin exposes 13 tools"),
    (re.compile(r"dsh-socratic`?\s*0\.[0-4]\."), "npm is 0.5.1 (tools) / 0.1.1 (persona)"),
    (re.compile(r"socratic-mcp`?\s*0\.1\."), "socratic-mcp is 0.2.0"),
    (re.compile(r"calcbox\s*0\.3\.0"), "calcbox is 0.3.1"),
]


def docs(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in
                       {"node_modules", ".git", ".venv-bge", ".venv-ocr", "cache", "data", "dist"}]
        for name in filenames:
            if name.endswith(".md"):
                out.append(os.path.join(dirpath, name))
    return out


def main(roots):
    for root in roots:
        files = docs(root)
        names = {os.path.relpath(f, root).replace("\\", "/") for f in files}
        basenames = {os.path.basename(n) for n in names}
        referenced = set()
        print("== %s  (%d docs)" % (root, len(files)))
        broken = []
        stale = []
        for path in files:
            rel = os.path.relpath(path, root).replace("\\", "/")
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for label, target in LINK.findall(text):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                clean = target.split("#")[0].strip()
                if not clean:
                    continue
                referenced.add(os.path.normpath(os.path.join(os.path.dirname(rel), clean)).replace("\\", "/"))
                abs_target = os.path.normpath(os.path.join(os.path.dirname(path), clean))
                if not os.path.exists(abs_target):
                    broken.append((rel, clean))
            for lineno, line in enumerate(text.splitlines(), 1):
                for pattern, why in STALE:
                    if pattern.search(line):
                        stale.append((rel, lineno, line.strip()[:110], why))
        print("  broken links: %d" % len(broken))
        for rel, target in broken[:20]:
            print("    %s -> %s" % (rel, target))
        orphans = sorted(n for n in names if n not in referenced
                         and os.path.basename(n) not in referenced
                         and not n.startswith("HANDOFF-"))
        print("  orphan docs (not linked from any doc, historical HANDOFFs excluded): %d" % len(orphans))
        for n in orphans[:20]:
            print("    %s" % n)
        print("  stale numbers: %d" % len(stale))
        for rel, lineno, text, why in stale[:15]:
            print("    %s:%d  %s  [%s]" % (rel, lineno, text, why))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
