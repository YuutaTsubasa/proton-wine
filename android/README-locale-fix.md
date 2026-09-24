# Android locale fix on the ARM64EC NULL-context build

Base: `6350d27402e39465516f3ccfd2519cdbf5b9c489` from
`YuutaTsubasa/proton-wine`, retaining its ARM64EC NULL-context fix and toolchain.

## Design and scope

Bannerlator 3.1.1 passes a shortcut's `lc_all` as the Wine process's `LC_ALL`.
On the AYANEO Pocket S2 Pro (Android 14), setting that variable to either
`zh_TW` or `zh_TW.UTF-8` still makes Bionic's `setlocale(category, "")` return
`C.UTF-8`. The existing converter only consults `LC_ALL` for NULL, empty, or
`C` input, so it produces `C` and NLS initialization falls back to English.

Extend the existing fallback to `C.UTF-8` only when compiling for Android.
Do not hardcode a game or language. Other platforms and explicit non-default
locale input keep their existing behavior. Missing/empty LC_ALL returns FALSE,
letting the existing NLS fallback choose English. The existing Android patch's
`setenv("LC_ALL", "C.UTF-8", 0)` still preserves an explicit locale.

Changing only the UI or registry cannot address this conversion. A replacement
game DLL would affect the wrong layer. The small Android-only Wine change
addresses the observed cause while retaining the existing package/toolchain.

## Validation

`python3 build-scripts/tests/test_android_locale.py` extracts the actual
production converter, compiles Android and non-Android variants, and checks
Traditional Chinese, Japanese, missing/empty variables, length limits, script
modifiers, and preservation of existing conversion behavior. The pre-fix source
fails the Android locale assertions. The host harness does not validate NLS
loading, Windows API results, or full game behavior.

Use `--emit /path/to/locale.c` to generate the same harness for the Android NDK.
Build with `-DTEST_DEVICE_LIBC` and run on Android to also test its real
`setlocale` result. CI additionally runs the existing ARM64EC NULL-context
regression and cross-builds/packages Wine. Device verification of a resulting
package must check GetSystemDefaultLocaleName = zh-TW and Evoland's menu.

Local validation on 2026-09-25: all 23 host converter cases passed (10 non-Android,
13 Android), all 3 existing NULL-context tests passed, and the NDK-built harness
passed 14 cases on the connected Pocket S2 Pro. Its actual libc returned
`C.UTF-8`, which the patched converter resolved to `zh-TW`. The existing Android
env.c patch still applies. These results are not full Wine/game validation.

## Package identity

The new package uses versionName `11.0-7.1.20260925-arm64ec`, versionCode 1,
to coexist with the prior NULL-context package. The numeric suffix is intentional:
Bannerlator's Wine version parser must still recognize the arm64ec architecture.
Artifacts only; no release publication or automatic device installation.
