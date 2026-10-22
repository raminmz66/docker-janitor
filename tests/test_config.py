"""Task 3 tests: config file loading with defaults and tolerance."""

import os
import tempfile
import unittest

import docker_janitor


class ConfigTests(unittest.TestCase):
    def _write(self, text):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        tmp.write(text)
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        return tmp.name

    def test_missing_file_yields_defaults(self):
        config = docker_janitor.load_config("/nonexistent/docker-janitor.env")
        self.assertEqual(config.image_min_age_days, 30)
        self.assertEqual(config.cache_min_age_hours, 168)

    def test_values_are_overridden(self):
        path = self._write("IMAGE_MIN_AGE_DAYS=7\nCACHE_MIN_AGE_HOURS=24\n")
        config = docker_janitor.load_config(path)
        self.assertEqual(config.image_min_age_days, 7)
        self.assertEqual(config.cache_min_age_hours, 24)

    def test_malformed_value_keeps_default(self):
        path = self._write("IMAGE_MIN_AGE_DAYS=soon\nCACHE_MIN_AGE_HOURS=168\n")
        config = docker_janitor.load_config(path)
        self.assertEqual(config.image_min_age_days, 30)

    def test_comments_and_blank_lines_are_ignored(self):
        path = self._write("# comment\n\nCACHE_MIN_AGE_HOURS=12\n")
        config = docker_janitor.load_config(path)
        self.assertEqual(config.cache_min_age_hours, 12)

    def test_unknown_keys_are_ignored(self):
        path = self._write("SOMETHING_ELSE=42\nIMAGE_MIN_AGE_DAYS=15\n")
        config = docker_janitor.load_config(path)
        self.assertEqual(config.image_min_age_days, 15)


if __name__ == "__main__":
    unittest.main()
