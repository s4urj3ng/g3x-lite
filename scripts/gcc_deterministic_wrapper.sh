#!/bin/sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REAL_GCC="${REPO_ROOT}/toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-gcc"
exec "${REAL_GCC}" -Wno-builtin-macro-redefined '-D__DATE__="Nov  9 2026"' '-D__TIME__="12:00:00"' "$@"
