"""Parses messages encoded by Tarn (build/tarn-messages.txt) with GDBus and
checks every header field and the body against the reference case."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from cases import MESSAGES, body, body_name, build, Gio

failures = 0
lines = (Path(__file__).parents[2] / "build/tarn-messages.txt").read_text().split()
for line in lines:
    name, data = line.split("|")
    parsed = Gio.DBusMessage.new_from_blob(bytes.fromhex(data), Gio.DBusCapabilityFlags.NONE)
    expected = build(name)
    checks = {
        "type": (parsed.get_message_type(), expected.get_message_type()),
        "flags": (int(parsed.get_flags()), int(expected.get_flags())),
        "serial": (parsed.get_serial(), expected.get_serial()),
        "path": (parsed.get_path(), expected.get_path()),
        "interface": (parsed.get_interface(), expected.get_interface()),
        "member": (parsed.get_member(), expected.get_member()),
        "error": (parsed.get_error_name(), expected.get_error_name()),
        "reply": (parsed.get_reply_serial(), expected.get_reply_serial()),
        "destination": (parsed.get_destination(), expected.get_destination()),
        "body": (parsed.get_body(), body(body_name(name))),
    }
    for field, (got, want) in checks.items():
        if got != want:
            failures += 1
            print(f"FAIL {name}.{field}: {got!r} != {want!r}")
print(f"GDBus verified {len(lines)} Tarn messages, {failures} failures")
sys.exit(1 if failures or len(lines) != len(MESSAGES) else 0)
