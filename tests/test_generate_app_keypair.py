#!/usr/bin/env python3
"""Host-side tests for scripts/generate-app-keypair."""

import hashlib
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/generate-app-keypair"


class GenerateAppKeypairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temp.name) / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        self.script = self.repo / "scripts/generate-app-keypair"
        shutil.copyfile(SOURCE, self.script)
        self.script.chmod(0o755)
        self.key_dir = self.repo / "local/production/keys/apps"
        self.rootfs_key = (
            self.repo
            / "configs/x2000/rootfs-overlay/usr/share/fre3nder/app-keys/fre3nder-official.pem"
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self):
        return subprocess.run(
            [str(self.script)],
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_initial_run_generates_and_installs_key(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)

        private = self.key_dir / "private.pem"
        public = self.key_dir / "public.pem"

        self.assertTrue(private.is_file())
        self.assertTrue(public.is_file())
        self.assertTrue(self.rootfs_key.is_file())
        self.assertEqual(public.read_bytes(), self.rootfs_key.read_bytes())

        self.assertEqual(
            stat.S_IMODE(private.stat().st_mode),
            0o600,
        )
        self.assertEqual(
            stat.S_IMODE(public.stat().st_mode),
            0o644,
        )
        self.assertEqual(
            stat.S_IMODE(self.rootfs_key.stat().st_mode),
            0o644,
        )
        self.assertIn("App signing keypair: CREATED", result.stdout)

    def test_second_run_does_not_rotate_key(self):
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stderr)

        private = self.key_dir / "private.pem"
        public = self.key_dir / "public.pem"
        before = (
            self.digest(private),
            self.digest(public),
            self.digest(self.rootfs_key),
        )

        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stderr)
        after = (
            self.digest(private),
            self.digest(public),
            self.digest(self.rootfs_key),
        )

        self.assertEqual(before, after)
        self.assertIn("App signing keypair: VALID", second.stdout)

    def test_existing_rootfs_key_blocks_accidental_replacement(self):
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.digest(self.rootfs_key)

        shutil.rmtree(self.key_dir)

        second = self.run_script()
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(original, self.digest(self.rootfs_key))
        self.assertIn(
            "refusing to generate a replacement keypair",
            second.stderr,
        )


if __name__ == "__main__":
    unittest.main()
