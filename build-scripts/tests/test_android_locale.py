#!/usr/bin/env python3
"""Exercise the production locale converter with host and Android semantics.

The unmodified function is extracted from ntdll/unix/env.c and compiled with
minimal Windows type definitions. This tests conversion and environment fallback,
not NLS loading or the Windows API. --emit writes the same harness for an Android
NDK build and execution on a device, using its real setlocale implementation.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "dlls/ntdll/unix/env.c"

PREAMBLE = r'''
#include <locale.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define LOCALE_NAME_MAX_LENGTH 85
'''

TESTS = r'''
static int failures;
static void check(const char *label, const char *input, const char *lc_all,
                  int expected_ok, const char *expected)
{
    char result[LOCALE_NAME_MAX_LENGTH] = "";
    int ok;
#ifdef _WIN32
    _putenv_s("LC_ALL", lc_all ? lc_all : "");
#else
    if (lc_all) setenv("LC_ALL", lc_all, 1);
    else unsetenv("LC_ALL");
#endif
    ok = unix_to_win_locale(input, result);
    if (ok != expected_ok || (ok && strcmp(result, expected))) {
        fprintf(stderr, "FAIL %s: ok=%d locale=%s, expected ok=%d locale=%s\n",
                label, ok, result, expected_ok, expected);
        failures++;
    } else printf("PASS %s\n", label);
}

int main(void)
{
#ifdef __ANDROID__
    check("bionic traditional Chinese UTF-8", "C.UTF-8", "zh_TW.UTF-8", 1, "zh-TW");
    check("bionic traditional Chinese", "C.UTF-8", "zh_TW", 1, "zh-TW");
    check("bionic Japanese", "C.UTF-8", "ja_JP.UTF-8", 1, "ja-JP");
    check("bionic no override", "C.UTF-8", NULL, 0, "");
    check("bionic empty override", "C.UTF-8", "", 0, "");
#else
    check("host UTF-8 locale preserved", "C.UTF-8", "zh_TW.UTF-8", 1, "C");
    check("host no override preserved", "C.UTF-8", NULL, 1, "C");
#endif
    check("explicit locale preserved", "fr_FR.UTF-8", "zh_TW.UTF-8", 1, "fr-FR");
    check("script modifier preserved", "sr_RS.UTF-8@latin", NULL, 1, "sr-Latn-RS");
    check("existing C fallback", "C", "zh_TW.UTF-8", 1, "zh-TW");
    check("existing null fallback", NULL, "zh_TW.UTF-8", 1, "zh-TW");
    check("existing empty fallback", "", "zh_TW.UTF-8", 1, "zh-TW");
    check("C override", "C.UTF-8", "C", 1,
#ifdef __ANDROID__
          "en-US"
#else
          "C"
#endif
    );
    check("UTF-8 default override", "C.UTF-8", "C.UTF-8", 1, "C");
    check("overlong locale rejected", "C",
          "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
          0, "");
#ifdef TEST_DEVICE_LIBC
    setenv("LC_ALL", "zh_TW.UTF-8", 1);
    char actual[LOCALE_NAME_MAX_LENGTH];
    const char *name = setlocale(LC_CTYPE, "");
    if (!name || strlen(name) >= sizeof(actual)) return 2;
    strcpy(actual, name);
    printf("Android setlocale returned %s\n", actual);
    check("real device libc to Traditional Chinese", actual, "zh_TW.UTF-8", 1, "zh-TW");
#endif
    return failures ? 1 : 0;
}
'''


def harness():
    source = SOURCE.read_text()
    start = source.index("static BOOL unix_to_win_locale(")
    end = source.index("\n}\n", start) + 3
    return PREAMBLE + source[start:end] + TESTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit", type=Path)
    args = parser.parse_args()
    if args.emit:
        args.emit.write_text(harness())
        return
    with tempfile.TemporaryDirectory(prefix="wine-locale-test-") as temp:
        source = Path(temp) / "locale.c"
        source.write_text(harness())
        for android in (False, True):
            target = Path(temp) / ("android" if android else "host")
            if os.name == "nt":
                target = target.with_suffix(".exe")
            flags = ["-D__ANDROID__"] if android else []
            subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-D_POSIX_C_SOURCE=200809L",
                            "-Wall", "-Wextra", "-Werror", *flags, str(source), "-o", str(target)], check=True)
            subprocess.run([str(target)], check=True)


if __name__ == "__main__":
    main()
