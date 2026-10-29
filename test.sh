#!/bin/sh
set -eu
cd "$(dirname "$0")"
: "${TARN:=tarn}"
mkdir -p build
# Native wire format (offline): GDBus golden messages in both directions.
"$TARN" build test_wire.tarn -o build/test-wire
./build/test-wire
/usr/bin/python3 tests/golden/verify.py
"$TARN" check list_names.tarn
"$TARN" check test_client.tarn
if "$TARN" check negative_escape.tarn > build/escape.log 2>&1; then
    echo 'FAIL: borrowed connection escaped' >&2
    exit 1
fi
/usr/bin/python3 -c 'from pathlib import Path; assert "E3079" in Path("build/escape.log").read_text()'
# Pure Tarn: no native libraries are linked.
"$TARN" build list_names.tarn -o build/list-names
"$TARN" build test_client.tarn -o build/test-client
"$TARN" build test_native.tarn -o build/test-native
"$TARN" build test_notifications.tarn -o build/test-notifications
"$TARN" build notify_demo.tarn -o build/notify-demo
"$TARN" build test_router.tarn -o build/test-router
"$TARN" build test_tray.tarn -o build/test-tray
"$TARN" build tray_demo.tarn -o build/tray-demo
# Live tests on an isolated session bus with the GDBus fixture.
dbus-run-session -- /usr/bin/python3 tests/run_session.py
dbus-run-session -- /usr/bin/python3 tests/run_native.py
dbus-run-session -- /usr/bin/python3 tests/run_notifications.py
dbus-run-session -- /usr/bin/python3 tests/run_router.py
dbus-run-session -- /usr/bin/python3 tests/run_tray.py
