"""Command-line entry point for the socratic sidecar.

    python -m app --port 8765
    socratic-sidecar --data ~/socratic --port 8765

`app.config` reads every setting from the environment *at import time*, so this
module translates the flags into SOCRATIC_* variables before it imports app or
uvicorn. That also makes the two invocation styles above exactly equivalent:
with no arguments, `python -m app` is the same as the console script.

The flags mirror the environment variables; explicit flags win over an
already-exported SOCRATIC_* value because they are applied afterwards.
"""
import argparse
import os
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

#: flag -> environment variable, for the plain string-valued options. Paths are
#: made absolute so the service keeps resolving them if a later component
#: changes the working directory.
_ENV_FLAGS = {
    "data": "SOCRATIC_DATA",
    "db": "SOCRATIC_DB",
    "lexicon_db": "SOCRATIC_LEXICON_DB",
    "root": "SOCRATIC_ROOT",
    "curriculum": "SOCRATIC_CURRICULUM",
    "cache": "SOCRATIC_CACHE",
    "state_db": "SOCRATIC_STATE_DB",
}
_PATH_FLAGS = set(_ENV_FLAGS)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="socratic-sidecar",
        description="Minimal Socratic tutor sidecar: search, pages, compute.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "Every option maps to a SOCRATIC_* environment variable and is "
            "applied before the application is imported, so e.g. "
            "`--data DIR` is the same as exporting SOCRATIC_DATA=DIR. "
            "With no arguments this is equivalent to `python -m app`."
        ),
    )
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="interface to bind")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="TCP port to listen on")
    parser.add_argument("--data", metavar="DIR",
                        help="derived data root (indexes, vectors, caches)")
    parser.add_argument("--db", metavar="FILE",
                        help="RAG database holding the chunks index")
    parser.add_argument("--lexicon-db", metavar="FILE",
                        help="dictionary / grammar database")
    parser.add_argument("--root", metavar="DIR",
                        help="directory containing the book library")
    parser.add_argument("--curriculum", metavar="DIR",
                        help="directory of curriculum lesson packs")
    parser.add_argument("--cache", metavar="DIR",
                        help="page-image cache directory")
    parser.add_argument("--state-db", metavar="FILE",
                        help="SQLite file for learner state and the chapter index")
    parser.add_argument("--token", metavar="TOKEN",
                        help="shared token required by /v1/* (empty means no auth)")
    parser.add_argument("--bge", action=argparse.BooleanOptionalAction,
                        default=None,
                        help="enable/disable BGE embeddings; default follows SOCRATIC_BGE")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + _version())
    return parser


def _version():
    try:
        from importlib.metadata import version
        return version("socratic-sidecar")
    except Exception:
        try:
            from . import config
            return config.VERSION
        except Exception:
            return "unknown"


def configure_environment(args):
    """Apply parsed flags to the process environment (before importing app)."""
    for flag, env_name in _ENV_FLAGS.items():
        value = getattr(args, flag)
        if value:
            if flag in _PATH_FLAGS:
                value = os.path.abspath(os.path.expanduser(value))
            os.environ[env_name] = value
    if args.token is not None:
        os.environ["SOCRATIC_TOKEN"] = args.token
    if args.bge is not None:
        os.environ["SOCRATIC_BGE"] = "1" if args.bge else "0"


def main(argv=None):
    args = build_parser().parse_args(argv)
    configure_environment(args)

    # Import only after the environment is final: config.py snapshots it.
    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port,
                timeout_keep_alive=75)
    return 0


if __name__ == "__main__":
    sys.exit(main())
