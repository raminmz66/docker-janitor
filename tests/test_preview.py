"""Task 5 tests: collecting live state and asking before deleting."""

import os
import unittest
from datetime import datetime, timedelta, timezone

import docker_janitor as dj

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
LOCAL = timezone(timedelta(hours=3, minutes=30))
NOW = datetime(2026, 10, 22, 21, 40, tzinfo=LOCAL)


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return handle.read()


class FakeDocker:
    """Answers the exact command lines collect_preview uses."""

    def __init__(self, buildx_fails=False, info_fails=False):
        self.buildx_fails = buildx_fails
        self.info_fails = info_fails
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        command = " ".join(args)
        if command == "info":
            if self.info_fails:
                raise dj.DockerError("daemon down")
            return "ok"
        if command == "system df":
            return fixture("system_df.txt")
        if command == "system df -v":
            return fixture("system_df_verbose.txt")
        if command == "images --format {{json .}}":
            return fixture("images.jsonl")
        if command == "ps -aq":
            return "\n".join("container%d" % i for i in range(12))
        if command.startswith("container inspect"):
            return fixture("used_image_ids.txt")
        if command == "buildx du --verbose":
            if self.buildx_fails:
                raise dj.DockerError("no buildx")
            return fixture("buildx_du_verbose.txt")
        raise AssertionError("unexpected docker command: %r" % (command,))


class CollectPreviewTests(unittest.TestCase):
    def setUp(self):
        self.docker = FakeDocker()
        self.config = dj.Config(image_min_age_days=30, cache_min_age_hours=168)

    def test_preview_matches_the_fixtures(self):
        preview = dj.collect_preview(self.config, self.docker, now=NOW)
        self.assertEqual(preview.cache_bytes, 20832596679)
        self.assertEqual(preview.cache_records, 180)
        self.assertEqual(preview.image_bytes, 3558350010)
        self.assertEqual(preview.image_count, 19)
        self.assertFalse(preview.estimated)
        self.assertIn(("system", "df"), self.docker.calls)
        self.assertIn(("system", "df", "-v"), self.docker.calls)
        self.assertNotIn(("system df",), self.docker.calls)
        self.assertNotIn(("system df", "-v"), self.docker.calls)

    def test_volumes_and_containers_are_reported_not_removed(self):
        preview = dj.collect_preview(self.config, self.docker, now=NOW)
        self.assertEqual(preview.kept_volumes_count, 6)
        self.assertEqual(preview.kept_volumes_bytes, 156200000)
        self.assertEqual(preview.kept_containers_count, 12)

    def test_daemon_down_raises(self):
        with self.assertRaises(dj.DockerError):
            dj.collect_preview(self.config, FakeDocker(info_fails=True))

    def test_missing_buildx_falls_back_to_df_figure(self):
        preview = dj.collect_preview(self.config, FakeDocker(buildx_fails=True), now=NOW)
        self.assertTrue(preview.estimated)
        self.assertEqual(preview.cache_bytes, 20830000000)


class RunDockerTests(unittest.TestCase):
    def test_subcommand_words_stay_separate_arguments(self):
        import unittest.mock as mock

        completed = mock.Mock(returncode=0, stdout="table", stderr="")
        with mock.patch.object(dj.subprocess, "run", return_value=completed) as run:
            dj.run_docker("system", "df")
        self.assertEqual(run.call_args[0][0], ("docker", "system", "df"))

    def test_failure_raises(self):
        import unittest.mock as mock

        completed = mock.Mock(returncode=1, stdout="", stderr="boom")
        with mock.patch.object(dj.subprocess, "run", return_value=completed):
            with self.assertRaises(dj.DockerError):
                dj.run_docker("info")


class AskContinueTests(unittest.TestCase):
    def _preview(self):
        return dj.Preview(cache_bytes=20832596679, cache_records=180,
                          image_bytes=3558350010, image_count=19)

    def test_continue_is_zero_exit(self):
        seen = {}

        def fake_zenity(argv):
            seen["argv"] = argv
            return 0

        self.assertTrue(dj.ask_continue(self._preview(), fake_zenity))
        argv = seen["argv"]
        self.assertEqual(argv[0], "zenity")
        self.assertIn("--question", argv)
        self.assertIn("Continue", " ".join(argv))
        self.assertIn("Skip", " ".join(argv))
        self.assertIn("24.4 GB", " ".join(argv))

    def test_skip_is_nonzero_exit(self):
        self.assertFalse(dj.ask_continue(self._preview(), lambda argv: 1))

    def test_closed_dialog_counts_as_skip(self):
        self.assertFalse(dj.ask_continue(self._preview(), lambda argv: 5))


class ToastTests(unittest.TestCase):
    def test_show_toast_invokes_notify_send(self):
        seen = []
        dj.show_toast("Title", "Message text", runner=lambda argv: seen.append(argv))
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0], ["notify-send", "-a", dj.APP_ID, "Title", "Message text"])


if __name__ == "__main__":
    unittest.main()
