from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PARITY = ROOT / "scripts" / "live_parity.py"


FAKE_READER = r'''#!/usr/bin/env python3
import json
from pathlib import Path
import sys

candidate = "candidate" in Path(sys.argv[0]).name
args = sys.argv[1:]
command = next((value for value in args if not value.startswith("-") and value not in {"false", "20", "50"}), "")
capabilities = {name: True for name in ("sessions", "timeline", "search", "context", "tail", "media", "name_resolution")}
if command == "version":
    data = {"version": "candidate" if candidate else "legacy"}
elif command == "status":
    data = {"status": {"capabilities": capabilities}}
elif command == "sessions":
    sessions = [
        {"username": "private-sensitive-id", "display_name": "Private Name", "chat_type": "private"},
        {"username": "group-sensitive-id", "display_name": "Private Group", "chat_type": "group"},
        {"username": "folded-sensitive-id", "display_name": "Private Folded", "chat_type": "folded"},
    ]
    data = {"sessions": sessions[:-1] if candidate and "--mismatch" in args else sessions}
elif command == "contacts":
    data = {"contacts": [{"username": "private-sensitive-id", "display_name": "Private Name"}]}
elif command == "timeline":
    if "folded-sensitive-id" in args:
        raise SystemExit(2)
    data = {"messages": [{"local_id": 1, "server_id": 2, "create_time": 3, "kind": "text", "content": "private-message-body"}]}
else:
    raise SystemExit(2)
print(json.dumps({"ok": True, "data": data}))
'''


class LiveParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.legacy = self.root / "legacy-reader"
        self.candidate = self.root / "candidate-reader"
        for path in (self.legacy, self.candidate):
            path.write_text(FAKE_READER, encoding="utf-8")
            path.chmod(0o700)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_parity(self, candidate: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(PARITY),
                "--legacy-bin",
                str(self.legacy),
                "--candidate-bin",
                str(candidate or self.candidate),
                "--strict",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_ready_report_never_emits_private_values_or_message_text(self) -> None:
        result = self.run_parity()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["result"], "ready")
        self.assertNotIn("private-sensitive-id", result.stdout)
        self.assertNotIn("folded-sensitive-id", result.stdout)
        self.assertNotIn("Private Name", result.stdout)
        self.assertNotIn("private-message-body", result.stdout)

    def test_failure_reports_only_stage_not_reader_stderr(self) -> None:
        broken = self.root / "candidate-broken"
        broken.write_text("#!/bin/sh\necho 'private-message-body secret-id' >&2\nexit 4\n", encoding="utf-8")
        broken.chmod(0o700)
        result = self.run_parity(broken)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["result"], "blocked")
        self.assertNotIn("private-message-body", result.stdout)
        self.assertNotIn("secret-id", result.stdout)


if __name__ == "__main__":
    unittest.main()
