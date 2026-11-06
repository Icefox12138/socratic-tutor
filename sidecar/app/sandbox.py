"""Windows AppContainer runner for local compute workers.

The worker gets an AppContainer token with **no capabilities** (so no network)
and read-only access to the code/venv; only the per-run temp directory is
writable. On non-Windows or when AppContainer is unavailable the caller can
fall back explicitly to the killable-process runner.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes

PROFILE = "SocraticTutorCompute"
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009
WAIT_TIMEOUT = 0x102
ERROR_ALREADY_EXISTS_HR = 0x800700B7


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [("AppContainerSid", ctypes.c_void_p),
                ("Capabilities", ctypes.POINTER(_SID_AND_ATTRIBUTES)),
                ("CapabilityCount", wintypes.DWORD),
                ("Reserved", wintypes.DWORD)]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
    ]


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", _STARTUPINFOW),
                ("lpAttributeList", ctypes.c_void_p)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD)]


_profile_sid = None
_sid_string = None
_ensured = False
_last_error = None


def _userenv():
    return ctypes.WinDLL("userenv", use_last_error=True)


def _advapi():
    return ctypes.WinDLL("advapi32", use_last_error=True)


def _kernel():
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _hr(code):
    return code & 0xFFFFFFFF


def _profile():
    global _profile_sid, _sid_string, _last_error
    if _profile_sid:
        return _profile_sid
    userenv = _userenv()
    sid = ctypes.c_void_p()
    userenv.CreateAppContainerProfile.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
        ctypes.POINTER(_SID_AND_ATTRIBUTES), wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p)]
    userenv.CreateAppContainerProfile.restype = ctypes.c_long
    hr = userenv.CreateAppContainerProfile(
        PROFILE, PROFILE, PROFILE, None, 0, ctypes.byref(sid))
    if _hr(hr) == ERROR_ALREADY_EXISTS_HR:
        userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [
            wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
        userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
        hr = userenv.DeriveAppContainerSidFromAppContainerName(
            PROFILE, ctypes.byref(sid))
    if _hr(hr) != 0 or not sid:
        _last_error = "CreateAppContainerProfile hr=0x%08x" % _hr(hr)
        return None
    advapi = _advapi()
    string_sid = wintypes.LPWSTR()
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p,
                                              ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(string_sid)):
        _last_error = "ConvertSidToStringSidW failed"
        return None
    _profile_sid = sid
    _sid_string = string_sid.value
    return _profile_sid


def _grant(path, rights):
    sid = _profile()
    if not sid:
        return False
    try:
        proc = subprocess.run(
            ["icacls", path, "/grant", "*%s:(OI)(CI)%s" % (_sid_string, rights),
             "/C", "/Q"],
            capture_output=True, text=True, timeout=120)
        return proc.returncode == 0
    except Exception:
        return False


def ensure(root, temp):
    """Grant read-only code/venv and writable temp to the AppContainer SID."""
    global _ensured, _last_error
    if _ensured:
        return True
    if _profile() is None:
        return False
    paths = [
        (sys.base_prefix, "RX"),
        (sys.prefix, "RX"),
        (root, "RX"),
        (temp, "F"),
    ]
    ok = True
    for path, rights in paths:
        if path and os.path.exists(path):
            ok = _grant(path, rights) and ok
    _ensured = ok
    if not ok:
        _last_error = _last_error or "icacls grant failed"
    return ok


def status():
    if sys.platform != "win32":
        return {"available": False, "mode": "process", "reason": "not Windows"}
    available = _profile() is not None
    return {"available": available,
            "mode": "appcontainer" if available else "audit",
            "profile": PROFILE,
            "sid": _sid_string,
            "error": _last_error}


def run_worker(python_exe, module, inp, outp, cwd, timeout, temp):
    """Run ``python_exe -m module inp outp`` inside the AppContainer."""
    if not ensure(cwd, temp):
        raise OSError("AppContainer unavailable: %s" % (_last_error or "unknown"))
    cmd = '"%s" -m %s "%s" "%s"' % (python_exe, module, inp, outp)
    cmd_buf = ctypes.create_unicode_buffer(cmd)
    si = _STARTUPINFOEXW()
    si.StartupInfo.cb = ctypes.sizeof(_STARTUPINFOEXW)
    size = ctypes.c_size_t()
    kernel = _kernel()
    kernel.InitializeProcThreadAttributeList.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t)]
    if not kernel.InitializeProcThreadAttributeList(
            None, 1, 0, ctypes.byref(size)):
        raise OSError("InitializeProcThreadAttributeList size failed")
    attr = ctypes.create_string_buffer(size.value)
    si.lpAttributeList = ctypes.cast(attr, ctypes.c_void_p)
    if not kernel.InitializeProcThreadAttributeList(
            attr, 1, 0, ctypes.byref(size)):
        raise OSError("InitializeProcThreadAttributeList failed")
    caps = _SECURITY_CAPABILITIES(_profile(), None, 0, 0)
    if not kernel.UpdateProcThreadAttribute(
            attr, 0, PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
            ctypes.byref(caps), ctypes.sizeof(caps), None, None):
        raise OSError("UpdateProcThreadAttribute failed")
    pi = _PROCESS_INFORMATION()
    kernel.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(_STARTUPINFOEXW), ctypes.POINTER(_PROCESS_INFORMATION)]
    kernel.CreateProcessW.restype = wintypes.BOOL
    ok = kernel.CreateProcessW(
        None, cmd_buf, None, None, False, EXTENDED_STARTUPINFO_PRESENT,
        None, cwd, ctypes.byref(si), ctypes.byref(pi))
    kernel.DeleteProcThreadAttributeList(attr)
    if not ok:
        raise OSError("CreateProcessW failed: %d" % ctypes.get_last_error())
    try:
        wait = kernel.WaitForSingleObject(pi.hProcess, int(timeout * 1000))
        if wait == WAIT_TIMEOUT:
            kernel.TerminateProcess(pi.hProcess, 1)
            kernel.WaitForSingleObject(pi.hProcess, 3000)
            return "timeout", 1
        code = wintypes.DWORD()
        kernel.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
        return "ok", int(code.value)
    finally:
        kernel.CloseHandle(pi.hThread)
        kernel.CloseHandle(pi.hProcess)
