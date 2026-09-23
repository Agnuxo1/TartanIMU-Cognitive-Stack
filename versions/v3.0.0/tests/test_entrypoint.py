from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_BAT = PROJECT_ROOT / "run.bat"


class EntrypointTests(unittest.TestCase):
    def test_run_bat_imports_package_from_external_working_directory(self):
        environment = os.environ.copy()
        environment.pop("TYPESAFE_API_KEY", None)
        with tempfile.TemporaryDirectory(prefix="jev-external-cwd-") as external_cwd:
            completed = subprocess.run(
                f'call "{RUN_BAT}" --help',
                cwd=external_cwd,
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                shell=True,
                executable=os.environ.get("COMSPEC", "cmd.exe"),
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("usage", completed.stdout.lower())
        self.assertNotIn("TYPESAFE_API_KEY", completed.stdout)

    def test_connect_is_json_and_does_not_probe_without_remote_flag(self):
        environment = os.environ.copy()
        for name in ("TYPESAFE_API_KEY", "TYPESAFE_API_KEY_1", "TYPESAFE_API_KEY_2", "TYPESAFE_API_KEY_3"):
            environment.pop(name, None)
        completed = subprocess.run(
            f'call "{RUN_BAT}" connect',
            cwd=r"C:\Windows\Temp",
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            shell=True,
            executable=os.environ.get("COMSPEC", "cmd.exe"),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = __import__("json").loads(completed.stdout)
        self.assertFalse(payload["configured"])
        self.assertEqual(payload["provenance"], "local")

    def test_remote_probe_reports_missing_key_without_network(self):
        environment = os.environ.copy()
        for name in ("TYPESAFE_API_KEY", "TYPESAFE_API_KEY_1", "TYPESAFE_API_KEY_2", "TYPESAFE_API_KEY_3"):
            environment.pop(name, None)
        completed = subprocess.run(
            f'call "{RUN_BAT}" connect --remote',
            cwd=r"C:\Windows\Temp",
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            shell=True,
            executable=os.environ.get("COMSPEC", "cmd.exe"),
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        payload = __import__("json").loads(completed.stdout)
        self.assertEqual(payload["error"], "JEV_NOT_CONFIGURED")
        self.assertEqual(payload["provenance"], "local")


if __name__ == "__main__":
    unittest.main()
