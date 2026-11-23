#!/usr/bin/env python
"""Validate curriculum lesson packs (schema v1) before publishing a course.

    python scripts/curriculum_check.py --dir curriculum
    python scripts/curriculum_check.py --dir samples/curriculum --json

Exit code 0 = every pack is valid; 1 = at least one problem (printed per file).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "sidecar"))
from app import curriculum  # noqa: E402


def check_dir(path):
    if not os.path.isdir(path):
        return [{"file": path, "problems": ["directory not found"]}]
    out = []
    for name in sorted(f for f in os.listdir(path) if f.endswith(".json")):
        full = os.path.join(path, name)
        try:
            with open(full, encoding="utf-8-sig") as fh:
                pack = json.load(fh)
        except (OSError, ValueError) as e:
            out.append({"file": name, "problems": ["unreadable: %s" % e]})
            continue
        problems = curriculum.validate(pack)
        out.append({"file": name, "problems": problems})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate curriculum lesson packs")
    ap.add_argument("--dir", default="curriculum")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    results = check_dir(args.dir)
    bad = [r for r in results if r["problems"]]
    if args.json:
        print(json.dumps({"dir": args.dir, "checked": len(results),
                          "problems": bad}, ensure_ascii=False, indent=1))
    else:
        print("curriculum dir:", args.dir, "| packs:", len(results))
        for r in results:
            if r["problems"]:
                print("  FAIL", r["file"])
                for p in r["problems"]:
                    print("        -", p)
            else:
                print("  OK  ", r["file"])
    print("RESULT:", "OK" if not bad else "PROBLEMS (%d pack(s))" % len(bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
