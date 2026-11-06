"""Audit-hook policy sandbox for the compute worker.

It blocks Python-level socket/process creation and all filesystem writes
outside the per-run temp directory. This is the only compute sandbox; there is
no OS network namespace or read-only mount.
"""
import os
import sys


def install(temp):
    temp = os.path.realpath(temp or "")
    if not temp:
        raise RuntimeError("sandbox temp is required")

    def inside(path):
        if path is None:
            return False
        try:
            if isinstance(path, int):
                return False
            p = os.path.realpath(str(path))
        except Exception:
            return False
        return p == temp or p.startswith(temp + os.sep)

    def hook(event, args):
        if event in ("socket.__new__", "socket.connect", "socket.bind",
                     "socket.getaddrinfo", "socket.gethostbyname",
                     "socket.sendto"):
            raise PermissionError("network disabled by compute sandbox")
        if event in ("subprocess.Popen", "os.system", "os.exec",
                     "os.spawn", "os.posix_spawn", "os.fork"):
            raise PermissionError("process creation disabled by compute sandbox")
        if event == "open":
            path = args[0] if args else None
            mode = args[1] if len(args) > 1 else "r"
            flags = args[2] if len(args) > 2 else 0
            writing = False
            if isinstance(mode, str):
                writing = any(c in mode for c in "wax+")
            elif isinstance(flags, int):
                writing = bool(flags & (os.O_WRONLY | os.O_RDWR |
                                        os.O_CREAT | os.O_APPEND))
            if writing and not inside(path):
                raise PermissionError("read-only filesystem: %s" % (path,))
        if event in ("os.remove", "os.unlink", "os.mkdir", "os.rmdir",
                     "os.chmod", "os.utime", "os.truncate"):
            path = args[0] if args else None
            if path is not None and not inside(path):
                raise PermissionError("read-only filesystem: %s" % (path,))
        if event in ("os.rename", "os.replace"):
            for path in args[:2]:
                if path is not None and not inside(path):
                    raise PermissionError("read-only filesystem: %s" % (path,))

    sys.addaudithook(hook)
