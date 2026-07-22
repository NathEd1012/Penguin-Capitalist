import os
import tempfile
import unittest
from pathlib import Path

import save


class SaveCollectionTests(unittest.TestCase):
    def test_collect_files_keeps_non_out_files_and_latest_out_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_current_dir = Path(tmpdir) / "run_current"
            run_current_dir.mkdir(parents=True, exist_ok=True)

            old_out = run_current_dir / "old.out"
            old_out.write_text("old", encoding="utf-8")
            current_out = run_current_dir / "current.out"
            current_out.write_text("current", encoding="utf-8")
            notes = run_current_dir / "notes.txt"
            notes.write_text("ignore", encoding="utf-8")
            metrics = run_current_dir / "metrics.json"
            metrics.write_text("{}", encoding="utf-8")

            os.utime(old_out, (1, 1))
            os.utime(current_out, (2, 2))

            collected = save._collect_files(run_current_dir)

            self.assertIn(notes, collected)
            self.assertIn(metrics, collected)
            self.assertNotIn(old_out, collected)
            self.assertIn(current_out, collected)


if __name__ == "__main__":
    unittest.main()
