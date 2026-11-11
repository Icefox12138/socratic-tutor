"""Computation endpoint — thin adapter over the calcbox package.

The implementation moved to https://github.com/Icefox12138/calcbox (MIT). This
module exists so the sidecar's HTTP contract does not change: same operations,
same result fields, same error types.

calcbox is a runtime dependency; if it is missing the endpoint reports it as a
backend problem instead of failing at import time.
"""
try:
    from calcbox import (BackendUnavailable, ComputeError, backend_status,
                         compute)
    from calcbox import backends as _calcbox_backends
    from calcbox import sandbox as _calcbox_sandbox
    HAVE_CALCBOX = True
    CALCBOX_ERROR = None
except ImportError as e:  # pragma: no cover - depends on the install
    HAVE_CALCBOX = False
    CALCBOX_ERROR = str(e)

    class ComputeError(ValueError):
        pass

    class BackendUnavailable(ComputeError):
        pass

    def _missing(*args, **kwargs):
        raise BackendUnavailable("calcbox is not installed: %s" % CALCBOX_ERROR)

    compute = _missing
    backend_status = _missing

    class _calcbox_sandbox(object):  # type: ignore
        @staticmethod
        def status():
            return {"available": False, "mode": "unavailable"}

# kept for callers/tests that patched the old worker entry point
_run_worker = getattr(_calcbox_backends, "_run_worker", None) if HAVE_CALCBOX else None

SANDBOX = "audit-only"


def sandbox_status():
    return _calcbox_sandbox.status()
