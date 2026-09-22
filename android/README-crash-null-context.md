# Experimental ARM64EC NULL-context fix

This branch adds an early `STATUS_INVALID_PARAMETER` return for a NULL context
in ARM64EC `NtGetContextThread`. The wrapper previously read `ContextFlags`
before checking the pointer. The same situation was addressed for x86-64 in
[Wine commit ec418e7f](https://github.com/wine-mirror/wine/commit/ec418e7f55f5e38f8825187ae5dfe33fec31689b),
associated with [Wine bug 45428](https://bugs.winehq.org/show_bug.cgi?id=45428).
Non-NULL handling and initialization of the ARM64 context are preserved.

## Source and build

- Base: `The412Banner/proton-wine`, `wip/proton_11.7-GE-valve`,
  commit `20518b4ce72b463877ad03db4804c0bb9a5e0dfb`.
- Build: `.github/workflows/build-ge-proton-11.0-7-valve.yml`, triggered by pushes
  to `codex/crash-arm64ec-null-context`.
- Target: Android ARM64EC, API 28, 16 KB alignment, using the upstream toolchain.
- Bannerlator artifact: `proton-crashnull-arm64ec-sdk28`, containing
  `GE-proton-11.0-7.1-crashnull-arm64ec.wcp`.
- Component identity: `11.0-7.1-crashnull-arm64ec`, versionCode `1`.
- Evidence artifact: `crashnull-build-evidence`, containing source identity,
  package checksums, profile, and compiled ntdll exports/disassembly.

The base is pinned but is not asserted to be the exact source of any previously
installed Bannerlator package. The distinct component name keeps this test build
separate from existing components. The workflow uploads artifacts; it does not
publish releases or install anything on a device.

## Validation and limits

Run `python3 build-scripts/tests/test_arm64ec_context.py` for the host regression
harness. It extracts the production wrapper and compiles it with minimal type,
syscall, and conversion stubs. This checks the NULL branch and preservation of
success/error control flow; it does not validate the Windows/ARM64EC ABI or game
compatibility. CI also cross-compiles Wine and runs upstream binary and package
checks.

This is a candidate fix for the observed NULL-context access violation, not a
claim that Crash Bandicoot is fully fixed. A later test on the device must confirm
progress beyond the title screen, level loading, and controller operation.
