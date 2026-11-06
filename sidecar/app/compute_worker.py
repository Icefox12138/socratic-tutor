"""Killed subprocess worker for local compute backends."""
import json
import os
import sys

from .sandbox_policy import install

install(os.environ.get("SOCRATIC_SANDBOX_TEMP", ""))

from .compute import BackendUnavailable, ComputeError, _execute_local  # noqa: E402


def main():
    if len(sys.argv) != 3:
        return 2
    with open(sys.argv[1], encoding="utf-8") as fh:
        payload = json.load(fh)
    try:
        out = _execute_local(**payload)
        body = {"ok": True, "out": out}
    except BackendUnavailable as e:
        body = {"ok": False, "kind": "unavailable", "error": str(e)}
    except ComputeError as e:
        body = {"ok": False, "kind": "compute", "error": str(e)}
    except Exception as e:
        body = {"ok": False, "kind": "internal", "error": str(e)[:300]}
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
