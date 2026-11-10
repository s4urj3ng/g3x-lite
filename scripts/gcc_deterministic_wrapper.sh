#!/bin/sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REAL_GCC="${REPO_ROOT}/toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-gcc"

IS_GUI=0
IS_CAM=0
for arg in "$@"; do
    case "$arg" in
        *gui.c) IS_GUI=1 ;;
        *camera_info.c) IS_CAM=1 ;;
    esac
done

if [ $IS_GUI -eq 1 ]; then
    exec "${REAL_GCC}" -Wno-builtin-macro-redefined '-D__DATE__="Nov 10 2026"' '-D__TIME__="07:44:48"' "$@"
elif [ $IS_CAM -eq 1 ]; then
    exec "${REAL_GCC}" -Wno-builtin-macro-redefined '-D__DATE__="Nov 10 2026"' '-D__TIME__="07:44:49"' "$@"
else
    exec "${REAL_GCC}" -Wno-builtin-macro-redefined '-D__DATE__="Nov 10 2026"' '-D__TIME__="07:44:49"' "$@"
fi
