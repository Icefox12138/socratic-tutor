"""Temporary directories that survive the DSH Windows file sandbox.

`tempfile.mkdtemp()` creates its directory with a DACL that carries no entry
for the sandbox token, so inside it every write fails (`PermissionError`, and
SQLite reports "unable to open database file") and the directory cannot even be
deleted afterwards. `os.makedirs()` produces an ordinary directory, which the
sandbox allows.

Use `mkdtemp()` / `TemporaryDirectory()` from here instead of the stdlib ones
whenever the test writes files (especially SQLite databases) into the directory.
"""
import os
import secrets
import shutil
import tempfile


def mkdtemp(suffix=None, prefix=None, dir=None):
    """Like tempfile.mkdtemp(), but with a DACL the sandbox can write to."""
    base = dir or tempfile.gettempdir()
    for _ in range(100):
        path = os.path.join(base, (prefix or "tmp") + secrets.token_hex(6) + (suffix or ""))
        try:
            os.makedirs(path)
            return path
        except FileExistsError:
            continue
    raise FileExistsError("could not create a unique temp directory under %r" % base)


class TemporaryDirectory(object):
    """Like tempfile.TemporaryDirectory(), but usable under the sandbox."""

    def __init__(self, suffix=None, prefix=None, dir=None):
        self.name = mkdtemp(suffix, prefix, dir)

    def __enter__(self):
        return self.name

    def __exit__(self, exc_type, exc, tb):
        shutil.rmtree(self.name, ignore_errors=True)
        return False
