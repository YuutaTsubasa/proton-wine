# Android Locale Implementation Plan

**Goal:** Honor Bannerlator's LC_ALL on Android while retaining the NULL-context fix.

**Architecture:** Extend unix_to_win_locale's existing fallback for Android's
C.UTF-8 result. Keep non-Android behavior and the existing cross-build unchanged.

**Tech Stack:** Wine C, Python host harness, Android NDK, GitHub Actions.

- [x] Locate and pin the user's successful NULL-context source commit.
- [x] Add a harness extracting the production converter; observe failing Android cases.
- [x] Extend the fallback with an Android-only C.UTF-8 condition.
- [x] Run host regression, existing NULL-context regression, and real Android libc harness.
- [x] Check the existing Android patch still applies and use a distinct numeric package identity.
- [x] Commit the stacked branch, push to the user's fork, and verify the cross-build.
- [x] Verify the built package's identity and distinguish build success from game validation.
- [x] Install alongside the old layer; verify Windows APIs and Evoland's Traditional Chinese menu on device.
