#!/usr/bin/env python3
"""Host control-flow regression for the real ARM64EC NtGetContextThread wrapper.

Run with Python 3 and a host C compiler (cc by default, or set CC to its path).
The wrapper is extracted unchanged from signal_arm64ec.c; minimal types and
conversion/syscall stubs let it run on Windows or Linux. This checks NULL handling,
zero initialization, and conversion/error flow, not the full ARM64EC ABI or the
real conversion routines. A Wine build and an ARM64EC device test are separate.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[2] / "dlls/ntdll/signal_arm64ec.c"

PREAMBLE = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SYSCALL_API
#define STATUS_INVALID_PARAMETER ((NTSTATUS)0xc000000d)
#define STATUS_ACCESS_DENIED ((NTSTATUS)0xc0000022)
#define CHECK(expr) do { if (!(expr)) { \
    fprintf(stderr, "line %d: %s\n", __LINE__, #expr); exit(1); \
} } while (0)

typedef int32_t NTSTATUS;
typedef void *HANDLE;
typedef struct { uint32_t ContextFlags, registers[8]; } CONTEXT;
typedef CONTEXT ARM64EC_NT_CONTEXT;
typedef struct { uint32_t ContextFlags, registers[8]; } ARM64_NT_CONTEXT;

static const uint32_t input_flags = 0x0010000b;
static const uint32_t flag_mask = 0x00500000;
static const uint32_t output_flags = 0x0040000b;
static unsigned int flag_calls, syscall_calls, output_calls;
static NTSTATUS syscall_status;
static int handle_token;
static CONTEXT *expected_output;

static uint32_t ctx_flags_x64_to_arm(uint32_t flags)
{
    ++flag_calls;
    CHECK(flags == input_flags);
    return flags ^ flag_mask;
}

static NTSTATUS syscall_NtGetContextThread(HANDLE handle, ARM64_NT_CONTEXT *context)
{
    unsigned int i;
    ++syscall_calls;
    CHECK(flag_calls == 1);
    CHECK(handle == &handle_token);
    CHECK(context->ContextFlags == (input_flags ^ flag_mask));
    for (i = 0; i < 8; ++i) CHECK(context->registers[i] == 0);
    context->ContextFlags = output_flags;
    for (i = 0; i < 8; ++i) context->registers[i] = 0x12340000 + i;
    return syscall_status;
}

static void context_arm_to_x64(ARM64EC_NT_CONTEXT *output, const ARM64_NT_CONTEXT *input)
{
    unsigned int i;
    ++output_calls;
    CHECK(syscall_calls == 1);
    CHECK(output == expected_output);
    CHECK(input->ContextFlags == output_flags);
    output->ContextFlags = input->ContextFlags ^ flag_mask;
    for (i = 0; i < 8; ++i) output->registers[i] = input->registers[i];
}
"""

DRIVER = r"""
int main(int argc, char **argv)
{
    CONTEXT context, before;
    NTSTATUS status;
    unsigned int i;

    CHECK(argc == 2);
    if (!strcmp(argv[1], "null"))
    {
        status = NtGetContextThread(&handle_token, NULL);
        CHECK(status == STATUS_INVALID_PARAMETER);
        CHECK(flag_calls == 0);
        CHECK(syscall_calls == 0);
        CHECK(output_calls == 0);
        return 0;
    }

    memset(&context, 0xa5, sizeof(context));
    context.ContextFlags = input_flags;
    before = context;
    expected_output = &context;
    CHECK(!strcmp(argv[1], "success") || !strcmp(argv[1], "failure"));
    syscall_status = !strcmp(argv[1], "failure") ? STATUS_ACCESS_DENIED : 0;
    status = NtGetContextThread(&handle_token, &context);
    CHECK(status == syscall_status);
    CHECK(flag_calls == 1);
    CHECK(syscall_calls == 1);
    if (syscall_status)
    {
        CHECK(output_calls == 0);
        CHECK(!memcmp(&context, &before, sizeof(context)));
    }
    else
    {
        CHECK(output_calls == 1);
        CHECK(context.ContextFlags == (output_flags ^ flag_mask));
        for (i = 0; i < 8; ++i) CHECK(context.registers[i] == 0x12340000 + i);
    }
    return 0;
}
"""


def extract_wrapper():
    source = SOURCE.read_text(encoding="utf-8")
    signature = re.search(
        r"^NTSTATUS SYSCALL_API NtGetContextThread\([^\n]*\)\s*\{", source, re.M
    )
    if signature is None:
        raise RuntimeError("Cannot find the ARM64EC NtGetContextThread definition")
    depth = 1
    for index in range(signature.end(), len(source)):
        depth += (source[index] == "{") - (source[index] == "}")
        if depth == 0:
            return source[signature.start():index + 1]
    raise RuntimeError("Unclosed ARM64EC NtGetContextThread definition")


class Arm64ecContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which(os.environ.get("CC", "cc"))
        if compiler is None:
            raise RuntimeError("A host C compiler is required; set CC to its executable path")
        cls.directory = tempfile.TemporaryDirectory(prefix="arm64ec-context-")
        cls.addClassCleanup(cls.directory.cleanup)
        directory = Path(cls.directory.name)
        source = directory / "context.c"
        cls.executable = directory / ("context.exe" if os.name == "nt" else "context")
        source.write_text(PREAMBLE + extract_wrapper() + DRIVER, encoding="utf-8")
        command = [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O0",
                   str(source), "-o", str(cls.executable)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(f"Host fixture compilation failed:\n{result.stdout}{result.stderr}")

    def run_case(self, case):
        # Child processes inherit this mode, suppressing Windows crash dialogs
        # when the NULL regression is run against an unfixed wrapper.
        if os.name == "nt":
            import ctypes
            previous_mode = ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
        try:
            result = subprocess.run([str(self.executable), case], capture_output=True,
                                    text=True, timeout=10, cwd=self.directory.name)
        finally:
            if os.name == "nt":
                ctypes.windll.kernel32.SetErrorMode(previous_mode)
        self.assertEqual(result.returncode, 0,
                         f"{case}: host process returned {result.returncode:#x}\n"
                         f"{result.stdout}{result.stderr}")

    def test_null_returns_invalid_parameter_without_conversion_or_syscall(self):
        self.run_case("null")

    def test_success_converts_flags_and_output_from_zero_initialized_context(self):
        self.run_case("success")

    def test_syscall_failure_preserves_output_context(self):
        self.run_case("failure")


if __name__ == "__main__":
    unittest.main()
