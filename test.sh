#!/bin/sh
set -eu
cd "$(dirname "$0")"
: "${TARN:=tarn}"
mkdir -p build
# Compiler flags come from the installed system's pkg-config metadata.
cc tests/abi.c $(pkg-config --cflags --libs dbus-1) -o build/abi-check
./build/abi-check
"$TARN" check list_names.tarn
"$TARN" check test_client.tarn
if "$TARN" check negative_escape.tarn > build/escape.log 2>&1; then
    echo 'FAIL: borrowed connection escaped' >&2
    exit 1
fi
/usr/bin/python3 -c 'from pathlib import Path; assert "E3074" in Path("build/escape.log").read_text()' 
"$TARN" build list_names.tarn --link dbus-1 -o build/list-names
"$TARN" build test_client.tarn --link dbus-1 -o build/test-client
dbus-run-session -- /usr/bin/python3 tests/run_session.py
