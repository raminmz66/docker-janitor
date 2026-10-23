"""Task 6 tests: constructing safe prune commands and reporting reclaimed space."""

import os
import tempfile
import unittest
from datetime import datetime

import docker_janitor as dj


class PruneCommandsTests(unittest.TestCase):
    def test_prune_commands_exact_argv(self):
        config = dj.Config(image_min_age_days=30, cache_min_age_hours=168)
        cmds = dj.prune_commands(config)
        self.assertEqual(
            cmds,
            [
                ["builder", "prune", "-af", "--filter", "until=168h"],
                ["image", "prune", "-f"],
                ["image", "prune", "-af", "--filter", "until=720h"],
            ],
        )

    def test_no_volume_or_container_prune(self):
        config = dj.Config(image_min_age_days=30, cache_min_age_hours=168)
        cmds = dj.prune_commands(config)
        for cmd in cmds:
            joined = " ".join(cmd)
            self.assertNotIn("volume", joined)
            self.assertNotIn("container", joined)

    def test_custom_config_thresholds(self):
        config = dj.Config(image_min_age_days=7, cache_min_age_hours=48)
        cmds = dj.prune_commands(config)
        self.assertIn(["builder", "prune", "-af", "--filter", "until=48h"], cmds)
        self.assertIn(["image", "prune", "-af", "--filter", "until=168h"], cmds)


class RunPruneTests(unittest.TestCase):
    def test_run_prune_calculates_delta(self):
        calls = []

        before_df = (
            "TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE\n"
            "Images          63        12        25.0GB    23.6GB (94%)\n"
            "Containers      12        0         98.3kB    98.3kB (100%)\n"
            "Local Volumes   6         4         156.2MB   48.02MB (30%)\n"
            "Build Cache     673       0         20.83GB   20.83GB\n"
        )
        after_df = (
            "TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE\n"
            "Images          44        12        21.44GB   20.04GB (93%)\n"
            "Containers      12        0         98.3kB    98.3kB (100%)\n"
            "Local Volumes   6         4         156.2MB   48.02MB (30%)\n"
            "Build Cache     493       0         0B        0B\n"
        )

        def fake_runner(*args):
            calls.append(args)
            if args == ("system", "df"):
                return before_df if len(calls) == 1 else after_df
            return "pruned"

        cmds = [
            ["builder", "prune", "-af", "--filter", "until=168h"],
            ["image", "prune", "-f"],
        ]
        report = dj.run_prune(cmds, fake_runner)

        # Before: 25.0 GB + 98.3 kB + 156.2 MB + 20.83 GB = 45986298300 bytes
        # After: 21.44 GB + 98.3 kB + 156.2 MB + 0 B = 21596298300 bytes
        # Delta: 24390000000 bytes ≈ 24.4 GB
        self.assertEqual(report.before_bytes, 45986298300)
        self.assertEqual(report.after_bytes, 21596298300)
        self.assertEqual(report.reclaimed_bytes, 24390000000)

        # Verify exact sequence of calls
        self.assertEqual(calls[0], ("system", "df"))
        self.assertEqual(calls[1], ("builder", "prune", "-af", "--filter", "until=168h"))
        self.assertEqual(calls[2], ("image", "prune", "-f"))
        self.assertEqual(calls[3], ("system", "df"))

    def test_log_report_appends_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = os.path.join(tmp, "state", "docker-janitor.log")
            report = dj.Report(
                reclaimed_bytes=24390000000,
                before_bytes=45986298300,
                after_bytes=21596298300,
                timestamp=datetime(2026, 10, 23, 12, 0, 0),
            )
            dj.log_report(report, log_file)

            with open(log_file, encoding="utf-8") as handle:
                contents = handle.read()
            self.assertIn("reclaimed 24.4 GB", contents)
            self.assertIn("2026-10-23T12:00:00", contents)

    def test_notify_report_sends_toast(self):
        seen = []
        report = dj.Report(
            reclaimed_bytes=24390000000,
            before_bytes=45986298300,
            after_bytes=21596298300,
        )
        dj.notify_report(report, notifier=lambda title, msg: seen.append((title, msg)))
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], "Docker Janitor")
        self.assertIn("24.4 GB", seen[0][1])


if __name__ == "__main__":
    unittest.main()
