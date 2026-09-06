from datetime import datetime
import os
from pathlib import Path
import tempfile
import unittest

from maintenance import apply_cleanup, find_cleanup_candidates, validate_cleanup_root


class CleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output = Path(self.temp_dir.name) / "output"
        self.output.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_aged_file(self, name: str, age_days: int) -> Path:
        path = self.output / name
        path.write_text("private test data", encoding="utf-8")
        timestamp = datetime(2026, 8, 2, 12, 0, 0).timestamp() - age_days * 86400
        os.utime(path, (timestamp, timestamp))
        return path

    def test_cleanup_defaults_keep_recent_files_and_only_preview_candidates(self) -> None:
        old_raw = self.write_aged_file("messages.json", 8)
        recent_raw = self.write_aged_file("recent.jsonl", 2)
        old_report = self.write_aged_file("digest.md", 31)

        candidates = find_cleanup_candidates(
            self.output,
            raw_days=7,
            report_days=30,
            now=datetime(2026, 8, 2, 12, 0, 0),
        )

        self.assertEqual(
            {item.path for item in candidates},
            {old_raw.resolve(), old_report.resolve()},
        )
        self.assertTrue(old_raw.exists())
        self.assertTrue(recent_raw.exists())

    def test_apply_cleanup_only_removes_explicit_candidates(self) -> None:
        old_raw = self.write_aged_file("messages.json", 8)
        recent_raw = self.write_aged_file("recent.json", 2)
        candidates = find_cleanup_candidates(
            self.output,
            now=datetime(2026, 8, 2, 12, 0, 0),
        )

        removed, reclaimed = apply_cleanup(candidates)

        self.assertEqual(removed, 1)
        self.assertGreater(reclaimed, 0)
        self.assertFalse(old_raw.exists())
        self.assertTrue(recent_raw.exists())

    def test_cleanup_rejects_broad_roots(self) -> None:
        with self.assertRaises(ValueError):
            validate_cleanup_root(Path.home())


if __name__ == "__main__":
    unittest.main()
