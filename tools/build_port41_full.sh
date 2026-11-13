#!/bin/sh
set -e
exec python3 -B "$(dirname "$0")/build_port41_full.py" "$@"
