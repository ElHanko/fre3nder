#!/usr/bin/env python3
# Host-side dispatch tests for Fre3nder app CLI.

import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = ROOT / "configs/x2000/rootfs-overlay/usr/bin/fre3nder"


class Fre3nderAppCliDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.log = self.root / "dispatch.log"
        self.package = self.root / "package-core"

        for target in (self.package,):
            target.write_text(
                "#!/bin/sh\n"
                "{ printf '%s\\n' \"$0\"; "
                "printf '%s\\n' \"$@\"; } "
                "> \"$FRE3NDER_TEST_DISPATCH_LOG\"\n"
            )
            target.chmod(0o755)

        self.env = os.environ.copy()
        self.env["FRE3NDER_PACKAGE_CORE"] = str(self.package)
        self.env["FRE3NDER_TEST_DISPATCH_LOG"] = str(self.log)

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *arguments):
        return subprocess.run(
            [str(CLI), *arguments],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def dispatched(self):
        return self.log.read_text().splitlines()

    def test_legacy_install_is_rejected(self):
        result = self.run_cli("app", "install", "fluidd")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_legacy_actions_are_rejected(self):
        for action in ("uninstall", "restore"):
            result = self.run_cli("app", action, "fluidd")
            self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_fre3app_install_uses_package_core(self):
        result = self.run_cli(
            "app",
            "install",
            "/tmp/dummy.fre3app",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.dispatched(),
            [
                str(self.package),
                "install",
                "/tmp/dummy.fre3app",
            ],
        )

    def test_package_update_preserves_downgrade_flag(self):
        result = self.run_cli(
            "app",
            "update",
            "/tmp/dummy.fre3app",
            "--allow-downgrade",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.dispatched(),
            [
                str(self.package),
                "update",
                "/tmp/dummy.fre3app",
                "--allow-downgrade",
            ],
        )

    def test_key_add_maps_to_package_core(self):
        result = self.run_cli(
            "app",
            "key",
            "add",
            "community",
            "/tmp/community.pem",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.dispatched(),
            [
                str(self.package),
                "key-add",
                "community",
                "/tmp/community.pem",
            ],
        )

    def test_package_list_uses_package_core(self):
        result = self.run_cli("app", "list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.dispatched(),
            [str(self.package), "list"],
        )

    def test_package_status_uses_package_core(self):
        result = self.run_cli("app", "status", "fluidd")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.dispatched(), [str(self.package), "status", "fluidd"])

    def test_verify_and_remove_use_package_core(self):
        for action, target in (("verify", "/tmp/dummy.fre3app"), ("remove", "fluidd")):
            result = self.run_cli("app", action, target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.dispatched(), [str(self.package), action, target])


if __name__ == "__main__":
    unittest.main()
