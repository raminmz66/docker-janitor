"""Tests for install.sh and uninstall.sh scripts."""

import os
import stat
import subprocess
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_SCRIPT = os.path.join(PROJECT_ROOT, "install.sh")
UNINSTALL_SCRIPT = os.path.join(PROJECT_ROOT, "uninstall.sh")


class InstallerScriptTests(unittest.TestCase):
    def test_install_help_flag(self):
        result = subprocess.run(
            [INSTALL_SCRIPT, "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Docker Janitor — Automated Installer", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--prefix", result.stdout)

    def test_uninstall_help_flag(self):
        result = subprocess.run(
            [UNINSTALL_SCRIPT, "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Docker Janitor — Uninstaller", result.stdout)
        self.assertIn("--purge", result.stdout)
        self.assertIn("--prefix", result.stdout)

    def test_install_unknown_flag_fails(self):
        result = subprocess.run(
            [INSTALL_SCRIPT, "--invalid-flag"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown argument", result.stderr)

    def test_uninstall_unknown_flag_fails(self):
        result = subprocess.run(
            [UNINSTALL_SCRIPT, "--invalid-flag"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown argument", result.stderr)

    def test_install_dry_run_creates_no_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            prefix = os.path.join(tmpdir, "prefix")
            env = os.environ.copy()
            env["XDG_DATA_HOME"] = os.path.join(tmpdir, "data")
            env["XDG_CONFIG_HOME"] = os.path.join(tmpdir, "config")

            result = subprocess.run(
                [INSTALL_SCRIPT, "--dry-run", f"--prefix={prefix}"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("[DRY RUN MODE", result.stdout)
            self.assertFalse(os.path.exists(prefix))
            self.assertFalse(os.path.exists(env["XDG_DATA_HOME"]))

    def test_install_and_uninstall_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            prefix = os.path.join(tmpdir, "local")
            data_home = os.path.join(tmpdir, "data")
            config_home = os.path.join(tmpdir, "config")
            state_home = os.path.join(tmpdir, "state")

            env = os.environ.copy()
            env["PREFIX"] = prefix
            env["XDG_DATA_HOME"] = data_home
            env["XDG_CONFIG_HOME"] = config_home
            env["XDG_STATE_HOME"] = state_home

            # Step 1: Install
            result = subprocess.run(
                [INSTALL_SCRIPT, "--non-interactive", f"--prefix={prefix}"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"Install failed: {result.stderr}")

            # Verify binary launcher exists and is executable
            launcher = os.path.join(prefix, "bin", "docker-janitor")
            self.assertTrue(os.path.isfile(launcher))
            mode = os.stat(launcher).st_mode
            self.assertTrue(mode & stat.S_IXUSR)

            # Test launching CLI version flag through installed launcher
            run_res = subprocess.run(
                [launcher, "--version"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run_res.returncode, 0)
            self.assertIn("Docker Janitor 0.1.0", run_res.stdout)

            # Verify files in data_home
            app_script = os.path.join(data_home, "docker-janitor", "docker_janitor.py")
            self.assertTrue(os.path.isfile(app_script))

            icon_file = os.path.join(
                data_home, "icons", "hicolor", "scalable", "apps", "docker-janitor.svg"
            )
            self.assertTrue(os.path.isfile(icon_file))

            # Verify desktop files
            desktop_file = os.path.join(data_home, "applications", "docker-janitor.desktop")
            self.assertTrue(os.path.isfile(desktop_file))
            with open(desktop_file, "r") as f:
                content = f.read()
                self.assertIn("Name=Docker Janitor", content)
                self.assertIn(f"Exec={launcher}", content)
                self.assertIn("Icon=docker-janitor", content)

            autostart_file = os.path.join(config_home, "autostart", "docker-janitor.desktop")
            self.assertTrue(os.path.isfile(autostart_file))

            # Step 2: Idempotency (running install again succeeds)
            result_repeat = subprocess.run(
                [INSTALL_SCRIPT, "--non-interactive", f"--prefix={prefix}"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result_repeat.returncode, 0)

            # Step 3: Uninstall without purge
            config_dir = os.path.join(config_home, "docker-janitor")
            os.makedirs(config_dir, exist_ok=True)
            fake_config = os.path.join(config_dir, "config.env")
            with open(fake_config, "w") as f:
                f.write("IMAGE_MIN_AGE_DAYS=14\n")

            uninst_res = subprocess.run(
                [UNINSTALL_SCRIPT, f"--prefix={prefix}"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(uninst_res.returncode, 0)
            self.assertFalse(os.path.exists(launcher))
            self.assertFalse(os.path.exists(desktop_file))
            self.assertFalse(os.path.exists(autostart_file))
            self.assertFalse(os.path.exists(icon_file))
            self.assertFalse(os.path.exists(os.path.join(data_home, "docker-janitor")))
            # Config was preserved
            self.assertTrue(os.path.exists(fake_config))

            # Step 4: Uninstall with purge
            uninst_purge = subprocess.run(
                [UNINSTALL_SCRIPT, f"--prefix={prefix}", "--purge"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(uninst_purge.returncode, 0)
            self.assertFalse(os.path.exists(config_dir))

    def test_install_no_autostart_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            prefix = os.path.join(tmpdir, "local")
            data_home = os.path.join(tmpdir, "data")
            config_home = os.path.join(tmpdir, "config")

            env = os.environ.copy()
            env["XDG_DATA_HOME"] = data_home
            env["XDG_CONFIG_HOME"] = config_home

            result = subprocess.run(
                [
                    INSTALL_SCRIPT,
                    "--non-interactive",
                    "--no-autostart",
                    f"--prefix={prefix}",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)

            desktop_file = os.path.join(data_home, "applications", "docker-janitor.desktop")
            self.assertTrue(os.path.isfile(desktop_file))

            autostart_file = os.path.join(config_home, "autostart", "docker-janitor.desktop")
            self.assertFalse(os.path.exists(autostart_file))


if __name__ == "__main__":
    unittest.main()
