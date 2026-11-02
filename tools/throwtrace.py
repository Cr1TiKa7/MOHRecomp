"""Minimal Windows debugger for crashes before or without a debug server:
run an exe, stop at the first MinGW C++ throw (SEH code 0x20474343, raised
by libgcc's _Unwind_RaiseException) and print every stack word that points
into a known text symbol (a heuristic backtrace; arguments that are function
pointers show up too).

usage:
  <llvm-mingw>/x86_64-w64-mingw32-nm -C game.exe > syms.txt
  py -3 -I tools/throwtrace.py syms.txt game.exe [args...]
Resolve the printed addresses with llvm-addr2line -f -C -e game.exe <addr>...
"""
import bisect
import ctypes
import ctypes.wintypes as w
import subprocess
import sys

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
DEBUG_ONLY_THIS_PROCESS = 0x2
EXCEPTION_DEBUG_EVENT, CREATE_THREAD_DEBUG_EVENT, CREATE_PROCESS_DEBUG_EVENT = 1, 2, 3
EXIT_PROCESS_DEBUG_EVENT, LOAD_DLL_DEBUG_EVENT = 5, 6
DBG_CONTINUE, DBG_EXCEPTION_NOT_HANDLED = 0x00010002, 0x80010001
GCC_THROW = 0x20474343
PREFERRED_BASE = 0x140000000


class EXCEPTION_RECORD(ctypes.Structure):
    _fields_ = [("ExceptionCode", w.DWORD), ("ExceptionFlags", w.DWORD),
                ("ExceptionRecord", ctypes.c_void_p), ("ExceptionAddress", ctypes.c_void_p),
                ("NumberParameters", w.DWORD), ("ExceptionInformation", ctypes.c_uint64 * 15)]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("ExceptionRecord", EXCEPTION_RECORD), ("dwFirstChance", w.DWORD)]


class CREATE_THREAD_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("hThread", w.HANDLE), ("lpThreadLocalBase", ctypes.c_void_p),
                ("lpStartAddress", ctypes.c_void_p)]


class CREATE_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("hFile", w.HANDLE), ("hProcess", w.HANDLE), ("hThread", w.HANDLE),
                ("lpBaseOfImage", ctypes.c_void_p), ("dwDebugInfoFileOffset", w.DWORD),
                ("nDebugInfoSize", w.DWORD), ("lpThreadLocalBase", ctypes.c_void_p),
                ("lpStartAddress", ctypes.c_void_p), ("lpImageName", ctypes.c_void_p),
                ("fUnicode", w.WORD)]


class U(ctypes.Union):
    _fields_ = [("Exception", EXCEPTION_DEBUG_INFO), ("CreateThread", CREATE_THREAD_DEBUG_INFO),
                ("CreateProcessInfo", CREATE_PROCESS_DEBUG_INFO), ("raw", ctypes.c_byte * 176)]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [("dwDebugEventCode", w.DWORD), ("dwProcessId", w.DWORD),
                ("dwThreadId", w.DWORD), ("u", U)]


class STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR),
                ("lpTitle", w.LPWSTR), ("dwX", w.DWORD), ("dwY", w.DWORD), ("dwXSize", w.DWORD),
                ("dwYSize", w.DWORD), ("dwXCountChars", w.DWORD), ("dwYCountChars", w.DWORD),
                ("dwFillAttribute", w.DWORD), ("dwFlags", w.DWORD), ("wShowWindow", w.WORD),
                ("cbReserved2", w.WORD), ("lpReserved2", ctypes.c_void_p), ("hStdInput", w.HANDLE),
                ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE),
                ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


def load_symbols(path):
    syms = []
    for line in open(path, encoding="utf-8", errors="replace"):
        parts = line.rstrip("\n").split(" ", 2)
        if len(parts) == 3 and parts[0] and parts[1] in "TtWw" and not parts[2].startswith("."):
            syms.append((int(parts[0], 16), parts[2]))
    syms.sort()
    return syms


def resolve(syms, keys, addr):
    i = bisect.bisect_right(keys, addr) - 1
    if i < 0:
        return None
    a, name = syms[i]
    return "%s+0x%x" % (name, addr - a) if addr - a < 0x20000 else None


def main():
    syms = load_symbols(sys.argv[1])
    keys = [a for a, _ in syms]
    lo, hi = keys[0], keys[-1] + 0x1000
    cmd = subprocess.list2cmdline(sys.argv[2:])
    si, pi = STARTUPINFO(), PROCESS_INFORMATION()
    si.cb = ctypes.sizeof(si)
    if not k32.CreateProcessW(None, ctypes.create_unicode_buffer(cmd), None, None, False,
                              DEBUG_ONLY_THIS_PROCESS, None, None, ctypes.byref(si), ctypes.byref(pi)):
        raise OSError(ctypes.get_last_error())
    threads, delta, hproc = {}, 0, pi.hProcess
    ev = DEBUG_EVENT()
    while k32.WaitForDebugEvent(ctypes.byref(ev), 30000):
        status = DBG_CONTINUE
        code = ev.dwDebugEventCode
        if code == CREATE_PROCESS_DEBUG_EVENT:
            info = ev.u.CreateProcessInfo
            threads[ev.dwThreadId] = info.hThread
            delta = info.lpBaseOfImage - PREFERRED_BASE
            print("image base 0x%x (delta %#x)" % (info.lpBaseOfImage, delta))
        elif code == CREATE_THREAD_DEBUG_EVENT:
            threads[ev.dwThreadId] = ev.u.CreateThread.hThread
        elif code == EXIT_PROCESS_DEBUG_EVENT:
            print("process exited without a C++ throw")
            return
        elif code == EXCEPTION_DEBUG_EVENT:
            rec = ev.u.Exception.ExceptionRecord
            exc = rec.ExceptionCode
            if exc == GCC_THROW:
                print("C++ throw in thread %d at %s" % (ev.dwThreadId,
                      resolve(syms, keys, rec.ExceptionAddress - delta) or hex(rec.ExceptionAddress)))
                buf = (ctypes.c_byte * (1232 + 16))()
                ctx = (ctypes.addressof(buf) + 15) & ~15
                ctypes.c_uint32.from_address(ctx + 0x30).value = 0x100001  # CONTEXT_CONTROL
                if not k32.GetThreadContext(threads[ev.dwThreadId], ctypes.c_void_p(ctx)):
                    raise OSError(ctypes.get_last_error())
                rsp = ctypes.c_uint64.from_address(ctx + 0x98).value
                rip = ctypes.c_uint64.from_address(ctx + 0xF8).value
                print("rip %s" % (resolve(syms, keys, rip - delta) or hex(rip)))
                n = 0x40000
                stack = (ctypes.c_uint64 * (n // 8))()
                got = ctypes.c_size_t()
                k32.ReadProcessMemory(hproc, ctypes.c_void_p(rsp), stack, n, ctypes.byref(got))
                shown = 0
                for i in range(got.value // 8):
                    v = stack[i] - delta
                    if lo <= v < hi:
                        r = resolve(syms, keys, v)
                        if r:
                            print("  [rsp+%#06x] %#x %s" % (i * 8, v, r))
                            shown += 1
                            if shown >= 70:
                                break
                k32.TerminateProcess(hproc, 99)
                return
            if exc != 0x80000003:  # initial breakpoint
                status = DBG_EXCEPTION_NOT_HANDLED
        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, status)
    print("timeout")


main()
