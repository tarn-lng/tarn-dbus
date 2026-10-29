"""Runs build/test-notifications next to the fake notification server."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
fixture = subprocess.Popen(["/usr/bin/python3", str(root / "tests/notifications_fixture.py")],
                           stdout=subprocess.PIPE, text=True)
try:
    assert fixture.stdout.readline().strip() == "READY"
    subprocess.run([str(root / "build/test-notifications")], check=True, timeout=30)
finally:
    fixture.terminate()
    fixture.wait(timeout=5)
    fixture.stdout.close()
