"""Writes tests/golden/messages.txt: one GDBus-encoded message per line,
`name|hex`. Regenerate only when adding cases; the file is committed."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from cases import MESSAGES, build, Gio

out = Path(__file__).parent / "messages.txt"
lines = [f"{name}|{build(name).to_blob(Gio.DBusCapabilityFlags.NONE).hex()}" for name in MESSAGES]
out.write_text("\n".join(lines) + "\n")
print(f"wrote {len(lines)} messages to {out}")
