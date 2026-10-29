"""Runs build/test-native next to the GDBus fixture on the current (isolated) bus."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
fixture = subprocess.Popen(["/usr/bin/python3", str(root / "tests/fixture.py")], stdout=subprocess.PIPE, text=True)
try:
    assert fixture.stdout.readline().strip() == "READY"
    subprocess.run([str(root / "build/test-native")], check=True, timeout=60)
finally:
    fixture.terminate()
    fixture.wait(timeout=5)
    fixture.stdout.close()
