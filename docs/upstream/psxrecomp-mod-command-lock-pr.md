# PR draft: make psx_mod_register_command safe from PSX_MOD_CONSTRUCTOR

Target: RetroPortingToolKit/psxrecomp `master`. Commit
`c8b16403` on cr1tika7/psxrecomp branch `mod-command-lock-ctor-safe`
(based on `7097d536`; `runtime/src/mod_runtime.cpp` is unchanged in that area
up to `a7b37e07`, so it should apply cleanly).

## Title

Make mod command registration safe from PSX_MOD_CONSTRUCTOR

## Body

`mod_plugins.h` tells plugins to register from `PSX_MOD_CONSTRUCTOR`, a static
constructor. `psx_mod_register_command` locks `g_mod_commands_lock`, a
namespace-scope `std::mutex` in `mod_runtime.cpp`.

MinGW libstdc++ initializes `std::mutex` dynamically (`pthread_mutex_init`
from the translation unit's initializer, `_GTHREAD_USE_MUTEX_INIT_FUNC`), not
as a constant. A plugin constructor that runs before `mod_runtime.cpp`'s
initializer therefore locks a zeroed mutex, winpthreads returns `EINVAL`, and
the process ends before `main`:

```
terminate called after throwing an instance of 'std::system_error'
  what():  Invalid argument
```

Seen in the Windows release of Medal of Honor PAL Recompiled (CI, MSYS2
MINGW64 gcc), where two game plugins register a debug command each. Every
argument, including `--help`, exits with code 3. The same sources built with
clang/libc++ (llvm-mingw) run, because libc++'s `std::mutex` is
constant-initialized; Linux and macOS are not affected either.

How it was traced: a small debugger on the Windows debug API stopped at the
first C++ throw (SEH code `0x20474343`) and listed return addresses on the
stack. `psx_mod_register_command` calls `pthread_mutex_lock` and branches to
`std::__throw_system_error`; `g_mod_commands_lock` lives in `.bss` and its
only writer is `_GLOBAL__sub_I_…` of `mod_runtime.cpp` (`pthread_mutex_init`),
which had not run yet. `__do_global_ctors` was the outermost frame.

The fix moves the mutex into a function-local static, as
`registered_plugins()` already does for the other registration calls, so it
is constructed on first use (thread-safe static initialization).

Testing: the title's mouse plugin smoke test (registers and runs its command)
passes on a clang build; the Windows CI release built with this commit starts
(see the title repo's release v0.1.1).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
